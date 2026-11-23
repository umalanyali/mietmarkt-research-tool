"""Erzeugt die synthetischen Testdaten unter testdaten/ (Comps-Import, Marktbericht, Angebotsstatistik, Exposés,
Bilder für den Vision-Agenten, Text für die Volltextsuche, Fehlerfälle) und lädt auf Wunsch ein Testprojekt in die
Datenbank. Alle Orte, Anbieter, Adressen und Zahlen sind erfunden (fiktive „Musterstadt“, PLZ 99998).

Aufruf aus dem Repository-Ordner:
    backend/.venv/bin/python testdaten/erzeugen.py                     # Dateien erzeugen
    backend/.venv/bin/python testdaten/erzeugen.py laden                # Testprojekt „Südhang“ in daten/mietmarkt.db
    backend/.venv/bin/python testdaten/erzeugen.py laden --eigenes-projekt  # dasselbe als Nicht-Demo-Projekt
"""
import argparse
import csv
import datetime as dt
import io
import random
import sys
import textwrap
from pathlib import Path

import openpyxl
from PIL import Image, ImageDraw, ImageFont

ORDNER = Path(__file__).resolve().parent
REPO = ORDNER.parent
STICHTAG = dt.date(2026, 11, 20)
PROJEKTNAME = "Testquartier Südhang"
# Kartenlage nur Kulisse (wie in musterstadt.yaml); rund 4,8 km vom Lindenquartier entfernt, damit sich die Comps
# der beiden Demo-Projekte im Umkreis von 2 km nicht mischen
ZENTRUM = (51.2780, 9.4380)

# Spalte in der Datei → Feld im Datenmodell (so wie lese_comps sie erwartet)
ZUORDNUNG = {"Objekt": "objekt", "Anbieter": "anbieter", "Lage im Haus": "typ", "Zimmer": "zimmer",
             "Baujahr": "baujahr", "Wohnfläche (m²)": "wohnflaeche", "Kaltmiete (€)": "kaltmiete", "EBK": "ebk",
             "Online seit": "online_seit", "Anfragen": "anfragen", "Breitengrad": "lat", "Längengrad": "lon"}

# objekt, anbieter, typ, zimmer, baujahr, wohnfläche, kaltmiete, ebk, online_seit, anfragen, Versatz Nord/Ost in km
COMPS = [
    ("Sonnenhang 3", "Beispiel Wohnbau", "Regel", 2, 2025, 57.8, 1040, "ja", "2026-10-02", 34, (0.6, 0.4)),
    ("Sonnenhang 3", "Beispiel Wohnbau", "DG", 3, 2025, 84.2, 1640, "ja", "2026-10-02", 12, (0.6, 0.4)),
    ("Hangweg 11", "Musterbau Süd", "EG", 2, 2026, 62.4, 1045, "ja", "2026-10-21", 19, (-0.5, 0.9)),
    ("Hangweg 11", "Musterbau Süd", "Regel", 3, 2026, 76.9, 1300, "ja", "2026-10-21", 25, (-0.5, 0.9)),
    ("Hangweg 11", "Musterbau Süd", "DG", 4, 2026, 101.5, 1950, "ja", "2026-10-21", 5, (-0.5, 0.9)),
    ("Am Rebgarten 2", "Privat", "Regel", 1, 2024, 36.5, 690, "nein", "2026-11-05", 22, (1.1, -0.7)),
    ("Am Rebgarten 2", "Privat", "Regel", 2, 2024, 54.0, 920, "nein", "2026-11-05", 17, (1.1, -0.7)),
    ("Talblick 18", "Muster Immobilien", "Regel", 3, 2025, 80.3, 1365, "x", "2026-09-14", 40, (-1.2, -0.3)),
    ("Talblick 18", "Muster Immobilien", "DG", 3, 2025, 88.6, 1710, "x", "2026-09-14", 9, (-1.2, -0.3)),
    # Ausreißer: 28,65 €/m² liegt weit über Q3 + 1,5 × IQR
    ("Weinbergstraße 7", "Beispiel Wohnbau", "Regel", 2, 2025, 52.0, 1490, "ja", "2026-10-28", 3, (0.2, 1.4)),
    # älter als 12 Monate: online seit 15.09.2025, Stichtag 20.11.2026
    ("Kirschenweg 5", "Privat", "EG", 3, 2024, 83.0, 1290, "nein", "2025-09-15", 61, (0.9, 0.8)),
    ("Steinbruchweg 22", "Musterbau Süd", "Regel", 2.5, 2024, 66.0, 1150, "ja", "2026-10-30", 14, (-0.3, -1.1)),
    ("Lindenhang 9", "Muster Immobilien", "Regel", 4, 2026, 95.4, 1610, "ja", "2026-11-09", 6, (0.4, -0.2)),
    # Bestand (Baujahr 2018): fällt beim Filter „Baujahr ab 2020“ heraus
    ("Bergstraße 40", "Beispiel Wohnbau", "Regel", 2, 2018, 60.2, 890, "nein", "2026-11-01", 28, (-0.8, 0.2)),
    # ohne Datum und Anfragen: Alter unbekannt („ohne_datum“)
    ("Wiesenrain 1", "Privat", "Regel", 3, 2025, 72.0, 1180, "", "", None, (1.3, 0.1)),
    ("Gartenhof 4", "Beispiel Wohnbau", "EG", 2, 2026, 64.8, 1180, "ja", "2026-11-12", 11, (-0.1, 0.6)),
]

