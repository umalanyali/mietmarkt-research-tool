# Fortschritt

## M0 – Gerüst (21.11.2026)
- Repository, `.gitignore` (.env, daten/, docs/mockups/), Startskripte (`start.sh`, `start.bat`, `Mietmarkt Research.command`).
- Backend FastAPI + pytest/ruff (Python 3.13 über uv), Frontend React 18 + TypeScript + Vite + vitest.
- Projekt-Skills `tdd`, `verify`, `checkpoint`; Agenten `python-reviewer`, `security-reviewer`.

## M1 / R – Design (21.–22.11.2026, abgeschlossen)
- Drei Design-Richtungen A–C erprobt und verworfen; gewählt: Gestaltung nach Mockup (vormals „Richtung D“),
  Akzent Oliv, warme Neutraltöne, Hanken Grotesk, eigener MapLibre-Stil auf OpenFreeMap.
- Aufgeräumt: Entwürfe A–C und M1-Prototyp entfernt (−4.700 Zeilen), Kommentare nach Regel 9.
- Screenshots der Oberfläche: `docs/screenshots/` (seit 23.11.2026; die alten Entwurfsbilder sind entfernt).

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
- Paket `backend/mietmarkt/geo/`: Photon (Vorschläge, 2/s), Nominatim (Geokodieren/Rückwärtssuche, 1 Anfrage/s), Overpass (Umfeld 1 km;
  nachträglich: Server-Liste `OVERPASS_URLS`, Standard nur overpass-api.de, Ersatzserver nur auf Wunsch, Timeout 25 s je
  Server, Umfeld je Projekt 30 Tage in `umfeldcache`), OSRM über routing.openstreetmap.de (Fuß/Rad; der Demo-Server kennt nur Auto), Cache-Tabelle `geocache` 30 Tage.
- Endpunkte `GET /api/adressen/vorschlaege`, `POST /api/projekte`, `GET /api/projekte/{id}/umfeld`; Comps kommen aus dem Umkreis.
- Frontend: Combobox mit Debounce/Abbruch, Projektanlage per Auswahl, Umfeld-Karte, ehrlicher Leerzustand ohne Marktdaten.
- Demo-Comps nur bei Demo-Projekten; echte Adressen starten mit eingeschalteten Ebenen ÖPNV und Nahversorgung.
- python-reviewer und security-reviewer: alle Befunde behoben (u. a. Vite 5.4.21 ohne CORS, OSRM-null → Luftlinie,
  gleichzeitige Anfragen nur einmal, Overpass-Abbruch nicht gecacht, Eingabegrenzen, Drossel threadsicher).
- Tests: Backend 83, Frontend 11 (externe Dienste nur gemockt, Testadressen fiktiv). README-Abschnitt „Externe Dienste“.

## M5a – Agenten-Gerüst mit LangGraph (22.11.2026)
- `backend/mietmarkt/agenten/`: Zustand, Werkzeuge (nur Fachfunktionen, Ergebnisse mit Herkunft), Graph mit Supervisor
  (strukturierte Ausgabe, Leitplanken im Code), Standort-, Marktdaten- und Mietansatz-Agent, Zahlenprüfung,
  Kosten je Aufruf mit Budgetabbruch, Checkpointer `daten/checkpoints.db`.
- Konfiguration über `.env` (pydantic-settings); ohne Schlüssel „KI nicht konfiguriert“ statt Absturz.
- API: `POST /api/projekte/{id}/laeufe`, `GET /api/laeufe/{lauf_id}/ereignisse` (SSE); Tabelle `lauf`.
- Fachlogik aus der API ins Paket verschoben: `comps.im_umkreis`, `kennzahlen.comps_kennzahlen`.
- Tests: Backend 101 (+1 Live-Test, nur mit `-m live`), Frontend 11.
- Standort-Agent nutzt Projektkoordinaten aus der DB (Werkzeug `lage`), geokodiert nicht mehr.
- Reviews behoben: Modell ohne Preis vorab abgelehnt; 409 bei doppeltem Abruf; „fertig“ nur mit Rückfrage;
  Zahlenprüfung (Koordinaten/Nummern kein Beleg, kaufmännisch gerundet, Vorzeichen, Fehlerantworten kein Beleg,
  Zwischentexte geprüft); TrustedHost; Zu-/Abschläge ±10 €/m²; Endstand in Tabelle `lauf`, Checkpoint gelöscht;
  feste Fehlermeldung; Portal-Daten nur mit `KI_PORTALDATEN_SENDEN=true` an Anthropic.
