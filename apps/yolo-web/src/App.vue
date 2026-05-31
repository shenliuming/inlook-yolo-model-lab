<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const appBase = import.meta.env.BASE_URL || '/'
const withBase = (path) => `${appBase}${String(path || '').replace(/^\/+/, '')}`
const internalApiKey = import.meta.env.VITE_INTERNAL_API_KEY || ''
const MAX_IMAGE_FILE_BYTES = 10 * 1024 * 1024
const siteLinks = [
  {
    id: 'home',
    label: '返回首页',
    href: 'https://in-look.cn/',
  },
  {
    id: 'about',
    label: '关于我',
    href: 'https://in-look.cn/about.html',
  },
]

const apiHeaders = () => {
  if (!internalApiKey) return {}
  return {
    'X-INLOOK-Key': internalApiKey,
  }
}

const detectionTypes = [
  {
    id: 'image',
    label: '图片识别',
    uploadTitle: '上传 JPG / PNG',
    uploadHint: '上传图片后开始识别',
    accept: 'image/jpeg,image/png,image/*',
  },
  {
    id: 'camera',
    label: '摄像头识别',
    uploadTitle: '打开摄像头',
    uploadHint: '视频和摄像头识别会比图片慢一点',
    accept: '',
  },
]

const cameraProfiles = {
  demo: {
    id: 'demo',
    label: '演示模式',
    captureWidth: 512,
    imgsz: 448,
    minIntervalMs: 220,
    targetIntervalMs: 760,
    jpegQuality: 0.78,
    idealWidth: 960,
    idealHeight: 540,
    hint: '录视频更稳',
  },
  live: {
    id: 'live',
    label: '极速模式',
    captureWidth: 640,
    imgsz: 512,
    minIntervalMs: 120,
    targetIntervalMs: 420,
    jpegQuality: 0.82,
    idealWidth: 1280,
    idealHeight: 720,
    hint: '更新更快',
  },
}

const isMobileViewport = ref(false)
const currentType = ref('image')
const currentModelId = ref('')
const models = ref([])
const health = ref({
  status: 'loading',
  device: '检测中',
  message: '正在连接后端',
})
const status = ref('待开始')
const logs = ref(['[INFO] 正在连接后端'])
const reportData = ref(null)
const resultUrl = ref('')
const reportUrl = ref('')
const selectedFile = ref(null)
const selectedFileName = ref('')
const originalPreviewUrl = ref('')
const isRunning = ref(false)
const errorMessage = ref('')
const fileInput = ref(null)

const videoRef = ref(null)
const overlayCanvasRef = ref(null)
const captureCanvasRef = ref(null)
const cameraStream = ref(null)
const videoInputDevices = ref([])
const selectedVideoDeviceId = ref('')
const cameraReady = ref(false)
const cameraRecognizing = ref(false)
const cameraFacingMode = ref('user')
const cameraProfileId = ref('live')
const cameraAspect = ref('4 / 3')
const recentRealtimeResult = ref(null)
const recentRealtimeBoxes = ref([])
let realtimeLoopTimer = null

const syncViewportState = () => {
  isMobileViewport.value = window.innerWidth <= 720
}

const syncDefaultFacingMode = () => {
  cameraFacingMode.value = 'environment'
}

const isObsLikeVideoSource = (label = '') => /obs|virtual|虚拟摄像头|虚拟/.test(String(label).toLowerCase())

const normalizeVideoInputDevices = (devices) => {
  const normalized = devices.map((device, index) => {
    const rawLabel = String(device.label || '').trim()
    const isObsLike = isObsLikeVideoSource(rawLabel)
    return {
      id: device.deviceId,
      rawLabel,
      isObsLike,
      label: isObsLike ? 'OBS 虚拟摄像头' : (rawLabel || `普通摄像头 ${index + 1}`),
    }
  })

  return normalized.sort((left, right) => Number(right.isObsLike) - Number(left.isObsLike))
}

const currentTypeConfig = computed(() =>
  detectionTypes.find((item) => item.id === currentType.value) ?? detectionTypes[0],
)

const displayedDetectionTypes = computed(() => {
  if (!isMobileViewport.value) return detectionTypes
  return [
    detectionTypes.find((item) => item.id === 'camera'),
    detectionTypes.find((item) => item.id === 'image'),
  ].filter(Boolean)
})

const selectedVideoSource = computed(() =>
  videoInputDevices.value.find((device) => device.id === selectedVideoDeviceId.value) ?? null,
)

const preferredInlookModel = computed(() =>
  models.value.find((item) => item.id === 'inlook/best.pt')
  ?? models.value.find((item) => item.type === 'inlook')
  ?? null,
)

const preferredOfficialModelIdByType = {
  image: ['official/yolo26s.pt', 'official/yolo11s.pt', 'official/yolo26n.pt', 'official/yolo11n.pt'],
  camera: ['official/yolo26n.pt', 'official/yolo11n.pt', 'official/yolo26s.pt', 'official/yolo11s.pt'],
}

const pickPreferredOfficialModel = (typeId = currentType.value) => {
  const officialCandidates = models.value.filter((item) => item.type === 'official')
  const preferredIds = preferredOfficialModelIdByType[typeId] || preferredOfficialModelIdByType.image
  return (
    preferredIds.map((id) => officialCandidates.find((item) => item.id === id)).find(Boolean)
    || officialCandidates[0]
    || null
  )
}

const isScannerMode = computed(() =>
  isMobileViewport.value && currentType.value === 'camera',
)

const currentCameraProfile = computed(() =>
  cameraProfiles[cameraProfileId.value] ?? cameraProfiles.live,
)

