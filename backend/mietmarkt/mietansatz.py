"""Mietansatz-Herleitung als Kette: Basiswert, begründete Zu- und Abschläge, Ergebnis.
Das Sprachmodell schlägt später Anpassungen vor; gerechnet wird ausschließlich hier."""
from typing import Literal

from pydantic import BaseModel, field_validator

from .format import de
from .modelle import Herkunft, Wert


class Anpassung(BaseModel):
    """Ein Zu- (+) oder Abschlag (−) in €/m² mit Pflichtbegründung."""

    name: str
    betrag: float
    begruendung: str

    @field_validator("begruendung")
    @classmethod
    def _begruendung_noetig(cls, text: str) -> str:
        """Leere Begründungen ablehnen. Eingabe: Text. Ausgabe: Text oder ValueError."""
        if not text.strip():
            raise ValueError("Jede Anpassung braucht eine Begründung")
        return text


class Schritt(BaseModel):
    """Ein Glied der Kette, wie es in der Oberfläche erscheint."""

    art: Literal["basis", "anpassung", "ergebnis"]
    name: str
    wert: Wert
    begruendung: str = ""


class Herleitung(BaseModel):
    """Die ganze Kette und das Ergebnis."""

    schritte: list[Schritt]
    ergebnis: Wert


def _vorzeichen(betrag: float) -> str:
    """Betrag mit typografischem Vorzeichen. Eingabe: Zahl. Ausgabe: z. B. „+ 0,30“ oder „− 0,25“."""
    return f"{'+' if betrag >= 0 else '−'} {de(abs(betrag))}"


def herleiten(basis: Wert, anpassungen: list[Anpassung]) -> Herleitung:
    """Rechnet Basis plus Saldo der Anpassungen.

    Eingabe: Basiswert (z. B. Ø flächengewichtet der Regelgeschoss-Comps), Anpassungen.
    Ausgabe: Herleitung mit einem Schritt je Glied und dem Ergebnis inkl. Rechenweg.
    """
    schritte = [Schritt(art="basis", name="Basis", wert=basis)]
    for a in anpassungen:
        schritte.append(Schritt(art="anpassung", name=a.name, begruendung=a.begruendung,
                                wert=Wert(wert=a.betrag, einheit="€/m²", herkunft=Herkunft.MANUELL,
                                          rechenweg_text=f"{_vorzeichen(a.betrag)} €/m² ({a.begruendung})")))
    if basis.wert is None:
        ergebnis = Wert(wert=None, einheit="€/m²", herkunft=Herkunft.BERECHNET,
                        rechenweg_text=f"Basiswert fehlt ({basis.rechenweg_text})")
    else:
        summe = basis.wert + sum(a.betrag for a in anpassungen)
        teile = " ".join(_vorzeichen(a.betrag) for a in anpassungen)
        ergebnis = Wert(wert=summe, einheit="€/m²", herkunft=Herkunft.BERECHNET,
                        rechenweg_text=f"{de(basis.wert)} {teile} = {de(summe)} €/m²".replace("  ", " "))
    schritte.append(Schritt(art="ergebnis", name="Ergebnis", wert=ergebnis))
    return Herleitung(schritte=schritte, ergebnis=ergebnis)
