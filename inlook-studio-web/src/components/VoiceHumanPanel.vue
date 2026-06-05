<script setup>
defineProps({
  voices: {
    type: Array,
    required: true,
  },
  emotions: {
    type: Array,
    required: true,
  },
  avatars: {
    type: Array,
    required: true,
  },
  sceneOptions: {
    type: Array,
    required: true,
  },
  backgroundOptions: {
    type: Array,
    required: true,
  },
  selectedVoice: {
    type: String,
    required: true,
  },
  selectedEmotion: {
    type: String,
    required: true,
  },
  speed: {
    type: Number,
    required: true,
  },
  volume: {
    type: Number,
    required: true,
  },
  selectedAvatarId: {
    type: String,
    required: true,
  },
  selectedScene: {
    type: String,
    required: true,
  },
  selectedBackground: {
    type: String,
    required: true,
  },
  previewingVoice: {
    type: Boolean,
    default: false,
  },
  voiceGenerating: {
    type: Boolean,
    default: false,
  },
  humanGenerating: {
    type: Boolean,
    default: false,
  },
  voiceStatus: {
    type: String,
    required: true,
  },
  humanStatus: {
    type: String,
    required: true,
  },
  trainingStatus: {
    type: String,
    default: '未创建音色',
  },
  trainingReady: {
    type: Boolean,
    default: false,
  },
  synthesisAudioUrl: {
    type: String,
    default: '',
  },
  referenceAudioName: {
    type: String,
    default: '',
  },
})

defineEmits([
  'update:selectedVoice',
  'update:selectedEmotion',
  'update:speed',
  'update:volume',
  'update:selectedAvatarId',
  'update:selectedScene',
  'update:selectedBackground',
  'preview-voice',
  'generate-voice',
  'generate-human-video',
  'reference-audio-selected',
  'create-training',
])
</script>

<template>
  <section class="panel">
    <div class="panel-header">
      <div>
        <h2>3. 配音与数字人</h2>
        <p>先模拟完整交互，后续再接真实引擎。</p>
      </div>
    </div>

    <div class="panel-body stack-lg">
      <div class="sub-panel">
        <div class="field-headline">
          <span class="field-label">AI 配音</span>
          <span class="field-meta">{{ voiceStatus }}</span>
        </div>

        <div class="stack-md">
          <div class="field">
            <span class="field-label">参考音频</span>
            <div class="button-row">
              <label class="secondary-button file-button">
                选择参考音频
                <input type="file" accept="audio/*" class="hidden-input" @change="$emit('reference-audio-selected', $event)" />
              </label>
              <button class="secondary-button" type="button" @click="$emit('create-training')">创建音色</button>
            </div>
            <span class="field-meta">{{ referenceAudioName || trainingStatus }}</span>
          </div>

          <label class="field">
            <span class="field-label">TTS 声音</span>
            <select class="select-input" :value="selectedVoice" @change="$emit('update:selectedVoice', $event.target.value)">
              <option v-for="voice in voices" :key="voice" :value="voice">{{ voice }}</option>
            </select>
          </label>

          <label class="field">
            <div class="field-headline">
              <span class="field-label">语速</span>
              <span class="field-meta">{{ speed.toFixed(1) }}x</span>
            </div>
            <input class="range-input" type="range" min="0.8" max="1.3" step="0.1" :value="speed" @input="$emit('update:speed', Number($event.target.value))" />
          </label>

          <label class="field">
            <span class="field-label">情绪</span>
            <select class="select-input" :value="selectedEmotion" @change="$emit('update:selectedEmotion', $event.target.value)">
              <option v-for="emotion in emotions" :key="emotion" :value="emotion">{{ emotion }}</option>
            </select>
          </label>

          <label class="field">
            <div class="field-headline">
              <span class="field-label">音量</span>
              <span class="field-meta">{{ volume }}%</span>
            </div>
            <input class="range-input" type="range" min="0" max="100" step="1" :value="volume" @input="$emit('update:volume', Number($event.target.value))" />
          </label>

          <div class="wave-placeholder">
            <span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span>
          </div>

          <div class="button-row">
            <button class="secondary-button" type="button" :disabled="previewingVoice" @click="$emit('preview-voice')">
              {{ previewingVoice ? '试听中...' : '试听' }}
            </button>
            <button class="primary-button" type="button" :disabled="voiceGenerating" @click="$emit('generate-voice')">
              {{ voiceGenerating ? '生成中...' : '生成配音' }}
            </button>
          </div>
          <audio v-if="synthesisAudioUrl" class="audio-player" :src="synthesisAudioUrl" controls></audio>
        </div>
      </div>

      <div class="sub-panel">
        <div class="field-headline">
          <span class="field-label">数字人</span>
          <span class="field-meta">{{ humanStatus }}</span>
        </div>

        <div class="avatar-grid">
          <button
            v-for="avatar in avatars"
            :key="avatar.id"
            type="button"
            class="avatar-card"
            :class="{ 'avatar-card--active': avatar.id === selectedAvatarId }"
            @click="$emit('update:selectedAvatarId', avatar.id)"
          >
            <div class="avatar-card__visual" :style="{ background: avatar.accent }">
              <div class="avatar-silhouette"></div>
            </div>
            <div class="avatar-card__meta">
              <strong>{{ avatar.name }}</strong>
              <span>{{ avatar.role }}</span>
            </div>
          </button>
        </div>

        <div class="control-grid">
          <label class="field">
            <span class="field-label">出镜比例</span>
            <select class="select-input" :value="selectedScene" @change="$emit('update:selectedScene', $event.target.value)">
              <option v-for="item in sceneOptions" :key="item" :value="item">{{ item }}</option>
            </select>
          </label>

          <label class="field">
            <span class="field-label">背景选择</span>
            <select class="select-input" :value="selectedBackground" @change="$emit('update:selectedBackground', $event.target.value)">
              <option v-for="background in backgroundOptions" :key="background" :value="background">{{ background }}</option>
            </select>
          </label>
        </div>

        <button class="primary-button primary-button--full" type="button" :disabled="true" @click="$emit('generate-human-video')">
          数字人待接入
        </button>
      </div>
    </div>
  </section>
</template>
