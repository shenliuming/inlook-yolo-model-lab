<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { withBase } from '../api/client'
import { createTtsTask, downloadTtsFile, getTtsTask, healthTts } from '../api/contentLabApi'
import FileDownloadList from './FileDownloadList.vue'
import StatusCard from './StatusCard.vue'
import TaskLog from './TaskLog.vue'

const text = ref('你好，这里是 INLOOK AI 内容工作流，现在开始生成一段测试配音。')
const voiceMode = ref('clone')
const language = ref('zh')
const promptAudio = ref(null)
const promptAudioName = ref('')
const promptAudioPath = ref('')
const textFile = ref(null)
const textFileName = ref('')
const task = ref(null)
const logs = ref('等待开始。')
const submitting = ref(false)
const healthInfo = ref(null)
const errorMessage = ref('')
const promptAudioInput = ref(null)
const textFileInput = ref(null)
let pollTimer = null

const canSubmit = computed(() => {
  if (submitting.value) return false
  if (voiceMode.value === 'default') {
    return Boolean(text.value.trim() || textFile.value)
  }
  return Boolean((text.value.trim() || textFile.value) && (promptAudio.value || promptAudioPath.value.trim()))
})

const downloadLinks = computed(() => {
  if (!task.value?.task_id) return []
  const downloads = task.value.downloads || {}
  return [
    downloads['voice.wav'] && { label: '下载 voice.wav', href: withBase(downloads['voice.wav']) },
    downloads['metadata.json'] && { label: '下载 metadata.json', href: withBase(downloads['metadata.json']) },
    downloads['status.json'] && { label: '下载 status.json', href: withBase(downloads['status.json']) },
    downloads['run.log'] && { label: '下载 run.log', href: withBase(downloads['run.log']) },
  ].filter(Boolean)
})

const audioPreviewUrl = computed(() => {
  if (!task.value?.task_id) return ''
  const downloads = task.value.downloads || {}
  if (downloads['voice.wav']) return withBase(downloads['voice.wav'])
  return withBase(downloadTtsFile(task.value.task_id, 'voice.wav'))
})

const openPromptAudioPicker = () => promptAudioInput.value?.click()
const openTextFilePicker = () => textFileInput.value?.click()

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const renderStatusText = (payload) => {
  const status = payload?.status || 'idle'
  const message = payload?.message || '等待开始。'
  if (status === 'success') return `已完成：${message}`
  if (status === 'failed') return `失败：${message}`
  if (status === 'running') return `处理中：${message}`
  if (status === 'queued') return `排队中：${message}`
  return message
}

const handlePromptAudioChange = (event) => {
  const [file] = event.target.files || []
  if (!file) return
  promptAudio.value = file
  promptAudioName.value = file.name
}

const handleTextFileChange = (event) => {
  const [file] = event.target.files || []
  if (!file) return
  textFile.value = file
  textFileName.value = file.name
}

const refreshHealth = async () => {
  try {
    healthInfo.value = await healthTts()
  } catch (error) {
    errorMessage.value = error.message
  }
}

const pollTask = async (taskId) => {
  try {
    const payload = await getTtsTask(taskId)
    task.value = payload
    logs.value = payload.log_tail || '暂无日志。'
    if (payload.status === 'success' || payload.status === 'failed') {
      stopPolling()
      submitting.value = false
    }
  } catch (error) {
    logs.value = `[ERROR] ${error.message}`
    submitting.value = false
    stopPolling()
  }
}

const submitTask = async () => {
  if (!canSubmit.value) {
    logs.value = voiceMode.value === 'clone'
      ? '[WARN] 克隆模式需要文本内容和参考音频。'
      : '[WARN] 请先输入要生成的文本，或上传文本文件。'
    return
  }

  stopPolling()
  submitting.value = true
  task.value = null
  logs.value = '[INFO] 提交 TTS 任务中...'
  errorMessage.value = ''

  const formData = new FormData()
  formData.append('text', text.value)
  formData.append('voiceMode', voiceMode.value)
  formData.append('language', language.value)
  formData.append('engine', 'moss-tts-nano')
  formData.append('backend', 'onnx')
  formData.append('executionProvider', 'cpu')
  if (promptAudio.value) {
    formData.append('promptAudio', promptAudio.value)
  }
  if (promptAudioPath.value.trim()) {
    formData.append('promptAudioPath', promptAudioPath.value.trim())
  }
  if (textFile.value) {
    formData.append('textFile', textFile.value)
  }

  try {
    const payload = await createTtsTask(formData)
    task.value = payload
    logs.value = payload.log_tail || '[INFO] TTS 任务已创建，正在生成语音...'
    await pollTask(payload.task_id)
    pollTimer = setInterval(() => {
      pollTask(payload.task_id)
    }, 1800)
  } catch (error) {
    logs.value = `[ERROR] ${error.message}`
    submitting.value = false
  }
}

