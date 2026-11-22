# Fortschritt

## M0 – Gerüst (21.11.2026)
- Repository, Ordnerstruktur, `.gitignore` (.env, daten/, docs/mockups/), `start.sh` / `start.bat`.
- Backend: FastAPI mit `/api/gesundheit`, Python 3.13 über uv, pytest + ruff.
- Frontend: React 18 + TypeScript + Vite, vitest.
- Projekt-Skills `tdd`, `verify`, `checkpoint`; Agenten `python-reviewer`, `security-reviewer`.

## M1 – Design-Prototyp (21.11.2026, wartet auf Freigabe)
- Startseite und Dashboard mit synthetischen Musterstadt-Daten, MapLibre-Karte (OpenFreeMap), visx-Diagramme.
- Paletten-Umschalter A/B/C in der Kopfleiste. Screenshots unter `docs/screenshots/`.

## R – Redesign, drei Richtungen (21.11.2026, wartet auf Auswahl)
- Ist-Kritik: `docs/design/ist/kritik.md`.
- Entwürfe unter `/entwurf/a|b|c` (Startseite, Dashboard, Zustände), jeweils mit Agenten-Zeitleiste, Freigabe-Karte und Herleitungskette.
- Eigene MapLibre-Stile auf OpenFreeMap-Vektorkacheln (`frontend/src/entwuerfe/gemeinsam/kartenstil.ts`).
- Selbstkritik und Überarbeitung: `docs/design/selbstkritik.md`, erste Fassung in `docs/design/richtung-*/v1/`.
