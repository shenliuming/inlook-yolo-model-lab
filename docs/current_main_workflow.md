# INLOOK Studio 当前主流程时序图

更新时间：2026-06-12

## 1. 素材链接解析流程

```mermaid
flowchart TD
  U["用户粘贴抖音/B站/TikTok 链接"] --> FE["App.vue handleVideoLinkInput / extractScript"]
  FE --> API["POST /api/v1/materials/extract"]
  API --> CTRL["material_controller.extract_material_handler"]
  CTRL --> SVC["material_service.extract_material"]
  SVC --> AUTH["browser_auth_service.ensure_platform_authorized"]
  AUTH --> BROWSER["browser_client.open_material_page"]
  BROWSER --> PARSE["material_service 解析 response/html"]
  PARSE --> DL["material_download_service.download_material_video"]
  DL --> FILES["runtime/content_lab/materials/<material_id>"]
  FILES --> RES["返回 material payload"]
  RES --> FE2["App.vue applyMaterial"]
  FE2 --> UI["MaterialScriptPanel / VideoPreviewPanel"]
```

关键文件：

- [App.vue](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/inlook-studio-web/src/App.vue)
- [materials.js](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/inlook-studio-web/src/api/materials.js)
- [material_controller.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/controllers/material_controller.py)
- [material_service.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/services/material_service.py)
- [browser_client.py](/Users/shen/workspace/src/github.com/inlook-web3/inlook-yolo-model-lab/apps/yolo-api/app/clients/browser_client.py)

## 2. 本地视频上传流程

```mermaid
flowchart TD
  U["用户上传本地视频"] --> FE["App.vue handleFileSelected"]
  FE --> API["POST /api/v1/materials/upload"]
  API --> CTRL["material_controller.upload_material_handler"]
  CTRL --> SVC["material_service.upload_material"]
  SVC --> PROBE["ffmpeg_client.probe_video / 生成封面"]
  PROBE --> FILES["runtime/content_lab/materials/<material_id>/inputs/source.mp4"]
  FILES --> JSON["material.json + outputs/metadata.json"]
  JSON --> RES["返回 material payload"]
  RES --> FE2["App.vue applyMaterial"]
  FE2 --> UI["VideoPreviewPanel"]
```

输出文件：

- `runtime/content_lab/materials/<material_id>/inputs/source.mp4`
- `runtime/content_lab/materials/<material_id>/material.json`
- `runtime/content_lab/materials/<material_id>/outputs/metadata.json`

## 3. 文案改写流程

```mermaid
flowchart TD
  U["用户点击 AI 改写"] --> FE["PromptRewritePanel -> App.vue runRewrite"]
  FE --> API["POST /api/v1/copy/rewrite"]
  API --> CTRL["ai_controller.rewrite_copy_handler"]
  CTRL --> SVC["copy_rewrite_service.rewrite_copy"]
  SVC --> LLM["llm_client.chat (OpenAI Compatible)"]
  LLM --> RES["返回 versions JSON"]
  RES --> FE2["rewriteResults / activeResultId / currentProject.rewriteVersions"]
  FE2 --> UI["PromptRewritePanel 展示版本"]
```

说明：

- 改写结果当前只保存在前端内存，不写文件。
- 页面刷新后会丢失。

## 4. TTS 生成流程

```mermaid
flowchart TD
  U["用户选择音色并点击生成配音"] --> FE["VoiceHumanPanel -> App.vue generateVoice"]
  FE --> API["POST /api/v1/tts/synthesis"]
  API --> CTRL["studio_tts_controller.create_synthesis"]
  CTRL --> SVC["studio_tts_service.create_tts_synthesis"]
  SVC --> VOICE["voice_profile_service.resolve_voice_for_synthesis"]
  SVC --> TASK["tts_service.create_tts_task"]
  TASK --> ENGINE["tts_engines/cosyvoice_engine"]
  ENGINE --> FILES["runtime/content_lab/tts/tasks/<task_id>/outputs/voice.wav"]
  FILES --> POLL["GET /api/v1/tts/synthesis/{id}"]
  POLL --> FE2["App.vue synthesisPollTimer"]
  FE2 --> UI["Audio 试听 / 当前项目 currentAudio"]
```

## 5. 字幕生成流程

```mermaid
flowchart TD
  U["用户点击提取口播文案"] --> FE["App.vue extractCurrentMaterialScript"]
  FE --> API["POST /api/v1/transcriptions"]
  API --> CTRL["transcription_controller.create_transcription"]
  CTRL --> SVC["transcriptions_service.create_transcription_task"]
  SVC --> ASR["extract_audio + Whisper ASR"]
  SVC --> OCR["ocr_subtitle_service.extract_ocr_subtitles"]
  ASR --> FUSION["transcription_fusion_service"]
  OCR --> FUSION
  FUSION --> FILES["transcriptions/tasks/<task_id>/outputs + materials/<material_id>/outputs"]
  FILES --> RES["transcript/srt/vtt/finalText"]
  RES --> FE2["App.vue subtitleDownloads + originalText"]
  FE2 --> UI["MaterialScriptPanel / ExportPanel"]
```

## 6. 最终视频导出流程

```text
用户点击导出
-> ExportPanel 显示导出设置
-> render-video 事件已定义
-> App.vue 当前没有接入真实导出处理
-> 按钮被硬编码 disabled
-> 无后端导出接口
-> 无 FFmpeg 最终 MP4 输出
```

结论：

- 这是当前主产品最明确的断链。
- BGM、人声音量、字幕样式、分辨率、保存到素材库等设置都还没有接到真实导出执行层。

## 7. 实验能力说明

- 数字人流程没有进入主产品必经链路。
- 当前 `POST /api/v1/digital-human/generate` 会直接返回“数字人引擎暂未接入”。
- FaceFusion、LongCat 等都在 `runtime/avatar_poc` 范围，不应视为主产品正式工作流。
