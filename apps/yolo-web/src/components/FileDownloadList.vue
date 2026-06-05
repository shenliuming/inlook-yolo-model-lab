<script setup>
defineProps({
  title: {
    type: String,
    default: '下载结果',
  },
  links: {
    type: Array,
    default: () => [],
  },
  emptyText: {
    type: String,
    default: '任务成功后，这里会显示下载入口。',
  },
})
</script>

<template>
  <section class="card section">
    <div class="section-title">
      <h2>{{ title }}</h2>
    </div>
    <div class="link-grid file-download-grid">
      <a
        v-for="item in links"
        :key="item.href"
        class="ghost-button"
        :href="item.href"
        target="_blank"
        rel="noreferrer"
      >
        {{ item.label }}
      </a>
      <div v-if="!links.length" class="placeholder">{{ emptyText }}</div>
    </div>
  </section>
</template>

<style scoped>
.file-download-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

@media (max-width: 720px) {
  .file-download-grid {
    grid-template-columns: 1fr;
  }
}
</style>
