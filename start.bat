@echo off
echo ==========================================
echo    STARTING FOREX TRADING SYSTEM
echo ==========================================
echo.

echo [1/2] Starting MT5 Python Backend...
start "Forex MT5 Backend" cmd /k "cd backend && start.bat"

echo [2/2] Starting Next.js Web Dashboard...
start "Forex Web Dashboard" cmd /k "cd frontend && npm run dev"

echo.
echo ==========================================
echo ✅ All systems launched successfully!
echo You can now access your dashboard at http://localhost:3000
echo ==========================================
pause
