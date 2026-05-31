# inlook-yolo-model-lab

本地可运行的 YOLO 模型测试平台，前端使用 Vue，后端使用 FastAPI，Python 版本通过 `uv` 管理。

## 合规说明

本工具仅用于合规图像识别、CV 学习、数据集验证和模型测试。系统只输出识别结果图片或视频，不提供任何游戏控制能力。

## 目录结构

```text
inlook-yolo-model-lab/
├── prototype/
│   └── Vue 前端
├── backend/
│   ├── app.py
│   ├── models/
│   │   ├── official/
│   │   └── inlook/
│   │       └── best.pt
│   ├── requirements.txt
│   ├── uploads/
│   ├── outputs/
│   └── reports/
├── assets/
│   └── demo/
├── docs/
└── README.md
```

## 后端启动

推荐使用 `uv`：

```bash
cd backend
uv venv --python 3.11
uv pip install -r requirements.txt
uv run uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```

后端接口：

- `GET /api/health`
- `GET /api/models`
- `POST /api/detect/image`
- `POST /api/detect/video`
- `POST /api/realtime/detect`

静态结果目录：

- `/outputs`
- `/reports`

## 前端启动

```bash
cd prototype
npm install
npm run dev
```

打开：

- `http://127.0.0.1:5173`

## 当前功能

- 图片上传识别
- 视频上传识别
- 摄像头实时识别
- 模型列表扫描与切换
- 结果预览
- 结果下载
- 运行日志
- 测试报告 JSON
- CPU / CUDA 自动检测

## 摄像头模式

- 前端通过 `getUserMedia()` 打开摄像头
- 默认约 `1 FPS` 截帧并发送到后端
- 后端只对单帧做推理，不保存原始摄像头帧
- 前端使用 overlay canvas 绘制识别框、类别和置信度
- 页面展示最近一次识别结果 JSON

## 模型说明

默认自研模型：

- `backend/models/inlook/best.pt`

模型列表会自动扫描：

- `backend/models/official/*.pt`
- `backend/models/inlook/*.pt`

安全约束：

- 模型文件只存放在后端 `backend/models/`
- Nginx 不暴露模型目录
- FastAPI 不挂载模型目录为静态文件
- `/api/models` 只返回模型 ID 和展示信息，不返回真实模型路径
- 报告 JSON 不返回模型文件真实路径
- 图片上传限制为 `10MB`
- 视频上传限制为 `200MB`
- 实时帧上传限制为 `4MB`
- 图片只允许 `jpg/jpeg/png`
- 视频只允许 `mp4`
- 后端带有基础 IP 限流
- 上传历史文件会自动清理，避免磁盘长期堆积
- 支持通过 `INLOOK_API_KEY` 开启内测口令校验

## 内测口令

如果你要限制谁能调用接口，可以在后端容器环境变量中设置：

```bash
INLOOK_API_KEY=your-secret-key
```

前端如果也需要自动带上口令，可以在构建前设置：

```bash
VITE_INTERNAL_API_KEY=your-secret-key
```

前端请求会自动附带：

```txt
X-INLOOK-Key: your-secret-key
```

## Docker 部署

项目已经封装成 Docker 结构，适合直接部署到阿里云 ECS。

新增文件：

- `backend/Dockerfile`
- `prototype/Dockerfile`
- `deploy/nginx.conf`
- `docker-compose.yml`
- `.dockerignore`

### 部署前准备

确认服务器上已有：

- Docker
- Docker Compose Plugin
- 模型文件 `backend/models/inlook/best.pt`

可选官方模型：

- `backend/models/official/yolo11n.pt`
- `backend/models/official/yolo11s.pt`
- `backend/models/official/yolov8n.pt`

### 启动

在项目根目录执行：

```bash
docker compose up -d --build
```

启动后：

- 前端入口：`http://你的服务器IP/`
- 后端健康检查：`http://你的服务器IP/api/health`

### 停止

```bash
docker compose down
```

### Docker 缓存建议

日常更新代码时，优先使用：

```bash
docker compose build backend
docker compose up -d backend
```

不要默认使用：

```bash
docker compose build --no-cache backend
```

`--no-cache` 会强制丢掉镜像层缓存，导致 `torch`、`ultralytics`、`opencv` 这类大包重新下载。

只有在这些场景下，才建议使用 `--no-cache`：

- Dockerfile 刚调整过基础依赖
- `requirements.txt` 改动后怀疑缓存异常
- 构建层明显损坏，需要彻底重建

### 容器说明

- `web`
  - 基于 Nginx
  - 负责提供 Vue 静态页面
  - 反向代理 `/api`、`/outputs`、`/reports`
- `backend`
  - 基于 Python 3.11 + uv
  - 负责 YOLO 推理和报告生成

### 数据目录

以下目录通过 volume 挂载，容器重启后数据仍然保留：

- `./backend/models`
- `./backend/uploads`
- `./backend/outputs`
- `./backend/reports`

### 服务器建议

- CPU 环境也可以运行，但视频识别会慢
- 建议先以内测方式使用，优先体验图片识别和 30 秒内短视频
- 如果后续要多人同时使用，建议再考虑 GPU、任务队列和上传限流

## 挂到 `in-look.cn/yolo/`

如果你要把前端挂到现有官网子路径：

- 页面入口：`https://in-look.cn/yolo/`
- 后端接口：`https://in-look.cn/yolo/api/*`
- 结果文件：`https://in-look.cn/yolo/outputs/*`
- 报告文件：`https://in-look.cn/yolo/reports/*`

前端构建时使用子路径 base：

```bash
cd prototype
VITE_PUBLIC_BASE=/yolo/ npm run build
```

然后把 `prototype/dist/` 下的文件发布到：

```bash
/var/www/in-look.cn/html/yolo/
```

Nginx 在 `in-look.cn` 的 `server` 块里追加：

```nginx
location /yolo/ {
    alias /var/www/in-look.cn/html/yolo/;
    try_files $uri $uri/ /yolo/index.html;
}

location /yolo/api/ {
    proxy_pass http://127.0.0.1:8000/api/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location /yolo/outputs/ {
    proxy_pass http://127.0.0.1:8000/outputs/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location /yolo/reports/ {
    proxy_pass http://127.0.0.1:8000/reports/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

改完后执行：

```bash
nginx -t
systemctl reload nginx
```