const simplifiedModels = computed(() => {
  const official = pickPreferredOfficialModel()
  const inlook = preferredInlookModel.value

  return [
    official && {
      ...official,
      title: '官方通用模型',
      caption: official.version || 'YOLO 官方模型',
    },
    inlook && {
      ...inlook,
      title: 'INLOOK 三角洲模型',
      caption: inlook.version || 'best.pt',
    },
  ].filter(Boolean)
})

const officialPrimaryModel = computed(() =>
  simplifiedModels.value.find((item) => item.id === pickPreferredOfficialModel()?.id)
  ?? simplifiedModels.value.find((item) => item.type === 'official')
  ?? null,
)

const inlookSecondaryModel = computed(() =>
  simplifiedModels.value.find((item) => item.type === 'inlook') ?? null,
)

const preferredPrimaryModel = computed(() => {
  if (isMobileViewport.value && currentType.value === 'camera') {
    return inlookSecondaryModel.value ?? officialPrimaryModel.value ?? null
  }
  return officialPrimaryModel.value ?? inlookSecondaryModel.value ?? null
})

const currentModel = computed(() =>
  simplifiedModels.value.find((item) => item.id === currentModelId.value) ?? {
    id: '',
    title: '暂无模型',
    caption: '请启动后端并确认模型文件存在',
  },
)

const currentModeDescription = computed(() => {
  if (currentType.value === 'image') {
    return {
      title: '图片识别',
      description: '上传单张图片，快速查看目标框、日志和报告，适合先试模型效果。',
      hint: '适合快速测试',
    }
  }
  return {
    title: '摄像头识别',
    description: isMobileViewport.value
      ? '打开摄像头后自动开始识别，手机端默认使用 INLOOK 自研模型，更像扫一扫，适合直接演示。'
      : '打开手机或电脑摄像头，每秒约识别 1 帧，默认切轻量模型，稳定查看实时框选结果。',
    hint: isMobileViewport.value ? `${currentCameraProfile.value.label} · 默认 INLOOK 模型` : '支持前后摄切换',
  }
})

const currentDeviceLabel = computed(() => {
  const device = String(health.value.device || '').toLowerCase()
  if (device === 'cuda') return 'CUDA'
  if (device === 'cpu') return 'CPU'
  return health.value.device
})

const canRun = computed(() =>
  currentType.value === 'camera'
    ? Boolean(cameraReady.value && currentModelId.value && !cameraRecognizing.value)
    : Boolean(selectedFile.value) && Boolean(currentModelId.value) && !isRunning.value,
)

const displayLogs = computed(() => logs.value.slice(-6))

const resultMediaType = computed(() => currentType.value)

const currentCameraLabel = computed(() =>
  selectedVideoSource.value?.label
    ?? (cameraFacingMode.value === 'environment' ? '后摄像头' : '前摄像头'),
)

const cameraPrimaryActionLabel = computed(() => {
  if (!cameraReady.value) return isMobileViewport.value ? '扫一扫' : '打开摄像头'
  if (cameraRecognizing.value) return '正在识别，请稍等'
  return '开始识别'
})

const scannerStatusText = computed(() => {
  if (errorMessage.value) return errorMessage.value
  if (!cameraReady.value) return '点一下开始扫一扫'
  if (cameraRecognizing.value) return '识别中'
  return '摄像头已就绪'
})

const cameraStatusHint = computed(() => {
  if (!cameraReady.value) return `点一下打开摄像头，再进入实时识别。当前是${currentCameraProfile.value.label}。`
  if (cameraRecognizing.value) return '正在识别，请稍等'
  return '摄像头已打开，可以继续识别或切换前后摄。'
})

const videoSourceHint = computed(() => (
  '如果你使用 OBS，可以先在 OBS 中点击“启动虚拟摄像头”，然后在这里选择 OBS 视频源。'
))

const mobileModelEntryLabel = computed(() => {
  if (!currentModel.value?.title || currentModel.value.title === '暂无模型') {
    return '展开模型切换'
  }
  return `当前模型：${currentModel.value.title}`
})

const modelSectionHint = computed(() => {
  if (isMobileViewport.value && currentType.value === 'camera' && inlookSecondaryModel.value?.id === currentModelId.value) {
    return '手机端扫一扫默认使用 INLOOK 自研模型，优先展示你的专属识别效果。'
  }
  if (currentType.value === 'camera' && officialPrimaryModel.value?.id === currentModelId.value) {
    return '摄像头模式默认使用轻量官方模型，优先保证实时识别更流畅。'
  }
  if (officialPrimaryModel.value?.id === currentModelId.value) {
    return '默认使用官方通用模型，优先保证识别准确率。'
  }
  if (inlookSecondaryModel.value?.id === currentModelId.value) {
    return '当前已切换到 INLOOK 自研模型，适合特定场景测试。'
  }
  return '优先推荐官方通用模型。'
})

const cameraJson = computed(() =>
  recentRealtimeResult.value ? JSON.stringify(recentRealtimeResult.value, null, 2) : '',
)

const reportSummary = computed(() => {
  if (errorMessage.value) return errorMessage.value
  if (currentType.value === 'camera') {
    if (!recentRealtimeResult.value) return '最近一次识别结果会显示在这里。'
    return `最近一次识别：${recentRealtimeResult.value.boxes.length} 个目标`
  }
  if (!reportData.value) return '识别完成后会显示结果摘要。'
  return `输出文件：${reportData.value.output_path ?? '--'}`
})

