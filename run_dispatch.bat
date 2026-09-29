@echo off
chcp 65001 >NUL
cd /d "%~dp0"
if "%~1"=="" set "TARGET=all"
python github_dispatch.py %TARGET%
pause
