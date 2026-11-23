"""Zahlenprüfung (CLAUDE.md Regel 1): Jede Zahl in einer Agenten-Antwort muss aus einem Werkzeugergebnis
oder den Projektdaten stammen. Was nicht belegt ist, wird markiert – Herkunft „ki“ mit Warnhinweis."""
import re
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from ..modelle import Herkunft, Wert

# Zahl mit optionalem Vorzeichen (+, -, −; auch „+ 0,30“). Steht direkt davor ein Buchstabe oder eine Ziffer
# („2-Zimmer“, „12-14“), ist der Strich kein Vorzeichen; ein Bindestrich nach „Zahl Leerzeichen“ ist eine Spanne
# („13,9 - 24,1“). Das echte Minus „−“ und „+“ (so schreibt sie herleiten) gelten dort weiter als Vorzeichen.
ZAHL = re.compile(r"(?:(?<!\w)((?<!\d\s)-|[−+])\s?)?(\d[\d.,]*\d|\d)")
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


def _belegwerte(beleg: object, werte: set[Decimal], ohne: re.Pattern | None) -> set[Decimal]:
    """Sammelt alle fachlichen Zahlen eines Belegs. Eingabe: dict/list/Zahl/Text, Sammelmenge, auszublendende
    Dateinamen (Muster oder None). Ausgabe: die Menge.

    dicts und Listen werden durchlaufen (ohne IGNORIERT-Felder), Texte wie Rechenwege nach Zahlen durchsucht.
    """
    if isinstance(beleg, dict):
        for schluessel, wert in beleg.items():
            if schluessel not in IGNORIERT:
                _belegwerte(wert, werte, ohne)
    elif isinstance(beleg, list):
        for wert in beleg:
            _belegwerte(wert, werte, ohne)
    elif isinstance(beleg, int | float) and not isinstance(beleg, bool):
        werte.add(Decimal(repr(beleg)))
    elif isinstance(beleg, str):
        beleg = ohne.sub(" ", beleg) if ohne else beleg
        werte.update(_mit_vorzeichen(z, b) for z, roh in ZAHL.findall(beleg) for b, _ in _lesarten(roh))
    return werte


def _belegt(zeichen: str | None, betrag: Decimal, stellen: int, bekannt: set[Decimal]) -> bool:
    """Ob eine Textzahl durch einen Belegwert gedeckt ist. Eingabe: Vorzeichen, Betrag, Stellen, Belegwerte.

    Ausgabe: True, wenn ein Belegwert kaufmännisch auf die gezeigten Stellen gerundet genau die Zahl ergibt.
    Ohne Vorzeichen im Text zählt der Betrag („Abschlag von 0,30“ ← −0,3), mit Vorzeichen muss es stimmen.
    """
    ziel = _mit_vorzeichen(zeichen, betrag) if zeichen else betrag
    stufe = Decimal(1).scaleb(-stellen)
    return any((b if zeichen else abs(b)).quantize(stufe, ROUND_HALF_UP) == ziel for b in bekannt)


def _namensmuster(namen: Sequence[str]) -> re.Pattern | None:
    """Muster für Dateinamen als ganze Wörter. Eingabe: Namen. Ausgabe: Muster oder None ohne (nicht leere) Namen.

    Warum ganze Wörter: Ein Name „1“ würde sonst die 1 in „18“ entfernen.
    """
    namen = sorted(filter(None, namen), key=len, reverse=True)
    return re.compile(rf"(?<![\w.,])(?:{'|'.join(map(re.escape, namen))})(?![\w])") if namen else None


def dateinamen_entfernen(text: str, namen: Sequence[str]) -> str:
    """Text ohne die Dateinamen. Eingabe: Text, Namen. Ausgabe: Text, jeder Name durch ein Leerzeichen ersetzt."""
    muster = _namensmuster(namen)
    return muster.sub(" ", text) if muster else text


def zahlen_pruefen(text: str, belege: list[object], dateinamen: Sequence[str] = ()) -> list[dict]:
    """Findet Zahlen im Text, die in keinem Beleg vorkommen.

    Eingabe: Antworttext des Agenten, Belege (Werkzeugergebnisse als Daten, Projektdaten als Text), Namen der
    Unterlagen. Ausgabe: je unbelegter Zahl {"fundstelle": Text, "wert": Wert mit Herkunft ki}.
    Dateinamen wählt, wer die Datei erstellt hat (N1): In den Belegen fallen sie immer weg, also belegt
    „Expose 22,50 €-m².pdf“ keine Marktmiete. Im Text fallen nur Namen mit Buchstaben und ab drei Zeichen weg (eine
    Fundstelle mit Namen ist keine freie Zahl); ein Name wie „22,50“ verdeckte sonst genau diese Zahl.
    """
    ohne = _namensmuster(dateinamen)
    text = dateinamen_entfernen(text, [n for n in dateinamen if len(n) >= 3 and re.search(r"[^\W\d_]", n)])
    bekannt = set()
    for beleg in belege:
        _belegwerte(beleg, bekannt, ohne)
    markierungen = []
    for treffer in ZAHL.finditer(text):
        zeichen, roh = treffer.groups()
        lesarten = _lesarten(roh)
        if lesarten and not any(_belegt(zeichen, b, stellen, bekannt) for b, stellen in lesarten):
            wert = Wert(wert=float(_mit_vorzeichen(zeichen, lesarten[0][0])), einheit="", herkunft=Herkunft.KI,
                        rechenweg_text=HINWEIS)
            markierungen.append({"fundstelle": treffer.group(0), "wert": wert.model_dump()})
    return markierungen
