<script setup>
import { computed } from 'vue'

const props = defineProps({
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
  selectedVoiceId: {
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
  canCreateVoiceFromMaterial: {
    type: Boolean,
    default: false,
  },
  creatingVoiceFromMaterial: {
    type: Boolean,
    default: false,
  },
  hasCurrentMaterialVoice: {
    type: Boolean,
    default: false,
  },
  synthesisAudioUrl: {
    type: String,
    default: '',
  },
  voicePreviewAudioUrl: {
    type: String,
    default: '',
  },
  voiceReferenceAudioUrl: {
    type: String,
    default: '',
  },
  voiceQualityWarnings: {
    type: Array,
    default: () => [],
  },
  voiceCreateDialogVisible: {
    type: Boolean,
    default: false,
  },
  voiceCreateLoading: {
    type: Boolean,
    default: false,
  },
  voiceCreateName: {
    type: String,
    default: '',
  },
  voiceCreateAudioName: {
    type: String,
    default: '',
  },
  voiceCreateConsent: {
    type: Boolean,
    default: false,
  },
  voiceCreateError: {
    type: String,
    default: '',
  },
  currentScript: {
    type: String,
    default: '',
  },
  currentScriptSource: {
    type: String,
    default: 'empty',
  },
  currentScriptTitle: {
    type: String,
    default: '',
  },
  currentAudio: {
    type: Object,
    default: null,
  },
  canGenerateHumanVideo: {
    type: Boolean,
    default: false,
  },
  humanGenerateHint: {
    type: String,
    default: '请先输入或选择一版成片文案。',
  },
})

defineEmits([
  'update:selectedVoiceId',
  'update:selectedEmotion',
  'update:speed',
  'update:volume',
  'update:selectedAvatarId',
  'update:selectedScene',
  'update:selectedBackground',
  'preview-voice',
  'generate-voice',
  'generate-human-video',
  'open-voice-create',
  'create-voice-from-material',
  'close-voice-create',
  'voice-create-audio-selected',
  'create-voice',
  'update:voiceCreateName',
  'update:voiceCreateConsent',
])

const currentScriptLength = computed(() => props.currentScript.trim().length)
const hasCurrentScript = computed(() => currentScriptLength.value > 0)
const hasCurrentAudio = computed(() => Boolean(props.currentAudio?.audioUrl))
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
          <div class="info-block">
            <span>当前配音文案：{{ hasCurrentScript ? currentScriptTitle || '成片文案' : '未选择' }} · 字数：{{ currentScriptLength }}</span>
            <span v-if="!hasCurrentScript">请先选择一版成片文案，或将手动文案设为成片文案</span>
          </div>

          <div class="field">
            <span class="field-label">我的音色</span>
            <div class="button-row">
              <button class="secondary-button" type="button" @click="$emit('open-voice-create')">创建音色</button>
              <button
                class="secondary-button"
                type="button"
                :disabled="!canCreateVoiceFromMaterial || creatingVoiceFromMaterial"
                @click="$emit('create-voice-from-material')"
              >
                {{ creatingVoiceFromMaterial ? '创建中...' : hasCurrentMaterialVoice ? '使用视频参考音频' : '从视频提取参考音频' }}
              </button>
            </div>
            <span class="field-meta">{{ trainingStatus }}</span>
          </div>

          <label class="field">
            <span class="field-label">音色</span>
            <select class="select-input" :value="selectedVoiceId" @change="$emit('update:selectedVoiceId', $event.target.value)">
              <option v-if="!voices.length" value="" disabled>暂无可用音色</option>
              <option v-for="voice in voices" :key="voice.voiceId" :value="voice.voiceId">
                {{ voice.name }}
              </option>
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
            <button class="primary-button" type="button" :disabled="voiceGenerating || !hasCurrentScript" @click="$emit('generate-voice')">
              {{ voiceGenerating ? '生成中...' : '生成配音' }}
            </button>
          </div>
          <div v-if="voiceReferenceAudioUrl" class="audio-section">
            <span class="field-meta">参考音频试听</span>
            <audio class="audio-player" :src="voiceReferenceAudioUrl" controls></audio>
            <span class="field-meta">这里应该是清晰人声。如果听起来像背景音乐、杂音或机器声，请上传单独音频。</span>
            <span v-if="voiceQualityWarnings.length" class="field-meta">{{ voiceQualityWarnings.join(' ') }}</span>
          </div>
          <div v-if="voicePreviewAudioUrl" class="audio-section">
            <span class="field-meta">音色试听</span>
            <audio class="audio-player" :src="voicePreviewAudioUrl" controls></audio>
          </div>
          <div v-if="synthesisAudioUrl" class="audio-section">
            <span class="field-meta">正式配音</span>
            <audio class="audio-player" :src="synthesisAudioUrl" controls></audio>
          </div>
        </div>
      </div>

      <div v-if="voiceCreateDialogVisible" class="voice-dialog-backdrop" @click.self="$emit('close-voice-create')">
        <div class="voice-dialog">
          <div class="voice-dialog__header">
            <div>
              <h3>创建音色</h3>
              <p>上传本人或已授权的清晰人声，用于后续配音生成。</p>
            </div>
            <button class="icon-button" type="button" :disabled="voiceCreateLoading" @click="$emit('close-voice-create')">×</button>
          </div>

          <div class="stack-md">
            <label class="field">
              <span class="field-label">音色名称</span>
              <input
                class="text-input"
                type="text"
                :value="voiceCreateName"
                :disabled="voiceCreateLoading"
                placeholder="我的音色"
                @input="$emit('update:voiceCreateName', $event.target.value)"
              />
            </label>

            <div class="field">
              <span class="field-label">参考音频</span>
              <div class="button-row">
                <label class="secondary-button file-button">
                  上传音频
                  <input
                    type="file"
                    accept="audio/*"
                    class="hidden-input"
                    :disabled="voiceCreateLoading"
                    @change="$emit('voice-create-audio-selected', $event)"
                  />
                </label>
              </div>
              <span class="field-meta">{{ voiceCreateAudioName || '请选择 10 秒以上的清晰人声' }}</span>
            </div>

            <div class="info-block">
              建议 30 秒以上，环境安静，不要有背景音乐，普通说话即可。录制音频功能后续接入。
            </div>

            <label class="consent-row">
              <input
                type="checkbox"
                :checked="voiceCreateConsent"
                :disabled="voiceCreateLoading"
                @change="$emit('update:voiceCreateConsent', $event.target.checked)"
              />
              <span>我确认该声音属于本人或已获得授权，仅用于合法内容创作。</span>
            </label>

            <p v-if="voiceCreateError" class="inline-error">{{ voiceCreateError }}</p>

            <div class="button-row button-row--end">
              <button class="secondary-button" type="button" :disabled="voiceCreateLoading" @click="$emit('close-voice-create')">
                取消
              </button>
              <button
                class="primary-button"
                type="button"
                :disabled="voiceCreateLoading || !voiceCreateConsent || !voiceCreateAudioName"
                @click="$emit('create-voice')"
              >
                {{ voiceCreateLoading ? '创建中...' : '创建音色' }}
              </button>
            </div>
          </div>
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

        <div class="info-block">
          <span>数字人输入：文案 {{ hasCurrentScript ? '已选择' : '未选择' }} · 配音 {{ hasCurrentAudio ? '已生成' : '未生成' }}</span>
          <span>{{ humanGenerateHint }}</span>
        </div>

        <button
          class="primary-button primary-button--full"
          type="button"
          :disabled="humanGenerating || !canGenerateHumanVideo"
          @click="$emit('generate-human-video')"
        >
          {{ humanGenerating ? '生成中...' : canGenerateHumanVideo ? '生成数字人口播视频' : '数字人待准备' }}
        </button>
      </div>
    </div>
  </section>
</template>
