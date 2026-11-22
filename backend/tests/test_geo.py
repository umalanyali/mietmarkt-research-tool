"""Entfernung per Haversine: bekannte Abstände und Rechenweg."""
import pytest

from mietmarkt.geo import entfernung_km


def test_gleicher_punkt_ist_null():
    """Derselbe Punkt hat Abstand 0 km."""
    assert entfernung_km(51.3, 9.48, 51.3, 9.48).wert == 0


def test_ein_breitengrad_sind_rund_111_km():
    """Ein Breitengrad entspricht auf dem Meridian rund 111,2 km."""
    assert entfernung_km(51.0, 9.0, 52.0, 9.0).wert == pytest.approx(111.19, abs=0.01)


def test_ergebnis_traegt_herkunft_und_rechenweg():
    """Das Ergebnis ist als berechnet gekennzeichnet und nennt Methode und Koordinaten."""
    w = entfernung_km(51.3127, 9.4797, 51.3155, 9.4850)
    assert w.herkunft == "berechnet"
    assert w.einheit == "km"
    assert "Luftlinie" in w.rechenweg_text and "Haversine" in w.rechenweg_text
