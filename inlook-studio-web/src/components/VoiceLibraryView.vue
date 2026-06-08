<script setup>
import { computed, ref } from 'vue'
import { apiUrl } from '../api/client'

const props = defineProps({
  voices: {
    type: Array,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  busyVoiceId: {
    type: String,
    default: '',
  },
  selectedVoiceId: {
    type: String,
    default: '',
  },
  previewAudioUrl: {
    type: String,
    default: '',
  },
  previewVoiceId: {
    type: String,
    default: '',
  },
  message: {
    type: String,
    default: '',
  },
})

const emit = defineEmits([
  'return-workbench',
  'refresh',
  'use-voice',
  'rename-voice',
  'delete-voice',
  'preview-voice',
])

const editingVoiceId = ref('')
const editingName = ref('')

const customVoices = computed(() => props.voices.filter((voice) => voice.type === 'custom'))
const hasVoices = computed(() => props.voices.length > 0)

const typeLabel = (type) => {
  if (type === 'builtin') return '内置'
  if (type === 'custom') return '自定义'
  return type || '--'
}

const sourceLabel = (source, type) => {
  if (type === 'builtin' || source === 'builtin') return '内置'
  if (source === 'current_video') return '当前视频'
  if (source === 'upload') return '上传音频'
  return source || '--'
}

const formatTime = (value) => {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (num) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const resolveAudioUrl = (value) => {
  const url = String(value || '')
  if (!url) return ''
  return /^https?:\/\//i.test(url) ? url : apiUrl(url)
}

const startRename = (voice) => {
  editingVoiceId.value = voice.voiceId
  editingName.value = voice.name || ''
}

const cancelRename = () => {
  editingVoiceId.value = ''
  editingName.value = ''
}

const submitRename = (voice) => {
  const nextName = editingName.value.trim()
  if (!nextName || nextName === voice.name) {
    cancelRename()
    return
  }
  emit('rename-voice', { voiceId: voice.voiceId, name: nextName })
  cancelRename()
}
</script>

<template>
  <section class="voice-library">
    <div class="panel-header">
      <div>
        <h2>音色库</h2>
        <p>管理你的自定义音色、参考音频和试听结果。</p>
      </div>
      <div class="button-row button-row--compact">
        <button class="secondary-button secondary-button--small" type="button" :disabled="loading" @click="emit('refresh')">
          刷新
        </button>
        <button class="primary-button primary-button--small" type="button" @click="emit('return-workbench')">
          返回工作台
        </button>
      </div>
    </div>

    <p v-if="message" class="helper-text">{{ message }}</p>

    <div v-if="!hasVoices && !loading" class="panel voice-library__empty">
      <strong>暂无自定义音色。</strong>
      <p>你可以在工作台中从当前视频创建音色，或上传参考音频创建音色。</p>
      <button class="primary-button" type="button" @click="emit('return-workbench')">
        返回工作台创建音色
      </button>
    </div>

    <div v-else class="voice-library__table">
      <div class="voice-library__head">
        <span>名称</span>
        <span>类型</span>
        <span>来源</span>
        <span>引擎</span>
        <span>状态</span>
        <span>创建时间</span>
        <span>最后使用时间</span>
        <span>操作</span>
      </div>

      <div class="voice-library__body">
        <div v-if="loading" class="voice-library__row voice-library__row--empty">
          正在读取音色库...
        </div>

        <article v-for="voice in voices" :key="voice.voiceId" class="voice-library__row">
          <div>
            <template v-if="editingVoiceId === voice.voiceId">
              <input
                v-model="editingName"
                class="text-input voice-library__name-input"
                type="text"
                @keydown.enter.prevent="submitRename(voice)"
                @keydown.esc.prevent="cancelRename"
              />
              <div class="button-row button-row--compact">
                <button class="primary-button primary-button--small" type="button" @click="submitRename(voice)">保存</button>
                <button class="secondary-button secondary-button--small" type="button" @click="cancelRename">取消</button>
              </div>
            </template>
            <template v-else>
              <strong>{{ voice.name || voice.voiceId }}</strong>
              <span v-if="voice.voiceId === selectedVoiceId" class="field-meta">当前项目已选择</span>
            </template>
          </div>
          <span>{{ typeLabel(voice.type) }}</span>
          <span>{{ sourceLabel(voice.source, voice.type) }}</span>
          <span>{{ voice.engine === 'cosyvoice' ? 'CosyVoice' : voice.engine || '--' }}</span>
          <span>{{ voice.status || '--' }}</span>
          <span>{{ formatTime(voice.createdAt) }}</span>
          <span>{{ formatTime(voice.lastUsedAt) }}</span>
          <div class="voice-library__actions">
            <button class="primary-button primary-button--small" type="button" @click="emit('use-voice', voice)">
              使用到当前项目
            </button>
            <button
              class="secondary-button secondary-button--small"
              type="button"
              :disabled="voice.type === 'builtin' || busyVoiceId === voice.voiceId"
              @click="startRename(voice)"
            >
              修改名称
            </button>
            <button
              class="secondary-button secondary-button--small"
              type="button"
              :disabled="voice.type === 'builtin' || busyVoiceId === voice.voiceId"
              @click="emit('delete-voice', voice)"
            >
              删除
            </button>
            <audio
              v-if="voice.referenceAudioUrl"
              class="voice-library__audio"
              :src="resolveAudioUrl(voice.referenceAudioUrl)"
              controls
            ></audio>
            <button v-else class="secondary-button secondary-button--small" type="button" disabled>
              播放参考音频
            </button>
            <button
              class="secondary-button secondary-button--small"
              type="button"
              :disabled="busyVoiceId === voice.voiceId"
              @click="emit('preview-voice', voice)"
            >
              {{ busyVoiceId === voice.voiceId ? '试听中...' : '试听音色' }}
            </button>
            <audio
              v-if="previewVoiceId === voice.voiceId && previewAudioUrl"
              class="voice-library__audio"
              :src="resolveAudioUrl(previewAudioUrl)"
              controls
            ></audio>
          </div>
        </article>
      </div>
    </div>

    <div v-if="customVoices.length === 0 && hasVoices && !loading" class="panel voice-library__empty">
      <strong>暂无自定义音色。</strong>
      <p>你可以在工作台中从当前视频创建音色，或上传参考音频创建音色。</p>
      <button class="primary-button" type="button" @click="emit('return-workbench')">
        返回工作台创建音色
      </button>
    </div>
  </section>
</template>
