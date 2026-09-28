@echo off
chcp 65001 >NUL
cd /d "%~dp0"
set "DOTENV_PATH=%~dp0.env"
python tiktok_authorize.py
pause
