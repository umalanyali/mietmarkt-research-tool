---
name: tdd
description: Testgetriebene Entwicklung für ein Feature in Mietmarkt Research – Test zuerst (rot), minimale Umsetzung (grün), aufräumen. Nutzen für jede neue Fachlogik im Paket backend/mietmarkt und für Frontend-Logik.
---

# TDD-Ablauf

1. **Umfang:** ein Feature pro Durchlauf, damit der Nutzer es als einen Commit übernehmen kann.
2. **Rot:** Tests zuerst unter `backend/tests/` (pytest) bzw. `frontend/src/test/` (vitest).
   - Nur synthetische Daten: Stadt „Musterstadt“, fiktive Anbieter und Adressen.
   - Randfälle: leere Eingaben, `None`, Grenzwerte (z. B. genau 7 Tage online), Rundung.
   - Test ausführen und bestätigen, dass er aus dem richtigen Grund fehlschlägt.
3. **Grün:** minimale Umsetzung im Fachpaket. Kennzahlen nur in Python, nie im Frontend.
4. **Aufräumen:** Namen, Doku-Kommentare auf Deutsch, keine Duplikate; Tests bleiben grün.
5. **Prüfen:** `cd backend && .venv/bin/pytest -q && .venv/bin/ruff check .` sowie `cd frontend && npm test && npx tsc --noEmit`.
6. Bei Python-Änderungen den Agenten `python-reviewer` beauftragen; bei Uploads, Schlüsseln oder externen Diensten `security-reviewer`.
7. Zum Schluss `/code-review` und einen Vorschlag für Commit-Aufteilung und -Text. Committen tut nur der Nutzer (CLAUDE.md Regel 8).
