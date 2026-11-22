"""Plausibilitätsprüfungen für den Prüf-Agenten: Ausreißer (IQR), Anzahl und Alter der Comps, Ansatz gegen Kennzahl."""
import datetime as dt

import pytest

from mietmarkt.modelle import Comp, Herkunft, Wert
from mietmarkt.plausibilitaet import abgleich, alter, anzahl, ausreisser_iqr

STICHTAG = dt.date(2026, 11, 4)


def comp(nr: int, eur_qm: float, online_seit: dt.date | None = dt.date(2026, 10, 1)) -> Comp:
    """Comp mit 50 m² und passender Kaltmiete. Ausgabe: Comp."""
    return Comp(projekt_id=1, nr=nr, objekt=f"Musterweg {nr}", typ="Regel", zimmer=2, wohnflaeche=50,
                kaltmiete=eur_qm * 50, online_seit=online_seit)


def test_ausreisser_ausserhalb_von_eineinhalb_iqr():
    """Q1 16, Q3 18 (IQR 2) → Grenzen 13 und 21; nur 30 €/m² fällt heraus."""
    comps = [comp(1, 16), comp(2, 16), comp(3, 17), comp(4, 18), comp(5, 18), comp(6, 30)]
    aus = ausreisser_iqr(comps)
    assert aus["auffaellig"] is True and [x["nr"] for x in aus["ausreisser"]] == [6]
    assert aus["untergrenze"]["herkunft"] == Herkunft.BERECHNET and "1,5" in aus["untergrenze"]["rechenweg_text"]


def test_keine_ausreisser_und_leere_auswahl():
    """Gleichmäßige Werte sind unauffällig; ohne Comps gibt es nichts zu prüfen."""
    assert ausreisser_iqr([comp(i, 16 + i / 10) for i in range(6)])["auffaellig"] is False
    assert ausreisser_iqr([])["auffaellig"] is False


@pytest.mark.parametrize(("n", "auffaellig"), [(4, True), (5, False)])
def test_zu_wenige_comps(n, auffaellig):
    """Unter fünf Comps ist der Vergleich nicht belastbar."""
    aus = anzahl([comp(i, 16) for i in range(n)])
    assert aus["auffaellig"] is auffaellig and aus["anzahl"]["wert"] == n


def test_comps_aelter_als_zwoelf_monate():
    """Ein Angebot, das länger als 365 Tage vor dem Stichtag online ging, ist veraltet; fehlendes Datum wird gezählt."""
    comps = [comp(1, 16, dt.date(2025, 11, 3)), comp(2, 16, dt.date(2025, 11, 4)), comp(3, 16, None)]
    aus = alter(comps, STICHTAG)
    assert aus["auffaellig"] is True and [x["nr"] for x in aus["veraltet"]] == [1]
    assert aus["ohne_datum"] == [3]


def test_abgleich_mehr_als_fuenfzehn_prozent():
    """Ansatz 20 gegen Median 17 sind + 17,6 % (auffällig), gegen 18 nur + 11,1 %."""
    def w(x: float) -> Wert:
        return Wert(wert=x, einheit="€/m²", herkunft=Herkunft.BERECHNET)
    aus = abgleich(w(20), {"Median Comps": w(17), "Marktkennzahl": w(18), "ohne Wert": Wert(wert=None, herkunft="import")})
    assert aus["auffaellig"] is True
    assert [(x["kennzahl"], round(x["abweichung"]["wert"], 1), x["auffaellig"]) for x in aus["vergleiche"]] == [
        ("Median Comps", 17.6, True), ("Marktkennzahl", 11.1, False)]
    assert "17,6 %" in aus["vergleiche"][0]["abweichung"]["rechenweg_text"]


def test_genau_fuenfzehn_prozent_ist_nicht_auffaellig():
    """P4: 12,65 gegen 11,00 sind genau 15 % – „mehr als 15 %“ gilt erst darüber (kein Gleitkommafehler)."""
    w = lambda x: Wert(wert=x, einheit="€/m²", herkunft=Herkunft.BERECHNET)
    assert abgleich(w(12.65), {"Kennzahl": w(11.0)})["auffaellig"] is False
    assert abgleich(w(12.66), {"Kennzahl": w(11.0)})["auffaellig"] is True


def test_ausreisser_unter_vier_comps_nicht_pruefbar():
    """P14: Bei weniger als 4 Comps ist der IQR nicht aussagekräftig; das Ergebnis sagt das ausdrücklich."""
    aus = ausreisser_iqr([comp(1, 16), comp(2, 30), comp(3, 17)])
    assert aus["auffaellig"] is False and aus["pruefbar"] is False and "nicht prüfbar" in aus["rechenweg_text"]
    assert ausreisser_iqr([comp(i, 16 + i) for i in range(4)])["pruefbar"] is True
