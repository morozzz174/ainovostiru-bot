@echo off
chcp 65001 >NUL
cd /d "%~dp0"
set DOTENV_PATH=.env.beauty
set THEME=beauty
set BRAND_NAME=AESTHETIC.RU
set DATABASE_PATH=bot_beauty.db
python main.py --once
pause
