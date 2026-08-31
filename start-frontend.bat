@echo off
REM Starts the Vite dev server on http://localhost:5173
setlocal
cd /d "%~dp0frontend"

if not exist "node_modules" (
    echo [X] frontend\node_modules is missing. Run setup.bat first.
    pause
    exit /b 1
)

echo Starting dashboard on http://localhost:5173  (Ctrl+C to stop)
echo.
call npm run dev
