#!/usr/bin/env bash
# Startet Backend (FastAPI, Port 8000) und Frontend (Vite, Port 5173) mit einem Befehl.
set -euo pipefail
cd "$(dirname "$0")"

# Backend-Umgebung (Python 3.12/3.13) bei Bedarf anlegen
if [ ! -x backend/.venv/bin/python ]; then
  echo "Richte Python-Umgebung ein …"
  if command -v uv >/dev/null 2>&1; then
    uv venv --python 3.13 backend/.venv
    uv pip install --python backend/.venv -e 'backend[dev]'
  else
    PY=$(command -v python3.13 || command -v python3.12 || true)
    if [ -z "$PY" ]; then echo "Python 3.12 oder 3.13 fehlt (oder uv installieren)."; exit 1; fi
    "$PY" -m venv backend/.venv
    backend/.venv/bin/pip install -e 'backend[dev]'
  fi
fi

# Frontend-Abhängigkeiten bei Bedarf installieren
if [ ! -d frontend/node_modules ]; then
  echo "Installiere Frontend-Abhängigkeiten …"
  (cd frontend && npm install)
fi

mkdir -p daten

(cd backend && .venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000) &
BACKEND=$!
trap 'kill $BACKEND 2>/dev/null' EXIT INT TERM HUP

echo "Mietmarkt Research läuft auf http://localhost:5173 (Beenden mit Strg+C)"
(cd frontend && npx vite --port 5173 --open /entwurf/d)
