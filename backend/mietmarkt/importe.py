"""Import von Vergleichsangeboten aus CSV oder XLSX: Spaltenzuordnung, Prüfung je Zeile (pydantic),
deutsche Zahlenformate und Windows-1252. Fehler werden mit Zeile und Spalte gemeldet, gültige Zeilen bleiben erhalten."""
import csv
import datetime as dt
import io
import math
import re
from typing import Literal

import openpyxl
from pydantic import BaseModel, Field, ValidationError

ZAHLENFELDER = {"zimmer", "baujahr", "wohnflaeche", "kaltmiete", "anfragen"}
KOORDINATEN = {"lat", "lon"}
MELDUNGEN = {
    "int_from_float": "muss eine ganze Zahl sein",
    "less_than": "ist zu groß",
    "missing": "Pflichtangabe fehlt",
    "greater_than": "muss größer als 0 sein",
    "greater_than_equal": "darf nicht negativ sein",
    "less_than_equal": "ist zu groß",
    "literal_error": "erlaubt sind Regel, EG oder DG",
    "string_too_short": "darf nicht leer sein",
}


class CompZeile(BaseModel):
    """Eine geprüfte Zeile, bereit zum Speichern als Comp."""

    zeile: int  # Zeilennummer in der Datei, für die Fundstelle („Zeile 4“)
    objekt: str = Field(min_length=1)
    anbieter: str = ""
    typ: Literal["Regel", "EG", "DG"]
    zimmer: float = Field(gt=0)
    baujahr: int | None = Field(default=None, ge=1800, le=2100)
    wohnflaeche: float = Field(gt=0)
    kaltmiete: float = Field(gt=0)
    ebk: bool = False
    online_seit: dt.date | None = None
    anfragen: int | None = Field(default=None, ge=0)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


class Zeilenfehler(BaseModel):
    """Ein Fehler in der Datei. Zeile wie in Excel gezählt (Kopfzeile = 1)."""

    zeile: int
    spalte: str | None
    meldung: str


class ImportErgebnis(BaseModel):
    """Gültige Zeilen und alle Fehler."""

    zeilen: list[CompZeile]
    fehler: list[Zeilenfehler]


def _zahl(roh: object, tausender: bool = True) -> float:
    """Liest Zahlen wie „1.012,50“, „1 012,50“, „58,4“ oder 58.4.

    Eingabe: Zellwert; tausender=False für Koordinaten, bei denen „51.312“ eine Dezimalzahl ist.
    Ausgabe: endliche Zahl oder ValueError („inf“ und „nan“ gelten nicht).
    """
    if isinstance(roh, (int, float)):
        zahl = float(roh)
    else:
        # auch geschützte Leerzeichen, wie sie deutsches Excel/LibreOffice als Tausendertrenner schreibt
        text = re.sub(r"[\s\u00a0\u202f]", "", str(roh))
        if "," in text:
            text = (text.replace(".", "") if tausender else text).replace(",", ".")
        elif tausender and re.fullmatch(r"\d{1,3}(\.\d{3})+", text):  # „1.012“ ist ein Tausenderpunkt
            text = text.replace(".", "")
        zahl = float(text)
    if not math.isfinite(zahl):
        raise ValueError(roh)
    return zahl


def _datum(roh: object) -> dt.date:
    """Liest TT.MM.JJJJ, JJJJ-MM-TT oder Excel-Datumswerte. Eingabe: Zellwert. Ausgabe: date oder ValueError."""
    if isinstance(roh, dt.datetime):
        return roh.date()
    if isinstance(roh, dt.date):
        return roh
    text = str(roh).strip()
    for muster in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text, muster).date()
        except ValueError:
            pass
    raise ValueError(text)


def _wahr(roh: object) -> bool:
    """Liest ja/nein, x, 1/0, true/false. Eingabe: Zellwert. Ausgabe: bool oder ValueError."""
    text = str(roh).strip().lower()
    if text in ("ja", "j", "x", "1", "true", "wahr"):
        return True
    if text in ("nein", "n", "0", "false", "falsch", "-", "–"):
        return False
    raise ValueError(text)


