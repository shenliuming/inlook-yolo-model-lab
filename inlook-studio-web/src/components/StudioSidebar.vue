<script setup>
defineProps({
  items: {
    type: Array,
    required: true,
  },
  activeId: {
    type: String,
    required: true,
  },
})

defineEmits(['select'])
</script>

<template>
  <aside class="studio-sidebar">
    <div class="studio-logo">IN</div>

    <nav class="sidebar-nav">
      <button
        v-for="item in items"
        :key="item.id"
        type="button"
        class="sidebar-link"
        :class="{ 'sidebar-link--active': item.id === activeId }"
        @click="$emit('select', item.id)"
      >
        <span class="sidebar-link__icon">{{ item.icon }}</span>
        <span>{{ item.label }}</span>
      </button>
    </nav>

    <div class="sidebar-quick">
      <span class="sidebar-quick__label">快捷入口</span>
      <button class="secondary-button secondary-button--full" type="button">+ 新建任务</button>
    </div>
  </aside>
</template>
