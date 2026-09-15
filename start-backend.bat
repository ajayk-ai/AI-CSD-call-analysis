@echo off
REM Starts the FastAPI backend on the HOST/PORT set in backend\.env
REM (defaults to http://localhost:8000, API docs at /docs).
setlocal
cd /d "%~dp0backend"

if not exist ".env" (
    echo [X] backend\.env is missing. Run setup.bat first.
    pause
    exit /b 1
)

REM HOST/PORT below are read from .env by app/config.py at runtime (via
REM `python -m app.main`) - these local defaults are only for the echoed URL.
set "PORT=8000"
set "PROBE_HOST=localhost"
for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
    if "%%A"=="PORT" if not "%%B"=="" set "PORT=%%B"
    if "%%A"=="HOST" if not "%%B"=="" if /i not "%%B"=="0.0.0.0" set "PROBE_HOST=%%B"
)

echo Starting backend on http://%PROBE_HOST%:%PORT%  (Ctrl+C to stop)
echo.
call uv run python -m app.main
