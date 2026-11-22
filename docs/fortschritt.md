# Fortschritt

## M0 – Gerüst (21.11.2026)
- Repository, `.gitignore` (.env, daten/, docs/mockups/), Startskripte (`start.sh`, `start.bat`, `Mietmarkt Research.command`).
- Backend FastAPI + pytest/ruff (Python 3.13 über uv), Frontend React 18 + TypeScript + Vite + vitest.
- Projekt-Skills `tdd`, `verify`, `checkpoint`; Agenten `python-reviewer`, `security-reviewer`.

## M1 / R – Design (21.–22.11.2026, abgeschlossen)
- Drei Design-Richtungen A–C erprobt und verworfen; gewählt: Gestaltung nach Mockup (vormals „Richtung D“),
  Akzent Oliv, warme Neutraltöne, Hanken Grotesk, eigener MapLibre-Stil auf OpenFreeMap.
- Aufgeräumt: Entwürfe A–C und M1-Prototyp entfernt (−4.700 Zeilen), Kommentare nach Regel 9.
- Screenshots der gewählten Gestaltung: `docs/design/richtung-d/`.

## M2 – Fachkern und API (22.11.2026)
- Routen: `/` Startseite, `/analyse/:id` Dashboard, `/zustaende` Zustandsübersicht (vorher `/entwurf/d/…`).
- Datenmodell (SQLModel, `daten/mietmarkt.db`): Projekt, Quelle, Comp, Marktkennzahl; `Wert` mit Herkunft und Rechenweg.
- Fachfunktionen in `backend/mietmarkt/` (reines Python, jede mit Rechenweg): Entfernung (Haversine), Comp-Filter
  (Radius, Baujahr, Typ), Kennzahlen (Anzahl, Median, Quartile inklusiv, Ø flächengewichtet, Anfragen je Monat ab 7 Tagen,
  Zusammenfassung Regelgeschoss/EG vs. DG, Preisklassen), Mietansatz-Kette (Basis, begründete Zu-/Abschläge, Ergebnis).
- Import von Comps aus CSV/XLSX: Spaltenzuordnung, pydantic-Prüfung, deutsche Zahlen, Windows-1252, zeilengenaue Fehler.
- Demo-Datensatz `backend/mietmarkt/demo/musterstadt.yaml`, Befehl `python -m mietmarkt.demo seed`; Startskripte laden ihn beim
  ersten Start. Kartenlage ist nur Kulisse (README).
- API: `GET /api/projekte`, `/api/projekte/{id}`, `/comps`, `/kennzahlen`. Frontend liest ab jetzt von der API;
  `frontend/src/daten/beispiel.ts` entfernt.
- Noch Platzhalter: Adressvorschläge und Kartenpunkte (M4), Merkliste (M3), Agentenlauf, Freigabe und Mietansatz-Karte (M6).
  Ohne Comps blendet das Dashboard diese Platzhalter aus.
- Tests: Backend 47, Frontend 6. Review durch `python-reviewer`: 7 Befunde (Import, Tage online, Preisklassen), alle behoben und mit Tests abgesichert.

## Offen / nächste Schritte
- Entfernungen sind Luftlinie; Wegezeiten (OSM-Routing) mit M4.
- Import-Endpunkt (Upload) und Prüftabelle in der Oberfläche fehlen noch; der Import ist bisher nur als Fachfunktion da.

## M4 – Adresssuche und Standort (22.11.2026, weitgehend fertig)
- Paket `backend/mietmarkt/geo/`: Photon (Vorschläge, 2/s), Nominatim (Geokodieren/Rückwärtssuche, 1 Anfrage/s), Overpass (Umfeld 1 km,
  ohne Rückfall-Server), OSRM über routing.openstreetmap.de (Fuß/Rad; der Demo-Server kennt nur Auto), Cache-Tabelle `geocache` 30 Tage.
- Endpunkte `GET /api/adressen/vorschlaege`, `POST /api/projekte`, `GET /api/projekte/{id}/umfeld`; Comps kommen aus dem Umkreis.
- Frontend: Combobox mit Debounce/Abbruch, Projektanlage per Auswahl, Umfeld-Karte, ehrlicher Leerzustand ohne Marktdaten.
- Demo-Comps nur bei Demo-Projekten; echte Adressen starten mit eingeschalteten Ebenen ÖPNV und Nahversorgung.
- python-reviewer und security-reviewer: alle Befunde behoben (u. a. Vite 5.4.21 ohne CORS, OSRM-null → Luftlinie,
  gleichzeitige Anfragen nur einmal, Overpass-Abbruch nicht gecacht, Eingabegrenzen, Drossel threadsicher).
- Tests: Backend 83, Frontend 11 (externe Dienste nur gemockt, Testadressen fiktiv). README-Abschnitt „Externe Dienste“.
