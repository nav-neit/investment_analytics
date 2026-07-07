@echo off
REM VittaLens server start script (Windows).
REM Creates the virtual environment on first run, installs dependencies,
REM then starts the app on port 8030. Usage: start_server.bat
cd /d "%~dp0"

if not exist ".venv" (
    echo [vittalens] creating virtual environment...
    python -m venv .venv
)
call .venv\Scripts\activate.bat

echo [vittalens] installing dependencies...
pip install --quiet -r backend\requirements.txt

echo [vittalens] starting on http://127.0.0.1:8030 ...
uvicorn backend.main:app --host 0.0.0.0 --port 8030
