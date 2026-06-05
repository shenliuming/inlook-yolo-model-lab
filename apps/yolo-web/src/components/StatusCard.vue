<script setup>
defineProps({
  title: {
    type: String,
    default: '任务状态',
  },
  text: {
    type: String,
    default: '等待开始。',
  },
  taskId: {
    type: String,
    default: '',
  },
  status: {
    type: String,
    default: 'idle',
  },
})
</script>

<template>
  <section class="card section">
    <div class="section-title">
      <h2>{{ title }}</h2>
    </div>
    <div class="task-status-card" :class="`task-status-card--${status || 'idle'}`">
      <strong>{{ text }}</strong>
      <span v-if="taskId">任务 ID：{{ taskId }}</span>
    </div>
  </section>
</template>

<style scoped>
.task-status-card {
  display: grid;
  gap: 8px;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(6, 9, 14, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.task-status-card strong,
.task-status-card span {
  margin: 0;
}

.task-status-card--success {
  border-color: rgba(87, 236, 180, 0.45);
}

.task-status-card--failed {
  border-color: rgba(255, 125, 125, 0.45);
}

.task-status-card--running,
.task-status-card--queued {
  border-color: rgba(255, 211, 117, 0.45);
}
</style>