const reportMetrics = computed(() => {
  if (currentType.value === 'camera') {
    if (!recentRealtimeResult.value) {
      return {
        detectedCount: '--',
        avgConfidence: '--',
        elapsed: '--',
        outputPath: '--',
      }
    }

    const confidences = recentRealtimeResult.value.boxes.map((item) => item.confidence)
    const avgConfidence = confidences.length
      ? (confidences.reduce((sum, value) => sum + value, 0) / confidences.length).toFixed(2)
      : '--'

    return {
      detectedCount: recentRealtimeResult.value.boxes.length,
      avgConfidence,
      elapsed: recentRealtimeResult.value.inference_time != null ? `${recentRealtimeResult.value.inference_time}ms` : '--',
      outputPath: '实时模式不保存文件',
    }
  }

  if (!reportData.value) {
    return {
      detectedCount: '--',
      avgConfidence: '--',
      elapsed: '--',
      outputPath: '--',
    }
  }

  return {
    detectedCount: reportData.value.detected_objects_count ?? '--',
    avgConfidence: reportData.value.avg_confidence ?? '--',
    elapsed: reportData.value.elapsed_seconds != null ? `${reportData.value.elapsed_seconds}s` : '--',
    outputPath: reportData.value.output_path ?? '--',
  }
})

const setCameraProfile = async (profileId) => {
  if (!cameraProfiles[profileId] || cameraProfileId.value === profileId) return
  const wasRecognizing = cameraRecognizing.value
  cameraProfileId.value = profileId
  appendLog(`[INFO] 已切换到${cameraProfiles[profileId].label}`)
  if (currentType.value === 'camera' && cameraReady.value) {
    await openCamera({ autoRestart: wasRecognizing })
  }
}

const loadVideoInputDevices = async ({ preserveSelection = true } = {}) => {
  if (!navigator.mediaDevices?.enumerateDevices) return

  const devices = await navigator.mediaDevices.enumerateDevices()
  const videoDevices = normalizeVideoInputDevices(
    devices.filter((device) => device.kind === 'videoinput'),
  )
  videoInputDevices.value = videoDevices

  if (!videoDevices.length) {
    selectedVideoDeviceId.value = ''
    return
  }

  const hasSelection = videoDevices.some((device) => device.id === selectedVideoDeviceId.value)
  if (preserveSelection && hasSelection) return

  const preferredObsDevice = videoDevices.find((device) => device.isObsLike)
  if (preferredObsDevice && !isMobileViewport.value) {
    selectedVideoDeviceId.value = preferredObsDevice.id
    return
  }

  if (!preserveSelection || !selectedVideoDeviceId.value) {
    selectedVideoDeviceId.value = ''
  }
}

const handleVideoSourceChange = async (event) => {
  const nextDeviceId = event.target.value
  if (nextDeviceId === selectedVideoDeviceId.value) return

  const wasRecognizing = cameraRecognizing.value
  selectedVideoDeviceId.value = nextDeviceId
  const nextSource = videoInputDevices.value.find((device) => device.id === nextDeviceId)
  appendLog(`[INFO] 视频源：${nextSource?.label ?? '普通摄像头'}`)

  if (currentType.value === 'camera' && cameraReady.value) {
    await openCamera({ autoRestart: wasRecognizing })
  }
}

const appendLog = (message) => {
  logs.value = [...logs.value, message]
}

const clearRealtimeTimer = () => {
  if (realtimeLoopTimer) {
    clearTimeout(realtimeLoopTimer)
    realtimeLoopTimer = null
  }
}

const revokePreviewUrl = () => {
  if (originalPreviewUrl.value) {
    URL.revokeObjectURL(originalPreviewUrl.value)
    originalPreviewUrl.value = ''
  }
}

const clearOverlay = () => {
  const canvas = overlayCanvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.clearRect(0, 0, canvas.width, canvas.height)
}

const stopCameraRecognition = (shouldLog = true) => {
  clearRealtimeTimer()
  cameraRecognizing.value = false
  if (currentType.value === 'camera') {
    status.value = cameraReady.value ? '摄像头已打开' : '待开始'
  }
  if (shouldLog) {
    appendLog('[INFO] 已停止识别')
  }
}

const stopCamera = (shouldLog = false) => {
  stopCameraRecognition(false)
  if (cameraStream.value) {
    cameraStream.value.getTracks().forEach((track) => track.stop())
    cameraStream.value = null
  }
  if (videoRef.value) {
    videoRef.value.srcObject = null
  }
  cameraReady.value = false
  cameraAspect.value = '4 / 3'
  recentRealtimeResult.value = null
  recentRealtimeBoxes.value = []
  clearOverlay()
  if (currentType.value === 'camera') {
    status.value = '待开始'
  }
  if (shouldLog) {
    appendLog('[INFO] 摄像头已关闭')
  }
}

const clearResultState = () => {
  resultUrl.value = ''
  reportUrl.value = ''
  reportData.value = null
  recentRealtimeResult.value = null
  recentRealtimeBoxes.value = []
  errorMessage.value = ''
  clearOverlay()
}

