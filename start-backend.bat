@echo off
REM Starts the FastAPI backend on http://localhost:8000
REM (API docs at http://localhost:8000/docs)
setlocal
cd /d "%~dp0backend"

if not exist ".env" (
    echo [X] backend\.env is missing. Run setup.bat first.
    pause
    exit /b 1
)

echo Starting backend on http://localhost:8000  (Ctrl+C to stop)
echo.
call uv run uvicorn app.main:app --port 8000
