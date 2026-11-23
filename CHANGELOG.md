# Changelog

Alle nennenswerten Änderungen, zusammengefasst aus [`docs/fortschritt.md`](docs/fortschritt.md) (dort mit allen Details
und Review-Befunden). Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [0.1.0] – 23.11.2026

### Veröffentlichung
- README mit Schnellstart, Architekturdiagramm, gemessenen Kosten (0,18 € je Lauf), Datenschutz und Grenzen; MIT-Lizenz.
- Knopf „Demo-Standort öffnen“ und `POST /api/demo`: lädt Musterstadt, ohne eigene Projekte anzufassen.
- Neutrale Bezeichnungen statt Produktnamen fremder Datenanbieter; neue Screenshots und Lauf-GIF.
- Sicherheit: Upload-Größe vor dem Lesen geprüft, PDF-Parsen außerhalb der Event-Loop, kein Hängenbleiben auf 409.
- Behoben: Lauf brach ab, wenn der Mietansatz-Agent wegen fehlender DG-Herleitung zurückgeschickt wurde.

### M7 – Agenten in der Oberfläche
- Zeitleiste aus dem SSE-Strom (Status, Werkzeuge, Dauer, Token, Kosten), Freigabe-Karte (annehmen, ändern,
  ablehnen), Rückfragen mit Antwortfeld, Herkunfts-Kennzeichen mit Quelle und Rechenweg, Laufliste mit Fortsetzen.
- Upload eigener Unterlagen mit Häkchen „KI darf lesen“ (Standard aus).
- Sicherheit: Unterlagen nur mit eigener Freigabe an die KI; CSRF-Schutz für schreibende Anfragen.

### Umfeld-Cache und Overpass
- Overpass-Serverliste (`OVERPASS_URLS`), Umfeld je Projekt 30 Tage gespeichert, Jahreszahlen ohne Tausenderpunkt.

### M6 – Eigene Unterlagen
- Upload von PDF, Bild und Text mit Typprüfung am Inhalt; Volltextsuche (SQLite FTS5) als Werkzeug `dokumente_suchen`.
- Exposé-Agent (Parser zuerst, Modell nur für leere Felder, Zitat geprüft) und Vision-Agent (Herkunft `abgelesen`).

### M5 – KI-Agenten mit LangGraph
- Supervisor mit Standort-, Marktdaten- und Mietansatz-Agent; Werkzeuge rufen nur Fachfunktionen auf; Zahlenprüfung
  markiert freie Zahlen; Kosten je Aufruf mit Budgetabbruch; Checkpoints in SQLite, Läufe überleben Neustarts.
- Human-in-the-Loop-Freigabe des Mietansatzes, Prüf-Agent (Mindestzahl, Alter, IQR, ± 15 %), Bericht mit
  Platzhaltern und Fußnoten, Export als Markdown und PowerPoint.
- Mietansatz: Basis Regelgeschoss/EG, DG getrennt hergeleitet; Fortschreibung bis zum Vermarktungsstart.
- Dienstausfälle als Befund; importierte Portal-Daten gehen nur mit Freigabe an Anthropic.

### M4 – Adresssuche und Standort
- Photon, Nominatim, Overpass und OSRM (Fuß/Rad) über das Backend, gedrosselt und 30 Tage gecacht; Umfeld-Karte.

### M2 – Fachkern und API
- Datenmodell mit `Wert` (Herkunft, Rechenweg), Kennzahlen, Comp-Filter, Mietansatz-Kette, CSV/XLSX-Import,
  synthetischer Demo-Datensatz Musterstadt, Lese-API.

### M0/M1 – Gerüst und Gestaltung
- FastAPI + React/Vite, Startskripte; Gestaltung in warmen Neutraltönen mit eigenem MapLibre-Kartenstil.
