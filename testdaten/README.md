# Testdaten

Synthetische Dateien, um jede Funktion der App von Hand durchzuklicken. Alle Orte, Adressen, Anbieter und Zahlen sind
erfunden (fiktive „Musterstadt“, Ortsteil Südhang, PLZ 99998). Die Kartenlage ist wie beim Demo-Datensatz nur Kulisse.

```bash
backend/.venv/bin/python testdaten/erzeugen.py          # alle Dateien neu erzeugen (auch die großen Fehlerfälle)
backend/.venv/bin/python testdaten/erzeugen.py laden    # Testprojekt „Testquartier Südhang“ in daten/mietmarkt.db
```

`laden` legt ein zweites Demo-Projekt an: 16 Comps (über `lese_comps` aus der XLSX importiert), Marktbericht,
Angebotsstatistik, amtliche Werte, Quellen und Wohnungsmix. Es gibt die Projekt-Adresse aus, z. B.
`http://localhost:5173/analyse/4`. Mit `--eigenes-projekt` wird es wie eine echte Adresse angelegt (`demo=False`).
`python -m mietmarkt.demo seed` löscht es wieder; danach einfach erneut `laden`.

## Was testet welche Datei?

| Datei | Funktion | So geht's |
|---|---|---|
| `comps/comps_suedhang.csv` | Comps-Import CSV: UTF-8 mit BOM, Semikolon, „1.040,00“, „2,5“ Zimmer, ja/x/nein, TT.MM.JJJJ und ISO gemischt | `lese_comps` mit der Zuordnung `ZUORDNUNG` aus `erzeugen.py` (es gibt noch keinen Import-Endpunkt) |
| `comps/comps_suedhang.xlsx` | Comps-Import XLSX: dieselben 16 Comps mit echten Zahlen und Datumswerten, Leerzeile vor dem Kopf | wird von `laden` importiert |
| `comps/comps_fehlerhaft.csv` | Zeilengenaue Fehler, Windows-1252: Typ „Penthouse“, „abc“ als Miete, fehlende Fläche, 31.02., Zimmer 0, Baujahr 1750, negative Anfragen, leeres Objekt, Breitengrad 91 | `lese_comps`: 1 gültige Zeile, 10 Fehler |
| `markt/marktbericht_kennzahlen.csv` | Marktbericht: Einwohner, Haushalte, Kaufkraft, Arbeitslosen- und Leerstandsquote (Ortsteil/Stadt), Zeitreihe Median/unteres/oberes Quartil Q4/24–Q3/26, Preisklassen, Baufertigstellungen 2023–2025, Mietspiegel (Stand 01.04.2026) | wird von `laden` übernommen; Analyse-Seite des Testprojekts |
| `markt/angebotsstatistik.csv` | Angebotsstatistik: Angebotsmiete Neubau, Veränderung, Vermarktungsdauer, Tabelle nach Zimmerzahl (n, Ø m², Min, Ø, Median, P75, Max) | wie oben |
| `markt/quellen.csv` | Quellen mit Datenstand (Herkunft-Kennzeichen, Fußnoten) | wie oben |
| `unterlagen/expose_talblick18_dg.pdf` | Exposé-Parser: Wohnfläche, Kaltmiete, Zimmer mit Etikett; Baujahr nur im Fließtext („im Frühjahr 2025 fertiggestellt“) → KI-Ergänzung | im Projekt hochladen, „KI darf lesen“ an, Analyse starten |
| `unterlagen/expose_hangweg11_mehrseitig.pdf` | 4 Seiten: Kaltmiete und Baujahr (S. 3) gefunden, Wohnfläche („rund 76,9 Quadratmetern“) und Zimmer („3 Räume“) nur im Fließtext → KI. Volltextsuche: Nebenkosten, Wallbox, Haustiere, Kaution, Glasfaser, Energieausweis, Kellergröße, Einbauküche (nicht enthalten!) | hochladen mit „KI darf lesen“; die Agenten durchsuchen es mit `dokumente_suchen` |
| `unterlagen/expose_gartenhof4_eg.pdf` | „Miete kalt“ statt „Kaltmiete“, „Fertigstellung 2026“ statt „Baujahr“ → KI ergänzt beide | hochladen mit „KI darf lesen“ |
| `unterlagen/marktbericht_tabelle.png` | Vision-Agent, Tabelle (Median, Quartile, Leerstand, Einwohner, Baufertigstellungen, Mietspiegel) | hochladen mit „KI darf lesen“ |
| `unterlagen/angebotsmieten_balkendiagramm.png` | Vision-Agent, Balkendiagramm (Median €/m² nach Zimmerzahl, Werte an den Balken, „rd.“ im Bericht) | hochladen mit „KI darf lesen“ |
| `unterlagen/projektbeschreibung_suedhang.txt` | Text-Upload und Volltextsuche (RAG), 4 Abschnitte | hochladen; Treffer z. B. zu Wallboxen, Kita, Energie, Stellplatzmiete |
| `fehlerfaelle/getarnt_tabelle.pdf` | Binärdatei mit Endung .pdf | Upload → 415 |
| `fehlerfaelle/kaputt.pdf` | PDF-Kopf, kaputter Inhalt | Upload → 422 |
| `fehlerfaelle/kaputt_bild.png` | PNG-Kopf, kaputter Inhalt | Upload → 422 |
| `fehlerfaelle/bild_zu_breit.png` | 8200 px breit | Upload → 422 |
| `fehlerfaelle/injektion_expose.pdf` | Prompt-Injection: Anweisungen im Exposé (Zahlwörter, Bild von fremder Adresse, URL, 30 % Zuschlag) | hochladen als „Expose 22,50 €-m².pdf“ mit „KI darf lesen“, Analyse starten: nichts davon darf in Freigabe, Bericht oder Export wirken |
| `fehlerfaelle/zu_gross.pdf` | 11 MB (nicht im Repo) | Upload → 413 |
| `fehlerfaelle/bild_zu_gross.png` | knapp 6 MB (nicht im Repo) | Upload → 413 |

## Was die Comps auslösen sollen

- **Ausreißer:** Nr. 10 (Weinbergstraße 7) mit 28,65 €/m², weit über Q3 + 1,5 × IQR.
- **Älter als 12 Monate:** Nr. 11 (Kirschenweg 5), online seit 15.09.2025, Stichtag 20.11.2026.
- **Ohne Datum:** Nr. 15 (Wiesenrain 1), Alter unbekannt.
- **Baujahr-Filter:** Nr. 14 (Bergstraße 40, Baujahr 2018) fällt bei „Baujahr ab 2020“ heraus.
- **DG-Einheiten:** Nr. 2, 5 und 9 (Dachgeschoss mit Aufschlag), dazu EG-Einheiten und ein Wohnungsmix mit DG.
- Alle 16 Comps liegen im Umkreis von 2 km um das Testprojekt und mindestens 3,6 km vom Lindenquartier entfernt.

Die Exposés gehören zu Comps aus der Importdatei (Talblick 18 DG, Hangweg 11 3 Zi., Gartenhof 4 EG); die Zahlen stimmen
überein. Bild-Werte passen zu den CSV-Kennzahlen (Q3/2026).
