@echo off
chcp 65001 >NUL
cd /d "%~dp0"
set "DOTENV_PATH=%~dp0.env.facts"
if not exist "%~dp0logs" mkdir "%~dp0logs"
python main.py >> "%~dp0logs\facts.log" 2>&1
