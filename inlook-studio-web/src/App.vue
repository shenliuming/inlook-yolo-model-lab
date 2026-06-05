<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import StudioTopbar from './components/StudioTopbar.vue'
import StudioSidebar from './components/StudioSidebar.vue'
import MaterialScriptPanel from './components/MaterialScriptPanel.vue'
import PromptRewritePanel from './components/PromptRewritePanel.vue'
import VoiceHumanPanel from './components/VoiceHumanPanel.vue'
import ExportPanel from './components/ExportPanel.vue'
import VideoPreviewPanel from './components/VideoPreviewPanel.vue'
import RecentTaskTable from './components/RecentTaskTable.vue'
import { clearBrowserAuth, getBrowserAuthStatus, startBrowserAuth } from './api/browserAuth'
import { extractMaterial, uploadMaterial } from './api/materials'
import { createTranscription, getTranscription } from './api/transcriptions'
import { listTasks } from './api/tasks'
import { createSynthesis, createTraining, getSynthesis, getTraining } from './api/tts'
import { apiUrl } from './api/client'
import {
  aspectOptions,
  avatarOptions,
  backgroundOptions,
  bgmOptions,
  emotionOptions,
  initialRewriteResults,
  lengthOptions,
  navigationItems,
  platformOptions,
  promptTemplates,
  qualityOptions,
  sceneOptions,
  subtitlePositions,
  subtitleStyles,
  toneOptions,
  voiceOptions,
} from './data/mockData'

const activeNav = ref('home')
const serviceStatus = ref('运行中')
const modelStatus = ref('已连接')
const outputPath = ref('D:/Inlook_Outputs')

const videoLink = ref('')
const uploadedFile = ref(null)
const uploadedFileName = ref('')
const readStatus = ref('待读取')
const authHint = ref('')
const rawScript = ref('')
const materialId = ref('')
const material = ref(null)
const pendingUrls = ref([])
const isReading = ref(false)
const transcriptionLoading = ref(false)
const transcriptionId = ref('')
const subtitleDownloads = ref({})
const subtitleStatus = ref('未生成字幕')

const promptText = ref('把这段文案改成普通人真实分享口吻，开头更抓人，不要太营销，适合抖音 30 秒口播。')
const selectedPlatform = ref(platformOptions[0])
const selectedLength = ref(lengthOptions[1])
const selectedTone = ref(toneOptions[0])
const keepKeywords = ref('真实分享、自然表达、停留率')
const rewriteResults = ref([...initialRewriteResults])
const activeResultId = ref('A')

const selectedVoice = ref(voiceOptions[0])
const selectedEmotion = ref(emotionOptions[0])
const voiceSpeed = ref(1.0)
const voiceVolume = ref(82)
const previewingVoice = ref(false)
const voiceGenerating = ref(false)
const voiceStatus = ref('待生成')
const humanStatus = ref('数字人待接入')
const trainingStatus = ref('未创建音色')
const trainingId = ref('')
const trainingReady = ref(false)
const referenceAudioFile = ref(null)
const referenceAudioName = ref('')
const synthesisId = ref('')
const synthesisAudioUrl = ref('')
const selectedAvatarId = ref(avatarOptions[0].id)
const selectedScene = ref(sceneOptions[0])
const selectedBackground = ref(backgroundOptions[0])

const subtitleEnabled = ref(true)
const selectedSubtitleStyle = ref(subtitleStyles[0])
const selectedSubtitlePosition = ref(subtitlePositions[0])
const selectedBgm = ref(bgmOptions[0])
const narrationVolume = ref(82)
const bgmVolume = ref(26)
const selectedAspect = ref(aspectOptions[0])
const selectedQuality = ref(qualityOptions[1])
const saveToLibrary = ref(true)
const exportMaterials = ref(false)

const previewState = ref('idle')
const previewTitle = ref('尚未生成成片')
const currentStep = ref('等待任务')
const renderProgress = ref(0)
const tasks = ref([])
const appError = ref('')
const authStatuses = ref({
  douyin: { platform: 'douyin', status: 'unauthorized', message: '未授权' },
  bilibili: { platform: 'bilibili', status: 'unauthorized', message: '未授权' },
})
const rawScriptSource = ref('manual')

