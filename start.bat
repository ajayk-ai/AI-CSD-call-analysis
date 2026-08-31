@echo off
REM ===================================================================
REM  DEV MODE: launches the backend and the Vite dev server, each in
REM  its own window, then opens the browser once both answer. Frontend
REM  edits hot-reload instantly - use this while working on the UI.
REM
REM  Just want to run the app, not edit it? Use start-prod.bat instead:
REM  one process, one port, no separate dev server.
REM
REM  Close either window, or run stop.bat, to shut things down.
REM ===================================================================
setlocal
cd /d "%~dp0"

if not exist "backend\.env" (
    echo [X] backend\.env is missing. Run setup.bat first.
    pause
    exit /b 1
)
if not exist "frontend\node_modules" (
    echo [X] frontend\node_modules is missing. Run setup.bat first.
    pause
    exit /b 1
)

REM NOTE: `start "title" /d "dir" cmd /k <cmd>` - the working directory goes in
REM start's /d switch. Do NOT fold it into the command as
REM `cmd /k "cd /d "%~dp0backend" && ..."`: those nested quotes do not survive
REM cmd's parser when the project path contains spaces, and both windows exit
REM immediately without an error.
echo Starting backend...
start "CSD Backend" /d "%~dp0backend" cmd /k uv run uvicorn app.main:app --port 8000

echo Waiting for the API...
powershell -NoProfile -Command "$ok=$false; foreach($i in 1..60){ try{ Invoke-RestMethod 'http://localhost:8000/api/health' -TimeoutSec 2 | Out-Null; $ok=$true; break }catch{ Start-Sleep -Milliseconds 750 } }; if($ok){ Write-Host '[OK] Backend is up.' -ForegroundColor Green } else { Write-Host '[!] Backend did not answer in time - check the CSD Backend window for the error.' -ForegroundColor Yellow }"

echo Starting dashboard...
start "CSD Dashboard" /d "%~dp0frontend" cmd /k npm run dev

echo Waiting for the dashboard...
powershell -NoProfile -Command "foreach($i in 1..60){ try{ Invoke-WebRequest 'http://localhost:5173' -TimeoutSec 2 -UseBasicParsing | Out-Null; break }catch{ Start-Sleep -Milliseconds 750 } }"

start "" http://localhost:5173

echo.
echo ================================================================
echo   Dashboard : http://localhost:5173
echo   API docs  : http://localhost:8000/docs
echo.
echo   Click "Run Analysis" to process the next batch of recordings.
echo   Batch size = PIPELINE_RUN_LIMIT in backend\.env (default 5).
echo.
echo   Two windows opened: "CSD Backend" and "CSD Dashboard".
echo   Close them, or run stop.bat, to shut everything down.
echo ================================================================
echo.
pause
