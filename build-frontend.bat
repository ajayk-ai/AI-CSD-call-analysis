@echo off
REM ===================================================================
REM  Builds the dashboard into frontend\dist so the FastAPI backend can
REM  serve it directly (see start-prod.bat) - no separate Vite server,
REM  one process, one port.
REM
REM  Re-run this after any frontend code change; start-prod.bat serves
REM  whatever is currently in frontend\dist, it does not rebuild for you.
REM ===================================================================
setlocal
cd /d "%~dp0frontend"

if not exist "node_modules" (
    echo [X] frontend\node_modules is missing. Run setup.bat first.
    pause
    exit /b 1
)

echo Building dashboard...
call npm run build
if errorlevel 1 (
    echo [X] Build failed - see the error above.
    pause
    exit /b 1
)

echo.
echo [OK] Built to frontend\dist
echo      Run start-prod.bat to serve it.
