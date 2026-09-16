@echo off
REM ===================================================================
REM  CSD Call Analysis - one-time setup for a new Windows machine.
REM
REM  Installs backend + frontend dependencies, creates backend\.env from
REM  the template if it is missing, and applies database migrations.
REM  Safe to re-run: every step is idempotent.
REM ===================================================================
setlocal
cd /d "%~dp0"

echo.
echo ================================================================
echo   CSD Call Analysis - Setup
echo ================================================================
echo.

REM --- Prerequisites ------------------------------------------------
where uv >nul 2>&1
if errorlevel 1 (
    echo [X] 'uv' is not installed or not on PATH.
    echo     uv manages the Python version and the backend virtualenv.
    echo     Install it with:
    echo         powershell -c "irm https://astral.sh/uv/install.ps1 ^| iex"
    echo     then close and reopen this window and run setup.bat again.
    goto :fail
)
echo [OK] uv found

where npm >nul 2>&1
if errorlevel 1 (
    echo [X] 'npm' is not installed or not on PATH.
    echo     Install Node.js LTS from https://nodejs.org/ , then reopen
    echo     this window and run setup.bat again.
    goto :fail
)
echo [OK] npm found

REM --- Backend dependencies ----------------------------------------
echo.
echo [1/4] Installing backend dependencies (uv sync)...
pushd backend
call uv sync
if errorlevel 1 (
    echo [X] uv sync failed.
    popd
    goto :fail
)
echo [OK] Backend dependencies installed

REM --- Environment file --------------------------------------------
echo.
echo [2/4] Checking backend\.env ...
if exist ".env" (
    echo [OK] backend\.env already exists - leaving it untouched
) else (
    copy /y ".env.example" ".env" >nul
    echo [!] Created backend\.env from the template.
    echo.
    echo     YOU MUST EDIT IT BEFORE RUNNING AN ANALYSIS. Set at least:
    echo         GEMINI_API_KEY   - from Google AI Studio
    echo         DB_PASSWORD      - your local Postgres password
    echo.
    echo     Opening it in Notepad; save and close to continue...
    notepad ".env"
)

REM --- Database migrations -----------------------------------------
echo.
echo [3/4] Applying database migrations...
call uv run alembic upgrade head
if errorlevel 1 (
    echo.
    echo [X] Migrations failed. The usual causes:
    echo       - Postgres is not running on this machine
    echo       - DB_USER / DB_PASSWORD in backend\.env are wrong
    echo       - the database does not exist yet; create it with:
    echo             createdb csd_call_analysis
    echo         (or in psql:  CREATE DATABASE csd_call_analysis;)
    popd
    goto :fail
)
echo [OK] Database schema is up to date
popd

REM --- Frontend dependencies ---------------------------------------
echo.
echo [4/4] Installing frontend dependencies (npm install)...
pushd frontend
call npm install
if errorlevel 1 (
    echo [X] npm install failed.
    popd
    goto :fail
)
popd
echo [OK] Frontend dependencies installed

echo.
echo ================================================================
echo   Setup complete.
echo.
echo   Next:
echo     verify-setup.bat   check Postgres, GCS and Gemini actually work
echo     start.bat          launch the backend + dashboard
echo ================================================================
echo.
pause
exit /b 0

:fail
echo.
echo Setup did not complete. Fix the problem above and run setup.bat again.
echo.
pause
exit /b 1
