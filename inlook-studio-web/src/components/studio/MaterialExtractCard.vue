<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  material: {
    type: Object,
    required: true,
  },
  materialLamp: {
    type: String,
    default: 'idle',
  },
  materialLampText: {
    type: String,
    default: '未准备',
  },
  transcriptionLoading: {
    type: Boolean,
    default: false,
  },
  canExtract: {
    type: Boolean,
    default: true,
  },
})

const emit = defineEmits(['view-assets', 'extract-script'])
const copyHint = ref('')
const visibleTags = computed(() => (props.material?.tags || []).slice(0, 5))
const hiddenTagCount = computed(() => Math.max(0, (props.material?.tags || []).length - visibleTags.value.length))
const sourceCount = computed(() => (props.material?.video?.sources || []).length)
const downloadStatus = computed(() => {
  const value = String(props.material?.downloadStatus || '')
  const map = {
    not_downloaded: '未下载',
    downloading: '下载中',
    downloaded: '已下载',
    failed: '下载失败',
    missing: '文件丢失',
  }
  return map[value] || '未就绪'
})
const statusDescription = computed(() => {
  if (props.materialLamp === 'ready') return '素材已可用，可继续提取视频文案'
  if (props.materialLamp === 'processing') return '正在读取素材并校验本地视频'
  if (props.materialLamp === 'failed') return '素材暂不可用，请重试或上传本地视频'
  return '请先读取素材'
})

const copyText = async (text, hint) => {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    copyHint.value = hint
    window.setTimeout(() => {
      if (copyHint.value === hint) copyHint.value = ''
    }, 1400)
  } catch {
    copyHint.value = '复制失败'
  }
}

const formatBytes = (value) => {
  const size = Number(value || 0)
  if (!size) return '--'
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

const downloadUrl = (url, filename = 'source-video.mp4') => {
  if (!url) return
  const link = document.createElement('a')
  link.href = url
  link.target = '_blank'
  link.rel = 'noreferrer'
  link.download = filename
  link.click()
}
</script>

<template>
  <article class="material-card">
    <div class="material-card__header">
      <div>
        <strong>素材摘要</strong>
        <p>平台：{{ material.sourceType }} · 作者：{{ material.authorName || '未知' }}</p>
      </div>
      <span class="material-card__status" :class="`material-card__status--${materialLamp}`">
        <span class="status-dot" :class="`status-dot--${materialLamp}`"></span>
        {{ materialLampText }}
      </span>
    </div>

    <p class="material-card__subtitle">{{ statusDescription }}</p>

    <div class="material-card__metrics">
      <span>时长：{{ material.video?.duration || 0 }}s</span>
      <span>分辨率：{{ material.video?.width || 0 }} × {{ material.video?.height || 0 }}</span>
      <span>大小：{{ formatBytes(material.video?.fileSize) }}</span>
    </div>

    <div class="field">
      <span class="field-label">标题</span>
      <div class="info-block"><span>{{ material.title || '未识别到独立标题' }}</span></div>
    </div>

    <div class="field">
      <span class="field-label">发布文案</span>
      <div class="info-block info-block--clamp"><span>{{ material.description || '暂无发布文案' }}</span></div>
    </div>

    <div class="field">
      <span class="field-label">标签</span>
      <div class="chip-group">
        <span v-for="tag in visibleTags" :key="tag" class="chip-button chip-button--small">#{{ tag }}</span>
        <span v-if="hiddenTagCount > 0" class="chip-button chip-button--small">+{{ hiddenTagCount }}</span>
        <span v-if="!(material.tags || []).length" class="helper-text">暂无标签</span>
      </div>
    </div>

    <div class="field">
      <span class="field-label">素材信息</span>
      <div class="material-summary-grid">
        <div class="info-block"><span>备用源：共 {{ sourceCount }} 个</span></div>
        <div class="info-block"><span>下载状态：{{ downloadStatus }}</span></div>
      </div>
    </div>

    <div class="button-row button-row--compact">
      <button class="secondary-button secondary-button--small" type="button" @click="downloadUrl(material.localVideoUrl || material.video?.url)">
        下载视频
      </button>
      <button class="secondary-button secondary-button--small" type="button" @click="emit('view-assets')">查看素材</button>
      <button class="secondary-button secondary-button--small" type="button" @click="copyText(material.description, '已复制文案')">复制文案</button>
      <button
        class="secondary-button secondary-button--small"
        type="button"
        @click="copyText(material.video?.remoteUrl || material.sourceUrl, '已复制视频链接')"
      >
        复制视频链接
      </button>
    </div>

    <p v-if="copyHint" class="helper-text helper-text--success">{{ copyHint }}</p>
  </article>
</template>
