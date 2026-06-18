<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import StudioTopbar from './components/StudioTopbar.vue'
import StudioSidebar from './components/StudioSidebar.vue'
import MaterialScriptPanel from './components/MaterialScriptPanel.vue'
import PromptRewritePanel from './components/PromptRewritePanel.vue'
import VoiceHumanPanel from './components/VoiceHumanPanel.vue'
import ChanjingDigitalHumanManager from './components/digital-human/ChanjingDigitalHumanManager.vue'
import VoiceLibraryView from './components/VoiceLibraryView.vue'
import ExportPanel from './components/ExportPanel.vue'
import VideoPreviewPanel from './components/VideoPreviewPanel.vue'
import RecentTaskTable from './components/RecentTaskTable.vue'
import { clearBrowserAuth, getBrowserAuthStatus, startBrowserAuth } from './api/browserAuth'
import {
  createVoiceFromMaterial,
  createVoicePreview,
  createVoiceProfile,
  deleteVoiceProfile,
  listVoiceProfiles,
  updateVoiceProfile,
} from './api/tts'
import { getAiStatus } from './api/ai'
import { apiUrl } from './api/client'
import { generateDigitalHumanVideo, getDigitalHumanTask } from './api/digitalHuman'
import {
  createStudioProject,
  createStudioSynthesis,
  createStudioTranscription,
  extractStudioMaterial,
  getStudioProject,
  getStudioSynthesis,
  listStudioTasks,
  rewriteStudioCopy,
  uploadStudioMaterial,
} from './api/studio'
import {
  aspectOptions,
  avatarOptions,
  backgroundOptions,
  bgmOptions,
  emotionOptions,
  navigationItems,
  promptTemplates,
  qualityOptions,
  sceneOptions,
  subtitlePositions,
  subtitleStyles,
} from './data/mockData'

const activeNav = ref('home')
const currentView = ref('workbench')
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
const lastInputRaw = ref('')
const currentNormalizedUrl = ref('')
const requestSeq = ref(0)

const promptText = ref('把这段文案改成普通人真实分享口吻，开头更抓人，不要太营销，适合抖音 30 秒口播。')
const selectedRewriteTemplate = ref('')
const rewriteResults = ref([])
const activeResultId = ref('')
const isRewriting = ref(false)
const rewriteFailed = ref(false)
const currentScript = ref('')
const currentScriptSource = ref('empty')
const currentScriptTitle = ref('')
const aiStatus = ref({
  available: false,
  provider: null,
  model: null,
  message: 'AI 改写服务未配置，请先配置模型服务。',
})

const voices = ref([])
const legacyVoiceNames = new Set(['磁性男声', '温柔女声', '知识老师', '普通人口播'])
const isCosyVoiceSynthesisReady = (voice) => {
  const duration = Number(voice?.duration || 0)
  return (
    voice?.status === 'ready' &&
    String(voice?.engine || 'cosyvoice').toLowerCase() === 'cosyvoice' &&
    voice?.promptTextConfigured === true &&
    duration >= 10 &&
    duration <= 30
  )
}
const selectedVoiceId = ref('')
const selectedEmotion = ref(emotionOptions[0])
const voiceSpeed = ref(1.0)
const voiceVolume = ref(82)
const previewingVoice = ref(false)
const voiceGenerating = ref(false)
const humanGenerating = ref(false)
const creatingVoiceFromMaterial = ref(false)
const voiceStatus = ref('待生成')
const humanStatus = ref('未生成数字人视频')
const trainingStatus = ref('未创建音色')
const voiceCreateDialogVisible = ref(false)
const voiceCreateLoading = ref(false)
const voiceCreateName = ref('我的音色')
const voiceCreateAudioFile = ref(null)
const voiceCreateAudioName = ref('')
const voiceCreateConsent = ref(false)
const voiceCreateError = ref('')
const synthesisId = ref('')
const synthesisAudioUrl = ref('')
const voicePreviewAudioUrl = ref('')
const voiceLibraryLoading = ref(false)
const voiceLibraryBusyId = ref('')
const voiceLibraryMessage = ref('')
const voiceLibraryPreviewAudioUrl = ref('')
const voiceLibraryPreviewVoiceId = ref('')
const selectedAvatarId = ref(avatarOptions[0].id)
const selectedScene = ref(sceneOptions[0])
const selectedBackground = ref(backgroundOptions[0])
const selectedDigitalHumanPerson = ref(null)
const studioDigitalHumanOutputPath = ref('')

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
const originalTextSource = ref('empty')
const createEmptyProject = () => ({
  projectId: null,
  material: null,
  materialMode: 'empty',
  originalText: '',
  originalTextSource: 'empty',
  rewriteVersions: [],
  selectedRewriteVersionId: null,
  currentScript: '',
  currentScriptSource: '',
  currentScriptTitle: '',
  selectedVoiceId: selectedVoiceId.value,
  selectedVoiceType: '',
  selectedAvatarId: selectedAvatarId.value,
  selectedAvatarName: avatarOptions.find((item) => item.id === selectedAvatarId.value)?.name || '',
  currentAudio: null,
  digitalHumanVideo: null,
  subtitles: null,
  bgm: {
    name: selectedBgm.value,
    narrationVolume: narrationVolume.value,
    bgmVolume: bgmVolume.value,
  },
  exportResult: null,
  previewVideo: null,
})
const currentProject = ref(createEmptyProject())

const renderingMeta = ref({
  sourceDuration: '--:--',
  voiceDuration: '--:--',
  finalDuration: '--:--',
})

let taskPollTimer = null
let trainingPollTimer = null
let synthesisPollTimer = null
let digitalHumanPollTimer = null
const authPollTimers = {
  douyin: null,
  bilibili: null,
}

const selectedAvatar = computed(() =>
  avatarOptions.find((item) => item.id === selectedAvatarId.value) ?? avatarOptions[0],
)

const scriptSourceLabel = computed(() => {
  const source = currentProject.value.originalTextSource || originalTextSource.value
  if (source === 'video_transcript') return '视频口播'
  if (source === 'platform_description') return '平台文案'
  if (source === 'manual') return '手动文案'
  return '空'
})

const rewriteSourceUsageText = computed(() => {
  const source = currentProject.value.originalTextSource || originalTextSource.value
  if (source === 'video_transcript') return '当前使用：视频口播'
  if (source === 'manual') return '当前使用：手动文案'
  if (source === 'platform_description') return '当前只有平台文案，建议先提取口播。'
  return '请先提取或输入文案'
})

const sourceTextReadyForRewrite = computed(
  () =>
    Boolean(currentProject.value.originalText.trim()) &&
    (currentProject.value.originalTextSource === 'video_transcript' || currentProject.value.originalTextSource === 'manual'),
)

const isManualTextMode = computed(() => currentProject.value.originalTextSource === 'manual' && !currentProject.value.material)

const canSetTextResultAsCurrent = computed(
  () =>
    Boolean(currentProject.value.originalText.trim()) &&
    (currentProject.value.originalTextSource === 'video_transcript' || currentProject.value.originalTextSource === 'manual'),
)

const canRewrite = computed(() => aiRewriteAvailable.value && sourceTextReadyForRewrite.value)

const canUsePlatformTextForRewrite = computed(
  () => aiRewriteAvailable.value && currentProject.value.originalTextSource === 'platform_description' && Boolean(currentProject.value.originalText.trim()),
)

const rewriteUnavailableMessage = computed(() => {
  if (!aiRewriteAvailable.value) return aiUnavailableMessage.value
  if (currentProject.value.originalTextSource === 'platform_description') {
    return '当前只有平台文案，请先提取视频口播，或手动确认后再改写。'
  }
  if (!currentProject.value.originalText.trim() || currentProject.value.originalTextSource === 'empty') return '请先提取视频口播，或手动输入文案。'
  return ''
})

