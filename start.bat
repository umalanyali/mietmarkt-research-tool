@echo off
rem Startet Backend (FastAPI, Port 8000) und Frontend (Vite, Port 5173) unter Windows.
cd /d "%~dp0"

if not exist backend\.venv\Scripts\python.exe (
  echo Richte Python-Umgebung ein ...
  where uv >nul 2>nul
  if %errorlevel%==0 (
    uv venv --python 3.13 backend\.venv
    uv pip install --python backend\.venv -e "backend[dev]"
  ) else (
    py -3.13 -m venv backend\.venv || py -3.12 -m venv backend\.venv
    backend\.venv\Scripts\pip install -e "backend[dev]"
  )
)

if not exist frontend\node_modules (
  echo Installiere Frontend-Abhaengigkeiten ...
  pushd frontend & call npm install & popd
)

if not exist daten mkdir daten
if not exist daten\mietmarkt.db backend\.venv\Scripts\python -m mietmarkt.demo seed

start "Mietmarkt Backend" /D backend .venv\Scripts\uvicorn api.main:app --host 127.0.0.1 --port 8000
echo Mietmarkt Research laeuft auf http://localhost:5173
pushd frontend & call npx vite --port 5173 --open & popd
