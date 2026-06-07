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
  isManualTextMode: {
    type: Boolean,
    default: false,
  },
  canSetAsCurrentScript: {
    type: Boolean,
    default: false,
  },
  inputDirty: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  'update:videoLink',
  'update:rawScript',
  'file-selected',
  'manual-input',
  'set-current-script',
  'extract-script',
  'start-auth',
  'clear-auth',
])

const fileInputRef = ref(null)
const assetDrawerOpen = ref(false)
const authExpanded = ref(false)
const copyHint = ref('')
const charCount = computed(() => props.rawScript.trim().length)
const materialFailureText = computed(() => {
  if (props.materialLamp !== 'failed') return ''
  return props.readStatus || '素材下载失败，请重试或上传本地视频。'
})
const primaryButtonText = computed(() => {
  if (props.isReading || props.transcriptionLoading) return '处理中...'
  if (props.inputDirty) return '提取文案'
  if (props.subtitleStatus === '失败') return '重试'
  if (props.materialLamp === 'failed') return '重试'
  if (props.rawScript.trim() && props.scriptSourceLabel === '视频口播') return '重新提取'
  return '提取文案'
})
const flowStatusText = computed(() => {
  if (props.isReading) return '正在读取素材...'
  if (props.transcriptionLoading) return '正在提取口播...'
  if (props.subtitleStatus === '完成') return '已完成'
  if (props.materialLamp === 'failed') return props.readStatus || '处理失败'
  return props.readStatus || '等待输入'
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

const copyText = async (text, hint = '已复制文案') => {
  const value = String(text || '').trim()
  if (!value) return
  try {
    await navigator.clipboard.writeText(value)
    copyHint.value = hint
    window.setTimeout(() => {
      if (copyHint.value === hint) copyHint.value = ''
    }, 1400)
  } catch {
    copyHint.value = '复制失败'
  }
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
      <div class="auth-compact">
        <div class="auth-compact__summary">
          <span>授权：抖音{{ authText('douyin') }} · B站{{ authText('bilibili') }}</span>
          <button class="ghost-button ghost-button--small" type="button" @click="authExpanded = !authExpanded">管理</button>
        </div>
        <p v-if="authHint" class="helper-text auth-strip__hint">{{ authHint }}</p>
        <div v-if="authExpanded" class="auth-compact__details">
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
        </div>
      </div>

      <label class="field">
        <span class="field-label">视频链接 / 分享口令</span>
        <textarea
          :value="videoLink"
          class="text-area share-input"
          placeholder="粘贴本人或授权视频链接，也可以粘贴完整分享口令"
          @input="emit('update:videoLink', $event.target.value)"
        ></textarea>
      </label>

      <div class="main-action">
        <button class="primary-button primary-button--full main-action__button" type="button" :disabled="isReading || transcriptionLoading" @click="emit('extract-script')">
          {{ primaryButtonText }}
        </button>
        <div class="button-row button-row--compact">
          <button class="ghost-button ghost-button--small" type="button" @click="triggerFileSelect">本地上传</button>
          <button class="ghost-button ghost-button--small" type="button" @click="emit('manual-input')">手动输入</button>
        </div>
        <p class="helper-text main-action__status">{{ flowStatusText }}</p>
      </div>

      <p v-if="uploadedFileName" class="helper-text">已选择文件：{{ uploadedFileName }}</p>
      <div v-if="isManualTextMode" class="material-lamp-row">
        <span class="status-dot status-dot--idle"></span>
        <strong>当前模式：手动文案</strong>
      </div>
      <div v-if="!material && !isManualTextMode" class="material-lamp-row">
        <span class="status-dot" :class="`status-dot--${materialLamp}`"></span>
        <strong>{{ materialLampText }}</strong>
      </div>
      <p v-if="materialFailureText" class="helper-text helper-text--error">{{ materialFailureText }}</p>

      <MaterialExtractCard
        v-if="material"
        :material="material"
        :material-lamp="materialLamp"
        :material-lamp-text="materialLampText"
        @view-assets="assetDrawerOpen = true"
      />

      <input ref="fileInputRef" class="hidden-input" type="file" accept="video/*" @change="onFileChange" />

      <label class="field script-result">
        <div class="field-headline">
          <span class="field-label">文案结果</span>
          <span class="field-meta">{{ charCount }} 字</span>
        </div>
        <div class="field-subline">
          <span class="field-meta">{{ scriptSourceLabel }}</span>
        </div>
        <textarea
          :value="rawScript"
          class="text-area text-area--tall"
          :placeholder="isManualTextMode ? '直接输入你的口播文案，后续可以改写、配音或生成字幕。' : '提取完成后，这里会回填视频口播文案。你也可以直接编辑。'"
          @input="emit('update:rawScript', $event.target.value)"
        ></textarea>
        <div class="button-row button-row--compact">
          <button class="secondary-button secondary-button--small" type="button" :disabled="!rawScript.trim()" @click="copyText(rawScript, '已复制文案')">
            复制文案
          </button>
          <button
            v-if="canSetAsCurrentScript"
            class="primary-button primary-button--small"
            type="button"
            :disabled="!canSetAsCurrentScript"
            @click="emit('set-current-script')"
          >
            设为成片文案
          </button>
        </div>
        <p v-if="copyHint" class="helper-text helper-text--success">{{ copyHint }}</p>
      </label>
    </div>

    <MaterialAssetDrawer :material="material" :open="assetDrawerOpen" @close="assetDrawerOpen = false" />
  </section>
</template>