- Zahlenprüfung auch für Begründung, Auftrag und Rückfrage des Supervisors; Zu-/Abschläge von 0,00 €/m² abgelehnt.
- Mietansatz: Basis nur noch `regel_eg` (Haupt-Mietansatz) oder `dg` (getrennte Herleitung); DG als Zuschlag wird
  abgelehnt; Prompt verlangt belegte Unterschiede Projekt ↔ Comps.
- Tests: Backend 129 (+1 Live-Test).
- Offen: Zeitleiste im Frontend (SSE anzeigen). **Hinweis dafür (security-review):** Agenten antworten in Markdown
  (Tabellen, Fettschrift). Texte nur als reinen Text oder mit einem Markdown-Renderer ohne HTML und ohne automatisch
  ladende Bilder/Links anzeigen – nie `dangerouslySetInnerHTML`. Sonst bekäme eine Prompt-Injection (z. B. über
  OSM-Namen oder Importtexte) einen Kanal nach außen (Bild-URL mit Daten als Parameter). Markierte Zahlen
  (`markierungen`, Herkunft ki) sichtbar kennzeichnen, auch in Supervisor-Begründungen.

## M5b – Freigabe, Prüfung und Bericht (22.11.2026)
- Human-in-the-Loop: Knoten `freigabe` mit `interrupt(…, response_schema=Freigabe)`; `POST /api/laeufe/{id}/freigabe`
  setzt mit `Command(resume=…)` fort (annehmen, aendern → Herkunft manuell, ablehnen mit Kommentar → Supervisor).
- Prüf-Agent: Regeln in `mietmarkt/plausibilitaet.py` (unter 5 Comps, älter als 12 Monate, IQR-Ausreißer, Ansatz
  > 15 % von Kennzahl); der Code ruft die Prüfwerkzeuge immer auf, das Modell vergibt Schweregrade. Kritisch →
  zurück zum Supervisor, höchstens 2 Prüfrunden.
- Bericht-Agent mit Platzhaltern `{{wert:ID}}`; Python füllt Werte mit Fußnote zur Herkunft und entfernt freie
  Zahlen. Export Markdown und PowerPoint (python-pptx) unter `GET /api/laeufe/{id}/bericht.md|.pptx`.
- Neue Ereignisse `wartet_auf_freigabe`, `freigabe`, `pruefung`, `bericht`; Status `rueckfrage` im Endstand.
- Tests: Backend 152 (+1 Live-Test, angepasst, noch nicht echt gelaufen).
- Rückfrage des Supervisors hält den Lauf an (`interrupt`), `POST /api/laeufe/{id}/antwort` setzt fort.
- Bericht: eine Korrekturrunde bei freien Zahlen, erst danach `[?]`.
- Tests: Backend 154 (+1 Live-Test).
- Bericht nach dem Live-Lauf überarbeitet: Entfernungen „rd. 230 m“, Sätze mit Belegen (unbelegte gestrichen),
  Zahlwörter wie Ziffern, gleiche Fußnoten zusammengelegt, wiederkehrende Methoden einmal erklärt.
- Mietansatz: Fortschreibung bis Vermarktungsstart (1 + g)^(Monate/12); Projektfelder `vermarktungsstart`,
  `mietwachstum_pa`, Standard `MIETWACHSTUM_PA`; Tabelle `wohnung` (Wohnungsmix), Demo mit 4 DG-Wohnungen;
  DG-Herleitung Pflicht bei DG im Mix; Vorschlag und Freigabe je Basis.
- Lokale DB per `ALTER TABLE` ergänzt (Sicherung `daten/mietmarkt.vor-m5c.db`).
- Tests: Backend 163 (+1 Live-Test).
- Review-Befunde behoben (python-reviewer P1, P2–P9, P14, P16–P18; security-reviewer S1–S3):
  Mietansatz erst nach Standort und Marktdaten; Freigabe des Laufs als Hintergrundaufgabe der Antwort (kein
  Hängen bei sofortigem Verbindungsabbruch); höchstens 10 Zu-/Abschläge, Name 80 und Begründung 500 Zeichen;
  genau 15 % nicht auffällig; Korrektur des Berichts als eigener Knoten (Kosten gesichert); kaufmännische Rundung
  in `de()` und Stellen der Quelle; Rundenlimit als Abbruch; Markdown-Export maskiert Modelltext und erklärt
  „[?]“; IQR unter 4 Comps „nicht prüfbar“; Export ohne Projekt 404; „aendern“ ohne Inhalt ungültig.
