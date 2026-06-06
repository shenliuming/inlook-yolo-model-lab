<script setup>
import { computed } from 'vue'

const props = defineProps({
  promptText: {
    type: String,
    required: true,
  },
  templates: {
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
  rewriteFailed: {
    type: Boolean,
    default: false,
  },
  featureReady: {
    type: Boolean,
    default: false,
  },
  unavailableMessage: {
    type: String,
    default: 'AI 改写服务未配置，请先配置模型服务。',
  },
  sourceUsageText: {
    type: String,
    default: '请先提取或输入文案',
  },
  canUsePlatformText: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  'update:promptText',
  'append-template',
  'rewrite',
  'rewrite-platform',
  'use-result',
  'optimize-result',
  'copy-result',
])

const resultHeadline = computed(() => {
  return props.isRewriting ? '正在生成改写结果...' : '改写结果'
})

const primaryButtonText = computed(() => {
  if (props.isRewriting) return '生成中...'
  if (props.rewriteFailed) return '重试'
  if (props.rewriteResults.length) return '重新改写'
  return '开始改写'
})

const showUnavailableHint = computed(() => {
  if (props.featureReady || props.canUsePlatformText || !props.unavailableMessage) return false
  return props.unavailableMessage !== props.sourceUsageText
})

const emptyResultText = computed(() => {
  if (props.featureReady) return '暂无改写结果，请输入文案后调用真实 AI 生成。'
  if (props.canUsePlatformText) return '确认使用平台文案后才会显示改写结果。'
  if (props.unavailableMessage.includes('未配置') || props.unavailableMessage.includes('状态获取失败')) {
    return '配置模型服务后才会显示真实改写结果。'
  }
  return '提取口播或手动输入后才会显示改写结果。'
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

      <p class="helper-text">{{ sourceUsageText }}</p>

      <div class="button-row">
        <button class="primary-button" type="button" :disabled="!featureReady || isRewriting" @click="emit('rewrite')">
          {{ primaryButtonText }}
        </button>
      </div>
      <p v-if="showUnavailableHint" class="helper-text">{{ unavailableMessage }}</p>
      <button
        v-if="canUsePlatformText"
        class="ghost-button ghost-button--small"
        type="button"
        :disabled="isRewriting"
        @click="emit('rewrite-platform')"
      >
        仍用平台文案改写
      </button>

      <div class="result-section">
        <div class="field-headline">
          <span class="field-label">{{ resultHeadline }}</span>
          <span class="field-meta">可直接选为当前成片文案</span>
        </div>

        <div class="result-list">
          <p v-if="!rewriteResults.length" class="helper-text">
            {{ emptyResultText }}
          </p>
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