onMounted(() => {
  refreshHealth()
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<template>
  <section class="card section intake-hero">
    <div class="intake-copy">
      <h2>TTS 配音生成</h2>
      <p>INLOOK AI 内容工作流 · 用 MOSS-TTS-Nano 生成本地语音输出，默认走 ONNX CPU。</p>
      <small>请确认你拥有参考音频的使用授权。不要上传未经授权的他人声音样本用于克隆。</small>
    </div>
    <div class="hero-meta">
      <span>moss-tts-nano</span>
      <span>ONNX · CPU</span>
    </div>
  </section>

  <section class="card section mode-summary">
    <div class="mode-summary-copy">
      <span class="mode-badge">内容工作流 · TTS 配音</span>
      <h2>生成方式</h2>
      <p>默认使用 ONNX CPU，先保证本地可跑和链路清晰。CUDA 入口保留给后续版本。</p>
    </div>
    <div class="mode-summary-meta">
      <div class="mode-meta-card">
        <span>当前执行器</span>
        <strong>{{ healthInfo?.execution_provider || 'cpu' }}</strong>
      </div>
      <div class="mode-meta-card">
        <span>模型目录</span>
        <strong>{{ healthInfo?.models_present ? '已检测' : '首次运行可自动下载' }}</strong>
      </div>
    </div>
  </section>

  <section class="card section">
    <div class="section-title">
      <h2>任务输入</h2>
    </div>

    <label class="intake-field">
      <span>配音模式</span>
      <select v-model="voiceMode" class="video-source-select">
        <option value="clone">克隆参考音频</option>
        <option value="default">默认音色</option>
      </select>
    </label>

    <label class="intake-field">
      <span>文本内容</span>
      <textarea
        v-model="text"
        class="intake-textarea"
        placeholder="输入要生成的中文文案，也可以上传 text 文件。"
      />
    </label>

    <input ref="textFileInput" class="file-input" type="file" accept=".txt,text/plain" @change="handleTextFileChange" />
    <div class="upload-box">
      <strong>可选上传文本文件</strong>
      <p>如果你的文案已经整理成 txt，可以直接上传，避免手动粘贴。</p>
      <p v-if="textFileName" class="file-name">{{ textFileName }}</p>
      <button type="button" class="secondary-button" @click="openTextFilePicker">选择文本文件</button>
    </div>

    <label class="intake-field">
      <span>语言</span>
      <select v-model="language" class="video-source-select">
        <option value="zh">中文</option>
        <option value="en">English</option>
        <option value="jp">日本語</option>
      </select>
    </label>

    <input ref="promptAudioInput" class="file-input" type="file" accept="audio/*" @change="handlePromptAudioChange" />
    <div class="upload-box">
      <strong>参考音频</strong>
      <p>克隆模式下，建议上传一段干净的人声作为参考音频。</p>
      <p v-if="promptAudioName" class="file-name">{{ promptAudioName }}</p>
      <button type="button" class="secondary-button" @click="openPromptAudioPicker">选择参考音频</button>
    </div>

    <label class="intake-field">
      <span>或填写本地 promptAudioPath</span>
      <input
        v-model="promptAudioPath"
        class="video-source-select"
        type="text"
        placeholder="/absolute/path/to/prompt.wav"
      />
      <small class="camera-hint">如果后端机器上已经有参考音频，可以直接填绝对路径。克隆模式至少要提供上传音频或本地路径其中一种。</small>
    </label>
  </section>

  <section class="card section action-section">
    <button type="button" class="primary-button" :disabled="!canSubmit" @click="submitTask">
      {{ submitting ? '生成中...' : '开始生成配音' }}
    </button>
  </section>

  <StatusCard
    :text="renderStatusText(task)"
    :task-id="task?.task_id || ''"
    :status="task?.status || 'idle'"
  />

  <TaskLog :logs="logs" />

  <section class="card section">
    <div class="section-title">
      <h2>音频预览</h2>
    </div>
    <div v-if="task?.status === 'success' && audioPreviewUrl" class="audio-preview-box">
      <audio controls class="audio-preview" :src="audioPreviewUrl"></audio>
    </div>
    <div v-else class="placeholder">任务成功后，这里会出现 voice.wav 的在线预览。</div>
  </section>

  <FileDownloadList
    :links="downloadLinks"
    empty-text="任务成功后，这里会显示 voice.wav、metadata.json、status.json、run.log 下载入口。"
  />

  <section v-if="healthInfo" class="card section">
    <div class="section-title">
      <h2>环境状态</h2>
    </div>
    <pre class="json-view">{{ JSON.stringify(healthInfo, null, 2) }}</pre>
  </section>

  <section v-if="errorMessage" class="card section">
    <div class="section-title">
      <h2>错误提示</h2>
    </div>
    <p class="placeholder">{{ errorMessage }}</p>
  </section>
</template>

<style scoped>
.audio-preview-box {
  display: grid;
  gap: 12px;
}

.audio-preview {
  width: 100%;
}
</style>
