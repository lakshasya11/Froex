@echo off
echo ==========================================
echo    STOPPING FOREX TRADING SYSTEM
echo ==========================================
echo.

echo [1/2] Sending graceful stop signal to MT5 Python Backend...
cd backend
call stop.bat
cd ..

echo [2/2] Shutting down Next.js Web Dashboard...
:: Kills the specific terminal window running the frontend
taskkill /F /FI "WINDOWTITLE eq Forex Web Dashboard*" /T >nul 2>&1

echo.
echo ==========================================
echo ✅ System shutdown initiated!
echo The Python Bot will finish its current tick and safely close.
echo You can safely press any key to close the remaining windows.
echo ==========================================
pause