- Tests: Backend 173 (+1 Live-Test).
- Nach dem Live-Lauf: Methoden nur aus fester Liste (OSRM, Haversine, Quartile inklusiv, Grenze ± 15 %), Formeln
  bleiben in der Fußnote; Risiken nur mit `befund:N` oder Katalog-ID belegt; Einheit im Dativ nach Präposition;
  Markdown maskiert nur Wirksames. Tests: Backend 175 (+1 Live-Test).
- Dienstausfälle (Overpass, OSRM) als Befund `dienst` im Code; Werte-Katalog und Fußnoten nennen Zeitraum, Gebiet
  und Quelle mit Stand; Risiken-Prompt ohne eigene Wertungen (Prompt-Regel, nicht maschinell prüfbar). Demo:
  Einheit „Einwohner“, Baufertigstellungen 2025 für die Stadt; lokale DB angepasst (Sicherung
  `daten/mietmarkt.vor-m5e.db`). Tests: Backend 179 (+1 Live-Test).

### Bekannte Punkte (bewusst offen)
- **S4** Zeitfenster zwischen der Prüfung „wartet auf Freigabe/Antwort“ und dem Fortsetzen: zwei gleichzeitige
  POSTs können beide die Prüfung bestehen; praktisch nur, wenn der erste Lauf ohne Modellaufruf sofort endet.
  Abhilfe später: Prüfung und `aktive_laeufe.add` vor das erste `await` ziehen.
- **P10** Werte-Katalog: mehrere `comps_filtern`-Aufrufe mit unterschiedlichem Filter überschreiben sich je
  Listenposition (IDs ohne Aufrufindex).
- **P11** Vergleichswerte der Angebotsstatistik aus `ansatz_pruefen` haben im Katalog keine Beschreibung (kein `rechenweg_text`).
- **P12** Ein Supervisor, der stur „fertig“ mit Rückfrage antwortet, fragt bis zum Rundenlimit erneut (begrenzt,
  aber bis zu 6 bezahlte Aufrufe). Der Docstring von `_leitplanken` ist angepasst.
- **P13** `recursion_limit` (80) gilt je Aufruf bzw. Fortsetzung, nicht je Lauf; die Agent-Werkzeug-Schleife
  begrenzen nur Budget und Nutzer.
- **P15** „Älter als 12 Monate“ ist als mehr als 365 Tage umgesetzt; im Schaltjahr gilt ein Angebot von genau
  12 Monaten schon als veraltet.
- **S5** Der Portal-Filter lässt bei Demo-Projekten alle Einträge durch. Heute kein Weg dahin (kein Import-
  Endpunkt); ein künftiger Import muss Demo-Projekte sperren oder je Eintrag filtern.
- Offen: Freigabe-Karte, Antwortfeld und Zeitleiste im Frontend.

## M6 – Eigene Unterlagen (22.11.2026)
- Upload `POST /api/projekte/{id}/dokumente` (PDF, PNG/JPG, Text; Typ am Inhalt, 10 MB bzw. Bilder 5 MB, Pillow
  prüft Bilder, höchstens 100 PDF-Seiten), Ablage `daten/uploads/<projekt>/<zufall>.<art>`, je Dokument eine Quelle.
  Je Dokument `ki_freigabe` (Standard aus), sonst wie Portal-Daten nur lokal.
- RAG: Abschnitte von rund 800 Zeichen mit Überlappung in SQLite FTS5 (`abschnitt`), Werkzeug `dokumente_suchen`
  mit Datei, Seite, Ausschnitt; Fragen werden nie als FTS5-Syntax ausgewertet.
- Exposé-Agent (Parser mit pdfplumber und Regex, Modell nur für leere Felder, Zitat am Text geprüft) und
  Vision-Agent (Bildeingabe, Herkunft abgelesen mit Ausschnitt); Supervisor-Leitplanke: beide vor dem Mietansatz,
  wenn passende Unterlagen freigegeben sind. MAX_RUNDEN 8.
