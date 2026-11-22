# Mietmarkt Research

Recherche-Tool für Neubau-Mietmarktanalysen: Adresse eingeben → Soziodemografie, Angebotsmieten,
Vergleichsangebote auf der Karte und Marktdaten an einem Ort → Merkliste → PowerPoint-Export.

> **Stand: Meilenstein 4 (Adresssuche und Standort).** Jede Adresse in Deutschland ist suchbar; Lage und Umfeld kommen live
> aus OpenStreetMap. Marktdaten gibt es nur, wo importierte oder Demo-Daten im Umkreis liegen; alle Zahlen rechnet das
> Python-Fachpaket.
> Agentenleiste, Freigabe, Mietansatz-Karte und Merkliste sind noch Platzhalter (M3/M6).

> **Kartenlage ist nur Kulisse.** Die Musterstadt-Koordinaten liegen in einer realen Stadt, damit die Karte Straßen
> und Bebauung zeigt. Alle Adressen, Anbieter und Zahlen sind erfunden und haben mit den Gebäuden dort nichts zu tun.

## Installation und Start

Voraussetzungen: Node.js 20+, Python 3.12/3.13 oder [uv](https://docs.astral.sh/uv/) (installiert Python 3.13 selbst).

```bash
./start.sh        # macOS / Linux
start.bat         # Windows
```

**macOS mit einem Klick:** im Finder `Mietmarkt Research.command` doppelklicken. Es öffnet sich ein Terminalfenster,
die App startet und der Browser geht auf. Läuft die App schon, öffnet sich nur der Browser. Beenden: Terminalfenster schließen.
Tipp: Die Datei in den rechten Bereich des Docks (neben den Papierkorb) ziehen, dann reicht ein Klick im Dock.

Beim ersten Start werden die Python-Umgebung (`backend/.venv`) und die Frontend-Pakete eingerichtet und der
Demo-Datensatz geladen. Neu laden (ersetzt den Bestand): `cd backend && .venv/bin/python -m mietmarkt.demo seed`.
Danach öffnet sich http://localhost:5173. Die API-Dokumentation liegt unter http://localhost:8000/docs.

Optional: `.env.example` nach `.env` kopieren und `ANTHROPIC_API_KEY` eintragen (erst ab Meilenstein 5 nötig).

## Bedienung (Prototyp)

- **Startseite:** Adresse tippen (z. B. „Linden“), mit Pfeiltasten wählen, Enter. Filter als Pills.
- **Dashboard:** Stern = auf die Merkliste. Merkliste per Maus oder Tastatur (Griff fokussieren, Leertaste, Pfeile) sortieren.
  Kartenebenen über die Pills auf der Karte; Klick auf eine Tabellenzeile hebt den Comp auf der Karte hervor.
- **Zustände:** `/zustaende` zeigt Laden, Leer, Fehler und Teildaten.

## API

| Endpunkt | Liefert |
|---|---|
| `GET /api/adressen/vorschlaege?q=…` | Adressvorschläge (Photon), ab 3 Zeichen, mit Attribution |
| `POST /api/projekte` | Projekt aus einem gewählten Vorschlag anlegen (Adresse über Nominatim) |
| `GET /api/projekte/{id}/umfeld` | ÖPNV, Supermärkte, Schulen, Kitas, Ärzte im Umkreis 1 km mit Wegezeiten |
| `GET /api/projekte` | alle Projekte, zuletzt analysierte zuerst |
| `GET /api/projekte/{id}` | ein Projekt mit Datenstand je Quelle |
| `GET /api/projekte/{id}/comps` | Comps mit €/m², Tagen online, Anfragen je Monat, Luftlinie – je als Wert mit Rechenweg |
| `GET /api/projekte/{id}/kennzahlen` | Marktkennzahlen mit Herkunft, Comps-Zusammenfassung, Preisklassen-Auswertung |
| `POST /api/projekte/{id}/laeufe` | Agenten-Lauf anlegen → `{lauf_id}`; 503 „KI nicht konfiguriert“ ohne Schlüssel |
| `GET /api/laeufe/{lauf_id}/ereignisse` | Lauf ausführen bzw. fortsetzen, Ereignisse als Server-Sent Events (siehe unten) |
| `GET /api/gesundheit` | Lebenszeichen; `ki: true/false`, ob ein Anthropic-Schlüssel eingetragen ist |

Jede Zahl kommt als `{wert, einheit, herkunft, quelle_id, rechenweg_text}`; `herkunft` ist `import | manuell | ki | abgelesen | berechnet`.

## KI-Agenten (LangGraph)

Ein Lauf ist ein LangGraph-Graph in `backend/mietmarkt/agenten/`:
`supervisor → Agent ⇄ Werkzeuge → validierung → supervisor → … → Ende`.

| Agent | Modell (`.env`) | Werkzeuge |
|---|---|---|
| Supervisor | `MODELL_STARK` (Standard `claude-sonnet-5-5`) | keine; entscheidet per strukturierter Ausgabe, wer als Nächstes dran ist |
| Standort | `MODELL_SCHNELL` (Standard `claude-haiku-5-5`) | `lage` (Adresse und Koordinaten aus der Datenbank, kein Geokodieren), `umfeld` |
| Marktdaten | `MODELL_SCHNELL` | `kennzahlen`, `comps_filtern` |
| Mietansatz | `MODELL_STARK` | `kennzahlen`, `mietansatz_herleiten` (rechnet; Basis `regel_eg` oder `dg`; Zu-/Abschläge des Modells tragen Herkunft `ki`) |

- **Zahlen:** Werkzeuge rufen nur Fachfunktionen auf. Der Knoten `validierung` markiert jede Zahl einer Agenten-Antwort,
  die in keinem Werkzeugergebnis und nicht in den Projektdaten steht (Herkunft `ki`, Warnhinweis); ebenso Begründung,
  Auftrag und Rückfrage des Supervisors.
- **Fachregeln Mietansatz:** Der Haupt-Mietansatz geht immer von Regelgeschoss/EG aus. DG ist eine getrennte
  Herleitung mit DG-Basis, nie ein Zuschlag (im Code geprüft). Jeder Zu-/Abschlag nennt einen belegten Unterschied
  zwischen Projekt und Comps; ohne belegten Unterschied kein Merkmal (Prompt-Regel, nicht maschinell prüfbar).
- **Leitplanken im Code:** „fertig“ vor allen drei Agenten nur mit Rückfrage an den Nutzer, Mietansatz erst nach den
  Marktdaten, Zu-/Abschläge höchstens ±10 €/m², höchstens 6 Supervisor-Runden (die siebte wird nicht mehr bezahlt).
- **Kosten:** Token je Aufruf aus `usage_metadata` × Preistabelle (`agenten/kosten.py`) × `KI_EUR_JE_USD`. Erreicht ein
  Lauf `KI_BUDGET_EUR_PRO_LAUF` (Standard 0,50 €), startet kein weiterer Modellaufruf; der letzte Aufruf kann das
  Budget also noch etwas überschreiten. Modelle ohne Eintrag in der Preistabelle werden vor jedem Aufruf abgelehnt.
  Ein Gesamtlimit über alle Läufe setzt man am einfachsten als Ausgabelimit in der Anthropic Console.
- **Wiederaufnahme:** Nach jedem Schritt sichert der Checkpointer den Zustand in `daten/checkpoints.db`
  (thread_id = Lauf-ID). Ruft man die Ereignisse eines unterbrochenen Laufs erneut ab, geht er dort weiter. Ein
  zweiter Abruf, während der Lauf noch läuft, bekommt 409. Ist ein Lauf beendet, steht sein Endstand in der Tabelle
  `lauf`, der Checkpoint wird gelöscht; der Endstand lässt sich auch ohne Schlüssel abrufen.
- **Ereignisse (SSE):** `agent_gestartet`, `werkzeugaufruf`, `werkzeugergebnis`, `text`, `agent_fertig`, `kosten`,
  `rueckfrage`, `abbruch`, `fehler`, zum Schluss `fertig` mit Ergebnissen, Markierungen und Gesamtkosten.

## Tests

```bash
cd backend && .venv/bin/pytest -q && .venv/bin/ruff check .
cd backend && .venv/bin/pytest -m live -s   # echter kurzer Lauf mit Claude (kostet Geld, braucht ANTHROPIC_API_KEY)
cd frontend && npm test && npx tsc --noEmit
cd frontend && node skripte/aufnahme.mjs <ordner> name=/pfad   # Screenshots (App muss laufen)
```

## Wo ändere ich was

| Was | Wo |
|---|---|
| Farben, Schriften, Abstände, Layout | `frontend/src/stil/app.css` (Tokens ganz oben) |
| Startseite / Analyse / Zustände | `frontend/src/seiten/` |
| Bausteine (Tabellen, Freigabe, Herleitung, Kopf, Agentenleiste) | `frontend/src/komponenten/` |
| Karte (Stil, Ringe, Marker) | `frontend/src/komponenten/kartenstil.ts`, `Karte.tsx` |
| Diagramme | `frontend/src/komponenten/Diagramme.tsx` |
| Beispieldaten des Prototyps | `frontend/src/daten/beispiel.ts` |
| Datenmodell (Projekt, Quelle, Comp, Marktkennzahl, Wert mit Herkunft) | `backend/mietmarkt/modelle.py` |
| Kennzahlen (€/m², Median, Quartile, Ø flächengewichtet, Anfragen je Monat) | `backend/mietmarkt/kennzahlen.py` |
| Entfernung, Comp-Filter, Mietansatz-Kette | `backend/mietmarkt/geo/distanz.py`, `comps.py`, `mietansatz.py` |
| CSV/XLSX-Import von Comps | `backend/mietmarkt/importe.py` |
| Demo-Datensatz | `backend/mietmarkt/demo/musterstadt.yaml` |
| API-Endpunkte | `backend/api/main.py` |
| Externe Geodienste (URLs, Drossel, Cache), Umfeld-Auswertung | `backend/mietmarkt/geo/` |
| Agenten: Prompts, Graph, Leitplanken | `backend/mietmarkt/agenten/graph.py` |
| Agenten-Werkzeuge / Modellpreise / Zahlenprüfung | `backend/mietmarkt/agenten/werkzeuge.py`, `kosten.py`, `pruefung.py` |
| Modelle, Budget, Schlüssel | `.env` (Vorlage `.env.example`), gelesen in `backend/mietmarkt/konfig.py` |
| Platzhalter bis M3–M6 (Merkliste, Bauprojekte, Agentenlauf) | `frontend/src/daten/` |

## Externe Dienste

Alle Anfragen laufen über das Backend (nicht direkt aus dem Browser), mit dem User-Agent
`MietmarktResearch/0.1 (privates Projekt)` und `Accept-Language: de`. Antworten werden 30 Tage in der Tabelle `geocache`
(`daten/mietmarkt.db`) zwischengespeichert; dieselbe Anfrage geht also nur einmal hinaus, auch wenn sie zweimal
gleichzeitig gestellt wird. Ältere Einträge werden gelöscht, fehlerhafte Antworten nie gespeichert.

| Dienst | Wofür | Was gesendet wird | Grenzen |
|---|---|---|---|
| Photon (`photon.komoot.io`) | Adressvorschläge beim Tippen | der getippte Suchtext (ab 3 Zeichen, 300 ms nach dem letzten Tastendruck) | nur Deutschland (bbox), max. 5 Treffer, gedrosselt (2 Anfragen/s) |
| Nominatim (`nominatim.openstreetmap.org`) | endgültige Adresse beim Anlegen eines Projekts, Rückwärtssuche | gewählte Adresse bzw. deren Koordinaten | höchstens 1 Anfrage pro Sekunde, nie für die Autovervollständigung (Nutzungsrichtlinie) |
| Overpass (`overpass-api.de`) | Umfeld: ÖPNV, Supermärkte, Schulen, Kitas, Ärzte | Koordinaten des Standorts, Radius 1.000 m | gedrosselt (1 Anfrage/s), Rechenzeit 25 s, bewusst ohne Rückfall-Server |
| OSRM (`routing.openstreetmap.de`, FOSSGIS) | Wegezeiten zu Fuß und mit dem Rad | Koordinaten von Standort und bis zu 3 Zielen je Kategorie | gedrosselt; fällt der Dienst aus oder ist ein Ziel nicht routbar, gilt die Luftlinie (Kennzeichnung „Luftlinie“); der Rechenweg nennt das Abrufdatum |
| OpenFreeMap (`tiles.openfreemap.org`) | Kartenkacheln und Schriften der Karte | Kachelkoordinaten des sichtbaren Ausschnitts (direkt aus dem Browser) | – |

Warum nicht `router.project-osrm.org`: Der OSRM-Demo-Server rechnet nur mit dem Autoprofil und liefert für „foot“ die
Autozeit. Die FOSSGIS-Server sprechen dieselbe OSRM-API mit echten Fuß- und Radprofilen (`backend/mietmarkt/geo/dienste.py`).

Warum kein Overpass-Rückfall: Die erreichbaren Ausweich-Server liegen außerhalb der EU; echte Projektkoordinaten
sollen dort nicht landen. Bei Überlast zeigt die App lieber „Dienst nicht erreichbar“.

Der Browser darf nur Adressen in Deutschland übergeben (Koordinaten-, Längen- und NaN-Prüfung, sonst 422).
Fällt ein Dienst aus, antwortet die API mit 503; die Oberfläche zeigt „Dienst nicht erreichbar“, der Rest bleibt nutzbar.
Marktdaten (Comps, RIWIS, VALUE) gehen an keinen dieser Dienste. Demo-Daten erscheinen nur bei Demo-Projekten, nie bei
echten Adressen.

## Datenschutz

- Uploads, Datenbank und Cache liegen lokal in `daten/` (nicht im Repository).
- An die Geodienste gehen nur Adressen und Koordinaten (Tabelle oben), keine Marktdaten.
- An die Anthropic-API gehen bei einem Agenten-Lauf: Projektdaten (Name, Adresse, PLZ, Ort, Ortsteil, Segment,
  Umkreis, Stichtag), die Werkzeugergebnisse und die Antworten der Agenten. Ohne Lauf geht nichts an Anthropic.
  Der Schlüssel steht nur in `.env`.
- **Importierte Portal-Daten gehen standardmäßig nicht an Anthropic.** Comps und Marktkennzahlen mit Herkunft
  `import` (RIWIS, VALUE, Portal-Exporte) dürfen nach ihrer Lizenz oft nicht an Dritte weitergegeben werden. Ohne
  Freigabe sehen die Agenten deshalb nur Demo-Daten, selbst erfasste Werte (Herkunft `manuell`) und das Umfeld aus
  OpenStreetMap – auch Kennzahlen und Mietansatz werden dann nur daraus berechnet, und das Werkzeug meldet dem
  Agenten, wie viele Einträge zurückgehalten wurden. Freigabe auf eigene Verantwortung: `KI_PORTALDATEN_SENDEN=true`.
- Ab M5 kommen Screenshot-Bilder zur Auslese und Exposé-Text hinzu, wenn der Parser Felder leer lässt.

Kartendaten und Umfeld © OpenStreetMap-Mitwirkende (ODbL), Kacheln OpenFreeMap / OpenMapTiles, Routing FOSSGIS.
Schrift: Hanken Grotesk (SIL Open Font License).
