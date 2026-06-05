<script setup>
defineProps({
  serviceStatus: {
    type: String,
    required: true,
  },
  modelStatus: {
    type: String,
    required: true,
  },
  outputPath: {
    type: String,
    required: true,
  },
})
</script>

<template>
  <header class="studio-topbar">
    <div class="studio-brand">
      <div>
        <h1>INLOOK Studio</h1>
        <p>口播智能体</p>
      </div>
    </div>

    <div class="studio-runtime">
      <span class="runtime-pill">
        <i class="status-dot status-dot--success"></i>
        本地服务：{{ serviceStatus }}
      </span>
      <span class="runtime-pill">
        <i class="status-dot status-dot--success"></i>
        模型：{{ modelStatus }}
      </span>
      <span class="runtime-path">输出目录：{{ outputPath }}</span>
    </div>

    <div class="window-actions">
      <button class="icon-button" type="button" aria-label="设置">⚙</button>
      <button class="icon-button" type="button" aria-label="最小化">—</button>
      <button class="icon-button" type="button" aria-label="最大化">□</button>
      <button class="icon-button icon-button--danger" type="button" aria-label="关闭">×</button>
    </div>
  </header>
</template>
