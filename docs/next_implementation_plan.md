# INLOOK Studio 后续实施计划

更新时间：2026-06-13

本计划用于约束后续开发顺序。数字人方向已收敛为 Template Digital Human v0.1，不再按“万能数字人”推进。

## 阶段一：稳定现有主流程

目标：

```text
素材
→ 文案
→ 改写
→ TTS
→ 字幕
→ BGM
→ 导出
```

能够稳定运行。

建议工作：

1. 补通普通视频导出最小链路。
2. 明确统一导出输入数据结构。
3. 让字幕下载、字幕烧录、BGM 混流都收敛到同一导出 service。
4. 明确正式输出目录与最终 MP4 命名规则。
5. 把模板数字人作为 Beta 能力挂在工作台侧边，不挡普通视频主链路。

阶段完成标准：

- 用户可以从一个本地或远程素材，走到一个可下载的普通 MP4 成片。
- 导出时至少支持：
  - 配音音轨
  - 可选字幕烧录
  - 可选 BGM
  - 人声音量和 BGM 音量

## 阶段二：整理架构

建议工作：

1. 统一 Provider 接口。
2. 统一任务状态存储与聚合格式。
3. 统一运行时目录分层。
4. 逐步拆分 `App.vue`。
5. 清点并下线无调用遗留入口。

建议拆分优先级：

1. 抽 `useMaterialWorkflow`
2. 抽 `useRewriteWorkflow`
3. 抽 `useTtsWorkflow`
4. 抽 `useTaskPolling`
5. 再考虑引入 store

阶段完成标准：

- 前端主工作台状态不再全部堆在 `App.vue`
- 后端主产品只有一套清晰主线接口
- 任务、文件、输出路径统一命名

## 阶段二点五：Template Digital Human v0.1

目标：

```text
30-120s 本人模板视频
→ template package
→ 文本或语音生成口播音频
→ 唇形驱动
→ 嘴部 ROI 合成
→ 严格音视频质检
→ final.mp4
```

产品原则：

1. 做模板数字人，不做泛化数字人。
2. 保持背景、身体、服装和镜头稳定，只局部驱动嘴部。
3. 唇形问题用 `唇形模型 + 精准嘴部 mask + 静音 gate + 严格混流质检` 组合解决。
4. FaceFusion、LongCat 等 POC 只能作为 provider 候选，不直接进入主链路。
5. final MP4 必须同时包含 video 和 audio，且音视频时长差不得超过一帧。

当前已完成：

1. 后端已支持模板包创建和读取。
2. 前端已支持上传 30-120s 模板视频并绑定当前模板。
3. 数字人生成接口已切换到 template avatar 语义。
4. 已接入 `standard_template` provider，能生成带音频、可预览、可下载的标准模板口播 `final.mp4`。
5. 已接入最小 `AudioPreflight` 和 `MediaQualityGate`，音视频时长差超过一帧不会标记为 final。
6. 已接入 `facefusion_lip_syncer` beta provider，可生成 `lipSync: true` 的嘴唇驱动 `final.mp4`。
7. FaceFusion 原始候选视频会被 INLOOK 重新混流并质检，避免 AAC padding 导致音视频超过一帧。

下一步：

1. 增加任务异步化和进度轮询，避免前端长时间等待 FaceFusion 同步请求。
2. 增加嘴部 ROI mask、静音闭嘴 gate 和最终混流质检。
3. 在前端区分 `standard_template` 与 `lip_sync_beta` 两类质量等级。
4. 增加短视频预览模式和长视频排队模式。
5. 再评估 10-20 秒真实用户口播样片质量。

阶段完成标准：

- 用户可以上传合规模板视频并生成一个可质检、可预览、可下载的短口播候选视频。
- 背景和人物主体稳定，主要变化集中在嘴部。
- 静音片段不明显张嘴。
- 不把 silent 文件、错混流文件或音视频不齐的文件标记为 final。

## 阶段三：AI 漫剧基础能力

本阶段仅规划，不开始开发。

规划方向：

1. 剧本结构
2. 角色卡
3. 场景卡
4. 分镜
5. 镜头资产
6. Video Provider
7. 时间线合成

建议前置原则：

- 不把 FaceFusion、LongCat、LongCat-MLX 这类实验能力直接混进主产品工作台。
- 先把普通视频工作流稳定下来，再扩展到 AI 漫剧。
