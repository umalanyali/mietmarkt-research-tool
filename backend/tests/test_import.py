"""Import von Comps aus CSV und XLSX: Spaltenzuordnung, deutsche Zahlen, Windows-1252, zeilengenaue Fehler."""
import datetime as dt
import io

import openpyxl
import pytest

from mietmarkt.importe import lese_comps

# Spalten wie in einem selbst gepflegten Export; die Zuordnung übersetzt sie auf die Felder des Datenmodells
ZUORDNUNG = {"Adresse": "objekt", "Anbieter": "anbieter", "Lage": "typ", "Zi.": "zimmer", "Bj.": "baujahr",
             "Wfl. m²": "wohnflaeche", "Kaltmiete €": "kaltmiete", "EBK": "ebk", "Online seit": "online_seit",
             "Anfragen": "anfragen"}
KOPF = "Adresse;Anbieter;Lage;Zi.;Bj.;Wfl. m²;Kaltmiete €;EBK;Online seit;Anfragen"


def csv(*zeilen: str, encoding: str = "utf-8") -> bytes:
    """Baut eine CSV-Datei mit Kopfzeile. Eingabe: Datenzeilen, Kodierung. Ausgabe: Bytes."""
    return "\n".join([KOPF, *zeilen]).encode(encoding)


def test_gueltige_zeilen_mit_deutschen_zahlen():
    """„1.012,50“ und „58,4“ werden als Zahlen gelesen, „ja“ als wahr, Datum im Format TT.MM.JJJJ."""
    e = lese_comps(csv("Lindenhof 4;Beispiel Wohnbau;Regel;2;2025;58,4;1.012,50;ja;01.10.2026;41"), "comps.csv", ZUORDNUNG)
    assert e.fehler == []
    z = e.zeilen[0]
    assert (z.wohnflaeche, z.kaltmiete, z.ebk, z.online_seit) == (58.4, 1012.5, True, dt.date(2026, 10, 1))


def test_windows_1252_wird_erkannt():
    """Umlaute aus einem Excel-CSV (Windows-1252) kommen korrekt an."""
    e = lese_comps(csv("Mühlgraben 12;Muster Immobilien;DG;3;2025;86;1720;nein;;9", encoding="cp1252"), "c.csv", ZUORDNUNG)
    assert e.zeilen[0].objekt == "Mühlgraben 12"


def test_fehler_werden_zeilengenau_gemeldet():
    """Die Kopfzeile ist Zeile 1; Fehler nennen Zeile, Spalte und Grund, gültige Zeilen bleiben erhalten."""
    e = lese_comps(csv("A 1;X;Regel;2;2025;60;900;ja;;5",
                       "B 2;X;Keller;2;2025;60;900;ja;;5",
                       "C 3;X;Regel;2;2025;abc;;ja;;5"), "c.csv", ZUORDNUNG)
    assert [z.objekt for z in e.zeilen] == ["A 1"]
    gemeldet = {(f.zeile, f.spalte) for f in e.fehler}
    assert (3, "Lage") in gemeldet
    assert (4, "Wfl. m²") in gemeldet and (4, "Kaltmiete €") in gemeldet


def test_fehlende_pflichtspalte_im_kopf():
    """Fehlt eine zugeordnete Spalte, kommt ein Fehler zu Zeile 1 und keine Zeile wird übernommen."""
    daten = b"Adresse;Lage\nA 1;Regel"
    e = lese_comps(daten, "c.csv", ZUORDNUNG)
    assert e.zeilen == [] and e.fehler[0].zeile == 1 and "Kaltmiete €" in e.fehler[0].meldung


def test_leere_zeilen_werden_uebersprungen():
    """Leerzeilen am Ende erzeugen weder Comps noch Fehler."""
    e = lese_comps(csv("A 1;X;EG;2;2025;60;900;ja;;5", ";;;;;;;;;", ""), "c.csv", ZUORDNUNG)
    assert len(e.zeilen) == 1 and e.fehler == []


def test_xlsx_mit_echten_zahlen_und_datum():
    """In XLSX liegen Zahlen und Datum bereits typisiert vor; das Ergebnis ist dasselbe wie bei CSV."""
    mappe = openpyxl.Workbook()
    blatt = mappe.active
    blatt.append(KOPF.split(";"))
    blatt.append(["Hafenkante 2", "Musterstadt Living", "Regel", 2, 2026, 63.8, 1148, "ja", dt.datetime(2026, 10, 26), 8])
    blatt.append(["Feldrain 9", "Muster Immobilien", "Regel", 4, 2025, None, 1625, "ja", None, 7])
    puffer = io.BytesIO()
    mappe.save(puffer)
    e = lese_comps(puffer.getvalue(), "comps.xlsx", ZUORDNUNG)
    assert e.zeilen[0].online_seit == dt.date(2026, 10, 26)
    assert [(f.zeile, f.spalte) for f in e.fehler] == [(3, "Wfl. m²")]


