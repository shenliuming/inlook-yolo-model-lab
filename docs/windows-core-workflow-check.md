# Windows Core Workflow Check

## 1. 检查范围

* 素材读取
* 文案来源
* DeepSeek 改写
* TTS 生成
* 音色管理
* currentAudio 回写
* 字幕
* BGM
* 导出
* runtime 静态文件
* Windows 兼容性

## 2. 素材读取

- **前端入口**：`inlook-studio-web/src/api/materials.js` (`extractMaterial`, `uploadMaterial`)
- **后端接口**：`apps/yolo-api/app/controllers/material_controller.py` (`/api/v1/materials/upload`, `/api/v1/materials/extract`)
- **输入输出**：前端上传视频或提供 URL。后端输出至 `runtime/content_workflow/material_intake/tasks/{task_id}/outputs/input.mp4` 及 `cover.jpg`。
- **Windows 风险**：后端依赖 `yt-dlp` 和 `ffmpeg`，这两者必须在 Windows 环境变量 `PATH` 中配置。路径拼接使用了 Python 跨平台的 `pathlib.Path`，相对安全。
- **验证方法**：在 Windows 上启动服务后，前端上传一段视频，观察任务是否成功完成并生成封面。

## 3. 文案改写

- **前端入口**：`inlook-studio-web/src/api/ai.js` (`rewriteCopy`)
- **后端接口**：`apps/yolo-api/app/controllers/ai_controller.py` (`/api/v1/copy/rewrite`)
- **环境变量**：`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` (通过 `.env.local` 注入)。
- **返回字段**：返回包含多个改写版本的 `text`, `title`, `reason` 列表。
- **Windows 风险**：纯 HTTP 请求调用，无文件读写，**无风险**。
- **验证方法**：配置好对应的 API Key，前端点击“改写文案”按钮，确保网络连通且返回结果正常。

## 4. TTS 生成

- **当前 TTS 方案**：默认配置为 `CosyVoice`，代码中亦兼容 `MOSS-TTS-Nano` 备用。
- **入口**：前端 `inlook-studio-web/src/api/contentLabApi.js` 和 `tts.js` -> 后端 `tts_controller.py`。
- **输入输出**：输入 `currentProject.currentScript` 和选定的 `voiceId`，输出至 `runtime/content_lab/tts/tasks/{task_id}/outputs/voice.wav`。
- **Windows 风险**：**高**。依赖 `torch`, `torchaudio`, `onnxruntime` 等深度学习包。Windows 上需要安装正确的 CUDA 环境以获得可用性能。此外，大模型须提前下载到 `pretrained_models/` 目录。
- **验证方法**：准备好模型文件并在 `.env.local` 配置路径，点击“生成音频”，观察终端有无缺失 DLL 或环境报错。

## 5. 音色管理

- **音色来源**：非前端 Mock，由后端真实读取并管理。
- **依赖文件**：每个音色需要 `reference.wav` 和对应的文本配置。存放在 `runtime/content_lab/voices/` 目录下。
- **Windows 风险**：低。使用 `pathlib.Path.glob` 遍历读取 JSON 和 WAV 文件，无系统强绑定风险。

## 6. currentAudio 回写和播放

- **后端返回**：通过 FastAPI 的 `FileResponse` 或 URL Router 提供访问接口 (如 `/api/v1/files/transcriptions/.../audio.wav`)。
- **前端状态**：`currentProject.currentAudio` 记录 API 路由供 HTML5 Audio 播放。
- **静态挂载**：后端通过 `app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR))` 挂载静态目录。
- **Windows URL 风险**：FastAPI 及 Starlette 底层良好支持 Windows 路径与 Web URL 的转换，只要后端没用 `\` (反斜杠) 手动拼接字符串就不会出现 404。

## 7. 字幕

- **当前实现**：调用 `/api/v1/transcriptions`。后端通过 `transcriptions_service.py` 使用 `faster-whisper` 进行音频 ASR 识别。
- **依赖**：`faster-whisper` (底层为 CTranslate2)。
- **Windows 风险**：中。`faster-whisper` 在 Windows 上支持良好，但需要保证 Python 环境中相关依赖（包括 cuDNN）已正确部署。输出格式为 `srt`, `vtt`，无特定系统风险。

## 8. BGM

- **当前实现**：前端在 `App.vue` 有 `selectedBgm` 与音量控制。
- **后端**：当前 API 层面未发现强绑定的服务端自动混音合并逻辑（无 `bgm_controller`），主要依赖前端状态预览或分离的处理流。
- **Windows 风险**：尚未强依赖服务端复杂 ffmpeg 混流，风险低。

## 9. 导出

- **当前实现**：前端具备 `ExportPanel.vue` 组件交互。
- **输入产物**：当前脚本（currentScript）、生成音频（currentAudio）、视视频素材。
- **Windows 风险**：后续若在后端完全实现 `ffmpeg` 最终混音合轨，Windows 下必须用双引号包裹路径参数，以防 Program Files 等带空格路径引发截断。

## 10. Windows 必装环境

- Git
- Node.js (建议 20 或 22 LTS)
- Python 3.10 或 3.11
- `uv` 包管理器
- `ffmpeg` (必须添加到系统的环境变量 PATH 中)
- (可选) Docker Desktop，用于运行数字人 POC 容器 (如 Duix-Avatar)
- (可选) NVIDIA Driver & CUDA Toolkit 12.x（供 GPU 加速的 TTS / ASR / 数字人使用）

## 11. Windows 首次启动步骤

1. `git clone https://github.com/shenliuming/inlook-yolo-model-lab.git`
2. **启动前端**：
   ```cmd
   cd inlook-studio-web
   npm install
   npm run dev
   ```
3. **启动后端**：
   ```cmd
   cd apps\yolo-api
   uv venv --python 3.11
   .venv\Scripts\activate
   uv pip install -r requirements.txt
   ```
4. **环境变量**：在 `apps\yolo-api` 下复制/创建 `.env.local`，填入 `LLM_API_KEY` 等关键 Key，设置 `COSYVOICE_MODEL_DIR=pretrained_models/CosyVoice2-0.5B`。
5. **验证运行**：
   ```cmd
   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   并验证 ffmpeg：
   ```cmd
   ffmpeg -version
   ```

## 12. 风险清单

- **必须修 (高危)**：若未将 `ffmpeg` 加入系统 PATH，后端素材上传/封面提取等流程将立即崩溃。
- **必须修 (高危)**：深度学习相关的库 (torch, onnxruntime) 可能在 Windows 下因缺少 `VC++ Redistributable` 报错，首次运行需观察。
- **不影响主流程**：后续即将开启的 Duix 数字人 POC 将完全运行于 Docker 环境下，对本机主项目的依赖互不干扰。