QUELLEN = [  # name, art, datei, stand, abgerufen_am
    ("Marktbericht", "datei", "marktbericht_kennzahlen.csv", "Q3/2026", "2026-11-16"),
    ("Angebotsstatistik", "datei", "angebotsstatistik.csv", "Q3/2026", "2026-11-14"),
    ("Portal-Exposés", "datei", "comps_suedhang.xlsx", "20.11.2026", "2026-11-20"),
    ("Statistikamt Musterstadt", "manuell", "", "31.12.2025", "2026-11-10"),
    ("Statistisches Landesamt", "manuell", "", "2025", "2026-11-10"),
    ("Mietspiegel Musterstadt", "manuell", "", "01.04.2026", "2026-11-10"),
]
WOHNUNGSMIX = [("EG", 2, 63.0, 6), ("Regel", 2, 58.5, 14), ("Regel", 3, 78.0, 10), ("DG", 3, 86.5, 4),
               ("DG", 4, 102.0, 2)]


def _de(x: float, stellen: int = 2) -> str:
    """Zahl im deutschen Format mit Tausenderpunkt. Eingabe: Zahl, Nachkommastellen. Ausgabe: Text wie „1.040,00“."""
    return f"{x:,.{stellen}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _koordinaten(versatz_km: tuple[float, float]) -> tuple[float, float]:
    """Koordinaten aus einem Versatz zum Zentrum. Eingabe: (Nord, Ost) in km. Ausgabe: (lat, lon), 6 Stellen."""
    return (round(ZENTRUM[0] + versatz_km[0] / 111.2, 6), round(ZENTRUM[1] + versatz_km[1] / 69.6, 6))


# ---------------------------------------------------------------- Comps-Import (CSV, XLSX, fehlerhafte CSV)

def comps_dateien(ziel: Path) -> None:
    """Schreibt dieselben Comps als CSV (deutsches Excel: UTF-8 mit BOM, Semikolon, Komma) und als XLSX.

    Eingabe: Zielordner. Ausgabe: keine. Die CSV mischt Datumsformate und ja/x/nein, die XLSX nutzt echte Zahlen und
    Datumswerte und hat eine Leerzeile vor dem Kopf (der Import nimmt die erste nicht leere Zeile).
    """
    kopf = list(ZUORDNUNG)
    zeilen_csv, zeilen_xlsx = [], []
    for i, (obj, anb, typ, zi, bj, wf, km, ebk, online, anfr, versatz) in enumerate(COMPS):
        lat, lon = _koordinaten(versatz)
        datum = dt.date.fromisoformat(online) if online else None
        # jede dritte Zeile im ISO-Format, sonst TT.MM.JJJJ
        datum_text = "" if not datum else (datum.isoformat() if i % 3 == 2 else f"{datum:%d.%m.%Y}")
        zeilen_csv.append([obj, anb, typ, _de(zi, 1).replace(",0", ""), bj, _de(wf, 1), _de(km), ebk, datum_text,
                           "" if anfr is None else anfr, str(lat), str(lon)])
        zeilen_xlsx.append([obj, anb, typ, zi, bj, wf, km, ebk or None, datum, anfr, lat, lon])
    puffer = io.StringIO()
    csv.writer(puffer, delimiter=";", lineterminator="\r\n").writerows([kopf, *zeilen_csv])
    (ziel / "comps_suedhang.csv").write_bytes(puffer.getvalue().encode("utf-8-sig"))

    mappe = openpyxl.Workbook()
    blatt = mappe.active
    blatt.title = "Angebote"
    blatt.append([])
    blatt.append(kopf)
    for z in zeilen_xlsx:
        blatt.append(z)
    for zelle in blatt["I"][2:]:
        zelle.number_format = "DD.MM.YYYY"
    mappe.properties.creator = "Mietmarkt Research Testdaten"
    mappe.properties.created = mappe.properties.modified = dt.datetime(2026, 11, 20)
    mappe.save(ziel / "comps_suedhang.xlsx")

    # Fehlerfälle für die zeilengenaue Meldung, als Windows-1252 wie aus Excel unter Windows
    fehler = [kopf,
              ["Ahornweg 1", "Privat", "Regel", "2", "2025", "55,0", "980,00", "ja", "01.11.2026", "4", "51.27", "9.43"],
              ["Ahornweg 3", "Privat", "Penthouse", "3", "2025", "90,0", "1.900,00", "ja", "01.11.2026", "2", "", ""],
              ["Ahornweg 5", "Privat", "Regel", "2", "2025", "", "abc", "ja", "01.11.2026", "", "", ""],
              ["Ahornweg 7", "Privat", "DG", "0", "1750", "70,0", "1.200,00", "vielleicht", "31.02.2026", "-3", "", ""],
              ["", "Privat", "Regel", "2", "2025", "60,0", "1.000,00", "nein", "2026-11-01", "1", "", ""],
              ["Ahornweg 9", "Privat", "EG", "2", "2026", "61,5", "1.050,00", "nein", "05.11.2026", "", "91.0", "9.43"]]
    puffer = io.StringIO()
    csv.writer(puffer, delimiter=";", lineterminator="\r\n").writerows(fehler)
    (ziel / "comps_fehlerhaft.csv").write_bytes(puffer.getvalue().encode("cp1252"))


