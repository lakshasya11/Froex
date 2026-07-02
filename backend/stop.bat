@echo off
cd /d "%~dp0"
title Forex Trading Bot - STOP

echo ==========================================
echo    SENDING STOP SIGNAL...
echo ==========================================

:: 1. Create a stop flag file (safe pause)
echo STOP > STOP_TRADING.txt
echo [INFO] STOP_TRADING.txt flag created.

:: 2. Try to close the bot window directly
echo [INFO] Searching for running bot window...
taskkill /FI "WINDOWTITLE eq Forex Trading Bot - START*" /T /F >nul 2>&1

if %errorlevel% equ 0 (
    echo [SUCCESS] Bot terminal found and closed.
) else (
    echo [INFO] Bot terminal not found (or already closed).
    echo [INFO] The stop flag is set for the next time the bot runs.
)

echo.
echo [DONE] Trading has been disabled.
echo ==========================================
timeout /t 5
