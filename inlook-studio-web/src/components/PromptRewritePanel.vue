<script setup>
import { computed } from 'vue'

const props = defineProps({
  promptText: {
    type: String,
    required: true,
  },
  selectedPlatform: {
    type: String,
    required: true,
  },
  selectedLength: {
    type: String,
    required: true,
  },
  selectedTone: {
    type: String,
    required: true,
  },
  keepKeywords: {
    type: String,
    required: true,
  },
  templates: {
    type: Array,
    required: true,
  },
  platforms: {
    type: Array,
    required: true,
  },
  lengths: {
    type: Array,
    required: true,
  },
  tones: {
    type: Array,
    required: true,
  },
  rewriteResults: {
    type: Array,
    required: true,
  },
  activeResultId: {
    type: String,
    required: true,
  },
  isRewriting: {
    type: Boolean,
    default: false,
  },
  featureReady: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  'update:promptText',
  'update:selectedPlatform',
  'update:selectedLength',
  'update:selectedTone',
  'update:keepKeywords',
  'append-template',
  'rewrite',
  'generate-versions',
  'use-result',
  'optimize-result',
  'copy-result',
])

const resultHeadline = computed(() => {
  return props.isRewriting ? '正在生成改写结果...' : '改写结果'
})
</script>

<template>
  <section class="panel panel--feature">
    <div class="panel-header">
      <div>
        <h2>2. 提示词改写</h2>
        <p>核心能力：让文案更像你的内容，而不是模板稿。</p>
      </div>
      <span class="panel-badge">核心模块</span>
    </div>

    <div class="panel-body stack-md">
      <label class="field">
        <span class="field-label">改写提示词</span>
        <textarea
          :value="promptText"
          class="text-area text-area--prompt"
          placeholder="请输入你想怎么改，例如：把这段文案改成普通人真实分享口吻，开头更抓人，不要太营销，适合抖音 30 秒口播。"
          @input="emit('update:promptText', $event.target.value)"
        ></textarea>
      </label>

      <div class="field">
        <span class="field-label">提示词模板</span>
        <div class="chip-group">
          <button
            v-for="template in templates"
            :key="template"
            class="chip-button"
            type="button"
            @click="emit('append-template', template)"
          >
            {{ template }}
          </button>
        </div>
      </div>

      <div class="control-grid">
        <label class="field">
          <span class="field-label">目标平台</span>
          <select
            class="select-input"
            :value="selectedPlatform"
            @change="emit('update:selectedPlatform', $event.target.value)"
          >
            <option v-for="platform in platforms" :key="platform" :value="platform">{{ platform }}</option>
          </select>
        </label>

        <label class="field">
          <span class="field-label">文案长度</span>
          <select
            class="select-input"
            :value="selectedLength"
            @change="emit('update:selectedLength', $event.target.value)"
          >
            <option v-for="length in lengths" :key="length" :value="length">{{ length }}</option>
          </select>
        </label>

        <label class="field">
          <span class="field-label">语气风格</span>
          <select
            class="select-input"
            :value="selectedTone"
            @change="emit('update:selectedTone', $event.target.value)"
          >
            <option v-for="tone in tones" :key="tone" :value="tone">{{ tone }}</option>
          </select>
        </label>
      </div>

      <label class="field">
        <span class="field-label">保留关键词</span>
        <input
          :value="keepKeywords"
          class="text-input"
          type="text"
          placeholder="例如：真实分享、停留率、自然表达"
          @input="emit('update:keepKeywords', $event.target.value)"
        />
      </label>

      <div class="button-row">
        <button class="primary-button" type="button" :disabled="!featureReady || isRewriting" @click="emit('rewrite')">
          {{ featureReady ? (isRewriting ? '改写中...' : '开始改写') : '待接入' }}
        </button>
        <button class="secondary-button" type="button" :disabled="!featureReady || isRewriting" @click="emit('generate-versions')">
          {{ featureReady ? '生成 3 个版本' : '待接入' }}
        </button>
      </div>
      <p v-if="!featureReady" class="helper-text">AI 改写与增强本阶段仅保留界面，尚未接入真实服务。</p>

      <div class="result-section">
        <div class="field-headline">
          <span class="field-label">{{ resultHeadline }}</span>
          <span class="field-meta">可直接选为当前成片文案</span>
        </div>

        <div class="result-list">
          <article
            v-for="result in rewriteResults"
            :key="result.id"
            class="result-card"
            :class="{ 'result-card--active': result.id === activeResultId }"
          >
            <div class="result-card__head">
              <div>
                <h3>{{ result.title }}</h3>
                <p>{{ result.tag }}</p>
              </div>
              <span class="result-card__id">{{ result.id }}</span>
            </div>
            <p class="result-card__body">{{ result.content }}</p>
            <div class="button-row button-row--compact">
              <button class="primary-button primary-button--small" type="button" :disabled="!featureReady" @click="emit('use-result', result.id)">
                使用此版本
              </button>
              <button class="secondary-button secondary-button--small" type="button" :disabled="!featureReady" @click="emit('optimize-result', result.id)">
                继续优化
              </button>
              <button class="secondary-button secondary-button--small" type="button" :disabled="!featureReady" @click="emit('copy-result', result.content)">
                复制文案
              </button>
            </div>
          </article>
        </div>
      </div>
    </div>
  </section>
</template>