const renderingMeta = ref({
  sourceDuration: '--:--',
  voiceDuration: '--:--',
  finalDuration: '--:--',
})

let taskPollTimer = null
let transcriptionPollTimer = null
let trainingPollTimer = null
let synthesisPollTimer = null
const authPollTimers = {
  douyin: null,
  bilibili: null,
}

const selectedAvatar = computed(() =>
  avatarOptions.find((item) => item.id === selectedAvatarId.value) ?? avatarOptions[0],
)

const scriptSourceLabel = computed(() => {
  if (rawScriptSource.value === 'transcription') return '视频口播'
  if (rawScriptSource.value === 'material') return '平台文案'
  return '手动输入'
})

const scriptDetailReady = computed(() => false)
const materialLocalReady = computed(
  () =>
    material.value?.cacheStatus === 'local_ready' &&
    material.value?.downloadStatus === 'downloaded' &&
    material.value?.localFileStatus === 'exists',
)

const materialSummary = computed(() => {
  if (!material.value) return ''
  if (material.value.cacheStatus === 'local_ready') return '素材已准备好，可继续提取视频文案'
  if (material.value.cacheStatus === 'metadata_cached') return '已有素材信息，视频未下载'
  if (material.value.cacheStatus === 'local_missing') return '本地视频文件丢失，请重新下载'
  if (material.value.cacheStatus === 'local_invalid') return '本地视频文件无效，请重新下载'
  return `${material.value.sourceType} · ${material.value.video?.width || 0}x${material.value.video?.height || 0} · ${material.value.video?.duration || 0}s`
})

const materialLamp = computed(() => {
  if (isReading.value) return 'processing'
  if (appError.value && !materialLocalReady.value) return 'failed'
  if (materialLocalReady.value) return 'ready'
  return 'idle'
})

const materialLampText = computed(() => {
  const map = {
    idle: '未准备',
    processing: '处理中',
    ready: '已就绪',
    failed: '失败',
  }
  return map[materialLamp.value] || '未准备'
})

const clearTimer = (timerName) => {
  if (timerName.value) {
    window.clearInterval(timerName.value)
    timerName.value = null
  }
}

const normalizeUiErrorMessage = (error, fallback = '操作失败，请稍后重试。') => {
  const message = String(error?.message || '')
  if (!message) return fallback
  if (message.includes('Page.goto') || message.includes('Target page') || message.includes('context or browser has been closed')) {
    return '授权页面打开失败，请重新授权。'
  }
  if (message.includes('Failed to fetch') || message.includes('NetworkError')) {
    return '网络连接失败，请检查服务状态。'
  }
  if (/[A-Za-z]/.test(message)) return fallback
  return message.length > 28 ? `${message.slice(0, 28)}…` : message
}

const normalizeMaterialReadErrorMessage = (error) => {
  const errorType = String(error?.data?.errorType || '')
  const sourceType = String(error?.data?.sourceType || '')
  const message = String(error?.message || '')
  if (errorType === 'url_not_found') {
    return '未识别到有效视频链接，请粘贴抖音/B站/TikTok分享链接，或上传本地视频。'
  }
  if (errorType === 'unsupported_platform') {
    return '当前仅支持抖音、B站、TikTok和本地视频。'
  }
  if (errorType === 'video_url_missing') {
    return '素材页面已识别，但未拿到可用视频地址。'
  }
  if (errorType === 'material_download_failed') {
    return '素材下载失败，请重试或上传本地视频。'
  }
  if (errorType === 'extractor_all_failed') {
    if (sourceType === 'douyin') {
      return '抖音素材读取失败，请重新授权或上传本地视频。'
    }
    if (sourceType === 'bilibili') {
      return 'B站素材读取失败，请先完成授权或稍后重试。'
    }
    return '素材读取失败：浏览器授权解析失败，请重新授权或上传本地视频。'
  }
  if (errorType === 'extractor_failed') {
    if (sourceType === 'douyin') {
      return message || '素材提取失败：CopyPilot 接口调用失败，请稍后重试。'
    }
    return '素材提取失败，请稍后重试。'
  }
  return normalizeUiErrorMessage(error, '素材读取失败，请稍后重试。')
}

