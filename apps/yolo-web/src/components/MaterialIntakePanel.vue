<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { withBase } from '../api/client'
import { createMaterialTask, getMaterialTask } from '../api/workflow'
import FileDownloadList from './FileDownloadList.vue'
import StatusCard from './StatusCard.vue'
import TaskLog from './TaskLog.vue'

const mode = ref('text')
const shareText = ref('')
const sourceUrl = ref('')
const engine = ref('auto')
const materialFile = ref(null)
const materialFileName = ref('')
const task = ref(null)
const logs = ref('等待开始。')
const submitting = ref(false)
const fileInput = ref(null)
let pollTimer = null

const modeTabs = [
  { id: 'text', label: '抖音分享文案', hint: '直接粘贴整段分享文案，系统会自动提取链接。' },
  { id: 'url', label: '视频链接', hint: '支持 B站链接、普通 mp4 链接，视频号请手动保存后上传。' },
  { id: 'upload', label: '本地视频', hint: '自动下载失败时，可以直接上传本地视频兜底。' },
]

const engineOptions = [
  { id: 'auto', label: 'auto 自动尝试' },
  { id: 'yt-dlp', label: 'yt-dlp' },
  { id: 'you-get', label: 'you-get' },
  { id: 'lux', label: 'lux' },
]

const currentMode = computed(() =>
  modeTabs.find((item) => item.id === mode.value) ?? modeTabs[0],
)

const downloadLinks = computed(() => {
  const downloads = task.value?.downloads || {}
  return [
    downloads['input.mp4'] && { label: '下载 input.mp4', href: withBase(downloads['input.mp4']) },
    downloads['metadata.json'] && { label: '下载 metadata.json', href: withBase(downloads['metadata.json']) },
    downloads['status.json'] && { label: '下载 status.json', href: withBase(downloads['status.json']) },
    downloads['run.log'] && { label: '下载 run.log', href: withBase(downloads['run.log']) },
  ].filter(Boolean)
})

const openMaterialPicker = () => {
  fileInput.value?.click()
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const resetFile = () => {
  materialFile.value = null
  materialFileName.value = ''
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

const handleFileChange = (event) => {
  const [file] = event.target.files || []
  if (!file) return
  materialFile.value = file
  materialFileName.value = file.name
}

const setMode = (nextMode) => {
  mode.value = nextMode
  if (nextMode !== 'upload') {
    resetFile()
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

const pollTask = async (taskId) => {
  try {
    const payload = await getMaterialTask(taskId)
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
  submitting.value = true
  stopPolling()
  task.value = null
  logs.value = '[INFO] 提交任务中...'

  const formData = new FormData()
  formData.append('mode', mode.value)
  formData.append('engine', engine.value)

  if (mode.value === 'text') {
    formData.append('text', shareText.value)
  } else if (mode.value === 'url') {
    formData.append('url', sourceUrl.value)
  } else if (materialFile.value) {
    formData.append('file', materialFile.value)
  }

  try {
    const payload = await createMaterialTask(formData)
    task.value = payload
    logs.value = '[INFO] 任务已创建，正在等待处理...'
    await pollTask(payload.task_id)
    pollTimer = setInterval(() => {
      pollTask(payload.task_id)
    }, 1500)
  } catch (error) {
    logs.value = `[ERROR] ${error.message}`
    submitting.value = false
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
      <p>素材导入器 · 把抖音/B站/视频号/本地视频统一整理成 input.mp4</p>
      <small>如果你使用微信视频号，建议先在手机里手动保存视频，再上传本地文件。当前版本不会强行破解视频号下载。</small>
    </div>
    <div class="hero-meta">
      <span>素材导入</span>
      <span>{{ currentMode.label }}</span>
    </div>
  </section>

  <section class="card section">
    <div class="section-title">
      <h2>导入方式</h2>
    </div>
    <div class="type-grid type-grid--three">
      <button
        v-for="item in modeTabs"
        :key="item.id"
        class="type-button"
        :class="{ active: mode === item.id }"
        type="button"
        @click="setMode(item.id)"
      >
        {{ item.label }}
      </button>
    </div>
  </section>

  <section class="card section mode-summary">
    <div class="mode-summary-copy">
      <span class="mode-badge">统一输出 input.mp4 / metadata.json / status.json / run.log</span>
      <h2>{{ currentMode.label }}</h2>
      <p>{{ currentMode.hint }}</p>
    </div>
    <div class="mode-summary-meta">
      <div class="mode-meta-card">
        <span>下载引擎</span>
        <strong>{{ engine }}</strong>
      </div>
      <div class="mode-meta-card">
        <span>任务状态</span>
        <strong>{{ task?.status || '待开始' }}</strong>
      </div>
    </div>
  </section>

  <section class="card section">
    <div class="section-title">
      <h2>任务输入</h2>
    </div>

    <label class="intake-field" v-if="mode === 'text'">
      <span>粘贴抖音分享文案</span>
      <textarea
        v-model="shareText"
        class="intake-textarea"
        placeholder="例如：复制这段抖音分享文案，系统会自动提取其中的链接。"
      />
    </label>

    <label class="intake-field" v-else-if="mode === 'url'">
      <span>粘贴 B站链接 / 视频号链接 / 普通 mp4 链接</span>
      <input
        v-model="sourceUrl"
        class="video-source-select"
        type="text"
        placeholder="https://www.bilibili.com/video/... 或 https://example.com/demo.mp4"
      />
    </label>

    <template v-else>
      <input
        ref="fileInput"
        class="file-input"
        type="file"
        accept="video/*"
        @change="handleFileChange"
      />
      <div class="upload-box">
        <strong>上传本地视频</strong>
        <p>自动下载失败时，直接上传本地视频兜底。</p>
        <p v-if="materialFileName" class="file-name">{{ materialFileName }}</p>
        <button type="button" class="secondary-button" @click="openMaterialPicker">选择文件</button>
      </div>
    </template>

    <label class="intake-field">
      <span>选择下载引擎</span>
      <select v-model="engine" class="video-source-select">
        <option
          v-for="option in engineOptions"
          :key="option.id"
          :value="option.id"
        >
          {{ option.label }}
        </option>
      </select>
      <small class="camera-hint">auto 会按 yt-dlp -> you-get -> lux 顺序自动尝试。微信视频号若不可直下，会提示手动保存后上传。</small>
    </label>
  </section>

  <section class="card section action-section">
    <button type="button" class="primary-button" :disabled="submitting" @click="submitTask">
      {{ submitting ? '处理中...' : '开始导入素材' }}
    </button>
  </section>

  <StatusCard
    :text="renderStatusText(task)"
    :task-id="task?.task_id || ''"
    :status="task?.status || 'idle'"
  />

  <TaskLog :logs="logs" />

  <FileDownloadList
    :links="downloadLinks"
    empty-text="任务成功后，这里会显示 input.mp4、metadata.json、status.json、run.log 下载入口。"
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

.intake-textarea {
  min-height: 160px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 18px;
  background: rgba(6, 9, 14, 0.8);
  color: #f3f5f8;
  padding: 14px 16px;
  resize: vertical;
  font: inherit;
  line-height: 1.7;
}

</style>
