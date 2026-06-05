<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  material: {
    type: Object,
    default: null,
  },
  open: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['close'])
const failedImages = ref([])
const copyHint = ref('')

watch(
  () => props.open,
  (open) => {
    if (open) {
      failedImages.value = []
      copyHint.value = ''
    }
  },
)

const visibleImages = computed(() =>
  (props.material?.images || []).filter((item) => item?.url && !failedImages.value.includes(item.url)),
)

const copyText = async (text, hint = '已复制') => {
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

const openUrl = (url) => {
  if (!url) return
  window.open(url, '_blank', 'noopener,noreferrer')
}

const downloadUrl = (url, filename) => {
  if (!url) return
  const link = document.createElement('a')
  link.href = url
  link.target = '_blank'
  link.rel = 'noreferrer'
  if (filename) link.download = filename
  link.click()
}

const hideBrokenImage = (url) => {
  if (url && !failedImages.value.includes(url)) {
    failedImages.value = [...failedImages.value, url]
  }
}
</script>

<template>
  <teleport to="body">
    <div v-if="open" class="drawer-backdrop" @click.self="emit('close')">
      <aside class="asset-drawer">
        <div class="asset-drawer__header">
          <div>
            <h3>素材详情</h3>
            <p>{{ material?.title || '当前素材' }}</p>
          </div>
          <button class="icon-button" type="button" @click="emit('close')">✕</button>
        </div>

        <div class="asset-drawer__body">
          <section class="sub-panel">
            <div class="field-headline">
              <span class="field-label">视频素材</span>
              <div class="button-row button-row--compact">
                <button class="secondary-button secondary-button--small" type="button" @click="downloadUrl(material?.localVideoUrl || material?.video?.url, 'source-video.mp4')">下载</button>
                <button class="secondary-button secondary-button--small" type="button" @click="copyText(material?.localVideoUrl || material?.video?.url, '已复制视频链接')">复制</button>
                <button class="secondary-button secondary-button--small" type="button" @click="openUrl(material?.localVideoUrl || material?.video?.url)">打开</button>
              </div>
            </div>

            <div v-if="material?.video?.sources?.length" class="asset-source-list">
              <div v-for="source in material.video.sources" :key="`${source.label}-${source.url}`" class="asset-source-item">
                <div>
                  <strong>{{ source.label || '备用源' }}</strong>
                  <p>{{ source.width || 0 }} × {{ source.height || 0 }}</p>
                </div>
                <div class="button-row button-row--compact">
                  <button class="secondary-button secondary-button--small" type="button" @click="copyText(source.url)">复制</button>
                  <button class="secondary-button secondary-button--small" type="button" @click="openUrl(source.url)">打开</button>
                </div>
              </div>
            </div>
            <p v-else class="helper-text">暂无备用视频源</p>
          </section>

          <section class="sub-panel">
            <span class="field-label">图片素材</span>
            <div v-if="visibleImages.length" class="asset-image-grid">
              <article v-for="image in visibleImages" :key="image.url" class="asset-image-card">
                <img :src="image.thumbnailUrl || image.url" :alt="image.label || '图片素材'" @error="hideBrokenImage(image.url)" />
                <strong>{{ image.label || '图片素材' }}</strong>
                <div class="button-row button-row--compact">
                  <button class="secondary-button secondary-button--small" type="button" @click="openUrl(image.url)">打开</button>
                  <button class="secondary-button secondary-button--small" type="button" @click="downloadUrl(image.url)">下载</button>
                  <button class="secondary-button secondary-button--small" type="button" @click="copyText(image.url)">复制</button>
                </div>
              </article>
            </div>
            <p v-else class="helper-text">暂无可用图片素材。</p>
          </section>
        </div>

        <p v-if="copyHint" class="asset-drawer__hint">{{ copyHint }}</p>
      </aside>
    </div>
  </teleport>
</template>
