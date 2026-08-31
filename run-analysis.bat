@echo off
REM ===================================================================
REM  Triggers one analysis run from the command line - the same thing
REM  the dashboard's "Run Analysis" button does.
REM
REM  Usage:
REM      run-analysis.bat        process the default batch (PIPELINE_RUN_LIMIT)
REM      run-analysis.bat 10     process up to 10 recordings
REM      run-analysis.bat 0      process the ENTIRE backlog (costs real money)
REM
REM  Requires the backend to be running already (start-backend.bat).
REM ===================================================================
setlocal
cd /d "%~dp0"

if "%~1"=="" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\run_analysis.ps1"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\run_analysis.ps1" -Limit %~1
)

echo.
pause