- Prüfung: Befund `fundstelle` für Aussagen aus Treffern ohne `[Quelle: Datei, S. X]` und für falsche Fundstellen.
- Behoben nebenbei: Kosten-Wert wurde als Enum im Checkpoint gespeichert (jetzt JSON, strikter Modus grün).
- Tests: Backend 209 (+1 Live-Test). Neue Abhängigkeiten: pdfplumber, pillow, python-multipart.
- Entschieden (22.11.2026): `ki_freigabe` bleibt standardmäßig aus.
- Offen: Upload und Dokumentliste im Frontend – das Häkchen `ki_freigabe` sichtbar beim Upload, mit dem Hinweis, dass das Dokument dann bei einem Lauf an Anthropic geht; Liste/Löschen von Dokumenten per API; Exposé-Werte als Comps
  übernehmen (nur über Freigabe); Live-Lauf mit OSRM/Haversine, sobald overpass-api.de wieder erreichbar ist.

## Nachtrag 23.11.2026 – Overpass-Ausfall, Umfeld-Cache, Live-Läufe
- Exposé- und Vision-Agent einmal echt mit Claude gelaufen (synthetisches Exposé + Bildtabelle, nur die beiden Knoten):
  Baujahr vom Modell ergänzt (Herkunft ki, Zitat geprüft), drei Tabellenwerte abgelesen (Ausschnitte auf ±2 px genau),
  Kosten 0,0069 € (Haiku 0,0002 €, Sonnet 0,0066 €).
- Jahreszahlen ohne Tausenderpunkt (`OHNE_TAUSENDER` in `agenten/bericht.py`, Einheit „Jahr“).
- Overpass: Server-Liste `OVERPASS_URLS` (Standard nur overpass-api.de; Ersatzserver nur auf Wunsch in `.env`),
  Timeout 25 s je Server, Rechenzeit 20 s, Fußnote nennt Server und Abrufdatum. Umfeld je Projekt 30 Tage in
  `umfeldcache` (Koordinaten müssen passen, Ausfälle werden nicht gespeichert); API und Werkzeug `umfeld` nutzen ihn.
- Tests: Backend 215 (+1 Live-Test).
- **Verschoben:** Live-Test mit Umfeld (`pytest -m live -s`, Abschnitte Lage, Risiken, Methoden ansehen) und das
  einmalige Befüllen von `umfeldcache` für das Demo-Projekt. overpass-api.de war am 23.11.2026 überlastet (502 und
  Zeitüberschreitungen von 10:50 bis 11:36, nur eine kurze Antwort um 11:22). Befüllen später mit
  `umfeld_fuer_projekt` für die Demo-Projekte bzw. einem Aufruf von `GET /api/projekte/1/umfeld` bei laufender App.

## M7 – Agenten-Elemente im Frontend (23.11.2026)
- Zeitleiste liest den SSE-Strom (`frontend/src/lauf.ts`: `sseLesen` über fetch, weil Freigabe/Antwort POST-Ströme sind;
  reine Funktion `verarbeite` plus Hook `useLauf`): Status je Agent (arbeitet, fertig, Rückfrage, wartet, Fehler),
  Werkzeugaufrufe mit Argumenten und Ergebnis aufklappbar, Dauer (Browser-Uhr), Token, Kosten in €, Text tokenweise.
- Freigabe-Karte aus dem Interrupt: Vorschlag je Basis, Begründung, Herleitungskette; Annehmen / Ändern (Basiswert und
  Beträge der Zu-/Abschläge) / Ablehnen (nur mit Kommentar). Rückfragen mit Antwortfeld in der Agentenleiste.
- Herkunfts-Kennzeichen (`komponenten/Herkunft.tsx`): Klick zeigt Quelle, Rechenweg bzw. Fundstelle und Bildausschnitt;
  an Herleitung, Mietansatz, KPIs und Comps-Zusammenfassung. Tabellenzellen behalten den title-Tooltip.
- Laufliste je Projekt: `GET /api/projekte/{id}/laeufe` (Status fertig, abgebrochen, offen); „Fortsetzen“ öffnet
  pausierte oder unterbrochene Läufe am Checkpoint.
- Hinweisleiste „KI nicht konfiguriert“ (aus `/api/gesundheit`), Startknopf dann gesperrt.
- Upload eigener Unterlagen mit Häkchen „KI darf lesen“ (Standard aus, Hinweis: geht bei einem Lauf an Anthropic).
- `agentenDaten.ts` und der Platzhalter „Comp 6 ausschließen“ entfernt; Mietansatz-Karte zeigt den echten Vorschlag bzw.
  die Freigabe, sonst einen Leerzustand.
- Farben nur noch in `frontend/src/stil/tokens.css` (`:root`); `farben.test.ts` verbietet Farbwerte in anderen CSS-
  und Komponentendateien (Ausnahme `kartenstil.ts`, MapLibre kennt keine CSS-Variablen).
