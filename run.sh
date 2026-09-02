#!/usr/bin/env bash
# BarberStudio dev server: installs deps on first run, frees the port if a
# previous instance is stuck, and serves UI + API from http://localhost:8000
set -euo pipefail

PORT=8000
cd "$(dirname "$0")"

if lsof -ti :"$PORT" >/dev/null 2>&1; then
  echo ">> freeing port $PORT (previous instance found)"
  kill -9 "$(lsof -ti :"$PORT")" 2>/dev/null || true
  sleep 1
fi

cd backend

if [ ! -d venv ]; then
  echo ">> creating virtualenv"
  python3 -m venv venv
fi

if [ ! -f venv/.deps-installed ] || [ requirements.txt -nt venv/.deps-installed ]; then
  echo ">> installing dependencies (first run takes a few minutes)"
  venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt
  if venv/bin/pip show ultralytics >/dev/null 2>&1; then
    venv/bin/pip install -q "opencv-python>=4.9,<5"
  fi
  venv/bin/pip install -q --force-reinstall "opencv-contrib-python>=4.9,<5"
  touch venv/.deps-installed
fi

echo ">> BarberStudio running at http://localhost:$PORT"
exec venv/bin/uvicorn app.main:app --reload --port "$PORT"
