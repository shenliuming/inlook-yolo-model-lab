#!/bin/bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python scripts/check_env.py

( sleep 2; open "http://127.0.0.1:7860" ) >/dev/null 2>&1 &
python -m uvicorn scripts.web_app:app --host 127.0.0.1 --port 7860 --app-dir .