def _tabelle(daten: bytes, dateiname: str) -> list[list[object]]:
    """Liest alle Zeilen der Datei als Listen. Eingabe: Bytes, Dateiname (Endung). Ausgabe: Zeilen inkl. Kopf."""
    endung = dateiname.lower().rsplit(".", 1)[-1]
    if endung == "xlsx":
        blatt = openpyxl.load_workbook(io.BytesIO(daten), read_only=True, data_only=True).active
        return [list(z) for z in blatt.iter_rows(values_only=True)]
    if endung == "csv":
        # Excel speichert CSV unter Windows oft als Windows-1252; UTF-8 (auch mit BOM) hat Vorrang
        try:
            text = daten.decode("utf-8-sig")
        except UnicodeDecodeError:
            # einzelne in Windows-1252 unbelegte Bytes als Ersatzzeichen statt Abbruch
            text = daten.decode("cp1252", errors="replace")
        erste = next((z for z in text.splitlines() if z.strip()), "")
        try:
            trenner = csv.Sniffer().sniff(erste, delimiters=";,\t").delimiter
        except csv.Error:  # z. B. nur eine Spalte: dann ist der Trenner egal
            trenner = ";"
        return list(csv.reader(io.StringIO(text), delimiter=trenner))
    raise ValueError(f"Dateiformat .{endung} wird nicht unterstützt (nur CSV oder XLSX)")


def _leer(wert: object) -> bool:
    """Ist die Zelle leer? Eingabe: Zellwert. Ausgabe: bool."""
    return wert is None or str(wert).strip() == ""


def lese_comps(daten: bytes, dateiname: str, zuordnung: dict[str, str]) -> ImportErgebnis:
    """Liest Comps aus einer Datei.

    Eingabe: Dateiinhalt, Dateiname (bestimmt CSV/XLSX), Zuordnung „Spalte in der Datei → Feld im Datenmodell“.
    Ausgabe: ImportErgebnis mit gültigen Zeilen und zeilengenauen Fehlern.
    """
    zeilen = _tabelle(daten, dateiname)
    # Kopf ist die erste nicht leere Zeile; Zeilennummern bleiben die der Datei
    k = next((i for i, z in enumerate(zeilen) if any(not _leer(w) for w in z)), None)
    if k is None:
        return ImportErgebnis(zeilen=[], fehler=[Zeilenfehler(zeile=1, spalte=None, meldung="Datei ist leer")])
    kopf = [str(w).strip() if w is not None else "" for w in zeilen[k]]
    fehlend = [s for s in zuordnung if s not in kopf]
    if fehlend:
        return ImportErgebnis(zeilen=[], fehler=[Zeilenfehler(zeile=k + 1, spalte=None,
                                                             meldung=f"Spalten fehlen im Kopf: {', '.join(fehlend)}")])
    position = {spalte: kopf.index(spalte) for spalte in zuordnung}
    spalte_zu = {feld: spalte for spalte, feld in zuordnung.items()}
    umwandeln = {"online_seit": _datum, "ebk": _wahr, **{f: _zahl for f in ZAHLENFELDER},
                 **{f: (lambda r: _zahl(r, tausender=False)) for f in KOORDINATEN}}

    gueltig, fehler = [], []
    for nr, zeile in enumerate(zeilen[k + 1:], start=k + 2):
        zellen = {spalte: zeile[i] if i < len(zeile) else None for spalte, i in position.items()}
        if all(_leer(w) for w in zellen.values()):
            continue
        felder, zeilenfehler = {}, []
        for spalte, roh in zellen.items():
            feld = zuordnung[spalte]
            if _leer(roh):
                continue  # fehlende Pflichtangaben meldet anschließend die Prüfung
            try:
                felder[feld] = umwandeln[feld](roh) if feld in umwandeln else str(roh).strip()
            except ValueError:
                zeilenfehler.append(Zeilenfehler(zeile=nr, spalte=spalte, meldung=f"„{roh}“ ist kein gültiger Wert"))
        # Immer prüfen, auch nach Umwandlungsfehlern: so werden „abc“ und eine fehlende Pflichtangabe gemeinsam gemeldet.
        # Felder, die schon an der Umwandlung scheiterten, nicht noch einmal als „fehlt“ melden.
        try:
            geprueft = CompZeile(**felder, zeile=nr)
        except ValidationError as e:
            schon = {z.spalte for z in zeilenfehler}
            for f in e.errors():
                spalte = spalte_zu.get(str(f["loc"][0]), str(f["loc"][0]))
                if spalte not in schon:
                    zeilenfehler.append(Zeilenfehler(zeile=nr, spalte=spalte, meldung=MELDUNGEN.get(f["type"], f["msg"])))
        if zeilenfehler:
            fehler.extend(zeilenfehler)
        else:
            gueltig.append(geprueft)
    return ImportErgebnis(zeilen=gueltig, fehler=fehler)
