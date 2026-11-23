# Architektur und Referenz

Technische Details zu Mietmarkt Research: API-Endpunkte, Agenten-Graph mit Leitplanken und Ereignissen, externe
Dienste und wo man was ändert. Überblick, Schnellstart und Datenschutz stehen im [README](../README.md).

## API

| Endpunkt | Liefert |
|---|---|
| `GET /api/adressen/vorschlaege?q=…` | Adressvorschläge (Photon), ab 3 Zeichen, mit Attribution |
| `POST /api/projekte` | Projekt aus einem gewählten Vorschlag anlegen (Adresse über Nominatim) |
| `GET /api/projekte/{id}/umfeld` | ÖPNV, Supermärkte, Schulen, Kitas, Ärzte im Umkreis 1 km mit Wegezeiten |
| `GET /api/projekte` | alle Projekte, zuletzt analysierte zuerst |
| `POST /api/demo` | Demo-Standort öffnen → `{projekt_id}`; legt die Demo-Daten nur an, wenn sie fehlen |
| `GET /api/projekte/{id}` | ein Projekt mit Datenstand je Quelle |
| `GET /api/projekte/{id}/comps` | Comps mit €/m², Tagen online, Anfragen je Monat, Luftlinie – je als Wert mit Rechenweg |
| `GET /api/projekte/{id}/kennzahlen` | Marktkennzahlen mit Herkunft, Comps-Zusammenfassung, Preisklassen-Auswertung |
| `POST /api/projekte/{id}/laeufe` | Agenten-Lauf anlegen → `{lauf_id}`; 503 „KI nicht konfiguriert“ ohne Schlüssel |
| `GET /api/laeufe/{lauf_id}/ereignisse` | Lauf ausführen bzw. fortsetzen, Ereignisse als Server-Sent Events (siehe unten) |
| `POST /api/laeufe/{lauf_id}/freigabe` | Mietansatz freigeben: `{aktion: annehmen \| aendern \| ablehnen, aenderungen?: {regel_eg?, dg?}, kommentar?}`; streamt weiter |
| `POST /api/laeufe/{lauf_id}/antwort` | Rückfrage des Supervisors beantworten: `{antwort}`; streamt weiter |
| `POST /api/projekte/{id}/dokumente` | Eigene Unterlage hochladen (Formular: `datei`, `ki_freigabe`): PDF, PNG/JPG, Text; höchstens 10 MB (Bilder 5 MB), Typ am Inhalt erkannt; Ablage unter `daten/uploads/` |
| `GET /api/laeufe/{lauf_id}/bericht.md` / `.pptx` | Bericht eines fertigen Laufs als Markdown oder PowerPoint |
| `GET /api/gesundheit` | Lebenszeichen; `ki: true/false`, ob ein Anthropic-Schlüssel eingetragen ist |

Jede Zahl kommt als `{wert, einheit, herkunft, quelle_id, rechenweg_text}`; `herkunft` ist `import | manuell | ki | abgelesen | berechnet`.

## KI-Agenten (LangGraph)

Ein Lauf ist ein LangGraph-Graph in `backend/mietmarkt/agenten/`:
`supervisor → Agent ⇄ Werkzeuge → validierung → supervisor → … → mietansatz → freigabe ⏸ → pruefung → bericht → Ende`.
„Ablehnen“ bei der Freigabe und ein kritischer Prüfbefund führen zurück zum Supervisor. Stellt der Supervisor eine
Rückfrage, hält der Lauf an (`rueckfrage ⏸`); die Antwort geht an den Supervisor, der neu entscheidet. Zahlen aus
Antworten des Nutzers gelten bei der Zahlenprüfung als belegt.