const resetSelection = () => {
  selectedFile.value = null
  selectedFileName.value = ''
  revokePreviewUrl()
  clearResultState()
  status.value = '待开始'
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

const normalizeError = async (response) => {
  if (response.status === 413) {
    return '上传文件过大，请换一个更小的文件再试。'
  }
  try {
    const payload = await response.json()
    return payload.detail || '请求失败'
  } catch {
    return `请求失败（HTTP ${response.status}）`
  }
}

const loadHealth = async () => {
  const response = await fetch(withBase('api/health'), {
    headers: apiHeaders(),
  })
  if (!response.ok) throw new Error(await normalizeError(response))
  health.value = await response.json()
}

const loadModels = async () => {
  const response = await fetch(withBase('api/models'), {
    headers: apiHeaders(),
  })
  if (!response.ok) throw new Error(await normalizeError(response))

  const payload = await response.json()
  models.value = payload.models || []

  if (!models.value.length) {
    appendLog('[WARN] 未找到模型')
    return
  }

  const officialModel = pickPreferredOfficialModel(currentType.value)
  const inlookModel = preferredInlookModel.value
  const mobileCameraPreferredModel =
    isMobileViewport.value && currentType.value === 'camera'
      ? inlookModel?.id || officialModel?.id
      : officialModel?.id || inlookModel?.id
  currentModelId.value = mobileCameraPreferredModel || models.value[0].id
  appendLog('[READY] 模型已加载')
}

const bootstrap = async () => {
  status.value = '待开始'
  logs.value = ['[INFO] 正在连接后端']

  try {
    await loadHealth()
    appendLog(`[INFO] 设备：${health.value.device}`)
    await loadModels()
  } catch (error) {
    status.value = '后端异常'
    errorMessage.value = error.message
    appendLog(`[ERROR] ${error.message}`)
  }
}

const openFilePicker = () => {
  fileInput.value?.click()
}

const handleFileChange = (event) => {
  const [file] = event.target.files || []
  if (!file) return

  if (currentType.value === 'image' && file.size > MAX_IMAGE_FILE_BYTES) {
    errorMessage.value = '图片文件过大，当前建议控制在 10MB 内。'
    appendLog('[WARN] 图片文件过大')
    event.target.value = ''
    return
  }

  clearResultState()
  status.value = '待开始'
  selectedFile.value = file
  selectedFileName.value = file.name
  revokePreviewUrl()
  originalPreviewUrl.value = URL.createObjectURL(file)
  appendLog(`[INFO] 文件：${file.name}`)
}

const runRecognition = async () => {
  if (!selectedFile.value) {
    errorMessage.value = '请先上传素材。'
    appendLog('[WARN] 请先上传素材')
    return
  }

  if (!currentModelId.value) {
    errorMessage.value = '当前没有可用模型。'
    appendLog('[WARN] 当前没有可用模型')
    return
  }

  clearResultState()
  isRunning.value = true
  status.value = '识别中'
  logs.value = [
    `[INFO] 类型：${currentTypeConfig.value.label}`,
    `[INFO] 模型：${currentModel.value.title}`,
    '[INFO] 参数：conf=0.25 · imgsz=640',
    '[RUNNING] 正在处理图片',
  ]

  const formData = new FormData()
  formData.append('file', selectedFile.value)
  formData.append('model_id', currentModelId.value)
  formData.append('conf', '0.25')
  formData.append('imgsz', '640')

  try {
    const endpoint = withBase('api/detect/image')
    const response = await fetch(endpoint, {
      method: 'POST',
      body: formData,
      headers: apiHeaders(),
    })

    if (!response.ok) {
      throw new Error(await normalizeError(response))
    }

    const payload = await response.json()
    resultUrl.value = withBase(payload.result_url)
    reportUrl.value = withBase(payload.report_url)
    reportData.value = payload.report
    status.value = '已完成'
    appendLog('[DONE] 识别完成')
    appendLog(`[DONE] 结果：${payload.result_url}`)
  } catch (error) {
    status.value = '失败'
    errorMessage.value = error.message
    appendLog(`[ERROR] ${error.message}`)
  } finally {
    isRunning.value = false
  }
}

const openCamera = async ({ autoRestart = false, autoStartRecognition = false } = {}) => {
  try {
    stopCamera(false)
    clearResultState()
    const videoConstraints = {
      width: { ideal: currentCameraProfile.value.idealWidth },
      height: { ideal: currentCameraProfile.value.idealHeight },
    }

    if (selectedVideoDeviceId.value) {
      videoConstraints.deviceId = { exact: selectedVideoDeviceId.value }
    } else {
      videoConstraints.facingMode = { ideal: cameraFacingMode.value }
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      video: videoConstraints,
      audio: false,
    })

    cameraStream.value = stream
    await loadVideoInputDevices()
    await nextTick()
    if (videoRef.value) {
      videoRef.value.srcObject = stream
      await videoRef.value.play()
      cameraReady.value = true
      status.value = '摄像头已打开'
      appendLog(`[INFO] 摄像头已打开 · ${currentCameraLabel.value}`)
      if (autoRestart || autoStartRecognition) {
        await startCameraRecognition()
      }
    }
  } catch (error) {
    cameraReady.value = false
    status.value = '摄像头异常'
    errorMessage.value = selectedVideoDeviceId.value
      ? '无法打开所选视频源，请重新选择或检查 OBS 虚拟摄像头是否已启动。'
      : '无法打开摄像头，请检查浏览器权限。'
    appendLog('[ERROR] 无法打开摄像头')
  }
}

const handleCameraPrimaryAction = async () => {
  if (!cameraReady.value) {
    await openCamera({ autoStartRecognition: true })
    return
  }
  if (!cameraRecognizing.value) {
    await startCameraRecognition()
  }
}

const selectDetectionType = async (typeId) => {
  currentType.value = typeId

  if (!isMobileViewport.value) return
  if (typeId !== 'camera') return
}

const toggleCameraFacing = async () => {
  const wasRecognizing = cameraRecognizing.value
  selectedVideoDeviceId.value = ''
  cameraFacingMode.value = cameraFacingMode.value === 'user' ? 'environment' : 'user'
  appendLog(`[INFO] 已切换到${currentCameraLabel.value}`)
  if (currentType.value === 'camera') {
    await openCamera({ autoRestart: wasRecognizing })
  }
}

const updateCameraStage = () => {
  const video = videoRef.value
  const overlay = overlayCanvasRef.value
  if (!video || !overlay) return

  const rect = video.getBoundingClientRect()
  if (!rect.width || !rect.height) return
  overlay.width = rect.width
  overlay.height = rect.height
}

