@echo off
chcp 65001 >NUL
cd /d "%~dp0"
set "TASK_NAME=FACTUM Bot"
set "LAUNCHER_PATH=%~dp0run_facts_service.bat"
set "PYTHON_PATH=python"

echo ============================================
echo  Установка автозапуска бота FACTUM
echo ============================================
echo.
echo Бот будет запускаться при каждом входе в систему.
echo.
echo Лаунчер: %LAUNCHER_PATH%
echo Лог:     %~dp0logs\facts.log
echo.
echo ВАЖНО: в файле .env.facts должен быть заполнен BOT_TOKEN.
echo.
schtasks /create /tn "%TASK_NAME%" /tr "cmd.exe /c \"%LAUNCHER_PATH%\"" /sc onlogon /delay 0000:01:00 /f /ru "%USERNAME%"

if %errorlevel% equ 0 (
    echo.
    echo [OK] Задача создана успешно!
    echo.
    echo Для удаления задачи выполните:
    echo   schtasks /delete /tn "%TASK_NAME%" /f
) else (
    echo.
    echo [ERR] Ошибка при создании задачи
    echo Запустите файл от имени администратора.
)

pause
