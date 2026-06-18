# INLOOK Studio 当前项目架构审计

更新时间：2026-06-12

## 审计范围

- 前端：`/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/inlook-studio-web`
- 后端：`/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api`
- 原则：只读审计，不修改产品功能代码，不处理无关 Git 状态

## 一、当前真正的主工作台入口

- 前端单入口是 [App.vue](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/inlook-studio-web/src/App.vue)。
- 页面结构由 `StudioSidebar + StudioTopbar + 5 个主面板 + RecentTaskTable` 组成。
- 当前没有 `src/stores` 和 `src/composables` 实现，业务状态几乎全部集中在 `App.vue` 内部 `ref/computed/watch`。
- 刷新页面后，当前素材、原始文案、改写结果、当前成片文案、音色选择、配音结果、字幕下载链接、BGM 配置都会丢失；只有后端运行时文件和任务目录还在。

## 二、前端主链路真实情况

### 1. 素材上传 / 链接解析

- 入口组件：`MaterialScriptPanel`
- 前端处理：`handleFileSelected()`、`extractScript()`、`readMaterial()`
- API：
  - 本地上传：`POST /api/v1/materials/upload`
  - 链接解析：`POST /api/v1/materials/extract`
- 后端控制器：[material_controller.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/controllers/material_controller.py)
- 后端主服务：[material_service.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/services/material_service.py)
- 真实输出：
  - `runtime/content_lab/materials/<material_id>/material.json`
  - `runtime/content_lab/materials/<material_id>/inputs/source.mp4`
  - `runtime/content_lab/materials/<material_id>/outputs/metadata.json`
  - `runtime/content_lab/materials/<material_id>/run.log`
- 结论：
  - 本地上传主链路已经接通。
  - 抖音 / B站链接解析主链路已经接到浏览器授权和页面抓取。
  - 前端会先做 URL 归一化，再调用后端。

### 2. 原始文案提取

- 前端入口仍在 `MaterialScriptPanel` 的“提取口播文案”动作。
- API：`POST /api/v1/transcriptions`
- 后端控制器：[transcription_controller.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/controllers/transcription_controller.py)
- 后端主服务：[transcriptions_service.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/services/transcriptions_service.py)
- 真实流程：
  - 从 `materials/<material_id>/inputs/source.mp4` 抽音频
  - Whisper ASR
  - OCR 硬字幕识别
  - ASR/OCR 融合
  - 写回 material outputs 和 transcription task outputs
- 真实输出：
  - `runtime/studio_alpha/transcriptions/tasks/<task_id>/outputs/*.json|*.txt|*.srt|*.vtt`
  - `runtime/content_lab/materials/<material_id>/outputs/audio.wav`
  - `runtime/content_lab/materials/<material_id>/outputs/final_transcript.txt`
  - `runtime/content_lab/materials/<material_id>/outputs/subtitles.srt`
- 结论：
  - “原始口播文案提取”不是只读页面，而是已接通的真实后端流程。
  - 原始文案来源当前主线是 `Whisper + OCR 融合`，不是单纯页面描述。
  - 平台描述文案会先进入 `currentProject.originalText`，但随后可被视频转写结果覆盖为正式原始文案。

### 3. DeepSeek / LLM 改写

- 前端入口组件：`PromptRewritePanel`
- API：`GET /api/v1/ai/status`、`POST /api/v1/copy/rewrite`
- 后端控制器：[ai_controller.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/controllers/ai_controller.py)
- 后端服务：[copy_rewrite_service.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/services/copy_rewrite_service.py)
- LLM 客户端：[llm_client.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/clients/llm_client.py)
- 结论：
  - 当前 LLM 接口是 OpenAI Compatible 风格，不是 DeepSeek 专用 SDK。
  - DeepSeek 只是可能通过 `.env` 的 `LLM_BASE_URL / LLM_MODEL / LLM_API_KEY` 接入。
  - 配置入口在 [settings.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/config/settings.py) 的 `get_llm_*`。
  - 当前代码能验证“是否配置”“是否发请求”“是否返回 JSON 改写版本”，但不能从仓库静态代码里证明当前线上配置一定就是 DeepSeek。

### 4. 音色选择与 TTS

- 前端入口组件：`VoiceHumanPanel` 和 `VoiceLibraryView`
- 主要 API：
  - `GET /api/v1/voices`
  - `POST /api/v1/voices`
  - `POST /api/v1/voices/from-material`
  - `POST /api/v1/voices/{voice_id}/preview`
  - `POST /api/v1/tts/synthesis`
- 后端主控制器：
  - [voice_controller.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/controllers/voice_controller.py)
  - [studio_tts_controller.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/controllers/studio_tts_controller.py)
- 后端主服务：
  - [voice_profile_service.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/services/voice_profile_service.py)
  - [studio_tts_service.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/services/studio_tts_service.py)
  - [tts_service.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/services/tts_service.py)
- 当前正式主线：
  - 音色库存储在 `runtime/content_lab/voices`
  - 合成任务存储在 `runtime/content_lab/tts/tasks`
  - 实际合成引擎是 `CosyVoice`
