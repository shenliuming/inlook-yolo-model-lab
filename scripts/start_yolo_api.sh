#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/apps/yolo-api"
VENV_DIR="$APP_DIR/.venv"
UV_CACHE_DIR="${UV_CACHE_DIR:-$ROOT_DIR/.uv-cache}"
HOST="${INLOOK_YOLO_API_HOST:-127.0.0.1}"
PORT="${INLOOK_YOLO_API_PORT:-7860}"

cd "$APP_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "未检测到 uv，请先安装：brew install uv" >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  echo "[setup] 创建 Python 虚拟环境..."
  uv venv --python 3.11
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
  echo "虚拟环境不完整，请删除 $VENV_DIR 后重试。" >&2
  exit 1
fi

mkdir -p "$UV_CACHE_DIR"
export UV_CACHE_DIR

if ! "$VENV_DIR/bin/python" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  echo "[setup] 安装后端依赖..."
  uv pip install -r requirements.txt
fi

export TTS_ENGINE="${TTS_ENGINE:-cosyvoice}"
export COSYVOICE_MODEL_DIR="${COSYVOICE_MODEL_DIR:-$ROOT_DIR/pretrained_models/CosyVoice2-0.5B}"
export COSYVOICE_DEVICE="${COSYVOICE_DEVICE:-auto}"
export COSYVOICE_SAMPLE_RATE="${COSYVOICE_SAMPLE_RATE:-24000}"

echo "[start] yolo-api -> http://$HOST:$PORT"
exec uv run uvicorn app:app --reload --host "$HOST" --port "$PORT"
