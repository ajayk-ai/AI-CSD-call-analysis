@echo off
REM ===================================================================
REM  Stops whatever this project left listening on ports 8000 and 5173.
REM
REM  Targets processes BY PORT rather than by image name, so it will not
REM  kill an unrelated python.exe or node.exe you have running.
REM ===================================================================
setlocal
cd /d "%~dp0"

echo.
echo Stopping CSD Call Analysis processes...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\stop.ps1"

echo.
echo Done. Any "CSD Backend" / "CSD Dashboard" windows can be closed.
echo.
pause
