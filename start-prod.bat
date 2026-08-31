@echo off
REM ===================================================================
REM  Single-process launch: builds the dashboard, then starts the
REM  FastAPI backend which serves BOTH the API and the built dashboard
REM  from one port (http://localhost:8000). No separate Vite window,
REM  no CORS involved - everything is same-origin.
REM
REM  Use this for a normal "just run it" session. Use start.bat instead
REM  only if you're editing the frontend and want Vite's hot-reload.
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

echo Building dashboard...
pushd frontend
call npm run build
if errorlevel 1 (
    echo [X] Build failed - see the error above.
    popd
    pause
    exit /b 1
)
popd
echo [OK] Dashboard built

REM See start.bat for why the working directory goes in start's /d switch
REM rather than being folded into the command.
echo.
echo Starting server...
start "CSD App" /d "%~dp0backend" cmd /k uv run uvicorn app.main:app --port 8000

echo Waiting for it to come up...
powershell -NoProfile -Command "$ok=$false; foreach($i in 1..60){ try{ Invoke-RestMethod 'http://localhost:8000/api/health' -TimeoutSec 2 | Out-Null; $ok=$true; break }catch{ Start-Sleep -Milliseconds 750 } }; if($ok){ Write-Host '[OK] Server is up.' -ForegroundColor Green } else { Write-Host '[!] Server did not answer in time - check the CSD App window for the error.' -ForegroundColor Yellow }"

start "" http://localhost:8000

echo.
echo ================================================================
echo   Dashboard + API : http://localhost:8000
echo   API docs        : http://localhost:8000/docs
echo.
echo   Click "Run Analysis" to process the next batch of recordings.
echo   Batch size = PIPELINE_RUN_LIMIT in backend\.env (default 5).
echo.
echo   One window opened: "CSD App". Close it, or run stop.bat, to
echo   shut everything down.
echo.
echo   Made a frontend change? Run build-frontend.bat, then restart
echo   this (or just re-run start-prod.bat).
echo ================================================================
echo.
pause