def test_unbekanntes_dateiformat():
    """Nur CSV und XLSX werden angenommen."""
    with pytest.raises(ValueError):
        lese_comps(b"", "comps.pdf", ZUORDNUNG)


def test_koordinaten_mit_drei_nachkommastellen_sind_keine_tausender():
    """„51.312“ in der Spalte Breite ist eine Koordinate, kein Tausenderpunkt (Befund python-reviewer)."""
    daten = b"Objekt;Lage;Zi.;Wfl.;Kalt;Lat;Lon\nA 1;Regel;2;60;900;51.312;9.485\n"
    e = lese_comps(daten, "c.csv", {"Objekt": "objekt", "Lage": "typ", "Zi.": "zimmer", "Wfl.": "wohnflaeche",
                                    "Kalt": "kaltmiete", "Lat": "lat", "Lon": "lon"})
    assert e.fehler == [] and (e.zeilen[0].lat, e.zeilen[0].lon) == (51.312, 9.485)


def test_koordinaten_ausserhalb_des_gueltigen_bereichs():
    """Breite über 90° ist ein Fehler, kein stiller Import."""
    daten = b"Objekt;Lage;Zi.;Wfl.;Kalt;Lat\nA 1;Regel;2;60;900;151,3\n"
    e = lese_comps(daten, "c.csv", {"Objekt": "objekt", "Lage": "typ", "Zi.": "zimmer", "Wfl.": "wohnflaeche",
                                    "Kalt": "kaltmiete", "Lat": "lat"})
    assert [(f.zeile, f.spalte) for f in e.fehler] == [(2, "Lat")]


@pytest.mark.parametrize("daten", [b"\n" + KOPF.encode() + b"\nA 1;X;Regel;2;2025;60;900;ja;;5\n", b"Adresse\nA 1\n"])
def test_ungewoehnlicher_dateianfang_ist_meldung_statt_absturz(daten):
    """Leerzeile vor dem Kopf oder einspaltiger Kopf: Meldung statt Ausnahme."""
    e = lese_comps(daten, "c.csv", ZUORDNUNG)
    assert e.zeilen or e.fehler


def test_nicht_dekodierbare_bytes_sind_meldung_statt_absturz():
    """Bytes, die weder UTF-8 noch Windows-1252 sind, brechen den Import nicht ab."""
    e = lese_comps(KOPF.encode() + b"\nA\x81 1;X;Regel;2;2025;60;900;ja;;5\n", "c.csv", ZUORDNUNG)
    assert e.zeilen or e.fehler


def test_unendlich_ist_keine_flaeche():
    """„inf“ als Wohnfläche wird als ungültig gemeldet."""
    e = lese_comps(csv("A 1;X;Regel;2;2025;inf;900;ja;;5"), "c.csv", ZUORDNUNG)
    assert [(f.zeile, f.spalte) for f in e.fehler] == [(2, "Wfl. m²")]


def test_geschuetztes_leerzeichen_als_tausendertrenner():
    """„1 012,50“ mit geschütztem Leerzeichen (deutsches Excel/LibreOffice) wird gelesen."""
    e = lese_comps(csv("A 1;X;Regel;2;2025;60;1 012,50;ja;;5"), "c.csv", ZUORDNUNG)
    assert e.zeilen[0].kaltmiete == 1012.5


def test_deutsche_meldung_bei_kommazahl_fuer_anfragen():
    """Anfragen „12,5“ ist keine ganze Zahl; die Meldung ist deutsch."""
    e = lese_comps(csv("A 1;X;Regel;2;2025;60;900;ja;;12,5"), "c.csv", ZUORDNUNG)
    assert e.fehler[0].spalte == "Anfragen" and "ganze Zahl" in e.fehler[0].meldung


def test_zeilennummer_bleibt_fuer_die_fundstelle_erhalten():
    """Jede gültige Zeile kennt ihre Zeilennummer, damit die Herkunft „Zeile n“ speicherbar ist."""
    e = lese_comps(csv("A 1;X;Regel;2;2025;60;900;ja;;5", "B 2;X;EG;2;2025;60;900;ja;;5"), "c.csv", ZUORDNUNG)
    assert [z.zeile for z in e.zeilen] == [2, 3]
