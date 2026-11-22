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
- **P11** VALUE-Vergleichswerte aus `ansatz_pruefen` haben im Katalog keine Beschreibung (kein `rechenweg_text`).
- **P12** Ein Supervisor, der stur „fertig“ mit Rückfrage antwortet, fragt bis zum Rundenlimit erneut (begrenzt,
  aber bis zu 6 bezahlte Aufrufe). Der Docstring von `_leitplanken` ist angepasst.
- **P13** `recursion_limit` (80) gilt je Aufruf bzw. Fortsetzung, nicht je Lauf; die Agent-Werkzeug-Schleife
  begrenzen nur Budget und Nutzer.
- **P15** „Älter als 12 Monate“ ist als mehr als 365 Tage umgesetzt; im Schaltjahr gilt ein Angebot von genau
  12 Monaten schon als veraltet.
- **S5** Der Portal-Filter lässt bei Demo-Projekten alle Einträge durch. Heute kein Weg dahin (kein Import-
  Endpunkt); ein künftiger Import muss Demo-Projekte sperren oder je Eintrag filtern.
- Offen: Freigabe-Karte, Antwortfeld und Zeitleiste im Frontend.