const aiRewriteAvailable = computed(() => Boolean(aiStatus.value?.available))

const aiUnavailableMessage = computed(() => {
  if (aiRewriteAvailable.value) return ''
  return aiStatus.value?.message || 'AI 改写服务未配置，请先配置模型服务。'
})

const materialLocalReady = computed(
  () =>
    material.value?.cacheStatus === 'local_ready' &&
    material.value?.downloadStatus === 'downloaded' &&
    material.value?.localFileStatus === 'exists' &&
    Boolean(material.value?.localVideoUrl),
)

const isMaterialPayloadReady = (payload) =>
  payload?.cacheStatus === 'local_ready' &&
  payload?.downloadStatus === 'downloaded' &&
  payload?.localFileStatus === 'exists' &&
  Boolean(payload?.localVideoUrl)

const getMaterialUrl = (payload) => cleanUrl(payload?.normalizedUrl || payload?.sourceUrl || '')

const activeMaterialUrl = computed(() => getMaterialUrl(material.value))

const currentInputUrl = computed(() => extractVideoLinksFromInput(videoLink.value)[0]?.normalizedUrl || '')

const isInputDirty = computed(() => {
  const inputUrl = currentInputUrl.value
  const activeUrl = activeMaterialUrl.value
  if (!inputUrl) return Boolean(material.value && videoLink.value.trim() && videoLink.value.trim() !== activeUrl)
  if (!material.value) return true
  return inputUrl !== activeUrl
})

const currentMaterialLocalReady = computed(() => materialLocalReady.value && !isInputDirty.value)

const selectedVoice = computed(() => voices.value.find((voice) => voice.voiceId === selectedVoiceId.value) || null)
const activeTtsText = computed(() => currentProject.value.currentScript || '')

const projectStepStatus = computed(() => ({
  materialReady: Boolean(
    currentProject.value.materialMode === 'video' &&
      currentProject.value.material?.localVideoUrl &&
      currentMaterialLocalReady.value,
  ),
  scriptReady: Boolean(currentProject.value.currentScript?.trim()),
  audioReady: Boolean(currentProject.value.currentAudio?.audioUrl),
  subtitleReady: Boolean(currentProject.value.subtitles || subtitleDownloads.value.srt || subtitleDownloads.value.vtt),
  avatarReady: Boolean(selectedDigitalHumanPerson.value?.templateId),
  exportReady: Boolean(currentProject.value.currentAudio?.audioUrl),
}))

const studioDigitalHumanBackendReady = computed(() => true)

const studioDigitalHumanDisplayName = computed(
  () => selectedDigitalHumanPerson.value?.name || selectedDigitalHumanPerson.value?.templateId || '',
)

const canGenerateStudioDigitalHuman = computed(
  () =>
    Boolean(currentProject.value.currentAudio?.audioUrl) &&
    Boolean(selectedDigitalHumanPerson.value?.templateId) &&
    studioDigitalHumanBackendReady.value,
)

const studioDigitalHumanHint = computed(() => {
  if (!currentProject.value.currentAudio?.audioUrl) return '请先生成配音。'
  if (!selectedDigitalHumanPerson.value?.templateId) return '请先选择数字人。'
  return `已准备：${currentProject.value.currentScriptTitle || '当前配音'} · ${studioDigitalHumanDisplayName.value}`
})

const studioDigitalHumanStatus = computed(() => {
  if (humanGenerating.value) return humanStatus.value || '数字人视频生成中'
  if (currentProject.value.digitalHumanVideo?.videoUrl) return humanStatus.value || '数字人视频已生成'
  if (humanStatus.value && ['缺少配音', '未选择数字人'].includes(humanStatus.value)) return humanStatus.value
  if (!selectedDigitalHumanPerson.value?.templateId) return '未选择数字人'
  if (!currentProject.value.currentAudio?.audioUrl) return `已选择 ${studioDigitalHumanDisplayName.value}，待配音`
  return humanStatus.value || `已选择 ${studioDigitalHumanDisplayName.value}`
})

const studioDigitalHumanMissingCapabilityHint = computed(() =>
  studioDigitalHumanBackendReady.value
    ? ''
    : '',
)

const resetCurrentProject = (overrides = {}) => {
  currentProject.value = {
    ...createEmptyProject(),
    selectedVoiceType: selectedVoice.value?.type || '',
    selectedAvatarName: selectedAvatar.value?.name || '',
    ...overrides,
  }
}

const clearProjectDigitalHumanOutput = () => {
  currentProject.value.digitalHumanVideo = null
  studioDigitalHumanOutputPath.value = ''
  if (currentProject.value.previewVideo?.type === 'digital_human') {
    currentProject.value.previewVideo = currentProject.value.material?.localVideoUrl
      ? {
          type: 'material',
          url: currentProject.value.material.localVideoUrl,
          title: currentProject.value.material.title || '素材视频',
        }
      : null
  }
}

const setProjectMaterial = (nextMaterial) => {
  currentProject.value.material = nextMaterial || null
  currentProject.value.materialMode = nextMaterial ? 'video' : 'empty'
  currentProject.value.previewVideo = nextMaterial?.localVideoUrl
    ? {
        type: 'material',
        url: nextMaterial.localVideoUrl,
        title: nextMaterial.title || '素材视频',
      }
    : null
  clearProjectDigitalHumanOutput()
}

const setProjectOriginalText = (text, source) => {
  const nextText = String(text || '')
  const nextSource = source || (nextText.trim() ? 'manual' : 'empty')
  const sourceChanged =
    nextText !== currentProject.value.originalText || nextSource !== currentProject.value.originalTextSource
  if (sourceChanged) {
    rewriteResults.value = []
    activeResultId.value = ''
    rewriteFailed.value = false
    currentProject.value.rewriteVersions = []
    currentProject.value.selectedRewriteVersionId = null
  }
  rawScript.value = nextText
  originalTextSource.value = nextSource
  currentProject.value.originalText = nextText
  currentProject.value.originalTextSource = originalTextSource.value
}

const clearProjectCurrentScript = () => {
  currentScript.value = ''
  currentScriptSource.value = 'empty'
  currentScriptTitle.value = ''
  activeResultId.value = ''
  synthesisAudioUrl.value = ''
  synthesisId.value = ''
  currentProject.value.currentScript = ''
  currentProject.value.currentScriptSource = ''
  currentProject.value.currentScriptTitle = ''
  currentProject.value.selectedRewriteVersionId = null
  currentProject.value.currentAudio = null
  clearProjectDigitalHumanOutput()
  voiceStatus.value = '待生成'
  humanStatus.value = '未生成数字人视频'
}

const setProjectCurrentScript = ({ text, source, title, activeResult = '' }) => {
  const nextText = String(text || '').trim()
  currentScript.value = nextText
  currentScriptSource.value = source || 'empty'
  currentScriptTitle.value = title || '当前文案'
  activeResultId.value = activeResult
  synthesisAudioUrl.value = ''
  synthesisId.value = ''
  currentProject.value.currentScript = nextText
  currentProject.value.currentScriptSource = currentScriptSource.value
  currentProject.value.currentScriptTitle = currentScriptTitle.value
  currentProject.value.selectedRewriteVersionId = source === 'rewrite_version' ? activeResult || null : null
  currentProject.value.currentAudio = null
  clearProjectDigitalHumanOutput()
  voiceStatus.value = `已选择 ${currentScriptTitle.value}`
  humanStatus.value = '未生成数字人视频'
}

