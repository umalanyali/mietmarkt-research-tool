# Mietmarkt Research

Recherche-Tool für Neubau-Mietmarktanalysen: Adresse eingeben → Soziodemografie, Angebotsmieten,
Vergleichsangebote auf der Karte und Marktdaten an einem Ort → Merkliste → PowerPoint-Export.

> **Stand: Meilenstein 1 (Design-Prototyp).** Startseite und Dashboard zeigen synthetische Beispieldaten
> der fiktiven „Musterstadt“. Importe, Berechnungen und Export folgen ab Meilenstein 2.

## Installation und Start

Voraussetzungen: Node.js 20+, Python 3.12/3.13 oder [uv](https://docs.astral.sh/uv/) (installiert Python 3.13 selbst).

```bash
./start.sh        # macOS / Linux
start.bat         # Windows
```

**macOS mit einem Klick:** im Finder `Mietmarkt Research.command` doppelklicken. Es öffnet sich ein Terminalfenster,
die App startet und der Browser geht auf. Läuft die App schon, öffnet sich nur der Browser. Beenden: Terminalfenster schließen.
Tipp: Die Datei in den rechten Bereich des Docks (neben den Papierkorb) ziehen, dann reicht ein Klick im Dock.

Beim ersten Start werden die Python-Umgebung (`backend/.venv`) und die Frontend-Pakete eingerichtet.
Danach öffnet sich http://localhost:5173/entwurf/d. Die API-Dokumentation liegt unter http://localhost:8000/docs.

Optional: `.env.example` nach `.env` kopieren und `ANTHROPIC_API_KEY` eintragen (erst ab Meilenstein 5 nötig).

## Bedienung (Prototyp)

- **Startseite:** Adresse tippen (z. B. „Linden“), mit Pfeiltasten wählen, Enter. Filter als Pills.
- **Dashboard:** Stern = auf die Merkliste. Merkliste per Maus oder Tastatur (Griff fokussieren, Leertaste, Pfeile) sortieren.
  Kartenebenen über die Pills auf der Karte; Klick auf eine Tabellenzeile hebt den Comp auf der Karte hervor.
- **Zustände:** `/entwurf/d/zustaende` zeigt Laden, Leer, Fehler und Teildaten.

## Tests

```bash
cd backend && .venv/bin/pytest -q && .venv/bin/ruff check .
cd frontend && npm test && npx tsc --noEmit
cd frontend && node skripte/aufnahme.mjs <ordner> name=/pfad   # Screenshots (App muss laufen)
```

## Wo ändere ich was

| Was | Wo |
|---|---|
| Farben, Schriften, Abstände, Layout | `frontend/src/entwuerfe/d/d.css` (Tokens ganz oben) |
| Startseite / Dashboard / Zustände | `frontend/src/entwuerfe/d/RichtungD.tsx` |
| Gemeinsame Bausteine (Tabellen, Freigabe, Herleitung) | `frontend/src/entwuerfe/gemeinsam/Bausteine.tsx` |
| Karte (Stil, Ringe, Marker) | `frontend/src/entwuerfe/gemeinsam/kartenstil.ts`, `EntwurfKarte.tsx` |
| Diagramme | `frontend/src/komponenten/Diagramme.tsx` |
| Beispieldaten des Prototyps | `frontend/src/daten/beispiel.ts` |
| Fachlogik (ab M2) | `backend/mietmarkt/` |
| API | `backend/api/` |

## Datenschutz

- Uploads, Datenbank und Cache liegen lokal in `daten/` (nicht im Repository).
- Externe Dienste: Kartenkacheln von OpenFreeMap; ab M4 Photon/Nominatim (Adresssuche) und OSRM (Routen), gedrosselt und gecacht.
- An die Anthropic-API gehen ab M5 nur: Screenshot-Bilder zur Auslese, Exposé-Text, wenn der Parser Felder leer lässt,
  und Chatfragen samt Werkzeugergebnissen. Der Schlüssel steht nur in `.env`.

Kartendaten © OpenStreetMap-Mitwirkende, Kacheln OpenFreeMap / OpenMapTiles. Schrift: Hanken Grotesk (SIL Open Font License).