| Agent | Modell (`.env`) | Werkzeuge |
|---|---|---|
| Supervisor | `MODELL_STARK` (Standard `claude-sonnet-5-5`) | keine; entscheidet per strukturierter Ausgabe, wer als Nächstes dran ist |
| Standort | `MODELL_SCHNELL` (Standard `claude-haiku-5-5`) | `lage` (Adresse und Koordinaten aus der Datenbank, kein Geokodieren), `umfeld` |
| Marktdaten | `MODELL_SCHNELL` | `kennzahlen`, `comps_filtern` |
| Mietansatz | `MODELL_STARK` | `kennzahlen`, `mietansatz_herleiten` (rechnet; Basis `regel_eg` oder `dg`; Zu-/Abschläge des Modells tragen Herkunft `ki`) |
| Prüfung | `MODELL_STARK` | `comps_pruefen` (unter 5 Comps, älter als 12 Monate, Ausreißer per 1,5 × IQR), `ansatz_pruefen` (Abweichung > 15 % zu Median, Ø Regel/EG, Kennzahlen der Angebotsstatistik); der Code ruft beide immer auf, das Modell vergibt nur den Schweregrad `hinweis \| warnung \| kritisch` |
| Bericht | `MODELL_STARK` | keine; schreibt Lage, Markt, Mietansatz, Risiken mit Platzhaltern `{{wert:ID}}` |

- **Zahlen:** Werkzeuge rufen nur Fachfunktionen auf. Der Knoten `validierung` markiert jede Zahl einer Agenten-Antwort,
  die in keinem Werkzeugergebnis und nicht in den Projektdaten steht (Herkunft `ki`, Warnhinweis); ebenso Begründung,
  Auftrag und Rückfrage des Supervisors.
- **Fachregeln Mietansatz:** Der Haupt-Mietansatz geht immer von Regelgeschoss/EG aus. DG ist eine getrennte
  Herleitung mit DG-Basis, nie ein Zuschlag (im Code geprüft). Jeder Zu-/Abschlag nennt einen belegten Unterschied
  zwischen Projekt und Comps; ohne belegten Unterschied kein Merkmal (Prompt-Regel, nicht maschinell prüfbar).
- **Leitplanken im Code:** „fertig“ ohne Rückfrage erst, wenn alle drei Agenten erledigt sind (Mietansatz erst mit
  Freigabe), Mietansatz erst nach Standort und Marktdaten, Zu-/Abschläge höchstens ±10 €/m² und höchstens 10 je
  Herleitung (Name 80, Begründung 500 Zeichen), höchstens 8 Supervisor-Entscheidungen je Lauf (danach Abbruch ohne Bericht; geprüft wird
  vor dem Modellaufruf, eine neunte Entscheidung wird also nicht mehr bezahlt).
- **Mietansatz:** je Basis eine Herleitung (`regel_eg` Pflicht, `dg` Pflicht, wenn der Wohnungsmix DG-Wohnungen hat;
  fehlt eine, schickt der Code den Agenten einmal mit Hinweis zurück). Jede Herleitung wird bis zum
  Vermarktungsstart fortgeschrieben: Ansatz × (1 + g)^(Monate/12), volle Kalendermonate ab Stichtag; g aus dem
  Projekt (`mietwachstum_pa`), sonst `MIETWACHSTUM_PA` in `.env` (Standard 0,02). Geprüft wird der Ansatz zum Stichtag.
- **Freigabe (Human-in-the-Loop):** Nach dem Mietansatz hält der Lauf an (`interrupt()`); der Vorschlag (Herleitungen
  je Basis, Zu-/Abschläge, Begründung) kommt als Ereignis `wartet_auf_freigabe`. `annehmen` übernimmt ihn, `aendern` rechnet mit
  neuer Basis bzw. neuen Zu-/Abschlägen neu (geänderte Werte Herkunft `manuell`, unveränderte bleiben `ki`),
  `ablehnen` (Kommentar Pflicht) schickt den Kommentar über den Supervisor an den Mietansatz-Agenten. Der angehaltene
  Lauf überlebt einen Neustart der App.
- **Prüfung:** Ausgefallene Dienste meldet der Code selbst als Befund `dienst` (Overpass weg → warnung, kein
  Umfeld; OSRM weg → hinweis, nur Luftlinie), damit sie unter Risiken stehen können. Bei einem kritischen Befund verfallen Freigabe und Mietansatz, es geht zum Supervisor zurück. Nach
  2 Prüfrunden geht es auch bei „kritisch“ zum Bericht; der Befund steht dann unter Risiken.
