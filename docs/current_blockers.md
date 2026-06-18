# INLOOK Studio 当前关键阻塞点

更新时间：2026-06-12

以下仅列最重要的 10 项，按优先级排序。

## 1. 普通视频导出链路未接通

- 问题：前端导出按钮被硬编码禁用，后端没有当前主工作台对应的最终导出接口。
- 用户表现：可以完成素材、文案、改写、配音，但无法得到真正成片 MP4。
- 涉及文件：
  - [ExportPanel.vue](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/inlook-studio-web/src/components/ExportPanel.vue)
  - [App.vue](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/inlook-studio-web/src/App.vue)
- 根因：导出执行层缺失，现有设置 UI 没有映射到后端 FFmpeg 编排。
- 影响范围：主产品最终交付能力。
- 建议处理方式：先补一条最小导出链路，只支持“素材视频 + voice.wav + 可选字幕 + 可选 BGM”。
- 预计工作量：中等。
- 是否会破坏现有功能：低，只要新增独立导出 service。

## 2. `App.vue` 过重且承担完整状态机

- 问题：主工作台所有关键状态和流程几乎都堆在单文件。
- 用户表现：刷新易丢状态，后续功能迭代风险高，回归成本高。
- 涉及文件：[App.vue](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/inlook-studio-web/src/App.vue)
- 根因：没有 store、没有 composable、没有工作流状态分层。
- 影响范围：前端稳定性、可维护性、后续导出与任务恢复能力。
- 建议处理方式：先抽离 `material workflow / rewrite workflow / tts workflow / task polling`。
- 预计工作量：中等到较大。
- 是否会破坏现有功能：中，需分阶段迁移。

## 3. 主产品与旧工作流并存，接口和运行时目录分裂

- 问题：Studio 主线与 `content_lab/workflow` 旧实现并行存在。
- 用户表现：任务来源混杂，排错困难，文件路径不统一。
- 涉及文件：
  - [main.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/main.py)
  - [content_lab_controller.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/controllers/content_lab_controller.py)
  - [studio_task_service.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/tasks/studio_task_service.py)
- 根因：新旧接口没有完成收口。
- 影响范围：任务列表、运行时目录治理、能力矩阵判断。
- 建议处理方式：定义唯一主线接口和唯一任务目录命名规范。
- 预计工作量：中等。
- 是否会破坏现有功能：中，需要兼容迁移。

## 4. 任务状态只能“落盘后恢复”，运行中任务无法重启恢复

- 问题：大量后台任务依赖 `BackgroundTasks`。
- 用户表现：服务重启时执行中的转写、TTS 会丢失。
- 涉及文件：
  - [transcriptions_service.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/services/transcriptions_service.py)
  - [studio_tts_service.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/services/studio_tts_service.py)
  - [tts_service.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/services/tts_service.py)
- 根因：无统一队列/worker/恢复机制。
- 影响范围：稳定性与可运营性。
- 建议处理方式：后续改为显式任务队列或可恢复 job runner。
- 预计工作量：较大。
- 是否会破坏现有功能：中。

## 5. 字幕能力分裂为“转写附带字幕”和“旧字幕工作流”

- 问题：当前字幕能力不是单一产品模型。
- 用户表现：主工作台能拿到 SRT/VTT，但不能真正编辑或稳定烧录。
- 涉及文件：
  - [transcriptions_service.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/services/transcriptions_service.py)
  - [subtitle_workflow_service.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/services/subtitle_workflow_service.py)
  - [ExportPanel.vue](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/inlook-studio-web/src/components/ExportPanel.vue)
- 根因：新工作台没有完成对旧字幕工作流的产品化接入。
- 影响范围：成片导出和字幕编辑体验。
- 建议处理方式：先统一“字幕数据模型”和“烧录入口”。
- 预计工作量：中等。
- 是否会破坏现有功能：低到中。

## 6. BGM 与音量目前只有 UI，没有真实后端执行

- 问题：`selectedBgm / narrationVolume / bgmVolume` 只存在前端内存。
- 用户表现：用户看到完整导出配置，但实际不生效。
- 涉及文件：
  - [ExportPanel.vue](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/inlook-studio-web/src/components/ExportPanel.vue)
  - [App.vue](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/inlook-studio-web/src/App.vue)
- 根因：缺少导出执行接口和混流 service。
- 影响范围：导出主功能可信度。
- 建议处理方式：在最小导出链路里先支持 1 个 BGM 源和 2 个音量参数。
- 预计工作量：中等。
- 是否会破坏现有功能：低。

## 7. 数字人 API 暴露但明确未接入

- 问题：前端可点击生成数字人，后端接口存在，但 service 直接返回 501。
- 用户表现：用户误以为能力可用，实际失败。
- 涉及文件：
  - [digitalHuman.js](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/inlook-studio-web/src/api/digitalHuman.js)
  - [digital_human_service.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/services/digital_human_service.py)
- 根因：实验能力入口未与正式产品边界隔离。
- 影响范围：产品认知和演示可靠性。
- 建议处理方式：在主工作台明确标记“实验/未接入”，不要让其看起来像正式完成项。
- 预计工作量：小。
- 是否会破坏现有功能：低。

## 8. 运行时目录会持续增长，缺乏清理策略

- 问题：`runtime/content_lab/materials`、`runtime/content_lab/tts/tasks`、`runtime/studio_alpha/transcriptions/tasks` 会不断落盘。
- 用户表现：磁盘持续增长，历史文件与临时文件界限不清。
- 涉及文件：
  - [paths.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/config/paths.py)
  - [task_store.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/tasks/task_store.py)
- 根因：没有 TTL、清理任务、用户数据归档策略。
- 影响范围：运行时存储、隐私与运维成本。
- 建议处理方式：先定义正式用户素材、缓存、日志、临时文件四类目录。
- 预计工作量：中等。
- 是否会破坏现有功能：低。

## 9. 前端存在重复轮询和状态散落

- 问题：任务列表、浏览器授权、TTS 合成分别各自轮询，没有统一生命周期。
- 用户表现：页面复杂时更容易出现状态不同步。
- 涉及文件：[App.vue](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/inlook-studio-web/src/App.vue)
- 根因：没有统一任务观察器或 composable。
- 影响范围：性能、维护性、排障。
- 建议处理方式：抽出统一 polling 管理层。
- 预计工作量：中等。
- 是否会破坏现有功能：低到中。

## 10. 无调用或半遗留 API/模块仍留在正式目录

- 问题：例如旧 provider/materials_service、旧 content-lab TTS、未使用前端 API 方法仍在主目录。
- 用户表现：新人难以判断真实主线。
- 涉及文件：
  - [materials_service.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/services/materials_service.py)
  - [provider_registry.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/providers/provider_registry.py)
  - [tts_controller.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/controllers/tts_controller.py)
- 根因：重构收口未完成。
- 影响范围：架构可读性和后续开发判断。
- 建议处理方式：先做分类和路由对照，不要立即删除。
- 预计工作量：小到中。
- 是否会破坏现有功能：中，若误删容易回归。
