<script setup>
import { computed, ref } from 'vue'
import MaterialAssetDrawer from './studio/MaterialAssetDrawer.vue'
import MaterialExtractCard from './studio/MaterialExtractCard.vue'

const props = defineProps({
  videoLink: {
    type: String,
    required: true,
  },
  rawScript: {
    type: String,
    required: true,
  },
  readStatus: {
    type: String,
    required: true,
  },
  uploadedFileName: {
    type: String,
    default: '',
  },
  materialStatus: {
    type: String,
    default: '',
  },
  materialSummary: {
    type: String,
    default: '',
  },
  material: {
    type: Object,
    default: null,
  },
  isReading: {
    type: Boolean,
    default: false,
  },
  transcriptionLoading: {
    type: Boolean,
    default: false,
  },
  subtitleStatus: {
    type: String,
    default: '未提取',
  },
  materialLamp: {
    type: String,
    default: 'idle',
  },
  materialLampText: {
    type: String,
    default: '未准备',
  },
  authStatuses: {
    type: Object,
    default: () => ({}),
  },
  authHint: {
    type: String,
    default: '',
  },
  scriptSourceLabel: {
    type: String,
    default: '手动输入',
  },
  scriptDetailReady: {
    type: Boolean,
    default: false,
  },
  materialLocalReady: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  'update:videoLink',
  'update:rawScript',
  'read-video',
  'file-selected',
  'manual-input',
  'extract-script',
  'start-auth',
  'clear-auth',
  'view-script-detail',
])

const fileInputRef = ref(null)
const assetDrawerOpen = ref(false)
const charCount = computed(() => props.rawScript.trim().length)
const materialUsageLabel = computed(() => {
  if (props.material?.cacheStatus === 'local_ready') return '本地 source.mp4'
  if (props.material?.cacheStatus === 'metadata_cached') return '已有素材信息，视频未下载'
  if (props.material?.cacheStatus === 'local_missing') return '本地视频文件丢失'
  if (props.material?.cacheStatus === 'local_invalid') return '本地视频文件无效'
  return '外部视频链接'
})
const materialFailureText = computed(() => {
  if (props.materialLamp !== 'failed') return ''
  return props.readStatus || '素材下载失败，请重试或上传本地视频。'
})

const triggerFileSelect = () => {
  fileInputRef.value?.click()
}

const onFileChange = (event) => {
  const [file] = event.target.files || []
  if (file) {
    emit('file-selected', file)
  }
  event.target.value = ''
}

const authText = (platform) => {
  const value = props.authStatuses?.[platform]?.status || 'unauthorized'
  const map = {
    unauthorized: '未授权',
    authorizing: '授权中',
    authorized: '已授权',
    expired: '已失效',
    failed: '失败',
  }
  return map[value] || value
}
</script>

<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <h2>1. 素材与原文案</h2>
        <p>从视频链接、本地视频或手动输入开始。</p>
      </div>
      <span class="panel-status">{{ readStatus }}</span>
    </div>

    <div class="panel-body stack-md">
      <div class="sub-panel auth-strip">
        <div class="auth-strip__row">
          <div class="auth-strip__status">
            <span>抖音</span>
            <strong>{{ authText('douyin') }}</strong>
          </div>
          <div class="auth-strip__actions">
            <button class="secondary-button secondary-button--small" type="button" @click="emit('start-auth', 'douyin')">
              授权
            </button>
            <button class="ghost-button ghost-button--small" type="button" @click="emit('clear-auth', 'douyin')">
              清除
            </button>
          </div>
        </div>
        <div class="auth-strip__row">
          <div class="auth-strip__status">
            <span>B站</span>
            <strong>{{ authText('bilibili') }}</strong>
          </div>
          <div class="auth-strip__actions">
            <button class="secondary-button secondary-button--small" type="button" @click="emit('start-auth', 'bilibili')">
              授权
            </button>
            <button class="ghost-button ghost-button--small" type="button" @click="emit('clear-auth', 'bilibili')">
              清除
            </button>
          </div>
        </div>
        <p v-if="authHint" class="helper-text auth-strip__hint">{{ authHint }}</p>
      </div>

      <label class="field">
        <span class="field-label">视频链接</span>
        <input
          :value="videoLink"
          class="text-input"
          type="text"
          placeholder="粘贴本人或授权视频链接"
          @input="emit('update:videoLink', $event.target.value)"
        />
      </label>

      <div class="action-grid">
        <button class="primary-button" type="button" :disabled="isReading" @click="emit('read-video')">
          {{ isReading ? '读取中...' : material ? '重新读取' : '读取素材' }}
        </button>
        <button class="secondary-button" type="button" @click="triggerFileSelect">本地上传</button>
        <button class="secondary-button" type="button" @click="emit('manual-input')">手动输入</button>
      </div>

      <p v-if="uploadedFileName" class="helper-text">已选择文件：{{ uploadedFileName }}</p>
      <div v-if="materialSummary" class="info-block">
        <span>{{ materialSummary }}</span>
      </div>
      <div v-if="!material" class="material-lamp-row">
        <span class="status-dot" :class="`status-dot--${materialLamp}`"></span>
        <strong>{{ materialLampText }}</strong>
      </div>
      <p v-if="materialFailureText" class="helper-text helper-text--error">{{ materialFailureText }}</p>

      <MaterialExtractCard
        v-if="material"
        :material="material"
        :material-lamp="materialLamp"
        :material-lamp-text="materialLampText"
        :transcription-loading="transcriptionLoading"
        :can-extract="Boolean(material) && !transcriptionLoading"
        @view-assets="assetDrawerOpen = true"
      />

      <input ref="fileInputRef" class="hidden-input" type="file" accept="video/*" @change="onFileChange" />

      <div class="sub-panel">
        <div class="field-headline">
          <span class="field-label">视频文案提取</span>
          <span class="field-meta">{{ transcriptionLoading ? '处理中' : subtitleStatus || '未开始' }}</span>
        </div>
        <div class="material-summary-grid">
          <div class="info-block">
            <span>当前状态：{{ transcriptionLoading ? '处理中' : subtitleStatus || '未开始' }}</span>
          </div>
          <div class="info-block">
            <span>使用素材：{{ materialUsageLabel }}</span>
          </div>
        </div>
        <div class="button-row button-row--compact">
          <button
            class="secondary-button secondary-button--small"
            type="button"
            :disabled="!materialLocalReady || transcriptionLoading"
            @click="emit('extract-script')"
            :title="materialLocalReady ? '' : '请先读取素材'"
          >
            {{ transcriptionLoading ? '提取中...' : rawScript ? '重新提取' : '提取视频文案' }}
          </button>
        </div>
      </div>

      <label class="field">
        <div class="field-headline">
          <span class="field-label">原始文案</span>
          <span class="field-meta">{{ charCount }} 字</span>
        </div>
        <div class="field-subline">
          <span class="field-meta">当前内容：{{ scriptSourceLabel }}</span>
          <div class="button-row button-row--compact">
            <button
              class="ghost-button ghost-button--small"
              type="button"
              :disabled="!scriptDetailReady"
              @click="emit('view-script-detail')"
            >
              查看识别详情
            </button>
          </div>
        </div>
        <textarea
          :value="rawScript"
          class="text-area text-area--tall"
          placeholder="这里优先回填平台发布文案；后续接入 ASR 后，再用 transcript 覆盖。"
          @input="emit('update:rawScript', $event.target.value)"
        ></textarea>
      </label>
    </div>

    <MaterialAssetDrawer :material="material" :open="assetDrawerOpen" @close="assetDrawerOpen = false" />
  </section>
</template>