- **Bericht:** Das Modell schreibt je Abschnitt Sätze mit Belegen (Katalog-ID, `befund:N`, `ergebnis:<agent>`,
  `freigabe`, `projekt`; unter Risiken nur `befund:N` und Katalog-IDs); Sätze ohne gültigen Beleg streicht Python. Zahlwörter („drei“, „zwölf“, „Hälfte“) zählen
  wie Ziffern. Entfernungen stehen gerundet im Text („rd. 230 m“), die Fußnote nennt den genauen Wert. Gleiche
  Fußnoten werden zusammengelegt. Unter „Methoden“ ([M1] …) stehen nur Quellen- und Verfahrenshinweise (OSRM,
  Haversine, Quartile inklusiv, Grenze ± 15 %); Formeln bleiben vollständig in der Fußnote. Nach Präpositionen steht
  die Einheit im Dativ („bei 36 Tagen“). Das Modell sieht einen Werte-Katalog (jeder Wert mit Herkunft aus Werkzeugergebnissen und der
  freigegebenen Herleitung) und darf Zahlen nur als `{{wert:ID}}` schreiben. Python setzt Wert, Einheit und Fußnote
  (Herkunft, Rechenweg bzw. Quelle) ein. Enthält der Entwurf freie Zahlen, bekommt das Modell einmal einen
  Korrekturauftrag mit genau diesen Zahlen (`bericht.korrektur`, eigener Knoten `bericht_korrektur`); was danach
  noch frei ist, wird zu `[?]` und als Markierung gemeldet. Zahlen rundet `de()` kaufmännisch; importierte
  Kennzahlen erscheinen mit ihren eigenen Nachkommastellen. Der Markdown-Export maskiert nur, was wirken würde (Links,
  Bilder, HTML, Backticks) in Modell- und Importtext und erklärt `[?]` sowie gestrichene Aussagen.
  Export als Markdown und PowerPoint (`backend/mietmarkt/export.py`, Sand/Stein/Oliv, ohne Logo).
- **Unterlagen (RAG):** Hochgeladene Texte werden seitenweise in Abschnitte von rund 800 Zeichen mit Überlappung
  geteilt und in SQLite FTS5 indexiert (Tabelle `abschnitt`, kein Embedding-Dienst). Das Werkzeug
  `dokumente_suchen` (Standort, Marktdaten, Mietansatz) liefert Datei, Seite und Ausschnitt; Aussagen daraus
  belegen die Agenten mit `[Quelle: Datei, S. X]`. Die Prüfung meldet im Code Sätze, die erkennbar aus Treffern
  stammen (vier gleiche Wörter in Folge oder eine Zahl, die nur dort steht), aber keine Fundstelle haben, und
  Fundstellen, die in keinem Treffer vorkommen (Befund `fundstelle`).
- **Exposé-Agent** (`MODELL_SCHNELL`): Ein Parser liest Wohnfläche, Kaltmiete, Zimmer, Baujahr und Ausstattung
  (Herkunft `import`, Seite). Nur leer gebliebene Felder ergänzt das Modell mit Seite und wörtlichem Zitat; Python
  prüft das Zitat am Text und die Zahl im Zitat, sonst wird die Ergänzung verworfen (Herkunft `ki`).
- **Vision-Agent** (`MODELL_STARK`): liest Tabellen und Diagramme aus hochgeladenen Bildern; jeder Wert trägt
  Herkunft `abgelesen` und den Bildausschnitt `[x, y, Breite, Höhe]`; Werte aus Diagrammen erscheinen als „rd.“.
  Werte ohne Zahl oder mit Ausschnitt außerhalb des Bildes fallen heraus. Kein Abruf von Webseiten.
- **Supervisor:** Mit freigegebenen Unterlagen sind Exposé- (PDF/Text) bzw. Vision-Agent (Bilder) Pflicht vor dem
  Mietansatz; ohne passende Unterlagen werden sie nicht aufgerufen.
