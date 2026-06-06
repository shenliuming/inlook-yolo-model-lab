# INLOOK YOLO Model Lab

一个用于图片、视频和摄像头识别测试的本地 YOLO 网页实验平台。

INLOOK YOLO Model Lab is a local-first YOLO web lab for image, video, and camera-based recognition tests. It is designed for computer vision learning, model validation, demo recording, and lightweight internal tooling.

## Online Demo

- [https://in-look.cn/yolo/](https://in-look.cn/yolo/)

## Features

- 图片识别
- 视频识别
- 摄像头识别
- OBS 虚拟摄像头
- 模型切换
- 运行日志
- JSON 测试报告
- 结果下载
- 字幕识别
- TTS 配音生成

## Screenshots

Project screenshots can be placed here:

- `docs/images/home.png`
- `docs/images/yolo-demo.png`

Current repository state:

- Screenshot placeholders only
- No fake images generated in README

## Quick Start

### 1. Install `uv`

```bash
brew install uv
```

### 2. Install backend dependencies

```bash
cd apps/yolo-api
uv venv --python 3.11
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 2.1 Prepare MOSS-TTS-Nano for local TTS

```bash
git clone https://github.com/OpenMOSS/MOSS-TTS-Nano.git third_party/MOSS-TTS-Nano
cd apps/yolo-api
uv pip install -r requirements.txt
```

Recommended ONNX CPU smoke test:

```bash
cd third_party/MOSS-TTS-Nano
python infer_onnx.py \
  --text "你好，这里是 INLOOK AI 内容工作流。" \
  --voice Junhao \
  --execution-provider cpu
```

If you prefer the CLI entry:

```bash
cd third_party/MOSS-TTS-Nano
python -m moss_tts_nano.cli generate \
  --backend onnx \
  --text "你好，这里是 INLOOK AI 内容工作流。" \
  --voice Junhao \
  --execution-provider cpu
```

### 3. Start FastAPI

```bash
cd apps/yolo-api
uv run uvicorn app:app --reload --host 127.0.0.1 --port 7860
```

### 4. Start frontend

```bash
cd apps/yolo-web
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

### 5. Open the local page

- Frontend: `http://127.0.0.1:5173`
- Backend health: `http://127.0.0.1:7860/api/health`

If you want to use the old local backend port `8000`, start Vite with:

```bash
VITE_API_TARGET=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1 --port 5173
```

## Compliance

本项目仅用于计算机视觉学习、模型测试和内容创作。  
系统只输出识别结果，不提供任何游戏控制、自动操作或绕过机制。

## Want To Train Your Own Model?

如果你正在训练自己的 YOLO 模型，可以先准备这些材料：

- `data.yaml`
- 训练结果图
- 少量样本图
- 测试视频

这样更容易判断问题可能出在：

- 数据本身
- 标注质量
- 类别设计
- 训练参数
- 场景差异

## Project Structure

```text
inlook-yolo-model-lab/
├── apps/
│   ├── yolo-api/
│   │   ├── app.py
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── controllers/
│   │   │   ├── services/
│   │   │   ├── clients/
│   │   │   ├── config/
│   │   │   ├── common/
│   │   │   └── utils/
│   │   ├── models/
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── yolo-web/
│       ├── src/api/
│       ├── src/components/
│       ├── src/App.vue
│       └── Vue frontend
├── assets/
│   └── demo/
├── docs/
├── deploy/
├── third_party/
│   └── MOSS-TTS-Nano/      # local clone, not committed with models/generated_audio
└── README.md
```

## AI Content Workflow

The content workflow is separate from the YOLO vision lab. It currently includes:

- Material Intake
- Subtitle Recognition
- TTS Voice Generation

Subtitle-related files are integrated into the backend service layer:

- `apps/yolo-api/app/services/subtitle_tool/subtitle_pack.py`
- `apps/yolo-api/app/services/subtitle_tool/burn_subtitles.py`
- `apps/yolo-api/app/services/subtitle_tool/check_env.py`

TTS-related files:

- `apps/yolo-api/app/controllers/tts_controller.py`
- `apps/yolo-api/app/services/tts_service.py`
- `apps/yolo-api/app/clients/moss_tts_client.py`

TTS runtime output:

- `apps/yolo-api/runtime/content_lab/tts/tasks/{task_id}/inputs`
- `apps/yolo-api/runtime/content_lab/tts/tasks/{task_id}/outputs`
- `apps/yolo-api/runtime/content_lab/tts/tasks/{task_id}/run.log`

Helpful docs:

- `docs/subtitle-workflow/example_usage.md`
- `docs/subtitle-workflow/PRODUCTION_WORKFLOW.md`

Quick env check:

```bash
uv run python apps/yolo-api/app/services/subtitle_tool/check_env.py
```

## Backend

Recommended startup:

```bash
cd apps/yolo-api
uv venv --python 3.11
uv pip install -r requirements.txt
uv run uvicorn app:app --reload --host 127.0.0.1 --port 7860
```

API endpoints:

- `GET /api/v1/health`
- `GET /api/v1/vision/health`
- `GET /api/v1/vision/models`
- `POST /api/v1/vision/models/select`
- `POST /api/v1/vision/images/detect`
- `POST /api/v1/vision/videos/detect`
- `POST /api/v1/vision/realtime/detect`
- `GET /api/v1/vision/tasks/{task_id}`
- `GET /api/v1/vision/tasks/{task_id}/files/{filename}`
- `GET /api/v1/content-lab/health`
- `GET /api/v1/content-lab/materials/health`
- `POST /api/v1/content-lab/materials/tasks`
- `GET /api/v1/content-lab/materials/tasks/{task_id}`
- `GET /api/v1/content-lab/materials/tasks/{task_id}/files/{filename}`
- `GET /api/v1/content-lab/subtitles/health`
- `POST /api/v1/content-lab/subtitles/tasks`
- `GET /api/v1/content-lab/subtitles/tasks/{task_id}`
- `POST /api/v1/content-lab/subtitles/tasks/{task_id}/reburn`
- `GET /api/v1/content-lab/subtitles/tasks/{task_id}/files/{filename}`
- `GET /api/v1/content-lab/tts/health`
- `POST /api/v1/content-lab/tts/tasks`
- `GET /api/v1/content-lab/tts/tasks/{task_id}`
- `GET /api/v1/content-lab/tts/tasks/{task_id}/files/{filename}`

Compatibility endpoints are still available:

- `GET /api/models`
- `POST /api/detect/image`
- `POST /api/detect/video`
- `POST /api/realtime/detect`
- `POST /api/materials/tasks`
- `GET /api/materials/tasks/{task_id}`
- `GET /api/materials/tasks/{task_id}/files/{filename}`

Static result paths:

- `/outputs`
- `/reports`

## Frontend

```bash
cd apps/yolo-web
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:

- `http://127.0.0.1:5173`

Frontend routes:

- `/`
- `/vision-lab`
- `/vision-lab/model-test`
- `/vision-lab/image`
- `/vision-lab/video`
- `/vision-lab/realtime`
- `/content-workflow`
- `/content-workflow/material-intake`
- `/content-workflow/subtitle-recognition`
- `/content-workflow/tts`
- `/content-lab`
- `/content-lab/material-intake`
- `/content-lab/subtitle-recognition`
- `/content-lab/tts`

Legacy redirects:

- `/material-intake` -> `/content-workflow/material-intake`
- `/content-intake` -> `/content-workflow/material-intake`
- `/vision-lab/image-detect` -> `/vision-lab/image`
- `/vision-lab/video-detect` -> `/vision-lab/video`
- `/vision-lab/realtime-detect` -> `/vision-lab/realtime`

Shared frontend modules:

- `src/api/client.js`
- `src/api/vision.js`
- `src/api/workflow.js`
- `src/api/contentLabApi.js`
- `src/components/StatusCard.vue`
- `src/components/TaskLog.vue`
- `src/components/FileDownloadList.vue`

## Camera Mode

- Frontend uses `getUserMedia()` to open camera devices
- Supports standard cameras and OBS virtual camera selection
- Captures frames and sends them to the backend for YOLO inference
- Draws boxes, labels, and confidence values on overlay canvas
- Shows the latest JSON result in realtime mode

## Models

Default custom model:

- `apps/yolo-api/models/inlook/best.pt`

Scanned model directories:

- `apps/yolo-api/models/official/*.pt`
- `apps/yolo-api/models/inlook/*.pt`

Security-related constraints:

- Model files stay in backend-only storage
- Nginx does not expose model directories
- FastAPI does not mount model directories as static paths
- `/api/models` returns display metadata instead of real model file paths
- Report JSON does not expose real model file paths
- Image upload limit: `10MB`
- Video upload limit: `200MB`
- Realtime frame upload limit: `4MB`
- Allowed image types: `jpg/jpeg/png`
- Allowed video type: `mp4`
- Basic IP rate limiting is enabled in backend
- Old uploads / outputs / reports are cleaned periodically
- Optional `INLOOK_API_KEY` is supported for internal access control

## Internal API Key

If you want to restrict who can call the backend:

```bash
INLOOK_API_KEY=your-secret-key
```

If frontend should attach the same key automatically before build:

```bash
VITE_INTERNAL_API_KEY=your-secret-key
```

The frontend will send:

```txt
X-INLOOK-Key: your-secret-key
```

## Docker Deployment

The project already includes a Docker-based deployment structure for ECS / VM deployment.

Files already included:

- `apps/yolo-api/Dockerfile`
- `apps/yolo-web/Dockerfile`
- `deploy/nginx.conf`
- `docker-compose.yml`
- `.dockerignore`

### Before deployment

Make sure the server already has:

- Docker
- Docker Compose Plugin
- Model file `apps/yolo-api/models/inlook/best.pt`

Optional official models:

- `apps/yolo-api/models/official/yolo11n.pt`
- `apps/yolo-api/models/official/yolo11s.pt`
- `apps/yolo-api/models/official/yolov8n.pt`

### Start

```bash
docker compose up -d --build
```

After startup:

- Frontend: `http://your-server-ip/`
- Backend health: `http://your-server-ip/api/health`

### Stop

```bash
docker compose down
```

### Docker cache note

For normal backend updates:

```bash
docker compose build backend
docker compose up -d backend
```

Avoid using:

```bash
docker compose build --no-cache backend
```

because it forces large dependencies such as `torch`, `ultralytics`, and `opencv` to be downloaded again.

## Deploy Under `in-look.cn/yolo/`

If you want to mount the frontend under an existing website path:

- Page entry: `https://in-look.cn/yolo/`
- Backend API: `https://in-look.cn/yolo/api/*`
- Result files: `https://in-look.cn/yolo/outputs/*`
- Report files: `https://in-look.cn/yolo/reports/*`

Build frontend with subpath base:

```bash
cd apps/yolo-web
VITE_PUBLIC_BASE=/yolo/ npm run build
```

Then publish `apps/yolo-web/dist/` to:

```bash
/var/www/in-look.cn/html/yolo/
```

## Notes

Please do not commit:

- model files
- videos
- audio files
- training datasets
- generated subtitle outputs
- generated recognition outputs

## INLOOK Studio LLM 配置

提示词改写、文案校对和标题生成统一走 OpenAI-compatible Chat Completions 服务。不要把真实 API Key 写进代码，使用环境变量：

```bash
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://your-model-service/v1
LLM_API_KEY=your_api_key
LLM_MODEL=your-model-name
LLM_TIMEOUT_SECONDS=60
```

未配置时 `GET /api/v1/ai/status` 会返回 `available=false`，前端会禁用 AI 改写按钮，不会生成 mock 文案。
