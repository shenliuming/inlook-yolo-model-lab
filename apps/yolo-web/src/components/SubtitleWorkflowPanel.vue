<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { withBase } from '../api/client'
import { createSubtitleTask, getSubtitleTask, reburnSubtitleTask } from '../api/workflow'
import FileDownloadList from './FileDownloadList.vue'
import StatusCard from './StatusCard.vue'
import TaskLog from './TaskLog.vue'

const videoFile = ref(null)
const audioFile = ref(null)
const assFile = ref(null)
const videoFileName = ref('')
const audioFileName = ref('')
const assFileName = ref('')
const task = ref(null)
const logs = ref('等待开始。')
const submitting = ref(false)
const reburning = ref(false)
const videoInput = ref(null)
const audioInput = ref(null)
const assInput = ref(null)
let pollTimer = null

const model = ref('small')
const computeType = ref('int8')

const downloadLinks = computed(() => {
  const downloads = task.value?.downloads || {}
  return [
    downloads['output_subtitled.mp4'] && { label: '下载 mp4', href: withBase(downloads['output_subtitled.mp4']) },
    downloads['output_subtitled.srt'] && { label: '下载 srt', href: withBase(downloads['output_subtitled.srt']) },
    downloads['output_subtitled.ass'] && { label: '下载 ass', href: withBase(downloads['output_subtitled.ass']) },
    downloads['output_subtitled.txt'] && { label: '下载 txt', href: withBase(downloads['output_subtitled.txt']) },
    downloads['output_fixed.mp4'] && { label: '下载重烧录 mp4', href: withBase(downloads['output_fixed.mp4']) },
    downloads['run.log'] && { label: '下载 run.log', href: withBase(downloads['run.log']) },
    downloads['status.json'] && { label: '下载 status.json', href: withBase(downloads['status.json']) },
  ].filter(Boolean)
})

const openVideoPicker = () => videoInput.value?.click()
const openAudioPicker = () => audioInput.value?.click()
const openAssPicker = () => assInput.value?.click()

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const handleVideoChange = (event) => {
  const [file] = event.target.files || []
  if (!file) return
  videoFile.value = file
  videoFileName.value = file.name
}

const handleAudioChange = (event) => {
  const [file] = event.target.files || []
  if (!file) return
  audioFile.value = file
  audioFileName.value = file.name
}