- **Kosten:** Token je Aufruf aus `usage_metadata` × Preistabelle (`agenten/kosten.py`) × `KI_EUR_JE_USD`. Erreicht ein
  Lauf `KI_BUDGET_EUR_PRO_LAUF` (Standard 0,50 €), startet kein weiterer Modellaufruf; der letzte Aufruf kann das
  Budget also noch etwas überschreiten. Modelle ohne Eintrag in der Preistabelle werden vor jedem Aufruf abgelehnt.
  Ein Gesamtlimit über alle Läufe setzt man am einfachsten als Ausgabelimit in der Anthropic Console.
- **Wiederaufnahme:** Nach jedem Schritt sichert der Checkpointer den Zustand in `daten/checkpoints.db`
  (thread_id = Lauf-ID). Ruft man die Ereignisse eines unterbrochenen Laufs erneut ab, geht er dort weiter. Ein
  zweiter Abruf, während der Lauf noch läuft, bekommt 409. Ist ein Lauf beendet, steht sein Endstand in der Tabelle
  `lauf`, der Checkpoint wird gelöscht; der Endstand lässt sich auch ohne Schlüssel abrufen.
- **Ereignisse (SSE):** `agent_gestartet`, `werkzeugaufruf`, `werkzeugergebnis`, `text`, `agent_fertig`, `kosten`,
  `rueckfrage`, `wartet_auf_freigabe` bzw. `wartet_auf_antwort` (Strom endet, Lauf pausiert), `freigabe`, `antwort`,
  `pruefung` (Befunde, `zurueck`), `bericht`, `abbruch`, `fehler`, zum Schluss `fertig` mit Status
  `fertig | abgebrochen`, Ergebnissen, Rückfragen mit Antworten, Freigabe, Bericht und Gesamtkosten.

## Wo ändere ich was

| Was | Wo |
|---|---|
| Farben, Schriften, Abstände (Design-Tokens) | `frontend/src/stil/tokens.css` (einzige Stelle mit Farbwerten) |
| Layout und Komponenten-Stile | `frontend/src/stil/app.css` |
| Startseite / Analyse / Zustände | `frontend/src/seiten/` |
| Bausteine (Tabellen, Freigabe, Herleitung, Kopf, Agentenleiste) | `frontend/src/komponenten/` |
| Karte (Stil, Ringe, Marker) | `frontend/src/komponenten/kartenstil.ts`, `Karte.tsx` |
| Diagramme | `frontend/src/komponenten/Diagramme.tsx` |
| Datenmodell (Projekt, Quelle, Comp, Marktkennzahl, Wert mit Herkunft) | `backend/mietmarkt/modelle.py` |
| Kennzahlen (€/m², Median, Quartile, Ø flächengewichtet, Anfragen je Monat) | `backend/mietmarkt/kennzahlen.py` |
| Entfernung, Comp-Filter, Mietansatz-Kette | `backend/mietmarkt/geo/distanz.py`, `comps.py`, `mietansatz.py` |
| CSV/XLSX-Import von Comps | `backend/mietmarkt/importe.py` |
| Demo-Datensatz (inkl. Wohnungsmix, Vermarktungsstart, g) | `backend/mietmarkt/demo/musterstadt.yaml` |
| Mietwachstum für Projekte ohne eigenen Wert | `.env`: `MIETWACHSTUM_PA` |
| API-Endpunkte | `backend/api/main.py` |
| Externe Geodienste (URLs, Drossel, Cache), Umfeld-Auswertung | `backend/mietmarkt/geo/` |
| Agenten: Prompts, Graph, Leitplanken | `backend/mietmarkt/agenten/graph.py` |
| Agenten-Werkzeuge / Modellpreise / Zahlenprüfung | `backend/mietmarkt/agenten/werkzeuge.py`, `kosten.py`, `pruefung.py` |
| Plausibilitätsregeln (Mindestzahl, Alter, IQR, 15 %) | `backend/mietmarkt/plausibilitaet.py` |
| Platzhalter im Bericht, Export Markdown/PowerPoint | `backend/mietmarkt/agenten/bericht.py`, `backend/mietmarkt/export.py` |
| Modelle, Budget, Schlüssel | `.env` (Vorlage `.env.example`), gelesen in `backend/mietmarkt/konfig.py` |
| Platzhalter (Merkliste-Beispiele) | `frontend/src/daten/platzhalter.ts` |

