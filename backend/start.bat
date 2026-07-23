@echo off
cd /d "%~dp0"
title Forex Trading Bot - 24HR DEMO RUN

echo ==========================================
echo    FOREX TRADING BOT - 24HR DEMO RUN
echo ==========================================

:: Disable QuickEdit mode
powershell -NoProfile -Command "$h = Get-StdHandle -10; $m = 0; if (Get-ConsoleMode $h ([ref]$m)) { Set-ConsoleMode $h ($m -band -bnot 0x0040) }" >nul 2>&1

:: Clear the stop flag if it exists
if exist STOP_TRADING.txt (
    del STOP_TRADING.txt
    echo [INFO] Stop flag cleared. Resuming trading...
)

set "PYTHON_CMD=python"
%PYTHON_CMD% --version >nul 2>&1
if %errorlevel% neq 0 (
    set "PYTHON_CMD=py"
    %PYTHON_CMD% --version >nul 2>&1
    if %errorlevel% neq 0 (
        set "PYTHON_CMD=python3"
        %PYTHON_CMD% --version >nul 2>&1
        if %errorlevel% neq 0 (
            echo [ERROR] Python not found. Install Python and check "Add to PATH".
            pause
            exit /b
        )
    )
)

echo [INFO] Using: %PYTHON_CMD%
echo [INFO] Bot will AUTO-RESTART if it crashes (for 24hr demo run)
echo [INFO] To STOP permanently: close this window OR create a file named STOP_TRADING.txt
echo.

:RESTART_LOOP
    if exist STOP_TRADING.txt (
        echo.
        echo [INFO] STOP_TRADING.txt detected — shutting down permanently.
        pause
        exit /b
    )

    echo [%date% %time%] Starting bot...
    %PYTHON_CMD% main.py
    set EXIT_CODE=%errorlevel%

    if exist STOP_TRADING.txt (
        echo [INFO] STOP_TRADING.txt detected — NOT restarting.
        pause
        exit /b
    )

    if %EXIT_CODE% neq 0 (
        echo [%date% %time%] Bot exited with error code %EXIT_CODE%.
        timeout /t 10 /nobreak >nul
    ) else (
        echo [%date% %time%] Bot exited cleanly. Restarting in 5 seconds...
        timeout /t 5 /nobreak >nul
    )
    goto RESTART_LOOP
