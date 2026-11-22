"""Zahlenprüfung (CLAUDE.md Regel 1): Jede Zahl in einer Agenten-Antwort muss aus einem Werkzeugergebnis
oder den Projektdaten stammen. Was nicht belegt ist, wird markiert – Herkunft „ki“ mit Warnhinweis."""
import re
from decimal import ROUND_HALF_UP, Decimal

from ..modelle import Herkunft, Wert

# Zahl mit optionalem Vorzeichen (+, -, −; auch „+ 0,30“). Steht direkt davor ein Buchstabe oder eine Ziffer
# („2-Zimmer“, „12-14“), ist der Strich kein Vorzeichen; ein Bindestrich nach „Zahl Leerzeichen“ ist eine Spanne
# („13,9 - 24,1“). Das echte Minus „−“ und „+“ (so schreibt sie herleiten) gelten dort weiter als Vorzeichen.
_ZAHL = re.compile(r"(?:(?<!\w)((?<!\d\s)-|[−+])\s?)?(\d[\d.,]*\d|\d)")
_DEUTSCH = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")
_PUNKT = re.compile(r"\d+(?:\.\d+)?")
# Felder, deren Zahlen nichts Fachliches belegen: sonst „belegt“ etwa lon 13,6 einen Mietansatz von 14 €/m²
IGNORIERT = {"lat", "lon", "nr", "id", "quelle_id", "projekt_id"}
HINWEIS = "Vom Modell genannt, in keinem Werkzeugergebnis belegt – bitte prüfen"


def _lesarten(roh: str) -> list[tuple[Decimal, int]]:
    """Mögliche Werte einer Ziffernfolge. Eingabe: z. B. „1.234,5“. Ausgabe: [(Betrag, Nachkommastellen)].

    Warum zwei Lesarten: Texte sind deutsch (Komma), Werkzeugergebnisse oft im Punktformat; „1.234“ kann beides sein.
    Daten wie „22.11.2026“ passen zu keiner Lesart und werden nicht geprüft.
    """
    lesarten = []
    if _DEUTSCH.fullmatch(roh):
        ganz, _, nachkomma = roh.replace(".", "").partition(",")
        lesarten.append((Decimal(f"{ganz}.{nachkomma or 0}"), len(nachkomma)))
    if _PUNKT.fullmatch(roh):
        lesarten.append((Decimal(roh), len(roh.partition(".")[2])))
    return lesarten


def _mit_vorzeichen(zeichen: str | None, betrag: Decimal) -> Decimal:
    """Betrag samt Vorzeichen. Eingabe: „-“, „−“, „+“ oder None; Betrag. Ausgabe: Decimal."""
    return -betrag if zeichen in ("-", "−") else betrag


def _belegwerte(beleg: object, werte: set[Decimal]) -> set[Decimal]:
    """Sammelt alle fachlichen Zahlen eines Belegs. Eingabe: dict/list/Zahl/Text, Sammelmenge. Ausgabe: die Menge.

    dicts und Listen werden durchlaufen (ohne IGNORIERT-Felder), Texte wie Rechenwege nach Zahlen durchsucht.
    """
    if isinstance(beleg, dict):
        for schluessel, wert in beleg.items():
            if schluessel not in IGNORIERT:
                _belegwerte(wert, werte)
    elif isinstance(beleg, list):
        for wert in beleg:
            _belegwerte(wert, werte)
    elif isinstance(beleg, int | float) and not isinstance(beleg, bool):
        werte.add(Decimal(repr(beleg)))
    elif isinstance(beleg, str):
        werte.update(_mit_vorzeichen(z, b) for z, roh in _ZAHL.findall(beleg) for b, _ in _lesarten(roh))
    return werte


def _belegt(zeichen: str | None, betrag: Decimal, stellen: int, bekannt: set[Decimal]) -> bool:
    """Ob eine Textzahl durch einen Belegwert gedeckt ist. Eingabe: Vorzeichen, Betrag, Stellen, Belegwerte.

    Ausgabe: True, wenn ein Belegwert kaufmännisch auf die gezeigten Stellen gerundet genau die Zahl ergibt.
    Ohne Vorzeichen im Text zählt der Betrag („Abschlag von 0,30“ ← −0,3), mit Vorzeichen muss es stimmen.
    """
    ziel = _mit_vorzeichen(zeichen, betrag) if zeichen else betrag
    stufe = Decimal(1).scaleb(-stellen)
    return any((b if zeichen else abs(b)).quantize(stufe, ROUND_HALF_UP) == ziel for b in bekannt)


def zahlen_pruefen(text: str, belege: list[object]) -> list[dict]:
    """Findet Zahlen im Text, die in keinem Beleg vorkommen.

    Eingabe: Antworttext des Agenten, Belege (Werkzeugergebnisse als Daten, Projektdaten als Text).
    Ausgabe: je unbelegter Zahl {"fundstelle": Text, "wert": Wert mit Herkunft ki}.
    """
    bekannt = set()
    for beleg in belege:
        _belegwerte(beleg, bekannt)
    markierungen = []
    for treffer in _ZAHL.finditer(text):
        zeichen, roh = treffer.groups()
        lesarten = _lesarten(roh)
        if lesarten and not any(_belegt(zeichen, b, stellen, bekannt) for b, stellen in lesarten):
            wert = Wert(wert=float(_mit_vorzeichen(zeichen, lesarten[0][0])), einheit="", herkunft=Herkunft.KI,
                        rechenweg_text=HINWEIS)
            markierungen.append({"fundstelle": treffer.group(0), "wert": wert.model_dump()})
    return markierungen
