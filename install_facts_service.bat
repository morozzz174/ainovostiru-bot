@echo off
chcp 65001 >NUL
cd /d "%~dp0"
set "TASK_NAME=FACTUM Bot"
set "SCRIPT_PATH=%~dp0main.py"
set "PYTHON_PATH=python"

echo ============================================
echo  Установка автозапуска бота FACTUM
echo ============================================
echo.
echo Бот будет запускаться при каждом входе в систему.
echo.
echo Путь к скрипту: %SCRIPT_PATH%
echo.

schtasks /create /tn "%TASK_NAME%" /tr "%PYTHON_PATH% %SCRIPT_PATH%" /sc onlogon /delay 0000:01:00 /f /ru "%USERNAME%"

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