# ---------------------------------------------------------------- Marktbericht, Angebotsstatistik, Quellen

QUARTALE = ["Q4/24", "Q1/25", "Q2/25", "Q3/25", "Q4/25", "Q1/26", "Q2/26", "Q3/26"]


def kennzahlen() -> list[dict]:
    """Alle Marktkennzahlen des Testprojekts (Felder wie Marktkennzahl). Eingabe: keine. Ausgabe: Liste von dicts."""
    k = []

    def neu(gruppe, bez, kat, gebiet, wert, einheit, stellen, quelle, herkunft="import"):
        """Hängt eine Kennzahl an. Eingabe: Felder. Ausgabe: keine."""
        k.append({"gruppe": gruppe, "bezeichnung": bez, "kategorie": kat, "gebiet": gebiet, "wert": wert,
                  "einheit": einheit, "stellen": stellen, "herkunft": herkunft, "quelle": quelle})

    mb = "Marktbericht"
    for bez, ot, st, einheit, stellen in [("Einwohner", 12840, 204300, "Einwohner", 0), ("Haushalte", 6610, 108900, "", 0),
                                          ("Ø Personen je HH", 1.94, 1.88, "", 2),
                                          ("Kaufkraft je Einw.", 27400, 25100, "€", 0),
                                          ("Arbeitslosenquote", 4.8, 6.9, "%", 1),
                                          ("Leerstandsquote", 1.6, 2.3, "%", 1)]:
        neu("soziodemografie", bez, "", "Ortsteil Südhang", ot, einheit, stellen, mb)
        neu("soziodemografie", bez, "", "Stadt", st, einheit, stellen, mb)
    reihen = {"Median PLZ 99998": [15.2, 15.4, 15.5, 15.9, 16.0, 16.2, 16.3, 16.4],
              "Unteres Quartil": [13.8, 13.9, 14.0, 14.3, 14.5, 14.6, 14.8, 14.9],
              "Oberes Quartil": [16.9, 17.1, 17.2, 17.5, 17.6, 17.8, 18.0, 18.1]}
    for bez, werte in reihen.items():
        for q, w in zip(QUARTALE, werte, strict=True):
            neu("zeitreihe", bez, q, "PLZ 99998", w, "€/m²", 2, mb)
    for kat, n in [("< 12", 3), ("12–13,50", 5), ("13,50–15", 11), ("15–16,50", 24), ("16,50–18", 31),
                   ("18–19,50", 17), ("19,50–21", 7), ("> 21", 2)]:
        neu("preisklassen", "Angebote", kat, "PLZ 99998", n, "", 0, mb)

    an = "Angebotsstatistik"
    for bez, w, einheit, stellen in [("Angebotsmiete Neubau", 17.6, "€/m²", 2), ("Veränderung 12 Monate", 4.1, "%", 1),
                                     ("Vermarktungsdauer", 31, "Tage", 0), ("Angebote (12 M.)", 286, "", 0)]:
        neu("angebot", bez, "", "Umkreis 2 km", w, einheit, stellen, an)
    for zi, werte in {"1 Zi.": (31, 36, 14.2, 19.1, 19.1, 20.3, 24.0), "2 Zi.": (104, 58, 13.1, 17.9, 17.8, 18.9, 22.4),
                      "3 Zi.": (92, 79, 12.6, 17.1, 17.0, 18.2, 21.0), "4 Zi.": (43, 99, 12.3, 16.6, 16.5, 17.7, 20.2),
                      "5+ Zi.": (16, 127, 12.5, 16.2, 16.1, 17.3, 19.6)}.items():
        for bez, w in zip(["n", "Ø m²", "Min", "Ø", "Median", "P75", "Max"], werte, strict=True):
            neu("angebot_tabelle", bez, zi, "Umkreis 2 km", w, {"n": "", "Ø m²": "m²"}.get(bez, "€/m²"),
                0 if bez in ("n", "Ø m²") else 2, an)

    neu("weitere", "Einwohner Ortsteil Südhang", "", "", 12840, "Einwohner", 0, "Statistikamt Musterstadt", "manuell")
    for jahr, n in [("2023", 1105), ("2024", 1180), ("2025", 1240)]:
        neu("weitere", "Baufertigstellungen Wohnungen", jahr, "Stadt", n, "Wohnungen", 0, "Statistisches Landesamt",
            "manuell")
    neu("weitere", "Mietspiegel Ø Nettokaltmiete", "", "Stadt", 10.2, "€/m²", 2, "Mietspiegel Musterstadt", "manuell")
    neu("weitere", "Mietspiegel Neubau ab 2020, Mittelwert", "", "Stadt", 13.45, "€/m²", 2, "Mietspiegel Musterstadt",
        "manuell")
    return k


