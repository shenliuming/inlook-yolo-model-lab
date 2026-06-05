<script setup>
defineProps({
  title: {
    type: String,
    default: '运行日志',
  },
  logs: {
    type: String,
    default: '等待开始。',
  },
})
</script>

<template>
  <section class="card section">
    <div class="section-title">
      <h2>{{ title }}</h2>
    </div>
    <pre class="json-view task-log">{{ logs }}</pre>
  </section>
</template>

<style scoped>
.task-log {
  max-height: 320px;
  overflow: auto;
}
</style>
