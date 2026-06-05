<script setup>
import { computed } from 'vue'

const props = defineProps({
  material: {
    type: Object,
    default: null,
  },
  readStatus: {
    type: String,
    default: '',
  },
  materialLamp: {
    type: String,
    default: 'idle',
  },
  materialLampText: {
    type: String,
    default: '未准备',
  },
  materialLocalReady: {
    type: Boolean,
    default: false,
  },
  previewState: {
    type: String,
    required: true,
  },
  previewTitle: {
    type: String,
    required: true,
  },
  currentStep: {
    type: String,
    required: true,
  },
  progress: {
    type: Number,
    required: true,
  },
  outputPath: {
    type: String,
    required: true,
  },
  renderingMeta: {
    type: Object,
    required: true,
  },
  finalVideoUrl: {
    type: String,
    default: '',
  },
  finalDownloadUrl: {
    type: String,
    default: '',
  },
})

const formatBytes = (value) => {
  const size = Number(value || 0)
  if (!size) return '--'
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

const hasMaterial = computed(() => Boolean(props.materialLocalReady && props.material?.localVideoUrl))
const hasFinal = computed(() => Boolean(props.finalVideoUrl))
const previewTitleText = computed(() => {
  if (hasFinal.value) return '成片预览'
  if (hasMaterial.value) return '素材预览'
  return '预览'
})
const previewStatusText = computed(() => {
  if (hasFinal.value) return '成片已生成'
  if (hasMaterial.value) return '素材已读取，待提取口播文案'
  return '暂无素材预览'
})
</script>

<template>
  <section class="panel panel--preview">
    <div class="panel-header">
      <div>
        <h2>5. {{ previewTitleText }}</h2>
        <p>{{ previewStatusText }}</p>
      </div>
      <span class="panel-status">9:16</span>
    </div>

    <div class="panel-body stack-md">
      <div class="preview-frame">
        <template v-if="hasFinal">
          <div class="preview-material preview-material--final">
            <video class="preview-material__video" :src="finalVideoUrl" controls playsinline></video>
            <span class="preview-badge">成片预览</span>
          </div>
        </template>
        <template v-else-if="hasMaterial">
          <div class="preview-material">
            <video
              v-if="material?.localVideoUrl"
              class="preview-material__video"
              :src="material.localVideoUrl"
              :poster="material.coverUrl || undefined"
              controls
              playsinline
            ></video>
            <img v-else class="preview-material__image" :src="material.coverUrl" alt="素材封面" />
            <span class="preview-badge">素材预览</span>
          </div>
        </template>
        <div v-else class="preview-idle">
          <div class="preview-idle__screen"></div>
          <p>暂无素材预览</p>
        </div>

        <div v-if="previewState === 'rendering'" class="preview-overlay">
          <div class="preview-rendering__screen">
            <div class="preview-rendering__pulse"></div>
            <div class="preview-rendering__content">
              <strong>处理中</strong>
              <span>{{ currentStep }}</span>
            </div>
          </div>
          <div class="progress-block">
            <div class="progress-track">
              <div class="progress-bar" :style="{ width: `${progress}%` }"></div>
            </div>
            <span>{{ progress }}%</span>
          </div>
        </div>
      </div>

      <div class="preview-meta">
        <template v-if="hasFinal">
          <div class="meta-row"><span>当前状态</span><strong>成片已生成</strong></div>
          <div class="meta-row"><span>输出路径</span><strong>{{ outputPath }}</strong></div>
        </template>
        <template v-else-if="material">
          <div class="meta-row"><span>当前状态</span><strong>{{ materialLampText }}</strong></div>
          <div class="meta-row"><span>作者</span><strong>{{ material.authorName || '--' }}</strong></div>
          <div class="meta-row"><span>时长</span><strong>{{ material.video?.duration || 0 }}s</strong></div>
          <div class="meta-row"><span>分辨率</span><strong>{{ material.video?.width || 0 }} × {{ material.video?.height || 0 }}</strong></div>
          <div class="meta-row"><span>文件大小</span><strong>{{ formatBytes(material.video?.fileSize) }}</strong></div>
        </template>
        <template v-else>
          <div class="meta-row"><span>当前步骤</span><strong>{{ currentStep }}</strong></div>
          <div class="meta-row"><span>总进度</span><strong>{{ progress }}%</strong></div>
          <div class="meta-row"><span>原始视频时长</span><strong>{{ renderingMeta.sourceDuration }}</strong></div>
          <div class="meta-row"><span>配音时长</span><strong>{{ renderingMeta.voiceDuration }}</strong></div>
          <div class="meta-row"><span>成片时长</span><strong>{{ renderingMeta.finalDuration }}</strong></div>
          <div class="meta-row"><span>输出路径</span><strong>{{ outputPath }}</strong></div>
        </template>
      </div>

      <div v-if="hasFinal" class="button-row">
        <a
          v-if="finalDownloadUrl"
          class="secondary-button secondary-button--small link-button"
          :href="finalDownloadUrl"
          target="_blank"
          rel="noreferrer"
        >
          下载结果
        </a>
        <button v-else class="secondary-button secondary-button--small" type="button" :disabled="true">下载结果</button>
      </div>
      <div v-else-if="material" class="button-row">
        <a
          class="ghost-button ghost-button--small link-button"
          :href="material.localVideoUrl || '#'"
          target="_blank"
          rel="noreferrer"
          :aria-disabled="!material.localVideoUrl"
          @click.prevent="!material.localVideoUrl"
        >
          打开视频
        </a>
        <a
          class="ghost-button ghost-button--small link-button"
          :href="material.coverUrl || '#'"
          target="_blank"
          rel="noreferrer"
          :aria-disabled="!material.coverUrl"
          @click.prevent="!material.coverUrl"
        >
          打开封面
        </a>
      </div>
      <template v-else>
        <div class="button-row">
          <button class="secondary-button" type="button" :disabled="true">预览待接入</button>
          <button class="secondary-button" type="button" :disabled="true">打开文件夹待接入</button>
        </div>
        <button class="secondary-button secondary-button--full" type="button" :disabled="true">导出素材包待接入</button>
      </template>
    </div>
  </section>
</template>
