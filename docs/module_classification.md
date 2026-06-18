# INLOOK Studio 模块分类

更新时间：2026-06-13

分类说明：

- `CORE` 主产品必须保留
- `OPTIONAL` 可选能力，失败不应影响主流程
- `POC` 实验能力，不进入正式打包
- `LEGACY` 旧实现，暂时保留但不继续扩展
- `UNKNOWN` 归属暂无法确认

## CORE

- `inlook-studio-web/src/App.vue`
  - 当前主工作台实际入口，虽然过重，但仍是产品主线。
- `inlook-studio-web/src/components/MaterialScriptPanel.vue`
  - 素材和原始文案入口。
- `inlook-studio-web/src/components/PromptRewritePanel.vue`
  - AI 改写入口。
- `inlook-studio-web/src/components/VoiceHumanPanel.vue`
  - 音色与配音主入口。
- `inlook-studio-web/src/components/VideoPreviewPanel.vue`
  - 当前真实预览载体。
- `inlook-studio-web/src/api/*` 中被 `App.vue` 直接使用的文件
  - `ai.js`
  - `browserAuth.js`
  - `client.js`
  - `digitalHuman.js`
  - `materials.js`
  - `tasks.js`
  - `transcriptions.js`
  - `tts.js`
- `apps/yolo-api/app/main.py`
  - FastAPI 真实注册入口。
- `apps/yolo-api/app/services/material_service.py`
  - Studio 主工作台素材主线。
- `apps/yolo-api/app/services/material_download_service.py`
  - 远程视频真实下载器。
- `apps/yolo-api/app/services/transcriptions_service.py`
  - 文案提取与字幕文件主线。
- `apps/yolo-api/app/services/copy_rewrite_service.py`
  - LLM 改写主线。
- `apps/yolo-api/app/services/studio_tts_service.py`
  - Studio TTS 编排入口。
- `apps/yolo-api/app/services/voice_profile_service.py`
  - 音色库存储与复用主线。
- `apps/yolo-api/app/services/tts_service.py`
  - CosyVoice 合成任务实际执行层。
- `apps/yolo-api/app/controllers/digital_human_controller.py`
  - Template Digital Human v0.1 对外 API，负责模板创建、模板读取和生成入口。
- `apps/yolo-api/app/services/digital_human_template_service.py`
  - 模板数字人的正式模板包管理服务，写入 `runtime/content_lab/digital_human/templates`。
- `apps/yolo-api/app/services/digital_human_service.py`
  - 模板数字人生成编排入口；当前 provider 尚未接入，但边界属于正式 v0.1 轨道。
- `apps/yolo-api/app/clients/browser_client.py`
  - 浏览器授权与页面抓取核心能力。
- `apps/yolo-api/app/clients/llm_client.py`
  - OpenAI Compatible LLM 核心调用层。

## OPTIONAL

- `apps/yolo-api/app/services/ocr_subtitle_service.py`
  - OCR 失败时主流程可回退到 ASR。
- `apps/yolo-api/app/services/transcription_fusion_service.py`
  - 提升文案质量，但不是素材读取前置。
- `apps/yolo-api/app/controllers/browser_auth_controller.py`
  - 对远程平台素材重要，但不影响本地视频上传主线。
- `apps/yolo-api/runtime/browser_profiles`
  - 抖音/B站登录态缓存。

## POC

- `apps/yolo-api/runtime/avatar_poc`
  - FaceFusion、LongCat 等实验残留。
- `apps/yolo-api/runtime/avatar_poc/facefusion`
  - 当前明确属于实验代码和实验输出。
- FaceFusion
  - 以当前仓库状态看属于实验能力，不应并入主产品必经链路。
- LongCat 残留
  - 现已暂停，不应进入正式打包。

## LEGACY

- `apps/yolo-api/app/controllers/content_lab_controller.py`
  - 同时承载 `/api/v1/content-lab/*` 和 `/api/workflow/*` 旧工作流接口。
- `apps/yolo-api/app/services/material_intake_service.py`
  - 旧内容工作流素材任务体系。
- `apps/yolo-api/app/services/materials_service.py`
  - provider 风格封装，但当前主工作台不走这条线。
- `apps/yolo-api/app/providers/*`
  - 旧 provider 抽象仍在，但 Studio 主工作台绕过了它们。
- `apps/yolo-api/app/services/subtitle_workflow_service.py`
  - 旧字幕烧录流水线，不在当前主工作台内。
- `apps/yolo-api/app/controllers/tts_controller.py`
  - 旧 content-lab TTS API。
- `apps/yolo-api/app/clients/moss_tts_client.py`
  - 文件头明确标记 Deprecated。
- `third_party/MOSS-TTS-Nano`
  - 遗留依赖，不是当前正式主线。

## UNKNOWN

- 阿里 TTS 相关正式入口
  - 本轮未在当前主工作台调用链中读到明确 controller/service 主线。
- YOLO 相关视觉检测链路
  - 后端已注册 `vision_router`，但不在本轮 Studio 主产品主链路范围内。

## 指定模块判定

- FaceFusion：`POC`
- LongCat 残留：`POC`
- MOSS-TTS-Nano：`LEGACY`
- CosyVoice：`CORE`
- 阿里 TTS：`UNKNOWN`
- YOLO 相关代码：`OPTIONAL`
- 素材浏览器 Profile：`OPTIONAL`
- 数字人 Controller：`CORE`
- 数字人 Template Service：`CORE`
- 数字人 Provider 实现：`POC / 待接入`
- 旧 TTS Service：`LEGACY`
- 新 Studio TTS Service：`CORE`

## 当前最需要保持边界清晰的地方

- `Studio 主线` 与 `content_lab/workflow 旧链路` 现在还混在同一个后端里。
- `runtime/content_lab` 是正式主产品运行时。
- `runtime/avatar_poc` 是实验区，不应再被误当作正式能力。
- Template Digital Human v0.1 的正式资产只能进入 `runtime/content_lab/digital_human`，不能反向依赖 `runtime/avatar_poc`。