const normalizeAuthErrorMessage = (error) => {
  const message = String(error?.message || '')
  if (message.includes('Page.goto') || message.includes('Target page') || message.includes('context or browser has been closed')) {
    return '授权页面打开失败，请重新授权。'
  }
  if (message.includes('Failed to fetch') || message.includes('NetworkError')) {
    return '授权服务连接失败，请稍后重试。'
  }
  if (/[A-Za-z]/.test(message)) return '授权失败，请重新授权。'
  return message.length > 24 ? `${message.slice(0, 24)}…` : message
}

const setGlobalErrorFromException = (error, fallback) => {
  appError.value = normalizeUiErrorMessage(error, fallback)
  console.error(error)
}

const setAuthHintFromException = (error) => {
  authHint.value = normalizeAuthErrorMessage(error)
  console.error(error)
}

const handleRawScriptInput = (value) => {
  rawScript.value = value
  rawScriptSource.value = 'manual'
}

const fetchTasks = async () => {
  try {
    const list = await listTasks()
    const taskNameMap = {
      'material.fetch': '素材读取',
      'transcription.extract': '视频文案提取',
      'tts.synthesis': '语音合成',
      'tts.training': '音色训练',
    }
    const statusLabelMap = {
      success: '成功',
      running: '进行中',
      failed: '失败',
      pending: '等待中',
      queued: '等待中',
      cancelled: '失败',
    }
    const formatTaskTime = (value) => {
      if (!value) return '-'
      const date = new Date(value)
      if (Number.isNaN(date.getTime())) return String(value)
      const pad = (num) => String(num).padStart(2, '0')
      return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
    }
    tasks.value = list.map((task) => {
      const statusKey = String(task.status || '').toLowerCase()
      return {
        ...task,
        name: taskNameMap[task.taskType] || task.taskType || task.name || '未知任务',
        source: task.sourceType,
        step: task.stage,
        statusLabel: statusLabelMap[statusKey] || '等待中',
        statusTone: statusKey || 'pending',
        createdAtLabel: formatTaskTime(task.createdAt),
      }
    })
  } catch (error) {
    setGlobalErrorFromException(error, '任务列表获取失败，请稍后重试。')
  }
}

const startTaskPolling = () => {
  if (taskPollTimer) return
  fetchTasks()
  taskPollTimer = window.setInterval(fetchTasks, 2500)
}

const stopTaskPolling = () => {
  if (taskPollTimer) {
    window.clearInterval(taskPollTimer)
    taskPollTimer = null
  }
}

const resetPreview = () => {
  previewState.value = 'idle'
  currentStep.value = '等待任务'
  renderProgress.value = 0
}

const trailingChars = '，。！？、；：《》）（】『』「」,.!?;:)]}>"\''

const trimExtractedUrl = (value) => {
  let url = String(value || '').trim()
  while (url && trailingChars.includes(url[url.length - 1])) {
    url = url.slice(0, -1)
  }
  return url
}