def markt_dateien(ziel: Path) -> None:
    """Schreibt Marktbericht, Angebotsstatistik und Quellen als CSV (UTF-8, Semikolon). Eingabe: Zielordner."""
    felder = ["gruppe", "bezeichnung", "kategorie", "gebiet", "wert", "einheit", "stellen", "herkunft", "quelle"]
    alle = kennzahlen()
    for name, quellen in [("marktbericht_kennzahlen.csv", {"Marktbericht", "Statistikamt Musterstadt",
                                                           "Statistisches Landesamt", "Mietspiegel Musterstadt"}),
                          ("angebotsstatistik.csv", {"Angebotsstatistik"})]:
        puffer = io.StringIO()
        w = csv.DictWriter(puffer, fieldnames=felder, delimiter=";", lineterminator="\n")
        w.writeheader()
        w.writerows({**k, "wert": _de(k["wert"], k["stellen"]).replace(".", "")} for k in alle if k["quelle"] in quellen)
        (ziel / name).write_text(puffer.getvalue(), encoding="utf-8")
    puffer = io.StringIO()
    csv.writer(puffer, delimiter=";", lineterminator="\n").writerows(
        [["name", "art", "datei", "stand", "abgerufen_am"], *QUELLEN])
    (ziel / "quellen.csv").write_text(puffer.getvalue(), encoding="utf-8")


# ---------------------------------------------------------------- Exposés als PDF (ohne Zusatzpaket)

def pdf_schreiben(pfad: Path, seiten: list[list[tuple[int, str]]]) -> None:
    """Schreibt ein einfaches Text-PDF mit Helvetica (WinAnsi, kann €, ² und Umlaute).

    Eingabe: Pfad, Seiten als Liste von Absätzen (Schriftgröße, Text); Größe ≥ 13 wird fett gesetzt.
    Ausgabe: keine. Warum von Hand: das Backend bringt kein PDF-Schreibpaket mit, und ein Text-PDF reicht für
    pdfplumber, Parser und Volltextsuche.
    """
    def zeichen(t: str) -> bytes:
        """PDF-String in WinAnsi. Ausgabe: Bytes mit maskierten Klammern."""
        return t.encode("cp1252").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")

    objekte = [b"<< /Type /Catalog /Pages 2 0 R >>", b"",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"]
    seiten_ids = []
    for nr, absaetze in enumerate(seiten, 1):
        strom, y = [b"BT"], 790
        for groesse, text in absaetze:
            schrift = b"/F2" if groesse >= 13 else b"/F1"
            for zeile in textwrap.wrap(text, int(1000 / groesse)) or [""]:
                strom.append(schrift + b" %d Tf 1 0 0 1 56 %d Tm (" % (groesse, y) + zeichen(zeile) + b") Tj")
                y -= int(groesse * 1.45)
            y -= 8
        strom += [b"/F1 8 Tf 1 0 0 1 56 40 Tm (" + zeichen(f"Synthetische Testdaten – Seite {nr} von {len(seiten)}")
                  + b") Tj", b"ET"]
        inhalt = b"\n".join(strom)
        objekte.append(b"<< /Length %d >>\nstream\n" % len(inhalt) + inhalt + b"\nendstream")
        objekte.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents %d 0 R "
                       b"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> >>" % (len(objekte)))
        seiten_ids.append(len(objekte))
    objekte[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
        b" ".join(b"%d 0 R" % i for i in seiten_ids), len(seiten_ids))
    aus, stellen = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"), []
    for i, obj in enumerate(objekte, 1):
        stellen.append(len(aus))
        aus += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(aus)
    aus += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objekte) + 1)
    aus += b"".join(b"%010d 00000 n \n" % s for s in stellen)
    aus += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objekte) + 1, xref)
    pfad.write_bytes(bytes(aus))


