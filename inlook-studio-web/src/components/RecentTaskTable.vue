<script setup>
defineProps({
  tasks: {
    type: Array,
    required: true,
  },
  totalCount: {
    type: Number,
    default: 0,
  },
})

defineEmits(['view-all'])

const statusClassMap = {
  已完成: 'task-status--done',
  进行中: 'task-status--progress',
  等待中: 'task-status--waiting',
  失败: 'task-status--failed',
  成功: 'task-status--done',
  success: 'task-status--done',
  running: 'task-status--progress',
  pending: 'task-status--waiting',
  failed: 'task-status--failed',
  cancelled: 'task-status--failed',
}

const statusClass = (status) => statusClassMap[status] || 'task-status--waiting'
</script>

<template>
  <section class="task-window">
    <div class="task-window__header">
      <div>
        <h2>最近任务</h2>
        <p>仅展示最近 5 条任务状态。</p>
      </div>
      <button class="ghost-button ghost-button--small" type="button" @click="$emit('view-all')">
        查看全部 {{ totalCount }} 条
      </button>
    </div>

    <div class="task-table">
      <div class="task-table__head">
        <span>任务名称</span>
        <span>素材来源</span>
        <span>当前步骤</span>
        <span>状态</span>
        <span>创建时间</span>
        <span>进度</span>
        <span>操作</span>
      </div>

      <div class="task-table__body">
        <div v-for="task in tasks" :key="task.taskId || task.id" class="task-table__row">
          <strong>{{ task.name || task.taskType }}</strong>
          <span>{{ task.source || task.sourceType || '-' }}</span>
          <span>{{ task.step || task.stage || '-' }}</span>
          <span><i class="task-status" :class="statusClass(task.statusLabel || task.status)">{{ task.statusLabel || task.status }}</i></span>
          <span>{{ task.createdAtLabel || task.createdAt || '-' }}</span>
          <span>{{ task.progress ?? 0 }}%</span>
          <div class="task-actions">
            <button class="table-action" type="button">▶</button>
            <button class="table-action" type="button">⧉</button>
            <button class="table-action" type="button">⌂</button>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