- `voice.wav` 真实输出位置：
  - `runtime/content_lab/tts/tasks/<tts_task_id>/outputs/voice.wav`
  - 对前端返回为 `/api/v1/content-lab/tts/tasks/<tts_task_id>/files/voice.wav`
- 结论：
  - 当前正式 TTS 主线是 `CosyVoice`。
  - 阿里 TTS 在这套 Studio 主链路中没有看到真实调用入口。
  - MOSS-TTS 代码仍保留，但文件头已明确标注 `Deprecated`，不在主流程中。

### 5. 字幕生成与编辑

- 当前主工作台对字幕的真实接入来自转写任务输出的 `srt/vtt` 文件。
- 前端 `ExportPanel` 只提供下载 SRT/VTT，不提供实际字幕编辑器。
- 后端存在两个相关实现：
  - 新主线：`/api/v1/transcriptions` 产出字幕文件
  - 旧内容工作流：`/api/v1/content-lab/subtitles/tasks`
- 结论：
  - “字幕生成”已部分实现。
  - “字幕编辑”在当前主工作台中没有真实编辑保存链路。
  - “字幕烧录”只存在于旧 content-lab 工作流，不在当前 Studio 主工作台导出链路里。

### 6. BGM、音量、视频预览、导出

- BGM 和音量配置当前只保存在前端内存状态：
  - `selectedBgm`
  - `narrationVolume`
  - `bgmVolume`
  - `currentProject.bgm`
- 视频预览当前读取：
  - 素材视频：`material.localVideoUrl`
  - 当前配音：`currentProject.currentAudio.audioUrl`
  - 不存在普通视频成片导出结果
- `ExportPanel` 的导出按钮被硬编码为禁用：
  - `:disabled="true || audioGateDisabled"`
- 结论：
  - BGM 配置只是 UI 状态。
  - 人声音量 / BGM 音量只保存到内存对象，没有映射到真实 FFmpeg 导出请求。
  - 普通视频导出链路当前没有真正跑通。

## 三、后端真实入口与 Router

真实启动入口：

- [app.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app.py)
- [main.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/main.py)

已注册 Router：

- `health_router`
- `vision_router`
- `content_lab_router`
- `ai_router`
- `browser_auth_router`
- `tts_router`
- `material_router`
- `transcription_router`
- `subtitle_router`
- `studio_tts_router`
- `voice_router`
- `digital_human_router`
- `task_router`
- `file_router`

说明：

- 这是“新旧接口并存”的后端，而不是单一路由体系。
- `content_lab_router` 暴露旧工作流接口，同时还保留 legacy URL。
- `material_router / transcription_router / studio_tts_router / voice_router / task_router` 是当前 Studio 主工作台实际在用的接口。

## 四、素材获取真实实现

### Playwright 持久化 Profile

- 使用了 Playwright 持久化浏览器配置目录。
- 代码位置：
  - [browser_client.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/clients/browser_client.py)
  - [browser_auth_service.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/services/browser_auth_service.py)
- Profile 目录：
  - `runtime/browser_profiles/douyin`
  - `runtime/browser_profiles/bilibili`

### 各来源当前主线

- 本地上传：`upload_material()` 直接写入 `materials/<id>/inputs/source.mp4`
- 抖音链接：需要浏览器授权，后端打开页面抓 response/html，再解析作品信息和视频源
- B站链接：同样走浏览器授权和页面 response/html 解析

说明：

- 代码里还保留 `material_intake_service + provider_registry + content_lab_controller` 旧链路。
- 但当前主工作台实际没有调用这套 provider-based content-lab material task API。

## 五、任务与历史记录

- 主工作台任务列表接口：`GET /api/v1/tasks`
- 聚合逻辑在 [studio_task_service.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/tasks/studio_task_service.py)
- 任务来源被混合聚合为：
  - `runtime/content_workflow/material_intake/tasks`
  - `runtime/studio_alpha/transcriptions/tasks`
  - `runtime/studio_alpha/tts/trainings`
  - `runtime/content_lab/tts/tasks`

结论：

- 任务状态主要落盘为 JSON 文件，不是 SQLite。
- 任务和历史在服务重启后理论上仍可从磁盘目录扫描恢复。
- 但 `BackgroundTasks` 正在执行中的任务会因为服务重启中断，无法恢复执行上下文。
- 当前不存在统一的任务数据库，也没有真正一致的“项目历史”概念。

## 六、当前前端重逻辑集中点

`App.vue` 目前承担了过重业务逻辑，包括：

- URL 清洗、平台识别、链接提取
- 素材导入流程控制
- 原始文案状态机
- AI 改写调用与结果选择
- 音色库管理
- TTS 任务轮询
- 浏览器授权轮询
- 任务列表轮询
- 数字人占位调用
- 预览与项目聚合状态

这不是立即要拆分的结论，而是后续架构整理的重点对象。

## 七、只有 UI 或未接通的前端能力

### 只有 UI，没有真实后端闭环

- `ExportPanel`
  - 有字幕、BGM、音量、比例、清晰度、导出目录等 UI。
  - 真实导出事件没有接通，按钮直接禁用。
