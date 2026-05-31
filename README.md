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
- 本地字幕工具

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

### 3. Start FastAPI

```bash
cd apps/yolo-api
uv run uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

### 4. Start frontend

```bash
cd apps/yolo-web
npm install
npm run dev
```

### 5. Open the local page

- Frontend: `http://127.0.0.1:5173`
- Backend health: `http://127.0.0.1:8000/api/health`

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
│   │   ├── models/
│   │   ├── requirements.txt
│   │   ├── uploads/
│   │   ├── outputs/
│   │   └── reports/
│   └── yolo-web/
│       └── Vue frontend
├── tools/
│   └── local-subtitle-packer/
├── assets/
│   └── demo/
├── docs/
├── deploy/
└── README.md
```

## Local Subtitle Tool

The repository also includes a separate local subtitle utility:

- `tools/local-subtitle-packer`

Use cases:

- 视频原声自动字幕
- 录屏视频 + 单独真人语音字幕
- 本地输出 `mp4 / srt / ass / txt`

This tool is independent from the YOLO apps. It does not reuse the YOLO backend and should not be described as part of the `/yolo/` recognition flow.

Recommended workflow with `uv`:

```bash
cd tools/local-subtitle-packer
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv run python scripts/check_env.py
```

## Backend

Recommended startup:

```bash
cd apps/yolo-api
uv venv --python 3.11
uv pip install -r requirements.txt
uv run uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

API endpoints:

- `GET /api/health`
- `GET /api/models`
- `POST /api/detect/image`
- `POST /api/detect/video`
- `POST /api/realtime/detect`

Static result paths:

- `/outputs`
- `/reports`

## Frontend

```bash
cd apps/yolo-web
npm install
npm run dev
```

Open:

- `http://127.0.0.1:5173`

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
