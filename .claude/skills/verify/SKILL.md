---
name: verify
description: Abnahmeprüfung nach einem Meilenstein von Mietmarkt Research – alle Tests, Typen, Lint, App-Start und Screenshots der Seiten.
---

# Prüfung

1. `cd backend && .venv/bin/pytest -q && .venv/bin/ruff check .`
2. `cd frontend && npm test && npx tsc --noEmit`
3. App starten (Backend `uvicorn api.main:app --port 8000`, Frontend `npx vite --port 5173`) und `curl localhost:8000/api/gesundheit` prüfen.
4. Screenshots: `cd frontend && node skripte/aufnahme.mjs <ordner> startseite=/ analyse=/analyse/1` (Breite per `BREITE=1280`). Bilder ansehen: Überlappungen, Abschneidungen.
5. Suche nach Firmenbezug und Schlüsseln: `git grep -nIiE "sk-ant-|api_key\s*=\s*['\"][^'\"]" -- . ':!*.example'`.
6. Ergebnis ehrlich melden: was grün ist, was rot ist, was nicht geprüft wurde.
