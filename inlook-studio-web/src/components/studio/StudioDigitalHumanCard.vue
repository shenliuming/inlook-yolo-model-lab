<script setup>
const props = defineProps({
  selectedTemplate: {
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
  scriptStatus: {
    type: String,
    default: '未准备',
  },
  audioStatus: {
    type: String,
    default: '未生成',
  },
  voiceModeLabel: {
    type: String,
    default: '',
  },
  generateButtonText: {
    type: String,
    default: '使用当前文案和配音生成数字人视频',
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

defineEmits(['open-template-picker', 'open-manager', 'generate'])
</script>

<template>
  <div class="sub-panel">
    <div class="field-headline">
      <span class="field-label">数字人模板</span>
      <span class="field-meta">{{ status }}</span>
    </div>

    <div class="info-block">
      <span>当前数字人模板：{{ selectedTemplate?.name || '未选择' }}</span>
      <span>当前文案：{{ scriptStatus }}</span>
      <span>当前配音：{{ audioStatus }}</span>
      <span>当前声音方案：{{ voiceModeLabel || '未选择' }}</span>
      <span v-if="outputPath">最近生成：已有本地输出</span>
      <span>{{ generateHint }}</span>
      <span v-if="!backendReady && missingCapabilityHint" class="helper-text--warning">{{ missingCapabilityHint }}</span>
    </div>

    <div class="button-row">
      <button class="secondary-button" type="button" @click="$emit('open-template-picker')">选择数字人模板</button>
      <button class="secondary-button" type="button" @click="$emit('open-manager')">管理模板仓</button>
      <button class="primary-button" type="button" :disabled="generating || !canGenerate || !backendReady" @click="$emit('generate')">
        {{ generating ? '生成中...' : generateButtonText }}
      </button>
    </div>
  </div>
</template>