def expose_dateien(ziel: Path) -> None:
    """Drei Exposés zu Comps aus der Importdatei. Eingabe: Zielordner. Ausgabe: keine.

    - Talblick 18: Wohnfläche, Kaltmiete, Zimmer mit Etikett; das Baujahr steht nur im Fließtext (KI ergänzt).
    - Hangweg 11: vier Seiten; Wohnfläche und Zimmer nur im Fließtext, Details für die Volltextsuche.
    - Gartenhof 4: „Miete kalt“ statt „Kaltmiete“ und „Fertigstellung“ statt „Baujahr“ (KI ergänzt beide).
    """
    pdf_schreiben(ziel / "expose_talblick18_dg.pdf", [[
        (16, "3-Zimmer-Dachgeschosswohnung mit Dachterrasse"),
        (10, "Talblick 18, 99998 Musterstadt (Ortsteil Südhang) · Anbieter: Muster Immobilien · Objekt-Nr. T18-DG"),
        (11, "Eckdaten"),
        (10, "Wohnfläche: 88,6 m²"), (10, "Kaltmiete: 1.710,00 €"), (10, "Zimmer: 3"),
        (10, "Nebenkosten: 260,00 € · Heizkosten in den Nebenkosten enthalten · Kaution: drei Nettokaltmieten"),
        (10, "Bezugsfrei: ab sofort · Etage: 4. OG (Dachgeschoss) von 4"),
        (11, "Objektbeschreibung"),
        (10, ("Das Gebäude wurde im Frühjahr 2025 fertiggestellt und liegt in ruhiger Hanglage mit Blick über das Tal. "
             "Die Wohnung erstreckt sich über das gesamte Dachgeschoss des Hauses B. Wohnen, Essen und Kochen gehen in "
             "einem offenen Raum ineinander über, von dem aus die nach Süden ausgerichtete Dachterrasse mit rund 18 "
             "Quadratmetern erreichbar ist. Beide Schlafräume liegen ruhig zur Gartenseite.")),
        (11, "Ausstattung"),
        (10, ("Einbauküche mit Markengeräten, Fußbodenheizung, bodentiefe Fenster mit elektrischen Rollläden, "
             "Aufzug bis ins Dachgeschoss, Kellerabteil, Tiefgarage (Stellplatz 95,00 € im Monat).")),
    ]])

    pdf_schreiben(ziel / "expose_hangweg11_mehrseitig.pdf", [
        [(16, "Neubau am Hangweg 11 – helle Wohnung im 2. Obergeschoss"),
         (10, "Hangweg 11, 99998 Musterstadt · Anbieter: Musterbau Süd · Objekt-Nr. HW11-2.3"),
         (11, "Auf einen Blick"),
         (10, "Kaltmiete: 1.300,00 € zzgl. Nebenkosten · Bezugsfrei ab 01.02.2027"),
         (11, "Beschreibung"),
         (10, ("Auf rund 76,9 Quadratmetern verteilen sich 3 Räume, dazu eine offene Küche, ein Tageslichtbad mit "
              "Dusche und Wanne sowie ein Gäste-WC. Der Wohnbereich öffnet sich zur Loggia mit Blick in den "
              "begrünten Innenhof. Das Haus hat 18 Wohnungen auf vier Geschossen.")),
         (10, ("Die Wohnanlage Hangweg besteht aus drei Häusern mit insgesamt 41 Wohnungen und einem gemeinsamen "
              "Innenhof mit Spielfläche. Die Hausverwaltung sitzt vor Ort."))],
        [(14, "Ausstattung im Detail"),
         (10, "Böden: Eichenparkett in allen Wohnräumen, Feinsteinzeug in Bad und Flur."),
         (10, ("Heizung: Fußbodenheizung mit Einzelraumregelung, Wärme aus einer Luft-Wasser-Wärmepumpe mit "
              "Photovoltaik auf dem Dach.")),
         (10, ("Küche: Eine Einbauküche ist nicht enthalten; Anschlüsse für Herd, Spülmaschine und Dunstabzug sind "
              "vorhanden. Gegen Aufpreis kann eine Küche des Bauträgers für 85,00 € im Monat gemietet werden.")),
         (10, "Bad: bodengleiche Dusche, Badewanne, Handtuchheizkörper, Waschmaschinenanschluss im Bad."),
         (10, "Fenster: dreifach verglast, elektrische Rollläden, Insektenschutz im Schlafraum."),
         (10, "Technik: Glasfaseranschluss bis in die Wohnung, Video-Gegensprechanlage, Rauchwarnmelder."),
         (10, ("Haus: Aufzug in alle Geschosse, barrierefreier Zugang von der Straße, Fahrradraum mit Lademöglichkeit "
              "für E-Bikes, Kellerabteil mit rund 6 Quadratmetern."))],
        [(14, "Energie und Kosten"),
         (10, ("Baujahr: 2026 · Energieausweis: Bedarfsausweis, Endenergiebedarf 28 kWh/(m²·a), Effizienzklasse A+, "
              "Energieträger Strom (Wärmepumpe).")),
         (10, "Nebenkosten-Vorauszahlung: 245,00 € im Monat, Heizung und Warmwasser enthalten."),
         (10, "Kaution: drei Nettokaltmieten. Mietvertrag unbefristet, Indexmiete nach dem Verbraucherpreisindex."),
         (10, ("Stellplatz in der Tiefgarage: 90,00 € im Monat, davon vier Plätze mit Wallbox (11 kW) für 120,00 € im "
              "Monat. Besucherstellplätze vor dem Haus."))],
        [(14, "Lage und Hausordnung"),
         (10, ("Der Ortsteil Südhang liegt am südlichen Stadtrand von Musterstadt. Bis zur Haltestelle der Buslinie 7 "
              "sind es rund 250 Meter, die Straßenbahn am Talplatz ist in 9 Minuten zu Fuß erreichbar. Eine "
              "Grundschule und zwei Kitas liegen im Umkreis von einem Kilometer, ein Supermarkt und eine Bäckerei "
              "befinden sich am Talplatz.")),
         (10, "Haustiere: Kleintiere sind erlaubt, Hunde und Katzen nach Absprache mit der Hausverwaltung."),
         (10, "Besichtigungen finden samstags statt. Anfragen bitte nur über das Kontaktformular.")],
    ])

    pdf_schreiben(ziel / "expose_gartenhof4_eg.pdf", [[
        (16, "2-Zimmer-Gartenwohnung im Erdgeschoss"),
        (10, "Gartenhof 4, 99998 Musterstadt · Anbieter: Beispiel Wohnbau"),
        (10, "Wohnfläche ca. 64,8 m² · Miete kalt: 1.180 € · Nebenkosten 210 € · frei ab 01.12.2026"),
        (11, "Das Haus"),
        (10, ("Der Gartenhof wurde mit der Fertigstellung 2026 als kleines Mehrfamilienhaus mit neun Wohnungen "
             "errichtet. Die Wohnung liegt im Erdgeschoss und hat einen eigenen Garten von etwa 80 Quadratmetern mit "
             "Terrasse.")),
        (11, "Ausstattung"),
        (10, ("Einbauküche, Fußbodenheizung, bodengleiche Dusche, Abstellraum in der Wohnung, Fahrradstellplatz im "
             "Hof. Ein Stellplatz kann für 60 € im Monat dazugemietet werden.")),
    ]])


