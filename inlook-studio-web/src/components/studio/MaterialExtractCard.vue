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
})

const emit = defineEmits(['view-assets', 'extract-script'])
const copyHint = ref('')
const visibleTags = computed(() => (props.material?.tags || []).slice(0, 5))
const hiddenTagCount = computed(() => Math.max(0, (props.material?.tags || []).length - visibleTags.value.length))
const sourceCount = computed(() => (props.material?.video?.sources || []).length)
const statusDescription = computed(() => {
  if (props.materialLamp === 'ready') return '素材已可用，可继续提取视频文案'
  if (props.materialLamp === 'processing') return '正在读取素材并校验本地视频'
  if (props.materialLamp === 'failed') return '素材暂不可用，请重试或上传本地视频'
  return '请先读取素材'
})
const tagDisplay = computed(() => visibleTags.value.map((tag) => `#${tag}`).join(' '))
const tagCopyText = computed(() => (props.material?.tags || []).map((tag) => `#${tag}`).join(' '))

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

    <div v-if="material.coverUrl" class="material-card__cover">
      <img :src="material.coverUrl" :alt="material.title || '素材封面'" />
    </div>

    <div class="material-card__metrics">
      <span>时长：{{ material.video?.duration || 0 }}s</span>
      <span>分辨率：{{ material.video?.width || 0 }} × {{ material.video?.height || 0 }}</span>
      <span>大小：{{ formatBytes(material.video?.fileSize) }}</span>
    </div>

    <div v-if="material.title" class="asset-line asset-line--single">
      <span class="asset-line__label">标题：</span>
      <span class="asset-line__text">{{ material.title }}</span>
      <button class="ghost-button ghost-button--small" type="button" @click="copyText(material.title, '已复制标题')">复制</button>
    </div>

    <div class="asset-line asset-line--description">
      <span class="asset-line__label">发布文案：</span>
      <span class="asset-line__text">{{ material.description || '暂无发布文案' }}</span>
      <button class="ghost-button ghost-button--small" type="button" :disabled="!material.description" @click="copyText(material.description, '已复制发布文案')">复制</button>
    </div>

    <div v-if="(material.tags || []).length" class="asset-line asset-line--single">
      <span class="asset-line__label">标签：</span>
      <span class="asset-line__text">{{ tagDisplay }}<template v-if="hiddenTagCount > 0"> +{{ hiddenTagCount }}</template></span>
      <button class="ghost-button ghost-button--small" type="button" @click="copyText(tagCopyText, '已复制标签')">复制</button>
    </div>

    <p class="material-card__subtitle">备用源：共 {{ sourceCount }} 个</p>

    <div class="button-row button-row--compact">
      <button class="secondary-button secondary-button--small" type="button" @click="emit('view-assets')">查看素材</button>
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
