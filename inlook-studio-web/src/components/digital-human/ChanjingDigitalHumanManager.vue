<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  generateDigitalHumanVideo,
  getDigitalHumanTask,
  importDigitalHumanTemplate,
  listDigitalHumanTasks,
  listDigitalHumanTemplates,
  syncDigitalHumanTemplates,
} from '../../api/digitalHuman'
import { apiUrl } from '../../api/client'

const props = defineProps({
  selectedPerson: {
    type: Object,
    default: null,
  },
  currentAudio: {
    type: Object,
    default: null,
  },
  currentScript: {
    type: String,
    default: '',
  },
  currentScriptTitle: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['return-workbench', 'select-person'])

const templates = ref([])
const tasks = ref([])
const loadingTemplates = ref(false)
const loadingTasks = ref(false)
const managerError = ref('')
const activeTab = ref('templates')
const generationText = ref('')
const submitting = ref(false)
const showImportDialog = ref(false)
const importFile = ref(null)
const importName = ref('INLOOK_数字人模板')
const importTrainingType = ref('full')
const importResolution = ref('1080p')

let templatePollTimer = null
let taskPollTimer = null

const selectedTemplate = computed(() => props.selectedPerson || null)
const totalTemplates = computed(() => templates.value.length)
const totalVideos = computed(() => tasks.value.filter((item) => item.videoUrl).length)
const totalPlayable = computed(() => tasks.value.filter((item) => item.videoUrl).length)

const canGenerate = computed(() => Boolean(selectedTemplate.value?.templateId) && Boolean(generationText.value.trim()) && !submitting.value)

const generationHint = computed(() => {
  if (!selectedTemplate.value?.templateId) return '请先从模板仓选择模板。'
  if (selectedTemplate.value?.status !== 'ready') return '当前模板仍在准备中，暂时不能生成。'
  if (!generationText.value.trim()) return '请输入要生成的数字人口播文案。'
  if (!selectedTemplate.value?.debug?.providerAudioProfileId && !props.currentAudio?.audioUrl) {
    return '当前模板没有可直接文本生成的声音配置，请使用工作台里的当前配音生成。'
  }
  return `将使用“${selectedTemplate.value.name}”生成数字人视频。`
})

const formatDateTime = (value) => {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (num) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const stopTemplatePolling = () => {
  if (templatePollTimer) {
    window.clearInterval(templatePollTimer)
    templatePollTimer = null
  }
}

const stopTaskPolling = () => {
  if (taskPollTimer) {
    window.clearInterval(taskPollTimer)
    taskPollTimer = null
  }
}

const loadTemplates = async () => {
  loadingTemplates.value = true
  try {
    templates.value = await listDigitalHumanTemplates()
  } catch (error) {
    managerError.value = String(error?.message || '模板列表读取失败。')
  } finally {
    loadingTemplates.value = false
  }
}

const loadTasks = async () => {
  loadingTasks.value = true
  try {
    tasks.value = await listDigitalHumanTasks()
  } catch (error) {
    managerError.value = String(error?.message || '生成任务读取失败。')
  } finally {
    loadingTasks.value = false
  }
}

const refreshAll = async () => {
  await Promise.all([loadTemplates(), loadTasks()])
}

const chooseTemplate = (template) => {
  emit('select-person', template)
  activeTab.value = 'generations'
}

const openImportDialog = () => {
  managerError.value = ''
  showImportDialog.value = true
}

const handleImportFile = (event) => {
  importFile.value = event?.target?.files?.[0] || null
}

const startTemplatePolling = () => {
  stopTemplatePolling()
  templatePollTimer = window.setInterval(async () => {
    await loadTemplates()
    if (!templates.value.some((item) => item.status === 'training')) stopTemplatePolling()
  }, 5000)
}

const startTaskPolling = () => {
  stopTaskPolling()
  taskPollTimer = window.setInterval(async () => {
    await loadTasks()
    const runningTask = tasks.value.find((item) => ['queued', 'running'].includes(item.status))
    if (!runningTask) {
      stopTaskPolling()
      return
    }
    try {
      await getDigitalHumanTask(runningTask.taskId)
      await loadTasks()
    } catch (error) {
      managerError.value = String(error?.message || '任务轮询失败。')
      stopTaskPolling()
    }
  }, 5000)
}

const submitImport = async () => {
  if (!importFile.value) {
    managerError.value = '请先上传模板视频。'
    return
  }
  submitting.value = true
  managerError.value = ''
  try {
    await importDigitalHumanTemplate(importFile.value, {
      name: importName.value.trim(),
      trainingType: importTrainingType.value,
      resolution: importResolution.value,
    })
    showImportDialog.value = false
    activeTab.value = 'templates'
    await loadTemplates()
    startTemplatePolling()
  } catch (error) {
    managerError.value = String(error?.message || '模板导入失败。')
  } finally {
    submitting.value = false
  }
}

const syncTemplates = async () => {
  submitting.value = true
  managerError.value = ''
  try {
    await syncDigitalHumanTemplates()
    await loadTemplates()
  } catch (error) {
    managerError.value = String(error?.message || '远程模板同步失败。')
  } finally {
    submitting.value = false
  }
}

const useCurrentScript = () => {
  if (props.currentScript?.trim()) generationText.value = props.currentScript.trim()
}

const submitGenerate = async () => {
  if (!selectedTemplate.value?.templateId) {
    managerError.value = '请先选择模板。'
    return
  }
  submitting.value = true
  managerError.value = ''
  try {
    await generateDigitalHumanVideo({
      templateId: selectedTemplate.value.templateId,
      script: generationText.value.trim(),
      mode: 'auto',
    })
    activeTab.value = 'generations'
    await loadTasks()
    startTaskPolling()
  } catch (error) {
    managerError.value = String(error?.message || '数字人视频生成失败。')
  } finally {
    submitting.value = false
  }
}

watch(
  () => props.currentScript,
  (value) => {
    if (!generationText.value.trim() && value?.trim()) generationText.value = value.trim()
  },
  { immediate: true },
)

onMounted(async () => {
  await refreshAll()
  if (templates.value.some((item) => item.status === 'training')) startTemplatePolling()
  if (tasks.value.some((item) => ['queued', 'running'].includes(item.status))) startTaskPolling()
})

onBeforeUnmount(() => {
  stopTemplatePolling()
  stopTaskPolling()
})
</script>

<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <h2>数字人</h2>
        <p>模板进入模板仓，生成结果进入视频列表，工作台和管理页共用同一套任务数据。</p>
      </div>

      <div class="button-row">
        <button class="secondary-button" type="button" @click="openImportDialog">导入数字人模板</button>
        <button class="secondary-button" type="button" :disabled="submitting" @click="syncTemplates">同步远程模板库</button>
        <button class="secondary-button" type="button" :disabled="loadingTemplates || loadingTasks" @click="refreshAll">刷新</button>
        <button class="secondary-button" type="button" @click="emit('return-workbench')">返回工作台</button>
      </div>
    </div>

    <div class="panel-body stack-lg">
      <div class="digital-human-stats">
        <article class="stat-card">
          <span class="field-label">模板总量</span>
          <strong>{{ totalTemplates }}</strong>
        </article>
        <article class="stat-card">
          <span class="field-label">成片总量</span>
          <strong>{{ totalVideos }}</strong>
        </article>
        <article class="stat-card">
          <span class="field-label">可直接播放</span>
          <strong>{{ totalPlayable }}</strong>
        </article>
      </div>

      <div v-if="managerError" class="status status--error">{{ managerError }}</div>

      <div class="button-row">
        <button class="secondary-button" :class="{ 'secondary-button--active': activeTab === 'templates' }" type="button" @click="activeTab = 'templates'">模板仓</button>
        <button class="secondary-button" :class="{ 'secondary-button--active': activeTab === 'generations' }" type="button" @click="activeTab = 'generations'">生成视频</button>
      </div>

      <div v-if="activeTab === 'templates'" class="stack-lg">
        <div class="sub-panel">
          <div class="field-headline">
            <span class="field-label">数字人模板仓</span>
            <span class="field-meta">{{ loadingTemplates ? '加载中' : `${templates.length} 个模板` }}</span>
          </div>
          <p class="helper-text">本地导入模板和远程模板库都会进入这里。选择模板后即可在工作台或本页直接生成数字人视频。</p>
        </div>

        <div v-if="!loadingTemplates && !templates.length" class="sub-panel">
          <div class="status status--warning">暂无数字人模板，请导入本地模板或同步远程模板库。</div>
        </div>

        <div v-else class="digital-human-card-grid">
          <article v-for="template in templates" :key="template.templateId" class="digital-human-card" :class="{ 'digital-human-card--selected': selectedTemplate?.templateId === template.templateId }">
            <div class="digital-human-card__media">
              <img v-if="template.coverUrl" :src="template.coverUrl" :alt="template.name" />
              <video v-else-if="template.previewUrl" :src="template.previewUrl" muted playsinline preload="metadata"></video>
              <div v-else class="digital-human-card__placeholder">模板</div>
            </div>
            <div class="digital-human-card__body">
              <div class="field-headline">
                <span class="field-label">{{ template.name }}</span>
                <span class="field-meta">{{ template.status === 'ready' ? '可用' : template.status === 'failed' ? '失败' : '训练中' }}</span>
              </div>
              <div class="info-block">
                <span>来源：{{ template.sourceLabel }}</span>
                <span>分辨率：{{ template.width || '--' }} x {{ template.height || '--' }}</span>
                <span>时间：{{ formatDateTime(template.updatedAt || template.createdAt) }}</span>
                <span v-if="template.errorMessage" class="helper-text--warning">{{ template.errorMessage }}</span>
              </div>
              <div class="button-row">
                <button class="secondary-button" type="button" @click="chooseTemplate(template)">选择模板</button>
                <a v-if="template.previewUrl" class="secondary-button secondary-button--link" :href="template.previewUrl" target="_blank" rel="noreferrer">播放预览</a>
              </div>
            </div>
          </article>
        </div>
      </div>

      <div v-if="activeTab === 'generations'" class="stack-lg">
        <div class="digital-human-context-grid">
          <article class="context-card">
            <span class="field-label">当前选中模板</span>
            <strong>{{ selectedTemplate?.name || '未选择模板' }}</strong>
            <p>{{ selectedTemplate?.sourceLabel || '请先从模板仓选择模板。' }}</p>
          </article>
          <article class="context-card">
            <span class="field-label">当前配音</span>
            <strong>{{ props.currentAudio?.audioUrl ? '已就绪' : '未生成' }}</strong>
            <p>{{ props.currentAudio?.sourceScriptTitle || props.currentScriptTitle || '当前页面也支持直接输入文本生成。' }}</p>
          </article>
          <article class="context-card">
            <span class="field-label">当前文案</span>
            <strong>{{ props.currentScriptTitle || '未命名文案' }}</strong>
            <p>{{ props.currentScript?.trim() ? `${props.currentScript.trim().length} 字` : '可直接使用当前工作台文案填充。' }}</p>
          </article>
        </div>

        <div class="sub-panel">
          <div class="field-headline">
            <span class="field-label">生成面板</span>
            <span class="field-meta">{{ generationHint }}</span>
          </div>
          <div class="stack-md">
            <textarea v-model="generationText" class="text-area" rows="5" placeholder="输入要生成的数字人口播文案。"></textarea>
            <div class="button-row">
              <button class="secondary-button" type="button" @click="useCurrentScript">使用当前文案</button>
              <button class="primary-button" type="button" :disabled="!canGenerate" @click="submitGenerate">
                {{ submitting ? '生成中...' : '生成数字人视频' }}
              </button>
            </div>
          </div>
        </div>

        <div class="sub-panel">
          <div class="field-headline">
            <span class="field-label">生成视频列表</span>
            <span class="field-meta">{{ loadingTasks ? '加载中' : `${tasks.length} 条记录` }}</span>
          </div>
          <p v-if="!loadingTasks && !tasks.length" class="helper-text">暂无生成视频。选择模板并发起生成后，成片会出现在这里。</p>
          <div v-else class="digital-human-card-grid">
            <article v-for="task in tasks" :key="task.taskId" class="digital-human-card">
              <div class="digital-human-card__media">
                <video v-if="task.videoUrl" :src="apiUrl(task.videoUrl)" controls preload="metadata"></video>
                <img v-else-if="task.coverUrl" :src="task.coverUrl" :alt="task.templateName" />
                <div v-else class="digital-human-card__placeholder">生成视频</div>
              </div>
              <div class="digital-human-card__body">
                <div class="field-headline">
                  <span class="field-label">{{ task.templateName || '数字人视频' }}</span>
                  <span class="field-meta">{{ task.status === 'success' ? '成功' : task.status === 'failed' ? '失败' : '生成中' }}</span>
                </div>
                <div class="info-block">
                  <span>创建时间：{{ formatDateTime(task.createdAt) }}</span>
                  <span>进度：{{ task.progress }}%</span>
                  <span v-if="task.errorMessage" class="helper-text--warning">{{ task.errorMessage }}</span>
                </div>
                <div class="button-row">
                  <a v-if="task.videoUrl" class="secondary-button secondary-button--link" :href="apiUrl(task.videoUrl)" target="_blank" rel="noreferrer">播放</a>
                  <a v-if="task.downloads?.video" class="secondary-button secondary-button--link" :href="apiUrl(task.downloads.video)" target="_blank" rel="noreferrer">下载</a>
                  <a v-if="task.downloads?.runLog" class="secondary-button secondary-button--link" :href="apiUrl(task.downloads.runLog)" target="_blank" rel="noreferrer">run.log</a>
                </div>
              </div>
            </article>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showImportDialog" class="voice-dialog-overlay">
      <div class="voice-dialog voice-dialog--wide">
        <div class="voice-dialog__header">
          <div>
            <h3>导入数字人模板</h3>
            <p>上传模板视频后，模板会先进入训练中状态，完成后自动出现在模板仓。</p>
          </div>
          <button class="icon-button" type="button" @click="showImportDialog = false">×</button>
        </div>

        <div class="voice-dialog__body stack-md">
          <label class="form-field">
            <span class="field-label">模板视频</span>
            <input type="file" accept="video/mp4,video/webm,video/quicktime" @change="handleImportFile" />
          </label>
          <label class="form-field">
            <span class="field-label">数字人名称</span>
            <input v-model="importName" class="text-input" type="text" />
          </label>
          <label class="form-field">
            <span class="field-label">训练类型</span>
            <select v-model="importTrainingType" class="select-input">
              <option value="full">完整数字人</option>
              <option value="figure">仅形象</option>
              <option value="voice">仅声音</option>
            </select>
          </label>
          <label class="form-field">
            <span class="field-label">分辨率</span>
            <select v-model="importResolution" class="select-input">
              <option value="1080p">1080p</option>
              <option value="4K">4K</option>
            </select>
          </label>
        </div>

        <div class="voice-dialog__footer">
          <button class="secondary-button" type="button" @click="showImportDialog = false">取消</button>
          <button class="primary-button" type="button" :disabled="submitting" @click="submitImport">
            {{ submitting ? '提交中...' : '开始训练' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
