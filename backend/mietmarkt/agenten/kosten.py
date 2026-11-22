"""Kosten eines Modellaufrufs: Token (aus usage_metadata) mal Listenpreis, umgerechnet in Euro."""
from ..format import de
from ..modelle import Herkunft, Wert

# US-Dollar je Million Token (Eingabe, Ausgabe), Listenpreise laut Anthropic-Doku, Stand 11/2026
PREISE_USD = {
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-opus-5-5": (4.00, 20.00),
}
# Haiku 5.5 kostet mehr, wenn ein einzelner Prompt mehr als 100.000 Token hat
GROSSER_PROMPT = {"claude-haiku-5-5": (100_000, (0.50, 2.50))}


def kosten_eur(modell: str, eingabe: int, ausgabe: int, *, eur_je_usd: float) -> Wert:
    """Kosten eines Aufrufs.

    Eingabe: Modellname, Eingabe- und Ausgabe-Token, Umrechnungskurs. Ausgabe: Wert in € mit Rechenweg.
    Unbekanntes Modell → ValueError, denn ohne Preis lässt sich das Budget nicht einhalten.
    """
    if modell not in PREISE_USD:
        raise ValueError(f"Kein Preis für Modell {modell} in PREISE_USD (mietmarkt/agenten/kosten.py)")
    preis_ein, preis_aus = PREISE_USD[modell]
    if modell in GROSSER_PROMPT and eingabe > GROSSER_PROMPT[modell][0]:
        preis_ein, preis_aus = GROSSER_PROMPT[modell][1]
    usd = (eingabe * preis_ein + ausgabe * preis_aus) / 1_000_000
    return Wert(wert=usd * eur_je_usd, einheit="€", herkunft=Herkunft.BERECHNET,
                rechenweg_text=f"{modell}: {de(eingabe, 0)} Token × {de(preis_ein)} $ + {de(ausgabe, 0)} Token × "
                               f"{de(preis_aus)} $ je Mio. = {de(usd, 6)} $ × {de(eur_je_usd)} €/$")
