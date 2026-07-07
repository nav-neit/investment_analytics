#!/usr/bin/env bash
# VittaLens server start script (Linux/macOS).
# Creates the virtual environment on first run, installs dependencies,
# then starts the app on port 8030. Usage: ./start_server.sh
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "[vittalens] creating virtual environment..."
    python3 -m venv .venv
fi
source .venv/bin/activate

echo "[vittalens] installing dependencies..."
pip install --quiet -r backend/requirements.txt

echo "[vittalens] starting on http://0.0.0.0:8030 ..."
exec uvicorn backend.main:app --host 0.0.0.0 --port 8030