# ---------------------------------------------------------------- Bilder für den Vision-Agenten

SAND, STEIN, TINTE, TERRAKOTTA = "#f3efe6", "#8c877d", "#1a1a19", "#b5643c"


def _schrift(groesse: int, fett: bool = False) -> ImageFont.FreeTypeFont:
    """Eine Schrift mit €, ² und Umlauten. Eingabe: Größe, fett. Ausgabe: Pillow-Schrift.

    Reihenfolge: Hanken Grotesk aus dem Frontend (wie in der App), dann Arial (macOS) und DejaVu Sans (Linux).
    Die Bitmap-Standardschrift von Pillow kann weder € noch ² und wird deshalb nie genommen.
    """
    gewicht = "700" if fett else "400"
    kandidaten = [REPO / f"frontend/node_modules/@fontsource/hanken-grotesk/files/hanken-grotesk-latin-{gewicht}-normal.woff",
                  Path("/System/Library/Fonts/Supplemental/" + ("Arial Bold.ttf" if fett else "Arial.ttf")),
                  Path("/Library/Fonts/Arial.ttf"),
                  Path("/usr/share/fonts/truetype/dejavu/" + ("DejaVuSans-Bold.ttf" if fett else "DejaVuSans.ttf"))]
    for pfad in kandidaten:
        if pfad.exists():
            return ImageFont.truetype(str(pfad), groesse)
    sys.exit("Keine Schrift mit € und ² gefunden: erst ./start.sh oder `cd frontend && npm install` ausführen.")


def tabelle_bild(pfad: Path) -> None:
    """Tabelle im Stil eines Marktberichts als PNG (1400 × 900 px). Eingabe: Pfad. Ausgabe: keine."""
    zeilen = [("Median Angebotsmiete", "16,40 €/m²", "15,80 €/m²"),
              ("Unteres Quartil", "14,90 €/m²", "14,10 €/m²"),
              ("Oberes Quartil", "18,10 €/m²", "17,60 €/m²"),
              ("Leerstandsquote", "1,6 %", "2,3 %"),
              ("Einwohner", "12.840", "204.300"),
              ("Baufertigstellungen 2025", "–", "1.240 Wohnungen"),
              ("Ø Wohnungsgröße Angebote", "71 m²", "68 m²"),
              ("Mietspiegel Ø Nettokaltmiete (Stand 01.04.2026)", "–", "10,20 €/m²")]
    bild = Image.new("RGB", (1400, 900), "white")
    d = ImageDraw.Draw(bild)
    d.text((60, 50), "Marktbericht Musterstadt – Mietkennzahlen Wohnen", font=_schrift(40, True), fill=TINTE)
    d.text((60, 110), "Ortsteil Südhang (PLZ 99998) im Vergleich zur Gesamtstadt · Stand Q3/2026",
           font=_schrift(24), fill=STEIN)
    spalten, y = [60, 860, 1130], 190
    d.rectangle((40, y - 12, 1360, y + 48), fill=SAND)
    for x, t in zip(spalten, ["Kennzahl", "PLZ 99998", "Stadt"], strict=True):
        d.text((x, y), t, font=_schrift(26, True), fill=TINTE)
    for i, zeile in enumerate(zeilen):
        y = 260 + i * 70
        d.line((40, y - 12, 1360, y - 12), fill="#e3e0d8", width=2)
        for x, t in zip(spalten, zeile, strict=True):
            d.text((x, y), t, font=_schrift(26), fill=TINTE)
    d.text((60, 840), "Synthetische Testdaten, keine echten Marktwerte.", font=_schrift(20), fill=STEIN)
    bild.save(pfad, optimize=True)


def diagramm_bild(pfad: Path) -> None:
    """Balkendiagramm Angebotsmieten nach Zimmerzahl als PNG (1400 × 900 px), Werte an den Balken.

    Eingabe: Pfad. Ausgabe: keine. Farben aus der App-Palette (Terrakotta, Stein), kein Blau.
    """
    werte = [("1 Zi.", 19.10), ("2 Zi.", 17.80), ("3 Zi.", 17.00), ("4 Zi.", 16.50), ("5+ Zi.", 16.10)]
    bild = Image.new("RGB", (1400, 900), "white")
    d = ImageDraw.Draw(bild)
    d.text((60, 40), "Angebotsstatistik: Neubau-Angebotsmieten nach Zimmerzahl", font=_schrift(38, True), fill=TINTE)
    d.text((60, 98), "Median in €/m² nettokalt, Umkreis 2 km um PLZ 99998, Q3/2026 (n = 286)",
           font=_schrift(24), fill=STEIN)
    links, unten, oben, hoechst = 160, 790, 180, 22.0
    for stufe in range(0, 23, 2):
        y = unten - (unten - oben) * stufe / hoechst
        d.line((links, y, 1340, y), fill="#e3e0d8", width=1)
        d.text((links - 20, y), f"{stufe}", font=_schrift(20), fill=STEIN, anchor="rm")
    d.text((60, oben - 40), "€/m²", font=_schrift(22), fill=STEIN)
    breite = 150
    for i, (zi, w) in enumerate(werte):
        x = links + 60 + i * 230
        y = unten - (unten - oben) * w / hoechst
        d.rectangle((x, y, x + breite, unten), fill=TERRAKOTTA)
        d.text((x + breite / 2, y - 12), _de(w), font=_schrift(28, True), fill=TINTE, anchor="ms")
        d.text((x + breite / 2, unten + 40), zi, font=_schrift(26), fill=TINTE, anchor="ms")
    d.line((links, unten, 1340, unten), fill=TINTE, width=2)
    d.text((60, 860), "Synthetische Testdaten, keine echten Marktwerte.", font=_schrift(20), fill=STEIN)
    bild.save(pfad, optimize=True)


