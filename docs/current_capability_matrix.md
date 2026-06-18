# INLOOK Studio 当前能力矩阵

更新时间：2026-06-12

状态说明：

- `READY` 已有完整实现并能从代码和运行时目录验证
- `PARTIAL` 有实现但流程不完整
- `BROKEN` 有代码但当前主链路无法正常完成
- `UI_ONLY` 只有前端页面或按钮
- `POC` 仅实验代码
- `LEGACY` 遗留实现
- `UNKNOWN` 暂无法确认

| 能力 | 状态 | 前端入口 | 后端入口 | 核心代码 | 输出文件 | 验证方式 | 当前问题 |
|---|---|---|---|---|---|---|---|
| 本地视频上传 | READY | `App.vue` `handleFileSelected` | `POST /api/v1/materials/upload` | `material_service.upload_material` | `runtime/content_lab/materials/<id>/inputs/source.mp4` | 已有真实 controller/service/runtime 写盘 | 无前端持久化 |
| 抖音链接解析 | READY | `App.vue` `extractScript/readMaterial` | `POST /api/v1/materials/extract` | `material_service.extract_material` | `runtime/content_lab/materials/<id>/material.json` | 代码已接 Playwright 授权与 response/html 解析 | 依赖浏览器登录态 |
| B站链接解析 | READY | 同上 | 同上 | 同上 | 同上 | 代码已接 Playwright 授权与页面解析 | 依赖浏览器登录态 |
| 素材下载 | READY | 前端通过 `/materials/extract` 间接触发 | 同上 | `material_service` + `material_download_service` | `materials/<id>/inputs/source.mp4` | 代码明确会下载并 ffprobe 校验 | 网络与平台限制可能失败 |
| 视频规范化 | PARTIAL | 当前 Studio 主链路未直接调用 | `content-lab/materials/tasks` 旧接口 | `material_intake_service.normalize_output` | `runtime/content_workflow/material_intake/tasks/.../outputs/input.mp4` | 旧工作流代码存在 | 不在当前主工作台主线 |
| 音频提取 | READY | `POST /api/v1/transcriptions` 间接触发 | `POST /api/v1/transcriptions` | `transcriptions_service.extract_audio` | `materials/<id>/outputs/audio.wav` | 代码明确输出 WAV | 依赖 ffmpeg |
| Whisper 转写 | READY | 主工作台“提取口播文案” | `POST /api/v1/transcriptions` | `transcriptions_service.process_transcription_task` | `transcriptions/tasks/<id>/outputs/transcript.*` | 代码明确写多种 transcript 文件 | 依赖 faster-whisper 环境 |
| OCR 字幕提取 | PARTIAL | 同上 | 同上 | `ocr_subtitle_service.extract_ocr_subtitles` | `materials/<id>/outputs/ocr_*` | 代码明确尝试 OCR 并降级 | OCR 失败时仅回退 ASR |
| 原始文案生成 | READY | `MaterialScriptPanel` | `POST /api/v1/transcriptions` | `transcriptions_service` + `transcription_fusion_service` | `final_transcript.txt` | ASR/OCR 融合逻辑明确 | 前端不持久化 |
| DeepSeek 文案改写 | PARTIAL | `PromptRewritePanel` | `POST /api/v1/copy/rewrite` | `copy_rewrite_service` + `llm_client` | 无文件输出，仅返回 JSON | OpenAI Compatible LLM 调用明确 | 是否实际接的是 DeepSeek 取决于环境 |
| 提示词自定义 | READY | `PromptRewritePanel` | 同上 | `runRewrite` + `CopyRewriteRequestDTO` | 无文件输出 | 前端 prompt 会真实传后端 | 仅内存态 |
| 阿里 TTS | UNKNOWN | 无当前主工作台入口 | 未见当前主线 router | 未发现 Studio 主线调用 | 无 | 仅读代码无法确认 | 不在当前主产品主线 |
| CosyVoice | READY | `VoiceHumanPanel` / `VoiceLibraryView` | `/api/v1/voices` `/api/v1/tts/synthesis` | `voice_profile_service` + `studio_tts_service` + `tts_service` | `runtime/content_lab/tts/tasks/<id>/outputs/voice.wav` | 真实任务与输出路径存在 | 依赖模型与环境 |
| MOSS-TTS | LEGACY | 无当前主工作台入口 | 无当前主线调用 | `moss_tts_client.py` | 理论可产出 voice.wav | 文件头已标注 Deprecated | 不应继续作为主线 |
| 音色库 | READY | `VoiceLibraryView` | `/api/v1/voices` | `voice_profile_service` | `runtime/content_lab/voices` | 有索引与 reference audio | 仅本地文件索引，无 DB |
| 参考音频上传 | READY | 创建音色弹窗 | `POST /api/v1/voices` | `create_voice_profile` | `runtime/content_lab/voices/<id>/...` | 真实上传和预处理代码存在 | 依赖音频质量校验 |
| 字幕生成 | PARTIAL | 当前主工作台通过转写任务获得 | `/api/v1/transcriptions` | `transcriptions_service` | `subtitles.srt` `subtitles.vtt` | 下载入口已接通 | 独立字幕工作流与主工作台分裂 |
| 字幕编辑 | UI_ONLY | `ExportPanel` 仅下载，不可编辑 | 无主工作台编辑接口 | 无真实编辑保存逻辑 | 无 | 未见保存 API | 只有展示和下载 |
| 字幕烧录 | LEGACY | 当前主工作台未调用 | `/api/v1/content-lab/subtitles/tasks` | `subtitle_workflow_service` | `output_subtitled.mp4` | 旧工作流代码完整 | 未接进当前工作台 |
| BGM | UI_ONLY | `ExportPanel` | 无主工作台导出接口 | 前端状态字段 בלבד | 无 | 仅 `selectedBgm` 等状态 | 没有后端混流链路 |
| 人声音量 | UI_ONLY | `ExportPanel` | 无 | 前端内存状态 | 无 | 没有真实导出请求 | 未接 FFmpeg |
| 视频预览 | READY | `VideoPreviewPanel` | 读取已有文件 URL | `material.localVideoUrl` / `currentAudio.audioUrl` | 已有素材/音频文件 | 可从代码验证 | 不是最终成片预览 |
| 普通视频导出 | BROKEN | `ExportPanel` | 无当前主线接口 | 导出按钮硬禁用 | 无 | 前端按钮不可用 | 主流程断点 |
| 数字人 | BROKEN | `VoiceHumanPanel` | `POST /api/v1/digital-human/generate` | `digital_human_service` | 无 | service 直接返回 501 | 明确未接入 |
| 任务状态 | PARTIAL | `RecentTaskTable` | `GET /api/v1/tasks` | `studio_task_service` | 多目录 task.json | 聚合任务列表已实现 | 多套任务目录混杂 |
| 历史记录 | PARTIAL | 仅近期任务表 | 复用 `/api/v1/tasks` | `studio_task_service` | 磁盘 JSON | 可重启后扫描目录 | 不是项目级历史 |
| 配置管理 | PARTIAL | 前端无系统设置页 | `.env/.env.local` + settings | `settings.py` | 环境变量 | 代码可验证 | 强依赖环境，不可视 |
| 错误提示 | READY | `appError/authHint/voiceStatus/...` | 全局异常包装 | `apiFetch` + AppException | 无 | 前后端均有错误映射 | 过于分散 |
| 任务重试 | PARTIAL | 用户可重新点击部分按钮 | 无统一 retry API | 通过重复创建新任务实现 | 新 task 目录 | 代码可验证 | 不是真正幂等重试 |

## 结论摘要

- 主产品今天真正能走通的是“素材、文案、改写、CosyVoice 配音”。
- “普通视频导出”仍然是当前最大缺口。
- “数字人”当前不是 READY，也不应该算进主产品可交付主链路。
- “字幕”和“BGM”目前处在 `PARTIAL/UI_ONLY/LEGACY` 混合状态。