- 数字人生成
  - 前端可以点击。
  - 后端明确返回 501，实际仍是未接入状态。

### 当前前端未使用的 API 方法

- `src/api/materials.js`
  - `getMaterial`
- `src/api/transcriptions.js`
  - `getTranscription`
  - `getSubtitleBundle`
- `src/api/tasks.js`
  - `getTask`
- `src/api/tts.js`
  - `listVoices`
  - `getVoiceProfile`
  - `createTraining`
  - `getTraining`

说明：

- 这些文件未必应该立刻删除。
- 但从当前主工作台实际引用关系看，它们不在当前用户点击主链路上。

## 八、运行时目录审计

### `apps/yolo-api/runtime`

- 目录用途：后端运行时总根目录。
- 创建它的代码：[paths.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/config/paths.py) `ensure_runtime_directories()`
- 读取它的代码：多处 service/task store
- 是否正式数据：混合
- 是否临时缓存：部分是
- 是否可以删除：不能整体删除
- 是否可能包含用户素材：是
- 是否可能无限增长：是

### `apps/yolo-api/runtime/content_lab`

- 目录用途：当前正式主产品运行时主根目录。
- 创建它的代码：`paths.py`
- 读取它的代码：
  - `task_store.py`
  - `voice_profile_service.py`
  - `tts_service.py`
- 是否正式数据：是
- 是否临时缓存：部分是
- 是否可以删除：不建议
- 是否可能包含用户素材：是
- 是否可能无限增长：是

### `apps/yolo-api/runtime/studio_alpha`

- 目录用途：Studio 主工作台的转写和 TTS 训练任务目录。
- 创建它的代码：`paths.py`
- 读取它的代码：
  - `transcriptions_service.py`
  - `studio_tts_service.py`
- 是否正式数据：是，但更偏任务中间产物
- 是否临时缓存：是
- 是否可以删除：不能直接删
- 是否可能包含用户素材：间接包含转写音频和字幕
- 是否可能无限增长：是

### `apps/yolo-api/runtime/browser_profiles`

- 目录用途：抖音/B站 Playwright 持久化登录态。
- 创建它的代码：`paths.py`
- 读取它的代码：
  - `browser_client.py`
  - `browser_auth_service.py`
- 是否正式数据：是，属于运行授权状态
- 是否临时缓存：部分是
- 是否可以删除：可以在重新授权前提下单独清理，但不应随意处理
- 是否可能包含用户素材：否
- 是否可能无限增长：有增长风险

### `apps/yolo-api/runtime/avatar_poc`

- 目录用途：FaceFusion 等数字人实验输出。
- 创建它的代码：非主产品代码路径，主要由实验脚本产生
- 读取它的代码：与本轮主产品主线无关
- 是否正式数据：否
- 是否临时缓存：是
- 是否可以删除：应作为实验区单独治理
- 是否可能包含用户素材：是
- 是否可能无限增长：是

### `apps/yolo-api/uploads`

- 目录用途：预留上传目录。
- 创建它的代码：`paths.py`
- 读取它的代码：本轮未看到当前主线强依赖
- 是否正式数据：不稳定，当前主线主要写 `runtime/content_lab/materials`
- 是否临时缓存：更像预留目录
- 是否可以删除：当前不建议碰
- 是否可能包含用户素材：可能
- 是否可能无限增长：有可能

### `apps/yolo-api/outputs`

- 目录用途：静态挂载公开输出目录。
- 创建它的代码：`paths.py` + `main.py` `app.mount("/outputs", ...)`
- 读取它的代码：当前主工作台主线里未见核心写入
- 是否正式数据：可能包含对外可访问输出
- 是否临时缓存：可能混合
- 是否可以删除：当前不建议碰
- 是否可能包含用户素材：可能
- 是否可能无限增长：有可能

### `apps/yolo-api/models`

- 目录用途：模型目录。
- 创建它的代码：`paths.py`
- 读取它的代码：YOLO 视觉相关逻辑
- 是否正式数据：是
- 是否临时缓存：否
- 是否可以删除：否
- 是否可能包含用户素材：否
- 是否可能无限增长：低

### `apps/yolo-api/reports`

- 目录用途：报告与可公开输出目录。
- 创建它的代码：`paths.py`
- 读取它的代码：`main.py` 静态挂载
- 是否正式数据：混合
- 是否临时缓存：部分可能是
- 是否可以删除：当前不建议碰
- 是否可能包含用户素材：低
- 是否可能无限增长：中

## 九、当前主结论

- 当前真正跑通的主链路是：`素材读取 -> 文案提取 -> AI改写 -> CosyVoice 配音 -> 音频预览/下载 -> 任务列表查看`
- 当前没有跑通的主链路是：`BGM -> 字幕编辑 -> 普通视频成片导出`
- 数字人接口当前明确未接入，不属于主产品已完成能力
- 代码中同时存在 `Studio 主线`、`旧 content-lab 工作流`、`FaceFusion/LongCat POC`、`MOSS-TTS 遗留` 四类实现，边界尚未完全分离