# ---------------------------------------------------------------- Text für die Volltextsuche (RAG)

PROJEKTBESCHREIBUNG = """\
Projektbeschreibung Testquartier Südhang, Musterstadt
Stand: 18.11.2026 · interne Arbeitsunterlage (synthetisch)

1. Überblick
Das Testquartier Südhang entsteht auf einem ehemaligen Gärtnereigelände am Hangweg im Süden von Musterstadt (PLZ 99998).
Geplant sind 36 Mietwohnungen in zwei Häusern mit je vier Geschossen sowie eine Kita mit drei Gruppen im Erdgeschoss
von Haus A. Baubeginn war im März 2026, die Fertigstellung ist für Juli 2027 vorgesehen, der Vermarktungsstart für den
01.09.2027.

2. Wohnungsmix
Erdgeschoss: 6 Zwei-Zimmer-Wohnungen mit rund 63 m² und eigenem Garten.
Regelgeschosse: 14 Zwei-Zimmer-Wohnungen mit rund 58,5 m² und 10 Drei-Zimmer-Wohnungen mit rund 78 m², alle mit Balkon.
Dachgeschoss: 4 Drei-Zimmer-Wohnungen mit rund 86,5 m² und 2 Vier-Zimmer-Wohnungen mit rund 102 m², jeweils mit
Dachterrasse.

3. Ausstattung
Alle Wohnungen erhalten Eichenparkett, Fußbodenheizung, bodengleiche Duschen und elektrische Rollläden. Eine Einbauküche
ist nur in den Dachgeschosswohnungen enthalten. Die Häuser haben Aufzüge, Kellerabteile und einen gemeinsamen
Fahrradraum für 80 Räder. In der Tiefgarage entstehen 24 Stellplätze, davon 8 mit Wallbox.

4. Energie und Technik
Wärme liefert eine Sole-Wasser-Wärmepumpe mit Erdsonden, ergänzt um Photovoltaik auf beiden Dächern mit zusammen 62 kWp.
Angestrebt ist der Effizienzhaus-Standard 40. Jede Wohnung erhält einen Glasfaseranschluss.

5. Lage und Mobilität
Die Bushaltestelle Hangweg (Linie 7) liegt rund 200 Meter entfernt, die Straßenbahn am Talplatz etwa 700 Meter.
Grundschule, zwei Kitas, ein Supermarkt und eine Arztpraxis liegen im Umkreis von einem Kilometer. Für Bewohner ist
ein Carsharing-Stellplatz mit zwei Fahrzeugen vorgesehen.

6. Zielgruppe und Vermarktung
Zielgruppe sind Paare und kleine Familien sowie Berufspendler. Die Vermarktung soll über Exposés, die eigene Website
und eine Infoveranstaltung vor Ort laufen. Haustiere sind nach Absprache erlaubt. Die Mieten sollen als Indexmiete
vereinbart werden.

7. Offene Punkte
Die Höhe der Stellplatzmiete (geplant 90 bis 120 € im Monat) und die Betriebskosten-Vorauszahlung (geschätzt
2,90 €/m²) sind noch abzustimmen. Ob die Kita einen eigenen Außenbereich erhält, entscheidet die Stadt im Frühjahr 2027.
"""


# ---------------------------------------------------------------- Fehlerfälle des Uploads

