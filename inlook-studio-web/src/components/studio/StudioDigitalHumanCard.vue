<script setup>
const props = defineProps({
  selectedPerson: {
    type: Object,
    default: null,
  },
  status: {
    type: String,
    default: '未选择数字人',
  },
  outputPath: {
    type: String,
    default: '',
  },
  canGenerate: {
    type: Boolean,
    default: false,
  },
  generating: {
    type: Boolean,
    default: false,
  },
  generateHint: {
    type: String,
    default: '',
  },
  backendReady: {
    type: Boolean,
    default: false,
  },
  missingCapabilityHint: {
    type: String,
    default: '',
  },
})

defineEmits(['open-manager', 'generate'])
</script>

<template>
  <div class="sub-panel">
    <div class="field-headline">
      <span class="field-label">数字人模板</span>
      <span class="field-meta">{{ status }}</span>
    </div>

    <div class="info-block">
      <span>当前模板：{{ selectedPerson?.name || '未选择模板' }}</span>
      <span v-if="selectedPerson?.previewUrl || selectedPerson?.preview_url">已配置模板预览，可前往数字人页面播放和切换。</span>
      <span v-if="outputPath">最近生成：已有本地输出</span>
      <span>{{ generateHint }}</span>
      <span v-if="!backendReady && missingCapabilityHint" class="helper-text--warning">{{ missingCapabilityHint }}</span>
    </div>

    <div class="button-row">
      <button class="secondary-button" type="button" @click="$emit('open-manager')">选择模板</button>
      <button class="secondary-button" type="button" @click="$emit('open-manager')">管理模板仓</button>
      <button class="primary-button" type="button" :disabled="generating || !canGenerate || !backendReady" @click="$emit('generate')">
        {{ generating ? '生成中...' : '使用当前配音生成数字人视频' }}
      </button>
    </div>
  </div>
</template>
