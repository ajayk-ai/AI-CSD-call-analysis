@echo off
REM ===================================================================
REM  Checks that this machine can actually reach everything the
REM  pipeline needs: Postgres, the GCS bucket, and the Gemini API.
REM
REM  Run this after setup.bat, before the first real analysis - it
REM  turns "Run Analysis did nothing" into a specific, fixable answer.
REM  The Gemini probe sends one tiny prompt (a fraction of a cent).
REM ===================================================================
setlocal
cd /d "%~dp0backend"

if not exist ".env" (
    echo [X] backend\.env is missing. Run setup.bat first.
    pause
    exit /b 1
)

echo.
echo Checking Postgres, GCS and Gemini - this takes a few seconds...
echo.

call uv run python scripts/verify_setup.py

if errorlevel 1 (
    echo.
    echo ================================================================
    echo   Something above is not working. Common fixes:
    echo.
    echo   database : is Postgres running? Are DB_USER / DB_PASSWORD in
    echo              backend\.env right? Does the database exist?
    echo                  CREATE DATABASE csd_call_analysis;
    echo              Then re-run setup.bat to apply migrations.
    echo.
    echo   gcs      : run  gcloud auth application-default login
    echo              or point GOOGLE_APPLICATION_CREDENTIALS at a
    echo              service-account JSON with Storage Object Viewer.
    echo.
    echo   gemini   : check GEMINI_API_KEY in backend\.env. A 404 about
    echo              the model means GEMINI_MODEL is retired for your
    echo              key - gemini-3.5-flash-lite is the current cheap tier.
    echo ================================================================
    echo.
    pause
    exit /b 1
)

echo.
echo ================================================================
echo   All checks passed. Run start.bat to launch the app.
echo ================================================================
echo.
pause
exit /b 0