const handleAssChange = (event) => {
  const [file] = event.target.files || []
  if (!file) return
  assFile.value = file
  assFileName.value = file.name
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

const pollTask = async (taskId) => {
  try {
    const payload = await getSubtitleTask(taskId)
    task.value = payload
    logs.value = payload.log_tail || '暂无日志。'

    if (payload.status === 'success' || payload.status === 'failed') {
      stopPolling()
      submitting.value = false
    }
  } catch (error) {
    logs.value = `[ERROR] ${error.message}`
    stopPolling()
    submitting.value = false
  }
}

const submitTask = async () => {
  if (!videoFile.value) {
    logs.value = '[WARN] 请先选择视频。'
    return
  }

  submitting.value = true
  stopPolling()
  task.value = null
  logs.value = '[INFO] 提交字幕识别任务...'

  const formData = new FormData()
  formData.append('video', videoFile.value)
  if (audioFile.value) {
    formData.append('audio', audioFile.value)
  }
  formData.append('model', model.value)
  formData.append('language', 'zh')
  formData.append('device', 'cpu')
  formData.append('compute_type', computeType.value)

  try {
    const payload = await createSubtitleTask(formData)
    task.value = payload
    logs.value = '[INFO] 任务已创建，正在识别字幕...'
    await pollTask(payload.task_id)
    pollTimer = setInterval(() => {
      pollTask(payload.task_id)
    }, 1800)
  } catch (error) {
    logs.value = `[ERROR] ${error.message}`
    submitting.value = false
  }
}

const submitReburn = async () => {
  if (!task.value?.task_id) {
    logs.value = '[WARN] 请先完成一次字幕识别。'
    return
  }

  reburning.value = true
  logs.value = '[INFO] 正在重新烧录 ASS 字幕...'

  const formData = new FormData()
  if (assFile.value) {
    formData.append('ass', assFile.value)
  }

  try {
    const payload = await reburnSubtitleTask(task.value.task_id, formData)
    task.value = payload
    logs.value = payload.log_tail || '[DONE] 重新导出完成'
  } catch (error) {
    logs.value = `[ERROR] ${error.message}`
  } finally {
    reburning.value = false
  }
}

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<template>
  <section class="card section intake-hero">
    <div class="intake-copy">
      <h2>INLOOK AI 内容工作流</h2>
      <p>字幕识别 · 本地 Whisper 识别语音，生成 srt / ass / txt，并输出带字幕 mp4</p>
      <small>第一次运行会下载 faster-whisper 模型。下载完成后可以本地离线跑，不需要上传云端。</small>
    </div>
    <div class="hero-meta">
      <span>字幕识别</span>
      <span>{{ model }} · CPU int8</span>
    </div>
  </section>

  <section class="card section">
    <div class="section-title">
      <h2>任务输入</h2>
    </div>

    <input ref="videoInput" class="file-input" type="file" accept="video/*" @change="handleVideoChange" />
    <input ref="audioInput" class="file-input" type="file" accept="audio/*" @change="handleAudioChange" />
    <input ref="assInput" class="file-input" type="file" accept=".ass,text/*" @change="handleAssChange" />

    <div class="upload-box">
      <strong>选择视频</strong>
      <p>选择素材导入器生成的 input.mp4，或任意本地视频。</p>
      <p v-if="videoFileName" class="file-name">{{ videoFileName }}</p>
      <button type="button" class="secondary-button" @click="openVideoPicker">选择视频</button>
    </div>

    <div class="upload-box">
      <strong>可选选择音频</strong>
      <p>如果你有单独真人语音，可以用它替换原视频声音来识别和输出。</p>
      <p v-if="audioFileName" class="file-name">{{ audioFileName }}</p>
      <button type="button" class="secondary-button" @click="openAudioPicker">选择音频</button>
    </div>
  </section>

  <section class="card section mode-summary">
    <div class="mode-summary-copy">
      <span class="mode-badge">默认 small · CPU · int8</span>
      <h2>识别参数</h2>
      <p>small 适合日常短视频字幕；如果要更快可以切 base，如果要更准可以后续切 medium。</p>
    </div>
    <div class="mode-summary-meta">
      <label class="intake-field">
        <span>模型</span>
        <select v-model="model" class="video-source-select">
          <option value="base">base</option>
          <option value="small">small</option>
          <option value="medium">medium</option>
        </select>
      </label>
      <label class="intake-field">
        <span>计算类型</span>
        <select v-model="computeType" class="video-source-select">
          <option value="int8">int8</option>
          <option value="float32">float32</option>
        </select>
      </label>
    </div>
  </section>

  <section class="card section action-section">
    <button type="button" class="primary-button" :disabled="submitting" @click="submitTask">
      {{ submitting ? '生成中...' : '开始生成字幕' }}
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
      <h2>修改 ASS 后重新导出</h2>
    </div>
    <div class="upload-box">
      <strong>上传修改后的 ASS</strong>
      <p>字幕文字修正后，选择新的 .ass 文件，只重新烧录，不重新跑 Whisper。</p>
      <p v-if="assFileName" class="file-name">{{ assFileName }}</p>
      <button type="button" class="secondary-button" @click="openAssPicker">选择 ASS</button>
    </div>
    <button type="button" class="primary-button" :disabled="reburning || !task?.task_id" @click="submitReburn">
      {{ reburning ? '重新导出中...' : '重新导出视频' }}
    </button>
  </section>

  <FileDownloadList
    :links="downloadLinks"
    empty-text="任务成功后，这里会显示 mp4、srt、ass、txt、run.log 下载入口。"
  />
</template>

<style scoped>
.intake-hero {
  display: grid;
  gap: 14px;
}

.intake-copy {
  display: grid;
  gap: 10px;
}

.intake-copy h2,
.intake-copy p,
.intake-copy small {
  margin: 0;
}

.intake-copy h2 {
  font-size: 1.5rem;
}

.intake-copy p {
  color: #d6dce6;
  line-height: 1.75;
}

.intake-copy small {
  color: #949daa;
  line-height: 1.7;
}

.intake-field {
  display: grid;
  gap: 10px;
}

.intake-field span {
  font-weight: 700;
}

</style>
