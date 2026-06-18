#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/inlook-studio-web"
HOST="${INLOOK_STUDIO_HOST:-127.0.0.1}"
PORT="${INLOOK_STUDIO_PORT:-5180}"

cd "$APP_DIR"

if ! command -v npm >/dev/null 2>&1; then
  echo "未检测到 npm，请先安装 Node.js 和 npm。" >&2
  exit 1
fi

if [ ! -d node_modules ]; then
  echo "[setup] 安装前端依赖..."
  npm install
fi

echo "[start] inlook-studio-web -> http://$HOST:$PORT"
exec npm run dev -- --host "$HOST" --port "$PORT"
