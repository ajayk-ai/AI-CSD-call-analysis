@echo off
cd /d "%~dp0backend"
uv run python -m app.main
