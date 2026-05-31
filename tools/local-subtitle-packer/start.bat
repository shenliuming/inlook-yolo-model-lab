@echo off
setlocal
cd /d %~dp0

if not exist .venv (
  py -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python scripts\check_env.py
if errorlevel 1 exit /b 1

start http://127.0.0.1:7860
python -m uvicorn scripts.web_app:app --host 127.0.0.1 --port 7860 --app-dir .