- Tests: Backend 216, Frontend 24 (Stream-Verarbeitung mit aufgezeichneten Ereignissen `src/test/aufzeichnung.json`,
  Freigabe-Karte, Herkunfts-Kennzeichen). Playwright-Skript `node skripte/lauf.mjs [ordner]`: startet
  `backend/tests/fake_server.py` (nur mit `KI_FAKE=1`) auf Port 8010 und Vite auf 5180 (`API_PORT`), kompletter Lauf
  bis zum freigegebenen Mietansatz. Fortsetzen nach Neuladen einmal im Browser (Playwright-MCP) geprüft.
- Review `python-reviewer`: ohne wesentlichen Befund; ergänzt: Test für Status „abgebrochen“ in der Laufliste, der
  Fake-Server räumt seinen Temp-Ordner auf (SIGTERM-Handler, weil uvicorn das Signal nach dem Herunterfahren erneut auslöst).
- Review `security-reviewer`, beide Befunde behoben:
  - **S6** Unterlagen gingen im Demo-Projekt und bei `KI_PORTALDATEN_SENDEN=true` auch ohne Häkchen an Anthropic,
    obwohl die Oberfläche „bleibt lokal“ sagt. Jetzt zählt für Unterlagen nur `ki_freigabe`; eigener Hinweis an das
    Modell (`HINWEIS_DOKUMENTE`), README angepasst. Entschieden 23.11.2026.
  - **S7** CSRF: Fremde Websites konnten POST-Anfragen an 127.0.0.1:8000 schicken (z. B. Upload mit KI-Freigabe).
    ASGI-Middleware `EigeneHerkunft` weist schreibende Anfragen mit fremdem `Origin` (auch „null“) mit 403 ab.
- Tests danach: Backend 222, Frontend 24.
- Offen:
  - **Zeitleiste beim Fortsetzen:** Das Backend speichert die Ereignisse nicht; ein fortgesetzter Lauf zeigt nur die
    Schritte ab dem Fortsetzen (beim Endstand ergänzt aus `ergebnisse`). Token zählen dann nur ab dort, die Kosten in €
    stimmen am Ende wieder (aus „fertig“). Abhilfe: Ereignisse je Lauf speichern oder aus dem Checkpoint rekonstruieren.
  - **Dokumentliste:** Upload zeigt nur das Ergebnis der letzten Datei; Liste und Löschen fehlen (API und Frontend),
    ebenso das nachträgliche Ändern von `ki_freigabe`.
  - Neue Anpassungen lassen sich beim Ändern nicht hinzufügen oder entfernen, nur Beträge und Basiswert ändern.

## Veröffentlichungsvorbereitung (23.11.2026)
- README neu (Schnellstart, Architektur als Mermaid, „Warum rechnet die KI nicht?“, gemessene Kosten, Datenschutz,
  Grenzen), `LICENSE` (MIT), `CHANGELOG.md`, Screenshots und Lauf-GIF in `docs/screenshots/` (`skripte/lauf-gif.mjs`).
- Knopf „Demo-Standort öffnen“ auf der Startseite, `POST /api/demo` (`demo_oeffnen`: ergänzt die Demo, löscht nichts).
- Neutral: Produktnamen fremder Datenanbieter in Code, Demo-Daten und Oberfläche ersetzt (Marktbericht,
  Angebotsstatistik, Portal-Exposés; Kennzahl-Gruppen `angebot`, `angebot_tabelle`). Alte Entwurfsbilder entfernt.
  Lokale DB: Demo neu laden (`python -m mietmarkt.demo seed`), sonst zeigt sie die alten Namen und Gruppen.
- Gemessen: echter Lauf auf dem Demo-Standort 95.941 Token, 0,18 € (Sonnet 5.5 + Haiku 5.5, Overpass ausgefallen).
- Fund aus dem echten Lauf behoben: `ereignisse()` scheiterte mit KeyError, wenn `validierung` den Mietansatz-Agenten
  wegen fehlender DG-Herleitung zurückschickt (Lauf brach ab).
- security-reviewer (ganzes Repo), Befunde behoben: N1 zu große Uploads schon an `Content-Length` abgewiesen (413),
  N2 PDF-/Bildprüfung im Thread statt in der Event-Loop, N3 `aktive_laeufe` per `finally` freigegeben (kein
  dauerhaftes 409), N4 Datenschutzliste im README vollständig.
- Tests: Backend 226, Frontend 25.