const drawRealtimeBoxes = (payload) => {
  const overlay = overlayCanvasRef.value
  if (!overlay) return

  updateCameraStage()
  const ctx = overlay.getContext('2d')
  if (!ctx) return
  ctx.clearRect(0, 0, overlay.width, overlay.height)

  const scaleX = overlay.width / payload.image_width
  const scaleY = overlay.height / payload.image_height

  payload.boxes.forEach((box) => {
    const x = box.x1 * scaleX
    const y = box.y1 * scaleY
    const width = (box.x2 - box.x1) * scaleX
    const height = (box.y2 - box.y1) * scaleY
    const label = `${box.class_name} ${box.confidence.toFixed(2)}`

    ctx.strokeStyle = '#5eead4'
    ctx.lineWidth = 2
    ctx.strokeRect(x, y, width, height)

    ctx.font = '14px sans-serif'
    const textWidth = ctx.measureText(label).width
    ctx.fillStyle = 'rgba(12, 19, 28, 0.82)'
    ctx.fillRect(x, Math.max(0, y - 28), textWidth + 12, 22)
    ctx.fillStyle = '#f8fbff'
    ctx.fillText(label, x + 6, Math.max(15, y - 12))
  })
}

const captureCameraFrame = async () => {
  if (!cameraRecognizing.value || !cameraReady.value || !videoRef.value || !captureCanvasRef.value) {
    return
  }

  const video = videoRef.value
  if (!video.videoWidth || !video.videoHeight) {
    realtimeLoopTimer = setTimeout(captureCameraFrame, currentCameraProfile.value.minIntervalMs)
    return
  }

  const captureCanvas = captureCanvasRef.value
  const targetWidth = Math.min(currentCameraProfile.value.captureWidth, video.videoWidth)
  const targetHeight = Math.round((video.videoHeight / video.videoWidth) * targetWidth)
  captureCanvas.width = targetWidth
  captureCanvas.height = targetHeight

  const ctx = captureCanvas.getContext('2d')
  if (!ctx) return
  ctx.drawImage(video, 0, 0, targetWidth, targetHeight)

  const blob = await new Promise((resolve) => captureCanvas.toBlob(resolve, 'image/jpeg', currentCameraProfile.value.jpegQuality))
  if (!blob) {
    realtimeLoopTimer = setTimeout(captureCameraFrame, currentCameraProfile.value.minIntervalMs)
    return
  }

  const formData = new FormData()
  formData.append('file', blob, 'frame.jpg')
  formData.append('model_id', currentModelId.value)
  formData.append('conf', '0.25')
  formData.append('imgsz', String(currentCameraProfile.value.imgsz))

  try {
    const response = await fetch(withBase('api/realtime/detect'), {
      method: 'POST',
      body: formData,
      headers: apiHeaders(),
    })

    if (!response.ok) {
      throw new Error(await normalizeError(response))
    }

    const payload = await response.json()
    recentRealtimeResult.value = payload
    recentRealtimeBoxes.value = payload.boxes
    drawRealtimeBoxes(payload)
    status.value = '识别中'
    appendLog(`[INFO] 实时识别：${payload.boxes.length} 个目标 · ${payload.inference_time}ms`)
  } catch (error) {
    errorMessage.value = error.message
    status.value = '失败'
    appendLog(`[ERROR] ${error.message}`)
    stopCameraRecognition(false)
    return
  }

  const inferenceDelay = Number(recentRealtimeResult.value?.inference_time ?? 0)
  const nextInterval = Math.max(currentCameraProfile.value.minIntervalMs, currentCameraProfile.value.targetIntervalMs - inferenceDelay)
  realtimeLoopTimer = setTimeout(captureCameraFrame, nextInterval)
}

const startCameraRecognition = async () => {
  if (!cameraReady.value) {
    errorMessage.value = '请先打开摄像头。'
    appendLog('[WARN] 请先打开摄像头')
    return
  }
  if (!currentModelId.value) {
    errorMessage.value = '当前没有可用模型。'
    appendLog('[WARN] 当前没有可用模型')
    return
  }

  clearResultState()
  clearRealtimeTimer()
  cameraRecognizing.value = true
  status.value = '识别中'
  logs.value = [
    `[INFO] 类型：${currentTypeConfig.value.label}`,
    `[INFO] 模型：${currentModel.value.title}`,
    `[INFO] 模式：${currentCameraProfile.value.label}`,
    `[INFO] 实时参数：imgsz=${currentCameraProfile.value.imgsz} · width=${currentCameraProfile.value.captureWidth}`,
    '[INFO] 正在识别，请稍等',
  ]
  await captureCameraFrame()
}

const handleCameraLoaded = () => {
  if (!videoRef.value) return
  cameraAspect.value = `${videoRef.value.videoWidth} / ${videoRef.value.videoHeight}`
  updateCameraStage()
}

watch(currentType, (nextType, prevType) => {
  resetSelection()
  if (prevType === 'camera' || nextType !== 'camera') {
    stopCamera(false)
  }
  if (!currentModelId.value) {
    currentModelId.value = (
      isMobileViewport.value && nextType === 'camera'
        ? preferredInlookModel.value?.id || pickPreferredOfficialModel(nextType)?.id
        : pickPreferredOfficialModel(nextType)?.id || preferredInlookModel.value?.id
    ) || currentModelId.value
    return
  }
  const isUsingOfficialModel = models.value.some((item) => item.id === currentModelId.value && item.type === 'official')
  const isUsingInlookModel = models.value.some((item) => item.id === currentModelId.value && item.type === 'inlook')
  if (isMobileViewport.value && nextType === 'camera') {
    if (isUsingOfficialModel || isUsingInlookModel) {
      currentModelId.value = preferredInlookModel.value?.id || pickPreferredOfficialModel(nextType)?.id || currentModelId.value
    }
    return
  }
  if (isUsingOfficialModel) {
    const nextPreferredOfficial = pickPreferredOfficialModel(nextType)
    if (nextPreferredOfficial?.id) {
      currentModelId.value = nextPreferredOfficial.id
    }
  }
})