const cleanUrl = (value) => {
  let url = trimExtractedUrl(value)
  if (!url) return ''
  if (!/^https?:\/\//i.test(url) && /^(?:v\.douyin\.com|(?:www\.)?douyin\.com|(?:www\.)?tiktok\.com|(?:www\.)?bilibili\.com|b23\.tv)/i.test(url)) {
    url = `https://${url}`
  }

  let parsed
  try {
    parsed = new URL(url)
  } catch {
    return ''
  }

  const host = parsed.hostname.toLowerCase()
  const path = parsed.pathname || '/'

  if (host === 'v.douyin.com') {
    const code = path.split('/').filter(Boolean)[0]
    return code ? `https://v.douyin.com/${code}/` : ''
  }
  if (host.endsWith('douyin.com')) {
    if (path === '/discover') {
      const modalId = parsed.searchParams.get('modal_id')?.trim()
      if (modalId) return `https://www.douyin.com/video/${modalId}`
    }
    const match = path.match(/\/video\/(\d+)/)
    if (match) return `https://www.douyin.com/video/${match[1]}`
    return `https://${host}${path.replace(/\/+$/, '') || '/'}`
  }
  if (host.endsWith('tiktok.com')) {
    const shortMatch = path.match(/\/t\/([^/]+)/)
    if (shortMatch) return `https://www.tiktok.com/t/${shortMatch[1]}/`
    const videoMatch = path.match(/\/@([^/]+)\/video\/(\d+)/)
    if (videoMatch) return `https://www.tiktok.com/@${videoMatch[1]}/video/${videoMatch[2]}`
    return `https://${host}${path.replace(/\/+$/, '') || '/'}`
  }
  if (host === 'b23.tv') {
    const code = path.split('/').filter(Boolean)[0]
    return code ? `https://b23.tv/${code}` : ''
  }
  if (host.endsWith('bilibili.com')) {
    const videoMatch = path.match(/\/video\/([^/?#]+)/)
    if (videoMatch) return `https://www.bilibili.com/video/${videoMatch[1]}`
    return `https://${host}${path.replace(/\/+$/, '') || '/'}`
  }
  return `https://${host}${path}${parsed.search}${parsed.hash}`
}

const detectSourceType = (url) => {
  const value = cleanUrl(url).toLowerCase()
  if (value.includes('v.douyin.com') || value.includes('douyin.com')) return 'douyin'
  if (value.includes('tiktok.com')) return 'tiktok'
  if (value.includes('bilibili.com') || value.includes('b23.tv')) return 'bilibili'
  return 'unknown'
}

const detectUrlType = (url) => {
  const rawValue = String(url || '').toLowerCase()
  if (rawValue.includes('douyin.com/discover') && rawValue.includes('modal_id=')) return 'douyin_discover'
  const normalized = cleanUrl(url)
  const value = normalized.toLowerCase()
  if (value.includes('v.douyin.com/')) return 'douyin_short'
  if (value.includes('douyin.com/video/')) return 'douyin_video'
  if (value.includes('tiktok.com/t/')) return 'tiktok_short'
  if (value.includes('tiktok.com/@') && value.includes('/video/')) return 'tiktok_video'
  if (value.includes('b23.tv/')) return 'bilibili_short'
  if (value.includes('bilibili.com/video/')) return 'bilibili_video'
  return 'unknown'
}

const extractVideoLinksFromInput = (rawInput) => {
  const text = String(rawInput || '')
  const matches = [
    ...text.matchAll(/https?:\/\/[^\s\u3000\n\r\t"'<>]+/gi),
    ...text.matchAll(/(?:(?:https?:\/\/)?(?:v\.douyin\.com|(?:www\.)?douyin\.com|(?:www\.)?tiktok\.com|(?:www\.)?bilibili\.com|b23\.tv))[^\s\u3000\n\r\t"'<>]*/gi),
  ]
  const sortedMatches = matches.sort((left, right) => left.index - right.index)
  const seen = new Set()
  const results = []
  for (const match of sortedMatches) {
    const rawUrl = match[0]
    const normalizedUrl = cleanUrl(rawUrl)
    if (!normalizedUrl || seen.has(normalizedUrl)) continue
    seen.add(normalizedUrl)
    const urlType = detectUrlType(rawUrl)
    let videoId = ''
    if (urlType === 'douyin_short' || urlType === 'tiktok_short' || urlType === 'bilibili_short') {
      videoId = normalizedUrl.split('/').filter(Boolean).pop() || ''
    } else {
      const videoMatch = normalizedUrl.match(/\/video\/([^/?#]+)/)
      videoId = videoMatch?.[1] || ''
    }
    results.push({
      rawUrl,
      normalizedUrl,
      sourceType: detectSourceType(normalizedUrl),
      urlType,
      videoId,
      index: results.length,
    })
  }
  return results
}

const applyMaterial = (payload) => {
  material.value = payload
  materialId.value = payload.materialId
  rawScript.value = payload.description || payload.caption || payload.title || ''
  rawScriptSource.value = rawScript.value ? 'material' : 'manual'
  subtitleDownloads.value = {}
  transcriptionId.value = ''
  subtitleStatus.value = '未生成字幕'
  appError.value = ''
  if (payload.cacheStatus === 'local_ready') readStatus.value = '素材读取成功'
  else if (payload.cacheStatus === 'metadata_cached') readStatus.value = '已有素材信息，视频未下载'
  else if (payload.cacheStatus === 'local_missing') readStatus.value = '本地视频文件丢失'
  else if (payload.cacheStatus === 'local_invalid') readStatus.value = '本地视频文件无效'
  else readStatus.value = payload.status === 'ready' ? '素材读取成功' : payload.status
  previewTitle.value = payload.title || '素材预览'
  renderingMeta.value.sourceDuration = formatDuration(payload.video?.duration)
}

const normalizeMaybeApiUrl = (value) => {
  if (!value) return ''
  return String(value).startsWith('/') ? apiUrl(value) : value
}

const normalizeMaterial = (payload) => ({
  ...payload,
  video: {
    ...(payload.video || {}),
    url: normalizeMaybeApiUrl(payload.localVideoUrl || payload.video?.url),
    sources: (payload.video?.sources || []).map((item) => ({
      ...item,
      url: normalizeMaybeApiUrl(item.url),
    })),
  },
  coverUrl: normalizeMaybeApiUrl(payload.coverUrl),
  localVideoUrl: normalizeMaybeApiUrl(payload.localVideoUrl),
  musicUrl: normalizeMaybeApiUrl(payload.musicUrl),
  images: (payload.images || []).map((item) => ({
    ...item,
    url: normalizeMaybeApiUrl(item.url),
    thumbnailUrl: normalizeMaybeApiUrl(item.thumbnailUrl || item.url),
  })),
})

const setAuthStatus = (platform, payload) => {
  authStatuses.value = {
    ...authStatuses.value,
    [platform]: {
      ...(authStatuses.value[platform] || {}),
      ...payload,
    },
  }
}

const stopAuthPolling = (platform) => {
  if (authPollTimers[platform]) {
    window.clearInterval(authPollTimers[platform])
    authPollTimers[platform] = null
  }
}

const pollAuthStatus = async (platform) => {
  const payload = await getBrowserAuthStatus(platform)
  setAuthStatus(platform, payload)
  if (payload.status !== 'authorizing') {
    stopAuthPolling(platform)
  }
  return payload
}

const startAuthPolling = (platform) => {
  stopAuthPolling(platform)
  authPollTimers[platform] = window.setInterval(async () => {
    try {
      const payload = await pollAuthStatus(platform)
      authHint.value = payload.message ? normalizeUiErrorMessage({ message: payload.message }, '') : ''
    } catch (error) {
      setAuthHintFromException(error)
      stopAuthPolling(platform)
    }
  }, 2500)
}

const loadAllAuthStatuses = async () => {
  for (const platform of ['douyin', 'bilibili']) {
    try {
      const payload = await getBrowserAuthStatus(platform)
      setAuthStatus(platform, payload)
    } catch {
      // ignore auth bootstrap failures
    }
  }
}

const handleStartAuth = async (platform) => {
  appError.value = ''
  try {
    const payload = await startBrowserAuth(platform)
    setAuthStatus(platform, payload)
    authHint.value = payload.message ? normalizeUiErrorMessage({ message: payload.message }, '') : ''
    if (payload.status === 'authorizing') {
      startAuthPolling(platform)
    }
  } catch (error) {
    setAuthHintFromException(error)
  }
}

const handleClearAuth = async (platform) => {
  appError.value = ''
  try {
    const payload = await clearBrowserAuth(platform)
    setAuthStatus(platform, payload)
    authHint.value = payload.message ? normalizeUiErrorMessage({ message: payload.message }, '') : ''
    stopAuthPolling(platform)
  } catch (error) {
    setAuthHintFromException(error)
  }
}

const handleFileSelected = async (file) => {
  uploadedFile.value = file
  uploadedFileName.value = file.name
  readStatus.value = `正在上传 ${file.name}...`
  material.value = null
  materialId.value = ''
  rawScript.value = ''
  subtitleDownloads.value = {}
  isReading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const payload = await uploadMaterial(formData)
    applyMaterial(normalizeMaterial(payload))
  } catch (error) {
    material.value = null
    materialId.value = ''
    readStatus.value = normalizeUiErrorMessage(error, '素材上传失败，请稍后重试。')
    setGlobalErrorFromException(error, '素材上传失败，请稍后重试。')
  } finally {
    isReading.value = false
  }
}

const handleManualInput = () => {
  readStatus.value = '手动输入中'
}

const readMaterial = async () => {
  appError.value = ''
  material.value = null
  materialId.value = ''
  rawScript.value = ''
  subtitleDownloads.value = {}
  const rawInput = videoLink.value.trim()
  const extractedLinks = extractVideoLinksFromInput(rawInput)
  if (!extractedLinks.length) {
    readStatus.value = '未识别到有效视频链接'
    appError.value = '未识别到有效视频链接，请粘贴抖音/B站/TikTok分享链接，或上传本地视频。'
    return
  }
  const primaryLink = extractedLinks[0]
  pendingUrls.value = extractedLinks.slice(1).map((item) => item.normalizedUrl)
  videoLink.value = primaryLink.normalizedUrl
  const detectedSourceType = primaryLink.sourceType
  if (detectedSourceType === 'unknown') {
    readStatus.value = '当前平台可能暂不稳定'
  }
  isReading.value = true
  try {
    const payload = await extractMaterial({
      sourceType: detectedSourceType,
      input: rawInput,
      url: primaryLink.normalizedUrl,
      urls: extractedLinks.map((item) => item.normalizedUrl),
    })
    applyMaterial(normalizeMaterial(payload))
  } catch (error) {
    const errorType = error.data?.errorType
    const sourceType = error.data?.sourceType
    if (errorType === 'platform_not_authorized') {
      authHint.value = normalizeAuthErrorMessage(error)
      if (sourceType) {
        setAuthStatus(sourceType, { status: 'unauthorized', message: error.message })
      }
      readStatus.value = '请先完成授权'
      return
    }
    const materialErrorMessage = normalizeMaterialReadErrorMessage(error)
    readStatus.value = materialErrorMessage
    appError.value = materialErrorMessage
    console.error(error)
  } finally {
    isReading.value = false
  }
}

const formatDuration = (seconds) => {
  const total = Math.max(0, Math.round(Number(seconds || 0)))
  const minutes = String(Math.floor(total / 60)).padStart(2, '0')
  const remain = String(total % 60).padStart(2, '0')
  return `00:${minutes}:${remain}`
}

const extractScript = async () => {
  if (!materialId.value) {
    appError.value = '请先完成素材导入。'
    return
  }
  transcriptionLoading.value = true
  subtitleStatus.value = '转写任务创建中'
  try {
    const task = await createTranscription({
      materialId: materialId.value,
      model: 'medium',
      language: 'zh',
      device: 'cpu',
      computeType: 'int8',
      beamSize: 5,
    })
    transcriptionId.value = task.transcriptionId
    currentStep.value = task.stage || '文案提取'
    previewState.value = 'rendering'
    renderProgress.value = task.progress || 0
    subtitleStatus.value = task.message || '转写任务已创建'
    await fetchTasks()
    transcriptionPollTimer = window.setInterval(async () => {
      try {
        const latest = await getTranscription(task.transcriptionId)
        currentStep.value = latest.stage || '文案提取'
        renderProgress.value = latest.progress || 0
        subtitleStatus.value = latest.message || latest.stage
        const preferredText =
          latest.finalText || latest.correctedAsrText || latest.asrText || latest.transcript || latest.text || ''
        if (preferredText) {
          rawScript.value = preferredText
          rawScriptSource.value = 'transcription'
          previewTitle.value = preferredText.slice(0, 24) || '已生成原始文案'
        }
        if (latest.status === 'success') {
          subtitleDownloads.value = latest.subtitleFiles || {}
          previewState.value = 'done'
          renderingMeta.value.finalDuration = renderingMeta.value.sourceDuration
          window.clearInterval(transcriptionPollTimer)
          transcriptionPollTimer = null
          transcriptionLoading.value = false
          readStatus.value = '视频文案提取完成'
        }
        if (latest.status === 'failed') {
          previewState.value = 'idle'
          window.clearInterval(transcriptionPollTimer)
          transcriptionPollTimer = null
          transcriptionLoading.value = false
          readStatus.value = latest.message || '视频文案提取失败'
        }
      } catch (error) {
        setGlobalErrorFromException(error, '视频文案提取失败，请稍后重试。')
      }
    }, 2000)
  } catch (error) {
    subtitleStatus.value = normalizeUiErrorMessage(error, '视频文案提取失败')
    setGlobalErrorFromException(error, '视频文案提取失败，请稍后重试。')
    transcriptionLoading.value = false
  }
}

const appendPromptTemplate = (template) => {
  const separator = promptText.value.trim() ? '；' : ''
  promptText.value = `${promptText.value}${separator}${template}`
}

const handleReferenceAudioSelected = (event) => {
  const [file] = event.target.files || []
  if (!file) return
  referenceAudioFile.value = file
  referenceAudioName.value = file.name
  trainingStatus.value = `已选择 ${file.name}`
  event.target.value = ''
}

const startTraining = async () => {
  if (!referenceAudioFile.value) {
    appError.value = '请先选择参考音频。'
    return
  }
  trainingStatus.value = '音色任务创建中'
  trainingReady.value = false
  try {
    const formData = new FormData()
    formData.append('referenceAudio', referenceAudioFile.value)
    const task = await createTraining(formData)
    trainingId.value = task.trainingId
    trainingStatus.value = task.message || '音色任务已创建'
    await fetchTasks()
    trainingPollTimer = window.setInterval(async () => {
      try {
        const latest = await getTraining(task.trainingId)
        trainingStatus.value = latest.message || latest.stage
        if (latest.status === 'success') {
          trainingReady.value = true
          window.clearInterval(trainingPollTimer)
          trainingPollTimer = null
        }
        if (latest.status === 'failed') {
          window.clearInterval(trainingPollTimer)
          trainingPollTimer = null
        }
      } catch (error) {
        setGlobalErrorFromException(error, '音色训练状态获取失败，请稍后重试。')
      }
    }, 2000)
  } catch (error) {
    trainingStatus.value = normalizeUiErrorMessage(error, '音色训练失败')
    setGlobalErrorFromException(error, '音色训练失败，请稍后重试。')
  }
}

const generateVoice = async () => {
  if (!rawScript.value.trim()) {
    appError.value = '请先提取或输入原始文案。'
    return
  }
  voiceGenerating.value = true
  voiceStatus.value = '配音任务创建中'
  try {
    const synthesis = await createSynthesis({
      text: rawScript.value,
      language: 'zh',
      trainingId: trainingReady.value ? trainingId.value : null,
      voiceMode: trainingReady.value ? 'clone' : 'preset',
      executionProvider: 'cpu',
    })
    synthesisId.value = synthesis.synthesisId
    voiceStatus.value = synthesis.message || '配音任务已创建'
    await fetchTasks()
    synthesisPollTimer = window.setInterval(async () => {
      try {
        const latest = await getSynthesis(synthesis.synthesisId)
        voiceStatus.value = latest.message || latest.status
        if (latest.audioUrl) {
          synthesisAudioUrl.value = apiUrl(latest.audioUrl)
          renderingMeta.value.voiceDuration = renderingMeta.value.sourceDuration
        }
        if (latest.status === 'success') {
          voiceGenerating.value = false
          window.clearInterval(synthesisPollTimer)
          synthesisPollTimer = null
        }
        if (latest.status === 'failed') {
          voiceGenerating.value = false
          window.clearInterval(synthesisPollTimer)
          synthesisPollTimer = null
        }
      } catch (error) {
        setGlobalErrorFromException(error, '语音合成状态获取失败，请稍后重试。')
      }
    }, 2000)
  } catch (error) {
    voiceStatus.value = normalizeUiErrorMessage(error, '语音合成失败')
    setGlobalErrorFromException(error, '语音合成失败，请稍后重试。')
    voiceGenerating.value = false
  }
}

const previewVoice = () => {
  if (!synthesisAudioUrl.value) {
    appError.value = '请先生成配音。'
    return
  }
  previewingVoice.value = true
  voiceStatus.value = '请使用下方播放器试听'
  window.setTimeout(() => {
    previewingVoice.value = false
  }, 500)
}

onMounted(() => {
  startTaskPolling()
  loadAllAuthStatuses()
})

onBeforeUnmount(() => {
  stopTaskPolling()
  if (transcriptionPollTimer) window.clearInterval(transcriptionPollTimer)
  if (trainingPollTimer) window.clearInterval(trainingPollTimer)
  if (synthesisPollTimer) window.clearInterval(synthesisPollTimer)
  stopAuthPolling('douyin')
  stopAuthPolling('bilibili')
})
</script>

<template>
  <div class="studio-shell">
    <StudioSidebar :items="navigationItems" :active-id="activeNav" @select="activeNav = $event" />

    <div class="studio-main">
      <StudioTopbar
        :service-status="serviceStatus"
        :model-status="modelStatus"
        :output-path="outputPath"
      />

      <main class="studio-workbench">
        <p v-if="appError" class="app-banner">{{ appError }}</p>

        <div class="workbench-grid">
          <MaterialScriptPanel
            v-model:video-link="videoLink"
            :raw-script="rawScript"
            :read-status="readStatus"
            :uploaded-file-name="uploadedFileName"
            :material-summary="materialSummary"
            :material="material"
            :is-reading="isReading"
            :transcription-loading="transcriptionLoading"
            :subtitle-status="subtitleStatus"
            :material-lamp="materialLamp"
            :material-lamp-text="materialLampText"
            :auth-statuses="authStatuses"
            :auth-hint="authHint"
            :script-source-label="scriptSourceLabel"
            :script-detail-ready="scriptDetailReady"
            :material-local-ready="materialLocalReady"
            @read-video="readMaterial"
            @file-selected="handleFileSelected"
            @manual-input="handleManualInput"
            @extract-script="extractScript"
            @start-auth="handleStartAuth"
            @clear-auth="handleClearAuth"
            @update:raw-script="handleRawScriptInput"
          />

          <PromptRewritePanel
            v-model:prompt-text="promptText"
            v-model:selected-platform="selectedPlatform"
            v-model:selected-length="selectedLength"
            v-model:selected-tone="selectedTone"
            v-model:keep-keywords="keepKeywords"
            :templates="promptTemplates"
            :platforms="platformOptions"
            :lengths="lengthOptions"
            :tones="toneOptions"
            :rewrite-results="rewriteResults"
            :active-result-id="activeResultId"
            :is-rewriting="false"
            :feature-ready="false"
            @append-template="appendPromptTemplate"
          />

          <VoiceHumanPanel
            v-model:selected-voice="selectedVoice"
            v-model:selected-emotion="selectedEmotion"
            v-model:speed="voiceSpeed"
            v-model:volume="voiceVolume"
            v-model:selected-avatar-id="selectedAvatarId"
            v-model:selected-scene="selectedScene"
            v-model:selected-background="selectedBackground"
            :voices="voiceOptions"
            :emotions="emotionOptions"
            :avatars="avatarOptions"
            :scene-options="sceneOptions"
            :background-options="backgroundOptions"
            :previewing-voice="previewingVoice"
            :voice-generating="voiceGenerating"
            :human-generating="false"
            :voice-status="voiceStatus"
            :human-status="humanStatus"
            :training-status="trainingStatus"
            :training-ready="trainingReady"
            :synthesis-audio-url="synthesisAudioUrl"
            :reference-audio-name="referenceAudioName"
            @preview-voice="previewVoice"
            @generate-voice="generateVoice"
            @reference-audio-selected="handleReferenceAudioSelected"
            @create-training="startTraining"
          />

          <ExportPanel
            v-model:subtitle-enabled="subtitleEnabled"
            v-model:subtitle-style="selectedSubtitleStyle"
            v-model:subtitle-position="selectedSubtitlePosition"
            v-model:selected-bgm="selectedBgm"
            v-model:narration-volume="narrationVolume"
            v-model:bgm-volume="bgmVolume"
            v-model:selected-aspect="selectedAspect"
            v-model:selected-quality="selectedQuality"
            v-model:output-path="outputPath"
            v-model:save-to-library="saveToLibrary"
            v-model:export-materials="exportMaterials"
            :subtitle-styles="subtitleStyles"
            :subtitle-positions="subtitlePositions"
            :bgm-options="bgmOptions"
            :aspect-options="aspectOptions"
            :quality-options="qualityOptions"
            :rendering="false"
            :subtitle-status="subtitleStatus"
            :subtitle-downloads="subtitleDownloads"
          />

          <VideoPreviewPanel
            :material="material"
            :read-status="readStatus"
            :material-lamp="materialLamp"
            :material-lamp-text="materialLampText"
            :material-local-ready="materialLocalReady"
            :preview-state="previewState"
            :preview-title="previewTitle"
            :current-step="currentStep"
            :progress="renderProgress"
            :output-path="outputPath"
            :rendering-meta="renderingMeta"
          />
        </div>

        <RecentTaskTable
          :tasks="tasks.slice(0, 5)"
          :total-count="tasks.length"
        />
      </main>
    </div>
  </div>
</template>
