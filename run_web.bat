@echo off
chcp 65001 >NUL
cd /d "%~dp0"
echo Starting MorozMax web panel on http://127.0.0.1:8000
set "DOTENV_PATH=%~dp0.env"
python -m uvicorn webapp.app:app --host 127.0.0.1 --port 8000
pause
