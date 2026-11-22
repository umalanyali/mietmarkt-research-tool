# Mietmarkt Research

Privates Portfolio-Tool für Neubau-Mietmarktanalysen.

## Stack
- Backend: FastAPI, Python 3.13. Fachlogik ausschließlich in `backend/mietmarkt/`, API nur als dünne Schicht in `backend/api/`.
- Frontend: React 18 + TypeScript + Vite, Karten mit MapLibre + OpenFreeMap.
- Datenbank: SQLite (`daten/`, nicht im Repo).
- KI: LangGraph-Agenten mit langchain-anthropic (Claude). Fake-Modell nur in Tests.
- Sprache: Oberfläche, Kommentare und Antworten auf Deutsch.

## Harte Regeln
1. **Zahlen rechnet nur Python.** Das Modell rechnet nie, es ruft Werkzeuge auf. Jede angezeigte Zahl hat eine
   Herkunft (`import | manuell | ki | abgelesen | berechnet`) und einen Verweis auf Quelle oder Rechenweg.
2. **Kein automatisches Abrufen** aus RIWIS, VALUE, ImmoScout24 oder anderen Portalen. Marktdaten kommen nur aus
   Dateien, die der Nutzer selbst importiert, oder aus dem synthetischen Demo-Datensatz.
3. **Kein Arbeitgeberbezug:** keine Namen, Logos, kein Corporate Design, keine firmeninterne Pricing-Logik, keine echten
   Projektdaten. Demo-Daten sind synthetisch (fiktive „Musterstadt“).
4. **API-Keys nur in `.env`:** nie im Code, nie in Logs, nie im Frontend. `.env` bleibt in `.gitignore`.
5. **Design:** warme Neutraltöne (Sand, Stein, Terrakotta, Oliv). Kein Blau, Lila, Türkis oder Mint, auch nicht in
   Diagrammen oder Karten.
6. **Externe Dienste nur gedrosselt und gecacht** (siehe Adresssuche). Jede Anfrage mit eigenem User-Agent
   `MietmarktResearch/0.x (privates Projekt)`.
7. **Tests zuerst** (Skill `tdd`). Vor „fertig“ laufen pytest, ruff, vitest und tsc grün (Skill `verify`).
8. **Kein `git commit`, `git push` oder PR.** Das macht der Nutzer selbst.
9. **Verständlich kommentieren:** Jede Datei beginnt mit 1–2 Sätzen, wofür sie da ist. Jede Funktion bekommt einen deutschen Docstring (was, Eingabe, Ausgabe). Nicht offensichtliche Schritte bekommen einen Kommentar zum Warum, vor allem bei LangGraph-Knoten, Zuständen und Werkzeugen. Der Leser kennt Python, aber nicht LangGraph.
10. **Knapp bleiben:** die kürzeste klare Lösung, keine Abstraktion auf Vorrat, keine ungenutzten Optionen.

## Befehle
- Start: `./start.sh` (macOS) bzw. `start.bat` (Windows), oder Doppelklick auf `Mietmarkt Research.command`
- Backend-Tests: `cd backend && .venv/bin/pytest -q && .venv/bin/ruff check .`
- Frontend-Tests: `cd frontend && npm test && npx tsc --noEmit`
- Demo-Daten laden: `cd backend && .venv/bin/python -m mietmarkt.demo seed`
- Screenshots: `cd frontend && node skripte/aufnahme.mjs <ordner> name=/pfad` (App muss laufen)