watch(isMobileViewport, async (isMobile) => {
  if (!isMobile) return
  syncDefaultFacingMode()
  currentType.value = 'camera'
  cameraProfileId.value = 'demo'
})

onMounted(() => {
  syncViewportState()
  syncDefaultFacingMode()
  if (isMobileViewport.value) {
    currentType.value = 'camera'
    cameraProfileId.value = 'demo'
  }
  bootstrap()
  loadVideoInputDevices()
  window.addEventListener('resize', syncViewportState)
  window.addEventListener('resize', updateCameraStage)
})

onBeforeUnmount(() => {
  revokePreviewUrl()
  stopCamera(false)
  window.removeEventListener('resize', syncViewportState)
  window.removeEventListener('resize', updateCameraStage)
})
</script>

<template>
  <div class="app-shell" :class="{ 'app-shell--scanner': isScannerMode }">
    <main class="page" :class="{ 'page--scanner': isScannerMode }">
      <section v-if="!isScannerMode" class="hero card">
        <div class="hero-copy">
          <h1>沈柳名的AI 实验室</h1>
          <p>图片识别 · 摄像头识别 · 模型切换 · 运行日志 · 测试报告</p>
          <small>仅用于合规图像识别学习、模型测试和内容创作。系统只输出识别结果，不提供任何游戏控制能力。</small>
        </div>
        <div class="hero-meta">
          <span>{{ currentDeviceLabel }}</span>
          <span>{{ status }}</span>
        </div>
        <div class="hero-links">
          <a
            v-for="link in siteLinks"
            :key="link.id"
            class="hero-link"
            :href="link.href"
          >
            {{ link.label }}
          </a>
        </div>
      </section>

      <section v-if="isScannerMode" class="card section scanner-stage-card">
        <div class="camera-stage camera-stage--scanner" :style="isScannerMode ? undefined : { aspectRatio: cameraAspect }">
          <video
            ref="videoRef"
            class="camera-video"
            autoplay
            muted
            playsinline
            @loadedmetadata="handleCameraLoaded"
          ></video>
          <canvas ref="overlayCanvasRef" class="camera-overlay"></canvas>
          <canvas ref="captureCanvasRef" class="capture-canvas"></canvas>
          <div class="scanner-mode-chip">{{ currentCameraProfile.label }}</div>
          <div class="scanner-site-links">
            <a
              v-for="link in siteLinks"
              :key="link.id"
              class="scanner-site-link"
              :href="link.href"
            >
              {{ link.label }}
            </a>
          </div>
          <div v-if="!cameraReady" class="scanner-entry">
            <label class="video-source-picker video-source-picker--scanner">
              <span>选择视频源</span>
              <select class="video-source-select" :value="selectedVideoDeviceId" @change="handleVideoSourceChange">
                <option value="">普通摄像头</option>
                <option
                  v-for="device in videoInputDevices"
                  :key="device.id"
                  :value="device.id"
                >
                  {{ device.label }}
                </option>
              </select>
              <small>{{ videoSourceHint }}</small>
            </label>
            <button type="button" class="primary-camera-button primary-camera-button--entry" @click="handleCameraPrimaryAction">
              {{ cameraPrimaryActionLabel }}
            </button>
          </div>
          <div v-else class="scanner-stage-overlay">
            <div class="camera-control-grid camera-control-grid--scanner">
              <button type="button" class="secondary-button secondary-button--floating" @click="toggleCameraFacing">切换前后摄</button>
            </div>
          </div>
        </div>
      </section>

      <section v-if="!isScannerMode" class="card section">
        <div class="section-title">
          <h2>识别类型</h2>
        </div>
        <div class="type-grid type-grid--three">
          <button
            v-for="item in displayedDetectionTypes"
            :key="item.id"
            class="type-button"
            :class="{ active: currentType === item.id }"
            type="button"
            @click="selectDetectionType(item.id)"
          >
            {{ item.label }}
          </button>
        </div>
      </section>

      <section v-if="!isScannerMode" class="card section mode-summary">
        <div class="mode-summary-copy">
          <span class="mode-badge">{{ currentModeDescription.hint }}</span>
          <h2>{{ currentModeDescription.title }}</h2>
          <p>{{ currentModeDescription.description }}</p>
        </div>
        <div class="mode-summary-meta">
          <div class="mode-meta-card">
            <span>当前模型</span>
            <strong>{{ currentModel.title }}</strong>
          </div>
          <div v-if="currentType === 'camera'" class="mode-meta-card">
            <span>摄像头</span>
            <strong>{{ currentCameraLabel }}</strong>
          </div>
        </div>
      </section>

      <section v-if="!isScannerMode" class="card section">
        <div class="section-title">
          <h2>模型选择</h2>
        </div>
        <p class="section-hint">{{ modelSectionHint }}</p>
        <div v-if="simplifiedModels.length">
          <div v-if="officialPrimaryModel" class="model-grid model-grid--single">
            <button
              type="button"
              class="model-button model-button--primary"
              :class="{ active: currentModelId === officialPrimaryModel.id }"
              @click="currentModelId = officialPrimaryModel.id"
            >
              <div class="model-card-head">
                <strong>{{ officialPrimaryModel.title }}</strong>
                <em v-if="currentModelId === officialPrimaryModel.id">默认推荐</em>
              </div>
              <span>{{ officialPrimaryModel.caption }}</span>
              <small>{{ officialPrimaryModel.description }}</small>
            </button>
          </div>
          <details v-if="isMobileViewport" class="secondary-entry">
            <summary>
              <span>进阶模型切换</span>
              <strong>{{ mobileModelEntryLabel }}</strong>
            </summary>
            <div v-if="inlookSecondaryModel" class="model-grid secondary-entry-body">
              <button
                type="button"
                class="model-button model-button--secondary"
                :class="{ active: currentModelId === inlookSecondaryModel.id }"
                @click="currentModelId = inlookSecondaryModel.id"
              >
                <div class="model-card-head">
                  <strong>{{ inlookSecondaryModel.title }}</strong>
                  <em v-if="currentModelId === inlookSecondaryModel.id">当前使用</em>
                </div>
                <span>{{ inlookSecondaryModel.caption }}</span>
                <small>{{ inlookSecondaryModel.description }}</small>
              </button>
            </div>
          </details>
          <div v-else-if="inlookSecondaryModel" class="model-grid model-grid--single secondary-model-block">
            <button
              type="button"
              class="model-button model-button--secondary"
              :class="{ active: currentModelId === inlookSecondaryModel.id }"
              @click="currentModelId = inlookSecondaryModel.id"
            >
              <div class="model-card-head">
                <strong>{{ inlookSecondaryModel.title }}</strong>
                <em v-if="currentModelId === inlookSecondaryModel.id">次入口</em>
              </div>
              <span>{{ inlookSecondaryModel.caption }}</span>
              <small>{{ inlookSecondaryModel.description }}</small>
            </button>
          </div>
        </div>
        <div v-else class="empty-state">
          <strong>暂无模型</strong>
          <p>请启动后端并确认模型文件存在。</p>
        </div>
      </section>

      <section v-if="false" class="card section scanner-secondary">
        <details class="secondary-entry">
          <summary>
            <span>识别类型</span>
            <strong>{{ currentModeDescription.title }}</strong>
          </summary>
          <div class="type-grid type-grid--three secondary-entry-body">
            <button
              v-for="item in displayedDetectionTypes"
              :key="item.id"
              class="type-button"
              :class="{ active: currentType === item.id }"
              type="button"
              @click="selectDetectionType(item.id)"
            >
              {{ item.label }}
            </button>
          </div>
        </details>
        <details class="secondary-entry">
          <summary>
            <span>模型切换</span>
            <strong>{{ mobileModelEntryLabel }}</strong>
          </summary>
          <div class="secondary-entry-body">
            <p class="section-hint">{{ modelSectionHint }}</p>
            <div v-if="officialPrimaryModel" class="model-grid model-grid--single">
              <button
                type="button"
                class="model-button model-button--primary"
                :class="{ active: currentModelId === officialPrimaryModel.id }"
                @click="currentModelId = officialPrimaryModel.id"
              >
                <div class="model-card-head">
                  <strong>{{ officialPrimaryModel.title }}</strong>
                  <em v-if="currentModelId === officialPrimaryModel.id">默认推荐</em>
                </div>
                <span>{{ officialPrimaryModel.caption }}</span>
                <small>{{ officialPrimaryModel.description }}</small>
              </button>
            </div>
            <div v-if="inlookSecondaryModel" class="model-grid model-grid--single secondary-model-block">
              <button
                type="button"
                class="model-button model-button--secondary"
                :class="{ active: currentModelId === inlookSecondaryModel.id }"
                @click="currentModelId = inlookSecondaryModel.id"
              >
                <div class="model-card-head">
                  <strong>{{ inlookSecondaryModel.title }}</strong>
                  <em v-if="currentModelId === inlookSecondaryModel.id">进阶测试</em>
                </div>
                <span>{{ inlookSecondaryModel.caption }}</span>
                <small>{{ inlookSecondaryModel.description }}</small>
              </button>
            </div>
          </div>
        </details>
      </section>

      <section v-if="currentType !== 'camera'" class="card section">
        <div class="section-title">
          <h2>上传素材</h2>
        </div>
        <input
          ref="fileInput"
          class="file-input"
          type="file"
          :accept="currentTypeConfig.accept"
          @change="handleFileChange"
        />
        <div class="upload-box">
          <strong>{{ currentTypeConfig.uploadTitle }}</strong>
          <p>{{ currentTypeConfig.uploadHint }}</p>
          <p v-if="selectedFileName" class="file-name">{{ selectedFileName }}</p>
          <button type="button" class="secondary-button" @click="openFilePicker">选择文件</button>
        </div>
      </section>

      <section v-else-if="!isScannerMode" class="card section">
        <div class="section-title">
          <h2>摄像头实时识别</h2>
        </div>
        <p class="camera-hint">{{ isMobileViewport ? '点一次就能打开摄像头并自动开始识别。' : '视频和摄像头识别会比图片慢一点' }}</p>
        <label class="video-source-picker">
          <span>选择视频源</span>
          <select class="video-source-select" :value="selectedVideoDeviceId" @change="handleVideoSourceChange">
            <option value="">普通摄像头</option>
            <option
              v-for="device in videoInputDevices"
              :key="device.id"
              :value="device.id"
            >
              {{ device.label }}
            </option>
          </select>
          <small>{{ videoSourceHint }}</small>
        </label>
        <div class="camera-profile-grid">
          <button
            v-for="profile in Object.values(cameraProfiles)"
            :key="profile.id"
            type="button"
            class="type-button type-button--soft"
            :class="{ active: cameraProfileId === profile.id }"
            @click="setCameraProfile(profile.id)"
          >
            {{ profile.label }}
          </button>
        </div>
        <div class="camera-control-grid">
          <button type="button" class="primary-camera-button" @click="handleCameraPrimaryAction">
            {{ cameraPrimaryActionLabel }}
          </button>
          <button type="button" class="secondary-button" @click="toggleCameraFacing">切换前后摄</button>
          <button type="button" class="ghost-button" :disabled="!cameraReady" @click="stopCamera(true)">停止识别</button>
        </div>
      </section>

      <section v-if="currentType !== 'camera'" class="card section action-section">
        <button type="button" class="primary-button" :disabled="!canRun" @click="runRecognition">
          {{ isRunning ? '识别中...' : '开始识别' }}
        </button>
      </section>

      <section v-if="!isScannerMode" class="card section">
        <div class="section-title">
          <h2>结果区域</h2>
        </div>

        <div class="result-overview">
          <div class="result-overview-card">
            <span>当前模式</span>
            <strong>{{ currentModeDescription.title }}</strong>
          </div>
          <div class="result-overview-card">
            <span>当前模型</span>
            <strong>{{ currentModel.title }}</strong>
          </div>
          <div class="result-overview-card">
            <span>当前状态</span>
            <strong>{{ status }}</strong>
          </div>
        </div>

        <template v-if="currentType === 'camera'">
          <div class="camera-stage" :style="{ aspectRatio: cameraAspect }">
            <video
              ref="videoRef"
              class="camera-video"
              autoplay
              muted
              playsinline
              @loadedmetadata="handleCameraLoaded"
            ></video>
            <canvas ref="overlayCanvasRef" class="camera-overlay"></canvas>
            <canvas ref="captureCanvasRef" class="capture-canvas"></canvas>
            <div v-if="!cameraReady" class="placeholder">点击“打开摄像头”后显示实时画面</div>
          </div>

          <div class="camera-json-card">
            <span>最近一次识别结果 JSON</span>
            <pre v-if="cameraJson" class="json-view">{{ cameraJson }}</pre>
            <div v-else class="placeholder">开始识别后显示最近一次返回结果</div>
          </div>
        </template>

        <template v-else>
          <div class="preview-stack">
            <div class="preview-card">
              <span>原始素材</span>
              <div class="preview-stage">
                <img
                  v-if="originalPreviewUrl && currentType === 'image'"
                  class="media"
                  :src="originalPreviewUrl"
                  alt="原始素材"
                />
                <div v-else class="placeholder">上传后显示原始素材</div>
              </div>
            </div>

            <div class="preview-card">
              <span>识别结果</span>
              <div class="preview-stage">
                <img
                  v-if="resultUrl && resultMediaType === 'image'"
                  class="media"
                  :src="resultUrl"
                  alt="识别结果"
                />
                <div v-else class="placeholder">
                  {{ isRunning ? '识别处理中...' : '识别完成后显示结果' }}
                </div>
              </div>
            </div>
          </div>

          <div class="link-grid">
            <a v-if="resultUrl" class="ghost-button" :href="resultUrl" download>下载结果</a>
            <a v-if="reportUrl" class="ghost-button" :href="reportUrl" target="_blank" rel="noreferrer">查看报告 JSON</a>
          </div>
        </template>
      </section>

      <section v-if="!isScannerMode" class="card section">
        <div class="section-title">
          <h2>运行日志</h2>
        </div>
        <div class="log-list">
          <p v-for="line in displayLogs" :key="line">{{ line }}</p>
        </div>
      </section>

      <section v-if="false" class="card section scanner-secondary">
        <details class="secondary-entry">
          <summary>
            <span>最近结果</span>
            <strong>{{ reportSummary }}</strong>
          </summary>
          <div class="secondary-entry-body">
            <div class="camera-json-card">
              <span>最近一次识别结果 JSON</span>
              <pre v-if="cameraJson" class="json-view">{{ cameraJson }}</pre>
              <div v-else class="placeholder">开始识别后显示最近一次返回结果</div>
            </div>
          </div>
        </details>
      </section>

      <section v-if="false" class="card section scanner-secondary">
        <details class="secondary-entry">
          <summary>
            <span>运行日志</span>
            <strong>{{ displayLogs[displayLogs.length - 1] || '暂无日志' }}</strong>
          </summary>
          <div class="secondary-entry-body">
            <div class="log-list">
              <p v-for="line in displayLogs" :key="line">{{ line }}</p>
            </div>
          </div>
        </details>
      </section>

      <section v-if="!isScannerMode" class="card section">
        <div class="section-title">
          <h2>测试报告</h2>
        </div>
        <div class="report-grid">
          <div class="metric-card">
            <span>检测数量</span>
            <strong>{{ reportMetrics.detectedCount }}</strong>
          </div>
          <div class="metric-card">
            <span>平均置信度</span>
            <strong>{{ reportMetrics.avgConfidence }}</strong>
          </div>
          <div class="metric-card">
            <span>耗时</span>
            <strong>{{ reportMetrics.elapsed }}</strong>
          </div>
        </div>
        <div class="report-path">
          <span>输出文件路径</span>
          <strong>{{ reportMetrics.outputPath }}</strong>
        </div>
        <p class="report-summary">{{ reportSummary }}</p>
      </section>

      <section v-if="false" class="card section scanner-secondary">
        <details class="secondary-entry">
          <summary>
            <span>测试报告</span>
            <strong>{{ reportMetrics.detectedCount }} 个目标 · {{ reportMetrics.avgConfidence }}</strong>
          </summary>
          <div class="secondary-entry-body">
            <div class="report-grid">
              <div class="metric-card">
                <span>检测数量</span>
                <strong>{{ reportMetrics.detectedCount }}</strong>
              </div>
              <div class="metric-card">
                <span>平均置信度</span>
                <strong>{{ reportMetrics.avgConfidence }}</strong>
              </div>
              <div class="metric-card">
                <span>耗时</span>
                <strong>{{ reportMetrics.elapsed }}</strong>
              </div>
            </div>
            <div class="report-path">
              <span>输出文件路径</span>
              <strong>{{ reportMetrics.outputPath }}</strong>
            </div>
          </div>
        </details>
      </section>
    </main>
  </div>
</template>