## Externe Dienste

Alle Anfragen laufen über das Backend (nicht direkt aus dem Browser), mit dem User-Agent
`MietmarktResearch/0.1 (privates Projekt)` und `Accept-Language: de`. Antworten werden 30 Tage in der Tabelle `geocache`
(`daten/mietmarkt.db`) zwischengespeichert; dieselbe Anfrage geht also nur einmal hinaus, auch wenn sie zweimal
gleichzeitig gestellt wird. Ältere Einträge werden gelöscht, fehlerhafte Antworten nie gespeichert.

| Dienst | Wofür | Was gesendet wird | Grenzen |
|---|---|---|---|
| Photon (`photon.komoot.io`) | Adressvorschläge beim Tippen | der getippte Suchtext (ab 3 Zeichen, 300 ms nach dem letzten Tastendruck) | nur Deutschland (bbox), max. 5 Treffer, gedrosselt (2 Anfragen/s) |
| Nominatim (`nominatim.openstreetmap.org`) | endgültige Adresse beim Anlegen eines Projekts, Rückwärtssuche | gewählte Adresse bzw. deren Koordinaten | höchstens 1 Anfrage pro Sekunde, nie für die Autovervollständigung (Nutzungsrichtlinie) |
| Overpass (`overpass-api.de`) | Umfeld: ÖPNV, Supermärkte, Schulen, Kitas, Ärzte | Koordinaten des Standorts, Radius 1.000 m | gedrosselt (1 Anfrage/s), Rechenzeit 20 s, Timeout 25 s je Server; Ersatzserver nur, wenn in `OVERPASS_URLS` eingetragen; Umfeld je Projekt 30 Tage gespeichert (Fußnote nennt das Abrufdatum) |
| OSRM (`routing.openstreetmap.de`, FOSSGIS) | Wegezeiten zu Fuß und mit dem Rad | Koordinaten von Standort und bis zu 3 Zielen je Kategorie | gedrosselt; fällt der Dienst aus oder ist ein Ziel nicht routbar, gilt die Luftlinie (Kennzeichnung „Luftlinie“); der Rechenweg nennt das Abrufdatum |
| OpenFreeMap (`tiles.openfreemap.org`) | Kartenkacheln und Schriften der Karte | Kachelkoordinaten des sichtbaren Ausschnitts (direkt aus dem Browser) | – |

Warum nicht `router.project-osrm.org`: Der OSRM-Demo-Server rechnet nur mit dem Autoprofil und liefert für „foot“ die
Autozeit. Die FOSSGIS-Server sprechen dieselbe OSRM-API mit echten Fuß- und Radprofilen (`backend/mietmarkt/geo/dienste.py`).

Overpass-Ersatzserver nur auf Wunsch: Standardmäßig steht in `OVERPASS_URLS` nur `overpass-api.de`. Weitere Server
(z. B. `https://overpass.kumi.systems/api/interpreter`) trägt man selbst in `.env` ein; sie bekommen dann die
Projektkoordinaten. Fällt der erste aus, fragt die App den nächsten, die Fußnote nennt den Server, der geliefert hat.
Ohne Ersatzserver zeigt die App bei Überlast „Dienst nicht erreichbar“. Ein erfolgreiches Umfeld liegt je Projekt
30 Tage in der Tabelle `umfeldcache`, ein Lauf braucht Overpass dann nicht.

Der Browser darf nur Adressen in Deutschland übergeben (Koordinaten-, Längen- und NaN-Prüfung, sonst 422).
Fällt ein Dienst aus, antwortet die API mit 503; die Oberfläche zeigt „Dienst nicht erreichbar“, der Rest bleibt nutzbar.
Marktdaten (Comps, Marktberichte, Angebotsstatistiken) gehen an keinen dieser Dienste. Demo-Daten erscheinen nur bei Demo-Projekten, nie bei
echten Adressen.
