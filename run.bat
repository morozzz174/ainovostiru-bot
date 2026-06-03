@echo off
chcp 65001 >NUL
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo ============================================
echo   AINOVOSTI.RU — AI News Bot
echo ============================================
echo.
pip install -r requirements.txt 1>NUL 2>&1
echo   [i] To start: python main.py
echo   [i] For single run: python main.py --once
echo   [i] Press Ctrl+C to stop
echo.
python main.py
pause
