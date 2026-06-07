<script setup>
import { computed } from 'vue'

const props = defineProps({
  subtitleEnabled: {
    type: Boolean,
    required: true,
  },
  subtitleStyles: {
    type: Array,
    required: true,
  },
  subtitleStyle: {
    type: String,
    required: true,
  },
  subtitlePositions: {
    type: Array,
    required: true,
  },
  subtitlePosition: {
    type: String,
    required: true,
  },
  bgmOptions: {
    type: Array,
    required: true,
  },
  selectedBgm: {
    type: String,
    required: true,
  },
  narrationVolume: {
    type: Number,
    required: true,
  },
  bgmVolume: {
    type: Number,
    required: true,
  },
  aspectOptions: {
    type: Array,
    required: true,
  },
  selectedAspect: {
    type: String,
    required: true,
  },
  qualityOptions: {
    type: Array,
    required: true,
  },
  selectedQuality: {
    type: String,
    required: true,
  },
  outputPath: {
    type: String,
    required: true,
  },
  saveToLibrary: {
    type: Boolean,
    required: true,
  },
  exportMaterials: {
    type: Boolean,
    required: true,
  },
  rendering: {
    type: Boolean,
    default: false,
  },
  subtitleStatus: {
    type: String,
    default: '未生成字幕',
  },
  subtitleDownloads: {
    type: Object,
    default: () => ({}),
  },
  scriptReady: {
    type: Boolean,
    default: false,
  },
  audioReady: {
    type: Boolean,
    default: false,
  },
  currentScript: {
    type: String,
    default: '',
  },
  currentAudio: {
    type: Object,
    default: null,
  },
})

const subtitleHelperText = computed(() => {
  if (!props.audioReady) {
    return props.scriptReady ? '请先生成配音，生成后才能继续字幕/BGM/导出。' : '请先选择成片文案并生成配音。'
  }
  return props.subtitleStatus || '配音已就绪，可继续字幕与导出设置。'
})

const audioGateDisabled = computed(() => !props.audioReady)

defineEmits([
  'update:subtitleEnabled',
  'update:subtitleStyle',
  'update:subtitlePosition',
  'update:selectedBgm',
  'update:narrationVolume',
  'update:bgmVolume',
  'update:selectedAspect',
  'update:selectedQuality',
  'update:outputPath',
  'update:saveToLibrary',
  'update:exportMaterials',
  'render-video',
])
</script>

<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <h2>4. 字幕、BGM 与导出</h2>
        <p>导出设置保持工具化，不做花哨视觉。</p>
      </div>
    </div>

    <div class="panel-body stack-lg">
      <div class="sub-panel">
        <div class="field-headline">
          <span class="field-label">字幕设置</span>
          <label class="toggle">
            <input
              :checked="subtitleEnabled"
              type="checkbox"
              :disabled="audioGateDisabled"
              @change="$emit('update:subtitleEnabled', $event.target.checked)"
            />
            <span></span>
          </label>
        </div>
        <p class="helper-text">{{ subtitleHelperText }}</p>

        <div class="stack-md">
          <label class="field">
            <span class="field-label">字幕样式</span>
            <select
              class="select-input"
              :value="subtitleStyle"
              :disabled="audioGateDisabled"
              @change="$emit('update:subtitleStyle', $event.target.value)"
            >
              <option v-for="style in subtitleStyles" :key="style" :value="style">{{ style }}</option>
            </select>
          </label>

          <label class="field">
            <span class="field-label">字幕位置</span>
            <select
              class="select-input"
              :value="subtitlePosition"
              :disabled="audioGateDisabled"
              @change="$emit('update:subtitlePosition', $event.target.value)"
            >
              <option v-for="position in subtitlePositions" :key="position" :value="position">{{ position }}</option>
            </select>
          </label>
          <div class="button-row">
            <a v-if="subtitleDownloads.srt" class="secondary-button link-button" :href="subtitleDownloads.srt" target="_blank" rel="noreferrer">下载 SRT</a>
            <a v-if="subtitleDownloads.vtt" class="secondary-button link-button" :href="subtitleDownloads.vtt" target="_blank" rel="noreferrer">下载 VTT</a>
          </div>
        </div>
      </div>

      <div class="sub-panel">
        <span class="field-label">BGM 设置</span>
        <div class="stack-md">
          <label class="field">
            <span class="field-label">BGM 选择</span>
            <select
              class="select-input"
              :value="selectedBgm"
              :disabled="audioGateDisabled"
              @change="$emit('update:selectedBgm', $event.target.value)"
            >
              <option v-for="bgm in bgmOptions" :key="bgm" :value="bgm">{{ bgm }}</option>
            </select>
          </label>

          <label class="field">
            <div class="field-headline">
              <span class="field-label">人声音量</span>
              <span class="field-meta">{{ narrationVolume }}%</span>
            </div>
            <input
              class="range-input"
              type="range"
              min="0"
              max="100"
              :value="narrationVolume"
              :disabled="audioGateDisabled"
              @input="$emit('update:narrationVolume', Number($event.target.value))"
            />
          </label>

          <label class="field">
            <div class="field-headline">
              <span class="field-label">BGM 音量</span>
              <span class="field-meta">{{ bgmVolume }}%</span>
            </div>
            <input
              class="range-input"
              type="range"
              min="0"
              max="100"
              :value="bgmVolume"
              :disabled="audioGateDisabled"
              @input="$emit('update:bgmVolume', Number($event.target.value))"
            />
          </label>
        </div>
      </div>

      <div class="sub-panel">
        <span class="field-label">导出设置</span>
        <div class="control-grid">
          <label class="field">
            <span class="field-label">视频比例</span>
            <select class="select-input" :value="selectedAspect" :disabled="audioGateDisabled" @change="$emit('update:selectedAspect', $event.target.value)">
              <option v-for="aspect in aspectOptions" :key="aspect" :value="aspect">{{ aspect }}</option>
            </select>
          </label>

          <label class="field">
            <span class="field-label">清晰度</span>
            <select class="select-input" :value="selectedQuality" :disabled="audioGateDisabled" @change="$emit('update:selectedQuality', $event.target.value)">
              <option v-for="quality in qualityOptions" :key="quality" :value="quality">{{ quality }}</option>
            </select>
          </label>
        </div>

        <label class="field">
          <span class="field-label">输出目录</span>
          <input :value="outputPath" class="text-input" type="text" :disabled="audioGateDisabled" @input="$emit('update:outputPath', $event.target.value)" />
        </label>

        <label class="checkbox-row">
          <input :checked="saveToLibrary" type="checkbox" :disabled="audioGateDisabled" @change="$emit('update:saveToLibrary', $event.target.checked)" />
          <span>保存到素材库</span>
        </label>

        <label class="checkbox-row">
          <input :checked="exportMaterials" type="checkbox" :disabled="audioGateDisabled" @change="$emit('update:exportMaterials', $event.target.checked)" />
          <span>导出素材包</span>
        </label>

        <button class="primary-button primary-button--full" type="button" :disabled="true || audioGateDisabled" @click="$emit('render-video')">
          {{ audioReady ? '成片导出待接入' : '请先生成配音' }}
        </button>
      </div>
    </div>
  </section>
</template>