const setProjectCurrentAudio = (audioResult) => {
  const rawAudioUrl = String(audioResult?.audioUrl || '')
  const audioUrl = rawAudioUrl
    ? rawAudioUrl.startsWith('http://') || rawAudioUrl.startsWith('https://')
      ? rawAudioUrl
      : apiUrl(rawAudioUrl)
    : ''
  currentProject.value.currentAudio = audioUrl
    ? {
        audioId: audioResult?.audioId || audioResult?.synthesisId || synthesisId.value,
        synthesisId: audioResult?.synthesisId || synthesisId.value,
        audioUrl,
        duration: audioResult?.duration || audioResult?.durationSeconds || null,
        voiceId: selectedVoiceId.value,
        voiceType: selectedVoice.value?.type || '',
        sourceScriptTitle: currentScriptTitle.value,
        status: audioResult?.status || 'success',
      }
    : null
}

watch(
  () => [selectedVoiceId.value, selectedVoice.value?.type || ''],
  ([voiceId, voiceType], [previousVoiceId] = []) => {
    currentProject.value.selectedVoiceId = voiceId
    currentProject.value.selectedVoiceType = voiceType
    if (previousVoiceId && previousVoiceId !== voiceId && currentProject.value.currentAudio) {
      currentProject.value.currentAudio = null
      clearProjectDigitalHumanOutput()
      synthesisAudioUrl.value = ''
      synthesisId.value = ''
      voiceStatus.value = '音色已切换，请重新生成配音'
      humanStatus.value = '未生成数字人视频'
    }
  },
  { immediate: true },
)

watch(
  () => [selectedBgm.value, narrationVolume.value, bgmVolume.value],
  ([name, narration, bgmLevel]) => {
    currentProject.value.bgm = {
      name,
      narrationVolume: narration,
      bgmVolume: bgmLevel,
    }
  },
  { immediate: true },
)

watch(
  () => [selectedAvatarId.value, selectedAvatar.value?.name || ''],
  ([avatarId, avatarName]) => {
    currentProject.value.selectedAvatarId = avatarId
    currentProject.value.selectedAvatarName = avatarName
  },
  { immediate: true },
)

const selectedVoiceReferenceAudioUrl = computed(() => {
  const voice = selectedVoice.value
  const url = String(voice?.referenceAudioUrl || '')
  if (!url) return ''
  return /^https?:\/\//i.test(url) ? url : apiUrl(url)
})

const selectedVoiceQualityWarnings = computed(() => selectedVoice.value?.quality?.warnings || [])

const currentMaterialVoice = computed(() => {
  const currentMaterialId = materialId.value
  if (!currentMaterialId) return null
  return (
    voices.value.find(
      (voice) =>
        voice.type === 'custom' &&
        (voice.source === 'current_video' || voice.source === 'material') &&
        (voice.materialId === currentMaterialId || voice.materialKey === material.value?.materialKey),
    ) || null
  )
})

const currentMaterialVoiceIsClean = computed(
  () => currentMaterialVoice.value?.referenceExtraction?.version === 'clean_segment_v1',
)

const hasCurrentMaterialVoice = computed(() => Boolean(currentMaterialVoice.value && currentMaterialVoiceIsClean.value))