def fehler_dateien(ziel: Path) -> None:
    """Dateien, die der Upload abweisen muss. Eingabe: Zielordner. Ausgabe: keine.

    getarnt_tabelle.pdf → 415 (Binärdaten mit Endung .pdf), kaputt.pdf und kaputt_bild.png → 422 (richtiger Kopf,
    unlesbarer Inhalt), bild_zu_breit.png → 422 (über 8000 px), zu_gross.pdf → 413 (über 10 MB),
    bild_zu_gross.png → 413 (über 5 MB). Die beiden großen Dateien stehen in .gitignore.
    """
    zufall = random.Random(2026)
    (ziel / "getarnt_tabelle.pdf").write_bytes(b"PK\x03\x04\x14\x00\x00\x00" + zufall.randbytes(2048))
    (ziel / "kaputt.pdf").write_bytes(b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R\n"
                                      + b"Hier bricht die Datei mitten im Objekt ab ..." * 20)
    (ziel / "kaputt_bild.png").write_bytes(b"\x89PNG\r\n\x1a\n" + zufall.randbytes(4096))
    Image.new("RGB", (8200, 40), SAND).save(ziel / "bild_zu_breit.png")
    # 11 MB: Kopf eines PDFs, danach PDF-Kommentarzeilen
    zeile = b"% Fuelltext fuer den Groessentest " + b"x" * 60 + b"\n"
    (ziel / "zu_gross.pdf").write_bytes(b"%PDF-1.4\n" + zeile * (11 * 1024 * 1024 // len(zeile)))
    # Rauschen lässt sich nicht komprimieren: 1500 × 1300 px RGB ergibt knapp 6 MB
    Image.frombytes("RGB", (1500, 1300), zufall.randbytes(1500 * 1300 * 3)).save(ziel / "bild_zu_gross.png")


def erzeugen() -> None:
    """Schreibt alle Testdateien neu. Eingabe: keine. Ausgabe: keine (Liste der Dateien auf der Konsole)."""
    ordner = {n: ORDNER / n for n in ("comps", "markt", "unterlagen", "fehlerfaelle")}
    for o in ordner.values():
        o.mkdir(exist_ok=True)
    comps_dateien(ordner["comps"])
    markt_dateien(ordner["markt"])
    expose_dateien(ordner["unterlagen"])
    tabelle_bild(ordner["unterlagen"] / "marktbericht_tabelle.png")
    diagramm_bild(ordner["unterlagen"] / "angebotsmieten_balkendiagramm.png")
    (ordner["unterlagen"] / "projektbeschreibung_suedhang.txt").write_text(PROJEKTBESCHREIBUNG, encoding="utf-8")
    fehler_dateien(ordner["fehlerfaelle"])
    for o in ordner.values():
        for d in sorted(o.iterdir()):
            print(f"{d.relative_to(ORDNER)}  ({d.stat().st_size / 1024:,.0f} KB)")


# ---------------------------------------------------------------- Testprojekt in die Datenbank laden

def laden(demo: bool) -> None:
    """Legt das Testprojekt „Südhang“ mit Comps (über lese_comps aus der XLSX), Kennzahlen, Quellen und Wohnungsmix
    an. Eingabe: demo (True: wie der Demo-Datensatz, Agenten sehen die Import-Daten; False: wie eine eigene Adresse,
    Import-Daten gehen nur mit KI_PORTALDATEN_SENDEN=true an die KI). Ausgabe: keine.

    Warum ein eigenes Projekt: Die App hat noch keinen Import-Endpunkt für Comps; so lassen sich Import, Prüfungen
    und Kennzahlen trotzdem in der Oberfläche durchklicken. Ein erneuter Demo-Seed löscht das Projekt wieder.
    """
    sys.path.insert(0, str(REPO / "backend"))
    from mietmarkt.db import engine
    from mietmarkt.importe import lese_comps
    from mietmarkt.modelle import Comp, Herkunft, Marktkennzahl, Projekt, Quelle, Wohnung
    from sqlmodel import Session, select

    xlsx = ORDNER / "comps" / "comps_suedhang.xlsx"
    if not xlsx.exists():
        erzeugen()
    ergebnis = lese_comps(xlsx.read_bytes(), xlsx.name, ZUORDNUNG)
    for f in ergebnis.fehler:
        print(f"Importfehler Zeile {f.zeile}, {f.spalte}: {f.meldung}")
    with Session(engine()) as s:
        if vorhanden := s.exec(select(Projekt).where(Projekt.name == PROJEKTNAME)).first():
            sys.exit(f"„{PROJEKTNAME}“ ist schon geladen: http://localhost:5173/analyse/{vorhanden.id}")
        p = Projekt(name=PROJEKTNAME, adresse="Hangweg 20", plz="99998", ort="Musterstadt", ortsteil="Südhang",
                    lat=ZENTRUM[0], lon=ZENTRUM[1], stichtag=STICHTAG, analysiert_am=STICHTAG,
                    vermarktungsstart=dt.date(2027, 9, 1), mietwachstum_pa=0.02, demo=demo)
        s.add(p)
        s.flush()
        quelle_id = {}
        for name, art, datei, stand, abgerufen in QUELLEN:
            q = Quelle(projekt_id=p.id, name=name, art=art, datei=datei or None, stand=stand,
                       abgerufen_am=dt.date.fromisoformat(abgerufen))
            s.add(q)
            s.flush()
            quelle_id[name] = q.id
        for nr, z in enumerate(ergebnis.zeilen, 1):
            s.add(Comp(projekt_id=p.id, nr=nr, **z.model_dump(exclude={"zeile"}), herkunft=Herkunft.IMPORT,
                       quelle_id=quelle_id["Portal-Exposés"], fundstelle=f"{xlsx.name}, Zeile {z.zeile}"))
        for k in kennzahlen():
            s.add(Marktkennzahl(projekt_id=p.id, quelle_id=quelle_id[k["quelle"]],
                                **{x: v for x, v in k.items() if x != "quelle"}))
        for typ, zimmer, flaeche, anzahl in WOHNUNGSMIX:
            s.add(Wohnung(projekt_id=p.id, typ=typ, zimmer=zimmer, wohnflaeche=flaeche, anzahl=anzahl))
        s.commit()
        print(f"{PROJEKTNAME} geladen ({len(ergebnis.zeilen)} Comps, demo={demo}): "
              f"http://localhost:5173/analyse/{p.id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synthetische Testdaten erzeugen oder als Testprojekt laden")
    parser.add_argument("befehl", nargs="?", default="erzeugen", choices=["erzeugen", "laden"])
    parser.add_argument("--eigenes-projekt", action="store_true",
                        help="beim Laden als Nicht-Demo-Projekt anlegen (prüft die Sperre für Portal-Daten)")
    a = parser.parse_args()
    laden(demo=not a.eigenes_projekt) if a.befehl == "laden" else erzeugen()
