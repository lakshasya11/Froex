@echo off
cd /d "%~dp0"
title Forex Trading Bot - 24HR DEMO RUN

echo ==========================================
echo    FOREX TRADING BOT - 24HR DEMO RUN
echo ==========================================

:: Disable QuickEdit mode (prevents pausing when clicking the window)
powershell -NoProfile -Command "$h = Get-StdHandle -10; $m = 0; if (Get-ConsoleMode $h ([ref]$m)) { Set-ConsoleMode $h ($m -band -bnot 0x0040) }" >nul 2>&1

:: Clear the stop flag if it exists
if exist STOP_TRADING.txt (
    del STOP_TRADING.txt
    echo [INFO] Stop flag cleared. Resuming trading...
)

:: Detect Python Command
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

:: ── AUTO-RESTART LOOP ──────────────────────────────────────────────────────
:: The bot restarts automatically if it exits for any reason EXCEPT a clean stop.
:: To stop the loop: close this window, or create STOP_TRADING.txt in this folder.
:RESTART_LOOP

    :: Check for manual stop signal
    if exist STOP_TRADING.txt (
        echo.
        echo [INFO] STOP_TRADING.txt detected — shutting down permanently.
        echo ==========================================
        echo    BOT STOPPED (Manual Stop)
        echo ==========================================
        pause
        exit /b
    )

    echo [%date% %time%] Starting bot...
    %PYTHON_CMD% main.py
    set EXIT_CODE=%errorlevel%

    :: Check again for stop signal before restarting
    if exist STOP_TRADING.txt (
        echo.
        echo [INFO] STOP_TRADING.txt detected — NOT restarting.
        echo ==========================================
        echo    BOT STOPPED (Manual Stop)
        echo ==========================================
        pause
        exit /b
    )

    echo.
    if %EXIT_CODE% neq 0 (
        echo [%date% %time%] Bot exited with error code %EXIT_CODE%.
        echo [INFO] Waiting 10 seconds before auto-restart...
        echo [TIP]  Make sure MetaTrader 5 is running and connected.
        timeout /t 10 /nobreak >nul
    ) else (
        echo [%date% %time%] Bot exited cleanly. Restarting in 5 seconds...
        timeout /t 5 /nobreak >nul
    )

    echo ──────────────────────────────────────────
    goto RESTART_LOOP