const materialLamp = computed(() => {
  if (isReading.value) return 'processing'
  if (isInputDirty.value) return 'idle'
  if (appError.value && !currentMaterialLocalReady.value) return 'failed'
  if (currentMaterialLocalReady.value) return 'ready'
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

const ttsErrorMessage = (payload, fallback = '语音合成失败') => {
  const data = payload?.data || payload || {}
  const errorType = String(data?.errorType || data?.error_type || '')
  const reason = String(data?.reason || '')
  const type = errorType || reason
  const typeMessages = {
    cosyvoice_not_installed: 'CosyVoice 运行依赖未安装。',
    cosyvoice_not_ready: 'CosyVoice 未配置或不可用，请检查 TTS 引擎配置。',
    cosyvoice_model_missing: 'CosyVoice 模型目录不存在。',
    model_dir_missing: 'CosyVoice 模型目录不存在。',
    reference_audio_missing: '当前音色缺少参考音频。',
    voice_reference_missing: '当前音色缺少参考音频。',
    voice_not_found: '当前音色不存在。',
    tts_text_required: '当前配音文案为空。',
    empty_text: '当前配音文案为空。',
    voice_prompt_text_missing: '当前音色缺少参考文本。',
    prompt_text_required: '当前音色缺少参考文本。',
    voice_profile_invalid: '当前音色配置无效，请重新创建音色。',
    prompt_text_mismatch: '当前音色参考文本与参考音频不匹配，请重新创建音色。',
    reference_audio_too_short: '当前音色参考音频太短。',
    reference_audio_format_invalid: '当前音色参考音频格式不符合要求。',
    reference_audio_volume_too_low: '当前音色参考音频人声过低。',
  }
  if (typeMessages[type]) return typeMessages[type]
  const message = String(payload?.message || data?.message || '')
  return message ? `语音合成失败：${message}` : fallback
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

const nextRequestSeq = () => {
  requestSeq.value += 1
  return requestSeq.value
}

const isCurrentRequest = (requestSeqSnapshot) => requestSeqSnapshot === requestSeq.value

const resetMaterialForDirtyInput = () => {
  material.value = null
  materialId.value = ''
  setProjectMaterial(null)
  setProjectOriginalText('', 'empty')
  clearCurrentScript()
  subtitleDownloads.value = {}
  currentProject.value.subtitles = null
  transcriptionId.value = ''
  subtitleStatus.value = '未生成字幕'
  previewState.value = 'idle'
  renderProgress.value = 0
  currentStep.value = '等待任务'
  readStatus.value = '等待提取当前链接'
  appError.value = ''
}

const clearCurrentScript = () => {
  clearProjectCurrentScript()
}

const handleVideoLinkInput = (value) => {
  videoLink.value = value
  const normalizedUrl = extractVideoLinksFromInput(value)[0]?.normalizedUrl || ''
  currentNormalizedUrl.value = normalizedUrl

  if (!material.value) return

  const activeUrl = activeMaterialUrl.value
  const trimmedInput = String(value || '').trim()
  const inputChangedFromActiveMaterial = normalizedUrl
    ? normalizedUrl !== activeUrl
    : Boolean(trimmedInput && trimmedInput !== activeUrl)

  if (!inputChangedFromActiveMaterial) return

  requestSeq.value += 1
  resetMaterialForDirtyInput()
}

const handleRawScriptInput = (value) => {
  const nextText = String(value || '')
  if (currentScriptSource.value === 'manual' && currentScript.value !== nextText.trim()) {
    clearCurrentScript()
    voiceStatus.value = '文案已修改，请重新设为成片文案'
  }
  setProjectOriginalText(
    nextText,
    nextText.trim() || originalTextSource.value === 'manual' ? 'manual' : 'empty',
  )
}

const fetchTasks = async () => {
  try {
    const list = await listStudioTasks()
    const taskNameMap = {
      'material.fetch': '素材读取',
      'transcription.extract': '视频文案提取',
      'tts.synthesis': '语音合成',
      'tts.training': '音色训练',
      'copy.rewrite': '文案改写',
      'digital_human.generate': '数字人任务',
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
  setProjectMaterial(payload)
  const platformText = payload.description || payload.caption || payload.title || ''
  setProjectOriginalText(platformText, platformText ? 'platform_description' : 'empty')
  clearCurrentScript()
  subtitleDownloads.value = {}
  currentProject.value.subtitles = null
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

const ensureStudioProjectId = async () => {
  const existingId = String(currentProject.value.projectId || '').trim()
  if (existingId) return existingId
  const project = await createStudioProject({ name: currentProjectTitle.value || 'Studio 项目' })
  currentProject.value.projectId = project.projectId
  return project.projectId
}

const startFreshStudioProject = async () => {
  const project = await createStudioProject({ name: 'Studio 项目' })
  currentProject.value.projectId = project.projectId
  return project.projectId
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
  const requestSeqSnapshot = nextRequestSeq()
  const projectId = await ensureStudioProjectId()
  uploadedFile.value = file
  uploadedFileName.value = file.name
  currentNormalizedUrl.value = ''
  lastInputRaw.value = file.name
  readStatus.value = `正在上传 ${file.name}...`
  currentProject.value.materialMode = 'video_pending'
  material.value = null
  materialId.value = ''
  setProjectMaterial(null)
  setProjectOriginalText('', 'empty')
  clearCurrentScript()
  subtitleDownloads.value = {}
  currentProject.value.subtitles = null
  isReading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const payload = await uploadStudioMaterial(projectId, formData)
    if (!isCurrentRequest(requestSeqSnapshot)) return
    applyMaterial(normalizeMaterial(payload))
  } catch (error) {
    if (!isCurrentRequest(requestSeqSnapshot)) return
    material.value = null
    materialId.value = ''
    setProjectMaterial(null)
    readStatus.value = normalizeUiErrorMessage(error, '素材上传失败，请稍后重试。')
    setGlobalErrorFromException(error, '素材上传失败，请稍后重试。')
  } finally {
    if (isCurrentRequest(requestSeqSnapshot)) {
      isReading.value = false
    }
  }
}

const handleManualInput = () => {
  const hasExistingProjectOutput = Boolean(
    currentProject.value.currentScript?.trim() || currentProject.value.currentAudio?.audioUrl || currentProject.value.material,
  )
  if (hasExistingProjectOutput) {
    const confirmed = window.confirm('开始新的纯文案项目会清理当前素材预览、成片文案和配音结果。是否继续？')
    if (!confirmed) return
  }
  requestSeq.value += 1
  videoLink.value = ''
  uploadedFile.value = null
  uploadedFileName.value = ''
  currentNormalizedUrl.value = ''
  lastInputRaw.value = ''
  pendingUrls.value = []
  material.value = null
  materialId.value = ''
  resetCurrentProject({
    originalText: '',
    originalTextSource: 'manual',
    materialMode: 'manual',
    selectedVoiceId: selectedVoiceId.value,
    selectedVoiceType: selectedVoice.value?.type || '',
  })
  setProjectOriginalText('', 'manual')
  currentProject.value.materialMode = 'manual'
  clearCurrentScript()
  subtitleDownloads.value = {}
  transcriptionId.value = ''
  subtitleStatus.value = '未生成字幕'
  previewState.value = 'idle'
  previewTitle.value = '纯文案模式'
  renderProgress.value = 0
  currentStep.value = '纯文案模式'
  renderingMeta.value.sourceDuration = '--:--'
  renderingMeta.value.voiceDuration = '--:--'
  renderingMeta.value.finalDuration = '--:--'
  readStatus.value = '当前模式：手动文案'
  appError.value = ''
  startFreshStudioProject().catch((error) => {
    setGlobalErrorFromException(error, '创建新项目失败，请稍后重试。')
  })
}

const readMaterial = async ({ rawInput, extractedLinks, primaryLink, requestSeqSnapshot }) => {
  const projectId = await ensureStudioProjectId()
  appError.value = ''
  material.value = null
  materialId.value = ''
  setProjectMaterial(null)
  setProjectOriginalText('', 'empty')
  clearCurrentScript()
  subtitleDownloads.value = {}
  currentProject.value.subtitles = null
  transcriptionId.value = ''
  subtitleStatus.value = '读取素材'
  if (!extractedLinks.length) {
    readStatus.value = '未识别到有效视频链接'
    appError.value = '未识别到有效视频链接，请粘贴抖音/B站/TikTok分享链接，或上传本地视频。'
    return null
  }
  pendingUrls.value = extractedLinks.slice(1).map((item) => item.normalizedUrl)
  videoLink.value = primaryLink.normalizedUrl
  currentNormalizedUrl.value = primaryLink.normalizedUrl
  currentProject.value.materialMode = 'video_pending'
  const detectedSourceType = primaryLink.sourceType
  if (detectedSourceType === 'unknown') {
    readStatus.value = '当前平台可能暂不稳定'
  }
  isReading.value = true
  try {
    console.info('[StudioAlpha] POST /materials/extract', {
      url: primaryLink.normalizedUrl,
      sourceType: detectedSourceType,
    })
    const payload = await extractStudioMaterial(projectId, {
      sourceType: detectedSourceType,
      input: rawInput,
      url: primaryLink.normalizedUrl,
      urls: extractedLinks.map((item) => item.normalizedUrl),
    })
    if (!isCurrentRequest(requestSeqSnapshot)) return null
    const normalizedPayload = normalizeMaterial(payload)
    applyMaterial(normalizedPayload)
    lastInputRaw.value = rawInput
    return normalizedPayload
  } catch (error) {
    if (!isCurrentRequest(requestSeqSnapshot)) return null
    const errorType = error.data?.errorType
    const sourceType = error.data?.sourceType
    if (errorType === 'platform_not_authorized') {
      authHint.value = normalizeAuthErrorMessage(error)
      if (sourceType) {
        setAuthStatus(sourceType, { status: 'unauthorized', message: error.message })
      }
      readStatus.value = '请先完成授权'
      return null
    }
    const materialErrorMessage = normalizeMaterialReadErrorMessage(error)
    readStatus.value = materialErrorMessage
    appError.value = materialErrorMessage
    console.error(error)
    return null
  } finally {
    if (isCurrentRequest(requestSeqSnapshot)) {
      isReading.value = false
    }
  }
}

const formatDuration = (seconds) => {
  const total = Math.max(0, Math.round(Number(seconds || 0)))
  const minutes = String(Math.floor(total / 60)).padStart(2, '0')
  const remain = String(total % 60).padStart(2, '0')
  return `00:${minutes}:${remain}`
}

const extractCurrentMaterialScript = async (targetMaterial, requestSeqSnapshot) => {
  const projectId = await ensureStudioProjectId()
  const targetMaterialId = targetMaterial?.materialId || ''
  if (!targetMaterialId) {
    appError.value = '请先完成素材导入。'
    return
  }
  if (!isMaterialPayloadReady(targetMaterial)) {
    appError.value = '请先读取素材。'
    readStatus.value = '请先读取素材'
    return
  }
  transcriptionLoading.value = true
  subtitleStatus.value = '处理中'
  try {
    console.info('[StudioAlpha] POST /transcriptions', {
      materialId: targetMaterialId,
      sourceUrl: targetMaterial.normalizedUrl || targetMaterial.sourceUrl || '',
    })
    const task = await createStudioTranscription(projectId, {
      materialId: targetMaterialId,
      model: 'medium',
      language: 'zh',
      device: 'cpu',
      computeType: 'int8',
      beamSize: 5,
    })
    if (!isCurrentRequest(requestSeqSnapshot)) return
    transcriptionId.value = task.transcriptionId
    currentStep.value = task.stage || '文案提取'
    previewState.value = 'done'
    renderProgress.value = task.progress || 100
    subtitleStatus.value = '完成'
    const preferredText =
      task.finalText || task.transcript || task.text || task.asrText || ''
    if (preferredText) {
      setProjectOriginalText(preferredText, 'video_transcript')
      previewTitle.value = preferredText.slice(0, 24) || '已生成原始文案'
    }
    subtitleDownloads.value = task.subtitleFiles || {}
    currentProject.value.subtitles = {
      transcriptionId: task.transcriptionId,
      files: task.subtitleFiles || {},
      source: 'transcription',
    }
    renderingMeta.value.finalDuration = renderingMeta.value.sourceDuration
    readStatus.value = '视频文案提取完成'
    await fetchTasks()
  } catch (error) {
    if (!isCurrentRequest(requestSeqSnapshot)) return
    subtitleStatus.value = '失败'
    readStatus.value = normalizeUiErrorMessage(error, '视频文案提取失败')
    previewState.value = 'idle'
    setGlobalErrorFromException(error, '视频文案提取失败，请稍后重试。')
  } finally {
    if (isCurrentRequest(requestSeqSnapshot)) {
      transcriptionLoading.value = false
    }
  }
}

const extractScript = async () => {
  appError.value = ''
  const rawInput = videoLink.value.trim()
  const extractedLinks = extractVideoLinksFromInput(rawInput)

  if (!extractedLinks.length) {
    if (material.value?.sourceType === 'local' && currentMaterialLocalReady.value) {
      const requestSeqSnapshot = nextRequestSeq()
      await extractCurrentMaterialScript(material.value, requestSeqSnapshot)
      return
    }
    readStatus.value = '未识别到有效视频链接'
    appError.value = '未识别到有效视频链接，请粘贴抖音/B站/TikTok分享链接，或上传本地视频。'
    return
  }

  const primaryLink = extractedLinks[0]
  const normalizedUrl = primaryLink.normalizedUrl
  const activeUrl = activeMaterialUrl.value
  const shouldReadMaterial = !currentMaterialLocalReady.value || normalizedUrl !== activeUrl
  const requestSeqSnapshot = nextRequestSeq()
  currentNormalizedUrl.value = normalizedUrl
  videoLink.value = normalizedUrl

  console.info('[StudioAlpha] extract:start', {
    rawInput,
    normalizedUrl,
    activeMaterialUrl: activeUrl,
    isInputDirty: shouldReadMaterial,
  })

  let payload = material.value
  if (shouldReadMaterial) {
    subtitleStatus.value = '读取素材'
    payload = await readMaterial({
      rawInput,
      extractedLinks,
      primaryLink,
      requestSeqSnapshot,
    })
  }

  if (!isCurrentRequest(requestSeqSnapshot)) return
  if (!payload || !isMaterialPayloadReady(payload)) {
    return
  }
  await extractCurrentMaterialScript(payload, requestSeqSnapshot)
}

const appendPromptTemplate = (template) => {
  const templateInstructions = {
    爆款开头: '强化开头 3 秒钩子，先抛出具体痛点或反差，让用户愿意继续听。',
    普通人分享: '把这段文案改成普通人真实分享口吻，表达自然，不要太像广告。',
    知识讲解: '把这段文案改成知识博主讲解风格，逻辑清楚，观点明确，适合口播。',
    小红书种草: '把这段文案改成小红书种草风格，真实、有体验感，不要过度营销。',
    私域引流: '把这段文案改成自然引导私域的口播风格，克制表达，不要硬广。',
    老板口播: '把这段文案改成老板本人出镜口播风格，表达直接，有观点，不要太像广告。',
    课程转化: '把这段文案改成课程转化口播风格，突出价值和行动理由，不夸大承诺。',
    避坑提醒: '把这段文案改成避坑提醒口播风格，先点出误区，再给出清晰建议。',
  }
  selectedRewriteTemplate.value = template
  promptText.value = templateInstructions[template] || template
  rewriteFailed.value = false
}

const loadAiStatus = async () => {
  try {
    aiStatus.value = await getAiStatus()
  } catch (error) {
    aiStatus.value = {
      available: false,
      provider: null,
      model: null,
      message: 'AI 改写服务状态获取失败，请检查后端服务。',
    }
    console.error(error)
  }
}

const loadVoices = async () => {
  voiceLibraryLoading.value = true
  try {
    const payload = await listVoiceProfiles()
    const nextVoices = Array.isArray(payload?.voices) ? payload.voices : []
    const voicesById = new Map()
    nextVoices.forEach((voice) => {
      const voiceId = String(voice?.voiceId || '').trim()
      const voiceName = String(voice?.name || '').trim()
      if (
        !voiceId ||
        voice.type === 'builtin' ||
        legacyVoiceNames.has(voiceName) ||
        !isCosyVoiceSynthesisReady(voice) ||
        voicesById.has(voiceId)
      ) {
        return
      }
      voicesById.set(voiceId, {
        ...voice,
        voiceId,
        engine: voice.engine || 'cosyvoice',
        source: voice.source || '',
      })
    })
    voices.value = [...voicesById.values()]
    if (!voices.value.some((voice) => voice.voiceId === selectedVoiceId.value)) {
      selectedVoiceId.value = voices.value[0]?.voiceId || ''
    }
    voiceLibraryMessage.value = ''
  } catch (error) {
    voices.value = []
    selectedVoiceId.value = ''
    voiceLibraryMessage.value = normalizeUiErrorMessage(error, '音色库读取失败，请稍后重试。')
    console.error(error)
  } finally {
    voiceLibraryLoading.value = false
  }
}

const runRewrite = async (options = {}) => {
  const projectId = await ensureStudioProjectId()
  if (!aiRewriteAvailable.value) {
    appError.value = aiUnavailableMessage.value
    return
  }
  const sourceText = currentProject.value.originalText.trim()
  const sourceTextType = currentProject.value.originalTextSource
  if (!sourceText) {
    appError.value = '请先提取或输入文案结果。'
    return
  }
  const allowPlatformText = Boolean(options.allowPlatformText)
  if (!sourceTextReadyForRewrite.value && !(sourceTextType === 'platform_description' && allowPlatformText)) {
    appError.value = rewriteUnavailableMessage.value
    return
  }
  isRewriting.value = true
  appError.value = ''
  try {
    const payload = await rewriteStudioCopy(projectId, {
      sourceText,
      sourceTextType,
      allowPlatformText,
      instruction: promptText.value,
      template: selectedRewriteTemplate.value,
    })
    const versions = Array.isArray(payload?.versions) ? payload.versions : []
    rewriteResults.value = versions
      .map((item, index) => ({
        id: String(item?.id || String.fromCharCode(65 + index)).trim(),
        title: String(item?.title || `版本 ${String.fromCharCode(65 + index)}`).trim(),
        text: String(item?.text || '').trim(),
        reason: String(item?.reason || '已改写为更自然的口播表达。').trim(),
      }))
      .filter((item) => item.id && item.text)
    currentProject.value.rewriteVersions = rewriteResults.value
    currentProject.value.selectedRewriteVersionId = null
    activeResultId.value = rewriteResults.value[0]?.id || ''
    rewriteFailed.value = false
    if (!rewriteResults.value.length) {
      appError.value = 'AI 改写服务未返回可用文案。'
      rewriteFailed.value = true
    }
  } catch (error) {
    if (error.data?.errorType === 'llm_not_configured') {
      aiStatus.value = {
        available: false,
        provider: null,
        model: null,
        message: 'AI 改写服务未配置，请先配置模型服务。',
      }
    }
    rewriteFailed.value = true
    setGlobalErrorFromException(error, 'AI 改写失败，请检查模型服务配置。')
  } finally {
    isRewriting.value = false
  }
}

const useRewriteResult = (id) => {
  const result = rewriteResults.value.find((item) => item.id === id)
  if (!result?.text) return
  setProjectCurrentScript({
    text: result.text,
    source: 'rewrite_version',
    title: result.title || `版本 ${id}`,
    activeResult: id,
  })
}

const setTextResultAsCurrentScript = () => {
  const text = currentProject.value.originalText.trim()
  const source = currentProject.value.originalTextSource
  if (!text || !['video_transcript', 'manual'].includes(source)) {
    appError.value = '请先提取视频口播，或手动输入一段成片文案。'
    return
  }
  setProjectCurrentScript({
    text,
    source,
    title: source === 'video_transcript' ? '视频口播文案' : '手动输入文案',
  })
}

const optimizeRewriteResult = (id) => {
  const result = rewriteResults.value.find((item) => item.id === id)
  if (!result?.text) return
  activeResultId.value = id
  promptText.value = `${promptText.value.trim()}；继续优化 ${result.title}，让表达更自然、更像真实口播。`
}

const copyRewriteResult = async (content) => {
  if (!content) return
  try {
    await navigator.clipboard.writeText(content)
  } catch {
    appError.value = '复制失败，请手动选择文案复制。'
  }
}

const rewriteWithPlatformText = async () => {
  const confirmed = window.confirm('当前内容只是平台发布文案，不是视频口播。继续改写可能不完整，是否继续？')
  if (!confirmed) return
  await runRewrite({ allowPlatformText: true })
}

const openVoiceCreateDialog = () => {
  voiceCreateDialogVisible.value = true
  voiceCreateError.value = ''
  if (!voiceCreateName.value.trim()) voiceCreateName.value = '我的音色'
}

const closeVoiceCreateDialog = () => {
  if (voiceCreateLoading.value) return
  voiceCreateDialogVisible.value = false
  voiceCreateError.value = ''
}

const handleVoiceCreateAudioSelected = (event) => {
  const [file] = event.target.files || []
  if (!file) return
  voiceCreateAudioFile.value = file
  voiceCreateAudioName.value = file.name
  voiceCreateError.value = ''
  event.target.value = ''
}

const createCustomVoice = async () => {
  if (!voiceCreateAudioFile.value) {
    voiceCreateError.value = '请先上传一段自己的清晰人声。'
    return
  }
  if (!voiceCreateConsent.value) {
    voiceCreateError.value = '请先确认该声音属于本人或已获得授权。'
    return
  }
  voiceCreateLoading.value = true
  voiceCreateError.value = ''
  trainingStatus.value = '音色创建中'
  try {
    const formData = new FormData()
    formData.append('name', voiceCreateName.value.trim() || '我的音色')
    formData.append('audio', voiceCreateAudioFile.value)
    formData.append('consent', String(voiceCreateConsent.value))
    const created = await createVoiceProfile(formData)
    await loadVoices()
    selectedVoiceId.value = created.voiceId
    trainingStatus.value = '音色创建成功'
    voiceCreateDialogVisible.value = false
    voiceCreateName.value = '我的音色'
    voiceCreateAudioFile.value = null
    voiceCreateAudioName.value = ''
    voiceCreateConsent.value = false
  } catch (error) {
    const message = normalizeUiErrorMessage(error, '音色创建失败，请重新上传清晰人声。')
    voiceCreateError.value = message
    trainingStatus.value = message
    console.error(error)
  } finally {
    voiceCreateLoading.value = false
  }
}

const createVoiceFromCurrentMaterial = async () => {
  if (creatingVoiceFromMaterial.value) return
  if (!currentMaterialLocalReady.value || !materialId.value) {
    appError.value = '请先读取并准备好视频素材。'
    return
  }
  if (currentMaterialVoice.value && currentMaterialVoiceIsClean.value) {
    selectedVoiceId.value = currentMaterialVoice.value.voiceId
    trainingStatus.value = '已选择视频参考音频'
    return
  }
  const confirmed = window.confirm('请确认该视频中的声音属于本人或已获得授权，仅用于合法内容创作。是否继续创建音色？')
  if (!confirmed) return
  creatingVoiceFromMaterial.value = true
  trainingStatus.value = '正在提取当前视频音色'
  try {
    const created = await createVoiceFromMaterial({
      materialId: materialId.value,
      name: '当前视频音色',
      consent: true,
      force: false,
    })
    await loadVoices()
    selectedVoiceId.value = created.voiceId
    trainingStatus.value = created.reused ? '已选择视频参考音频' : '参考音频已提取，请先试听'
  } catch (error) {
    const message = normalizeUiErrorMessage(error, '当前视频音色提取失败，请上传单独音频。')
    trainingStatus.value = message
    setGlobalErrorFromException(error, '当前视频音色提取失败，请上传单独音频。')
  } finally {
    creatingVoiceFromMaterial.value = false
  }
}

const generateVoice = async () => {
  const projectId = await ensureStudioProjectId()
  const displayedScriptText = currentProject.value.currentScript || ''
  const scriptText = activeTtsText.value
  if (!scriptText.trim()) {
    appError.value = '请先选择一版成片文案，或将手动文案设为成片文案。'
    return
  }
  if (!selectedVoiceId.value) {
    appError.value = '请先选择一个 TTS 声音。'
    return
  }
  voiceGenerating.value = true
  voiceStatus.value = '配音任务创建中'
  currentProject.value.currentAudio = null
  clearProjectDigitalHumanOutput()
  synthesisAudioUrl.value = ''
  try {
    const requestPayload = {
      text: scriptText,
      voiceId: selectedVoiceId.value,
      speed: voiceSpeed.value,
      emotion: selectedEmotion.value,
      volume: voiceVolume.value,
      language: 'zh',
      executionProvider: 'cpu',
    }
    if (import.meta.env.DEV) {
      console.info('[StudioAlpha] tts_synthesis', {
        action: 'tts_synthesis',
        displayedCurrentScript: displayedScriptText,
        displayedCurrentScriptLength: displayedScriptText.length,
        payloadText: requestPayload.text,
        payloadTextLength: requestPayload.text.length,
        payloadTextEqualsDisplayedCurrentScript: requestPayload.text === displayedScriptText,
        payloadVoiceId: requestPayload.voiceId,
        selectedVoiceId: selectedVoiceId.value,
        selectedRewriteVersionId: currentProject.value.selectedRewriteVersionId,
        materialMode: currentProject.value.materialMode,
        originalTextSource: currentProject.value.originalTextSource,
        currentScriptSource: currentProject.value.currentScriptSource,
        currentScriptTitle: currentScriptTitle.value || '未命名成片文案',
        currentScriptLength: scriptText.length,
        textPreview: scriptText.slice(0, 60),
        selectedVoiceType: selectedVoice.value?.type || 'unknown',
      })
    }
    const synthesis = await createStudioSynthesis(projectId, requestPayload)
    synthesisId.value = synthesis.synthesisId
    voiceStatus.value = synthesis.message || '配音任务已创建'
    await fetchTasks()
    synthesisPollTimer = window.setInterval(async () => {
      try {
        const latest = await getStudioSynthesis(projectId, synthesis.synthesisId)
        voiceStatus.value = latest.message || latest.status
        if (latest.audioUrl) {
          synthesisAudioUrl.value = apiUrl(latest.audioUrl)
          setProjectCurrentAudio({
            ...latest,
            synthesisId: synthesis.synthesisId,
            audioUrl: latest.audioUrl,
          })
          renderingMeta.value.voiceDuration = renderingMeta.value.sourceDuration
        }
        if (latest.status === 'success') {
          voiceGenerating.value = false
          window.clearInterval(synthesisPollTimer)
          synthesisPollTimer = null
        }
        if (latest.status === 'failed') {
          const message = ttsErrorMessage(latest)
          voiceStatus.value = message
          appError.value = message
          voiceGenerating.value = false
          window.clearInterval(synthesisPollTimer)
          synthesisPollTimer = null
        }
      } catch (error) {
        const message = ttsErrorMessage(error, '语音合成状态获取失败，请稍后重试。')
        appError.value = message
        console.error(error)
      }
    }, 2000)
  } catch (error) {
    const message = ttsErrorMessage(error)
    voiceStatus.value = message
    appError.value = message
    console.error(error)
    voiceGenerating.value = false
  }
}

const openDigitalHumanManager = () => {
  activeNav.value = 'human'
  currentView.value = 'digitalHuman'
}

const handleSelectDigitalHumanPerson = (person) => {
  selectedDigitalHumanPerson.value = person || null
  currentProject.value.selectedAvatarName = person?.name || person?.templateId || ''
  if (!currentProject.value.digitalHumanVideo) {
    humanStatus.value = person?.templateId ? `已选择 ${person.name || person.templateId}` : '未选择数字人'
  }
}

const stopDigitalHumanPolling = () => {
  if (digitalHumanPollTimer) {
    window.clearInterval(digitalHumanPollTimer)
    digitalHumanPollTimer = null
  }
}

const normalizeProjectVideoUrl = (value) => {
  const raw = String(value || '').trim()
  if (!raw) return ''
  return raw.startsWith('http://') || raw.startsWith('https://') ? raw : apiUrl(raw)
}

const applyDigitalHumanTaskResult = async (projectId, task) => {
  if (task?.status === 'success') humanStatus.value = '数字人视频已生成'
  else if (task?.status === 'failed') humanStatus.value = task?.errorMessage || '数字人视频生成失败'
  else humanStatus.value = '数字人任务处理中'
  const localVideoUrl = normalizeProjectVideoUrl(task?.videoUrl)
  if (localVideoUrl) {
    const projectSnapshot = await getStudioProject(projectId)
    currentProject.value.projectId = projectSnapshot.projectId || currentProject.value.projectId
    currentProject.value.digitalHumanVideo = {
      taskId: task.taskId,
      videoUrl: localVideoUrl,
      remoteVideoUrl: '',
      localOutputPath: '',
      previewUrl: task.coverUrl || '',
      personId: task.templateId || selectedDigitalHumanPerson.value?.templateId || '',
      status: task.status || 'success',
    }
    studioDigitalHumanOutputPath.value = task.downloads?.video || ''
    currentProject.value.previewVideo = {
      type: 'digital_human',
      url: localVideoUrl,
      title: currentProject.value.currentScriptTitle || '数字人口播',
    }
  }
}

const generateStudioDigitalHumanFromCurrentAudio = async () => {
  const projectId = await ensureStudioProjectId()
  const currentAudio = currentProject.value.currentAudio
  const person = selectedDigitalHumanPerson.value
  if (!currentAudio?.audioUrl) {
    humanStatus.value = '缺少配音'
    appError.value = '请先生成配音。'
    return
  }
  if (!person?.templateId) {
    humanStatus.value = '未选择数字人'
    appError.value = '请先选择数字人。'
    return
  }

  humanGenerating.value = true
  humanStatus.value = '数字人任务创建中'
  appError.value = ''
  clearProjectDigitalHumanOutput()
  stopDigitalHumanPolling()

  try {
    const task = await generateDigitalHumanVideo({
      templateId: person.templateId,
      script: currentProject.value.currentScript || '',
      audioTaskId: currentAudio.audioId || currentAudio.synthesisId || '',
      audioUrl: currentAudio.audioUrl,
      workflowId: projectId,
      projectId,
      mode: 'auto',
    })
    await fetchTasks()
    await applyDigitalHumanTaskResult(projectId, task)
    const taskId = task?.taskId
    if (!taskId) {
      humanGenerating.value = false
      return
    }
    digitalHumanPollTimer = window.setInterval(async () => {
      try {
        const latest = await getDigitalHumanTask(taskId)
        await applyDigitalHumanTaskResult(projectId, latest)
        if (latest?.status === 'success' || latest?.status === 'failed') {
          humanGenerating.value = false
          stopDigitalHumanPolling()
        }
      } catch (error) {
        humanStatus.value = normalizeUiErrorMessage(error, '数字人任务状态获取失败。')
        appError.value = humanStatus.value
        humanGenerating.value = false
        stopDigitalHumanPolling()
      }
    }, 5000)
  } catch (error) {
    humanStatus.value = normalizeUiErrorMessage(error, '数字人任务创建失败。')
    appError.value = humanStatus.value
    humanGenerating.value = false
  }
}

const previewVoice = async () => {
  previewingVoice.value = true
  voiceStatus.value = '试听生成中'
  try {
    const preview = await createVoicePreview(selectedVoiceId.value, {
      text: '你好，这是当前音色的一段试听。',
    })
    voicePreviewAudioUrl.value = apiUrl(preview.audioUrl)
    voiceStatus.value = '试听已生成'
  } catch (error) {
    voiceStatus.value = normalizeUiErrorMessage(error, '试听生成失败，请检查 TTS 引擎配置。')
    setGlobalErrorFromException(error, '试听生成失败，请检查 TTS 引擎配置。')
  } finally {
    previewingVoice.value = false
  }
}

const handleSidebarSelect = (navId) => {
  activeNav.value = navId
  if (navId === 'voice') {
    currentView.value = 'voices'
    loadVoices()
    return
  }
  if (navId === 'human') {
    currentView.value = 'digitalHuman'
    return
  }
  currentView.value = 'workbench'
}

const returnToWorkbench = () => {
  currentView.value = 'workbench'
  activeNav.value = 'home'
}

const voiceLibraryErrorMessage = (error, fallback) => {
  const errorType = String(error?.data?.errorType || '')
  if (errorType === 'cosyvoice_not_ready') {
    return 'CosyVoice 未就绪，请先完成模型配置后再试听。'
  }
  if (errorType === 'builtin_voice_readonly') {
    return '内置音色不可修改或删除。'
  }
  if (errorType === 'voice_not_found') {
    return '音色不存在或已被删除。'
  }
  return normalizeUiErrorMessage(error, fallback)
}

const useVoiceFromLibrary = (voice) => {
  if (!voice?.voiceId) return
  selectedVoiceId.value = voice.voiceId
  currentProject.value.selectedVoiceId = voice.voiceId
  currentProject.value.selectedVoiceType = voice.type || ''
  voiceStatus.value = `已选择 ${voice.name || voice.voiceId}`
  voiceLibraryMessage.value = `已选择 ${voice.name || voice.voiceId}`
  returnToWorkbench()
}

const renameVoiceFromLibrary = async ({ voiceId, name }) => {
  if (!voiceId || !name) return
  voiceLibraryBusyId.value = voiceId
  voiceLibraryMessage.value = '正在修改音色名称...'
  try {
    await updateVoiceProfile(voiceId, { name })
    await loadVoices()
    voiceLibraryMessage.value = '音色名称已更新。'
  } catch (error) {
    voiceLibraryMessage.value = voiceLibraryErrorMessage(error, '音色名称修改失败，请稍后重试。')
    console.error(error)
  } finally {
    voiceLibraryBusyId.value = ''
  }
}

const deleteVoiceFromLibrary = async (voice) => {
  if (!voice?.voiceId || voice.type === 'builtin') return
  const confirmed = window.confirm(`确认删除音色「${voice.name || voice.voiceId}」？`)
  if (!confirmed) return
  voiceLibraryBusyId.value = voice.voiceId
  voiceLibraryMessage.value = '正在删除音色...'
  try {
    await deleteVoiceProfile(voice.voiceId)
    if (selectedVoiceId.value === voice.voiceId) {
      selectedVoiceId.value = ''
      currentProject.value.selectedVoiceId = ''
      currentProject.value.selectedVoiceType = ''
    }
    await loadVoices()
    voiceLibraryMessage.value = '音色已删除。'
  } catch (error) {
    voiceLibraryMessage.value = voiceLibraryErrorMessage(error, '音色删除失败，请稍后重试。')
    console.error(error)
  } finally {
    voiceLibraryBusyId.value = ''
  }
}

const previewVoiceFromLibrary = async (voice) => {
  if (!voice?.voiceId) return
  voiceLibraryBusyId.value = voice.voiceId
  voiceLibraryPreviewVoiceId.value = voice.voiceId
  voiceLibraryPreviewAudioUrl.value = ''
  voiceLibraryMessage.value = '正在生成试听...'
  try {
    const preview = await createVoicePreview(voice.voiceId, {
      text: '你好，这是当前音色的一段试听。',
    })
    voiceLibraryPreviewAudioUrl.value = preview.audioUrl || ''
    voiceLibraryMessage.value = '试听已生成。'
  } catch (error) {
    voiceLibraryMessage.value = voiceLibraryErrorMessage(error, '音色试听失败，请检查 CosyVoice 配置。')
    console.error(error)
  } finally {
    voiceLibraryBusyId.value = ''
  }
}

onMounted(() => {
  loadAiStatus()
  loadVoices()
  startTaskPolling()
  loadAllAuthStatuses()
  createStudioProject({ name: 'Studio 项目' })
    .then((project) => {
      currentProject.value.projectId = project.projectId
    })
    .catch(() => {
      // ignore bootstrap failure here, later actions will retry
    })
})

onBeforeUnmount(() => {
  stopTaskPolling()
  if (trainingPollTimer) window.clearInterval(trainingPollTimer)
  if (synthesisPollTimer) window.clearInterval(synthesisPollTimer)
  stopDigitalHumanPolling()
  stopAuthPolling('douyin')
  stopAuthPolling('bilibili')
})
</script>

<template>
  <div class="studio-shell">
    <StudioSidebar :items="navigationItems" :active-id="activeNav" @select="handleSidebarSelect" />

    <div class="studio-main">
      <StudioTopbar
        :service-status="serviceStatus"
        :model-status="modelStatus"
        :output-path="outputPath"
      />

      <main class="studio-workbench">
        <p v-if="appError" class="app-banner">{{ appError }}</p>

        <VoiceLibraryView
          v-if="currentView === 'voices'"
          :voices="voices"
          :loading="voiceLibraryLoading"
          :busy-voice-id="voiceLibraryBusyId"
          :selected-voice-id="selectedVoiceId"
          :preview-audio-url="voiceLibraryPreviewAudioUrl"
          :preview-voice-id="voiceLibraryPreviewVoiceId"
          :message="voiceLibraryMessage"
          @return-workbench="returnToWorkbench"
          @refresh="loadVoices"
          @use-voice="useVoiceFromLibrary"
          @rename-voice="renameVoiceFromLibrary"
          @delete-voice="deleteVoiceFromLibrary"
          @preview-voice="previewVoiceFromLibrary"
        />

        <ChanjingDigitalHumanManager
          v-else-if="currentView === 'digitalHuman'"
          :selected-person="selectedDigitalHumanPerson"
          :current-audio="currentProject.currentAudio"
          :current-script="currentProject.currentScript"
          :current-script-title="currentProject.currentScriptTitle"
          @return-workbench="returnToWorkbench"
          @select-person="handleSelectDigitalHumanPerson"
        />

        <template v-else>
        <div class="workbench-grid">
          <MaterialScriptPanel
            :video-link="videoLink"
            :raw-script="rawScript"
            :read-status="readStatus"
            :uploaded-file-name="uploadedFileName"
            :material="material"
            :is-reading="isReading"
            :transcription-loading="transcriptionLoading"
            :subtitle-status="subtitleStatus"
            :material-lamp="materialLamp"
            :material-lamp-text="materialLampText"
            :input-dirty="isInputDirty"
            :auth-statuses="authStatuses"
            :auth-hint="authHint"
            :script-source-label="scriptSourceLabel"
            :is-manual-text-mode="isManualTextMode"
            :can-set-as-current-script="canSetTextResultAsCurrent"
            @file-selected="handleFileSelected"
            @manual-input="handleManualInput"
            @set-current-script="setTextResultAsCurrentScript"
            @extract-script="extractScript"
            @start-auth="handleStartAuth"
            @clear-auth="handleClearAuth"
            @update:video-link="handleVideoLinkInput"
            @update:raw-script="handleRawScriptInput"
          />

          <PromptRewritePanel
            v-model:prompt-text="promptText"
            :templates="promptTemplates"
            :rewrite-results="rewriteResults"
            :active-result-id="activeResultId"
            :is-rewriting="isRewriting"
            :rewrite-failed="rewriteFailed"
            :feature-ready="canRewrite"
            :unavailable-message="rewriteUnavailableMessage"
            :source-usage-text="rewriteSourceUsageText"
            :can-use-platform-text="canUsePlatformTextForRewrite"
            :can-use-current-text="canSetTextResultAsCurrent"
            @append-template="appendPromptTemplate"
            @rewrite="runRewrite"
            @rewrite-platform="rewriteWithPlatformText"
            @use-current-text="setTextResultAsCurrentScript"
            @use-result="useRewriteResult"
            @optimize-result="optimizeRewriteResult"
            @copy-result="copyRewriteResult"
          />

          <VoiceHumanPanel
            v-model:selected-voice-id="selectedVoiceId"
            v-model:selected-emotion="selectedEmotion"
            v-model:speed="voiceSpeed"
            v-model:volume="voiceVolume"
            v-model:selected-avatar-id="selectedAvatarId"
            v-model:selected-scene="selectedScene"
            v-model:selected-background="selectedBackground"
            :voices="voices"
            :emotions="emotionOptions"
            :avatars="avatarOptions"
            :scene-options="sceneOptions"
            :background-options="backgroundOptions"
            :previewing-voice="previewingVoice"
            :voice-generating="voiceGenerating"
            :human-generating="humanGenerating"
            :voice-status="voiceStatus"
            :human-status="studioDigitalHumanStatus"
            :training-status="trainingStatus"
            :can-create-voice-from-material="currentMaterialLocalReady"
            :creating-voice-from-material="creatingVoiceFromMaterial"
            :has-current-material-voice="hasCurrentMaterialVoice"
            :synthesis-audio-url="synthesisAudioUrl"
            :voice-preview-audio-url="voicePreviewAudioUrl"
            :voice-reference-audio-url="selectedVoiceReferenceAudioUrl"
            :voice-quality-warnings="selectedVoiceQualityWarnings"
            :voice-create-dialog-visible="voiceCreateDialogVisible"
            :voice-create-loading="voiceCreateLoading"
            :voice-create-name="voiceCreateName"
            :voice-create-audio-name="voiceCreateAudioName"
            :voice-create-consent="voiceCreateConsent"
            :voice-create-error="voiceCreateError"
            :current-script="currentProject.currentScript"
            :current-script-source="currentProject.currentScriptSource"
            :current-script-title="currentProject.currentScriptTitle"
            :current-audio="currentProject.currentAudio"
            :can-generate-human-video="canGenerateStudioDigitalHuman"
            :human-generate-hint="studioDigitalHumanHint"
            :selected-digital-human-person="selectedDigitalHumanPerson"
            :studio-digital-human-output-path="studioDigitalHumanOutputPath"
            :can-generate-studio-digital-human="canGenerateStudioDigitalHuman"
            :studio-digital-human-backend-ready="studioDigitalHumanBackendReady"
            :studio-digital-human-missing-capability-hint="studioDigitalHumanMissingCapabilityHint"
            @preview-voice="previewVoice"
            @generate-voice="generateVoice"
            @open-digital-human-manager="openDigitalHumanManager"
            @generate-studio-digital-human="generateStudioDigitalHumanFromCurrentAudio"
            @open-voice-create="openVoiceCreateDialog"
            @create-voice-from-material="createVoiceFromCurrentMaterial"
            @close-voice-create="closeVoiceCreateDialog"
            @voice-create-audio-selected="handleVoiceCreateAudioSelected"
            @create-voice="createCustomVoice"
            @update:voice-create-name="voiceCreateName = $event"
            @update:voice-create-consent="voiceCreateConsent = $event"
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
            :script-ready="projectStepStatus.scriptReady"
            :audio-ready="projectStepStatus.audioReady"
            :current-script="currentProject.currentScript"
            :current-audio="currentProject.currentAudio"
          />

          <VideoPreviewPanel
            :material="currentProject.material"
            :read-status="readStatus"
            :material-lamp="materialLamp"
            :material-lamp-text="materialLampText"
            :material-local-ready="currentMaterialLocalReady"
            :is-manual-text-mode="isManualTextMode"
            :current-script="currentProject.currentScript"
            :current-script-title="currentProject.currentScriptTitle"
            :current-audio="currentProject.currentAudio"
            :selected-avatar="selectedAvatar"
            :project-step-status="projectStepStatus"
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
        </template>
      </main>
    </div>
  </div>
</template>
