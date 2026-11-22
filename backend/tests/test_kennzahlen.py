"""Kennzahlen zu Comps: €/m², Anzahl, Median, Quartile, flächengewichteter Mittelwert, Anfragen je Monat."""
import pytest
from conftest import comp

from mietmarkt.kennzahlen import anfragen_je_monat, eur_qm, kennzahlen_eur_qm, zusammenfassung


def test_eur_qm_ist_kaltmiete_durch_flaeche():
    """€/m² = Kaltmiete / Wohnfläche, mit Rechenweg."""
    w = eur_qm(comp(1, wfl=50, kalt=900))
    assert w.wert == pytest.approx(18.0)
    assert "900" in w.rechenweg_text and "50" in w.rechenweg_text


def test_flaechengewichtet_ist_summe_kalt_durch_summe_flaeche():
    """Ø flächengewichtet = Σ Kaltmiete / Σ Wohnfläche, nicht der Mittelwert der €/m²."""
    k = kennzahlen_eur_qm([comp(1, wfl=50, kalt=1000), comp(2, wfl=100, kalt=1500)])
    assert k["mittel_flaechengewichtet"].wert == pytest.approx(2500 / 150)
    assert k["anzahl"].wert == 2


def test_median_und_quartile_inklusiv():
    """Median und Quartile über die €/m² (lineare Interpolation, inklusiv)."""
    cs = [comp(i, wfl=100, kalt=k) for i, k in enumerate([1000, 1200, 1400, 1600, 1800], start=1)]
    k = kennzahlen_eur_qm(cs)
    assert k["median"].wert == pytest.approx(14.0)
    assert k["q1"].wert == pytest.approx(12.0)
    assert k["q3"].wert == pytest.approx(16.0)


def test_leere_liste_liefert_keine_zahl_aber_erklaerung():
    """Ohne Comps gibt es keinen Wert, wohl aber einen Rechenweg, der das sagt."""
    k = kennzahlen_eur_qm([])
    assert k["anzahl"].wert == 0
    assert k["median"].wert is None and "keine" in k["median"].rechenweg_text.lower()


def test_anfragen_je_monat_mittel_der_einzelwerte_ab_7_tagen(stichtag):
    """Mittel der Einzelwerte (Anfragen / Tage × 30); Inserate unter 7 Tagen online zählen nicht."""
    cs = [comp(1, tage=30, anfragen=30), comp(2, tage=10, anfragen=20), comp(3, tage=6, anfragen=50)]
    w = anfragen_je_monat(cs, stichtag)
    assert w.wert == pytest.approx((30 + 60) / 2)
    assert "Nr. 3" in w.rechenweg_text


def test_genau_7_tage_zaehlen_mit(stichtag):
    """Grenzfall: genau 7 Tage online zählt."""
    assert anfragen_je_monat([comp(1, tage=7, anfragen=7)], stichtag).wert == pytest.approx(30.0)


def test_zusammenfassung_trennt_regelgeschoss_eg_und_dg(stichtag):
    """Regelgeschoss und EG werden zusammen, DG getrennt flächengewichtet."""
    cs = [comp(1, typ="Regel", wfl=50, kalt=800), comp(2, typ="EG", wfl=50, kalt=900), comp(3, typ="DG", wfl=80, kalt=1600)]
    z = zusammenfassung(cs, stichtag)
    assert z["regel_eg"].wert == pytest.approx(1700 / 100)
    assert z["dg"].wert == pytest.approx(20.0)
    assert "n = 2" in z["regel_eg"].rechenweg_text
    assert (z["regel_eg_n"].wert, z["dg_n"].wert) == (2, 1)


def test_preisklassen_summe_und_staerkste_klasse():
    """Summe aller Klassen und Anteil der stärksten Klasse, mit Rechenweg."""
    from mietmarkt.kennzahlen import preisklassen_auswertung

    a = preisklassen_auswertung([("< 12", 4), ("16,50–18", 38), ("> 21", 63 - 0)])
    assert a.summe.wert == 105
    assert a.staerkste == "> 21" and a.anteil.wert == pytest.approx(60.0)
    assert "63 / 105" in a.anteil.rechenweg_text


def test_tage_online_als_wert_und_negative_tage_ohne_zahl(stichtag):
    """Tage online sind ein berechneter Wert; liegt „online seit“ nach dem Stichtag, gibt es keine Zahl, aber eine Erklärung."""
    from mietmarkt.kennzahlen import tage_online

    assert tage_online(comp(1, tage=20), stichtag).wert == 20
    spaeter = tage_online(comp(2, tage=-6), stichtag)
    assert spaeter.wert is None and "nach dem Stichtag" in spaeter.rechenweg_text


def test_wohnflaeche_null_fuehrt_nicht_zum_absturz(stichtag):
    """Ein Comp mit 0 m² liefert keinen €/m²-Wert und wird bei Kennzahlen nicht mitgerechnet."""
    null = comp(1, wfl=0, kalt=900)
    assert eur_qm(null).wert is None
    k = kennzahlen_eur_qm([null, comp(2, wfl=50, kalt=1000)])
    assert k["mittel_flaechengewichtet"].wert == pytest.approx(20.0)
    assert "Nr. 1" in k["mittel_flaechengewichtet"].rechenweg_text


def test_preisklasse_ohne_wert_wird_als_fehlend_ausgewiesen():
    """Eine Klasse ohne Anzahl zählt nicht als 0, sondern steht als fehlend im Rechenweg."""
    from mietmarkt.kennzahlen import preisklassen_auswertung

    a = preisklassen_auswertung([("< 12", 4), ("12–13,50", None), ("13,50–15", 6)])
    assert a.summe.wert == 10 and "12–13,50 fehlt" in a.summe.rechenweg_text


def test_wohnungsmix_je_geschosslage():
    """Anzahl und Wohnfläche je Geschosslage aus dem Wohnungsmix, mit Rechenweg."""
    from mietmarkt.kennzahlen import wohnungsmix
    from mietmarkt.modelle import Wohnung
    mix = wohnungsmix([Wohnung(projekt_id=1, typ="Regel", zimmer=2, wohnflaeche=60, anzahl=8),
                       Wohnung(projekt_id=1, typ="DG", zimmer=3, wohnflaeche=85, anzahl=2),
                       Wohnung(projekt_id=1, typ="DG", zimmer=4, wohnflaeche=100, anzahl=1)])
    assert mix["dg_anzahl"].wert == 3 and mix["dg_wohnflaeche"].wert == 270
    assert mix["regel_eg_anzahl"].wert == 8 and mix["gesamt_anzahl"].wert == 11
    assert "2 × 85,0 m² + 1 × 100,0 m²" in mix["dg_wohnflaeche"].rechenweg_text
