"""Mietansatz-Herleitung als Kette: Basiswert, Zu-/Abschläge mit Begründung, Ergebnis."""
import pytest

from mietmarkt.mietansatz import Anpassung, herleiten
from mietmarkt.modelle import Wert


def test_ergebnis_ist_basis_plus_saldo():
    """Ergebnis = Basis + Summe der Zu- und Abschläge; jeder Schritt bleibt sichtbar."""
    basis = Wert(wert=16.96, einheit="€/m²", herkunft="berechnet", rechenweg_text="Ø Comps")
    h = herleiten(basis, [Anpassung(name="Energiestandard", betrag=0.30, begruendung="EH 40"),
                          Anpassung(name="Verkehr / Lärm", betrag=-0.25, begruendung="Hauptstraße 40 m")])
    assert h.ergebnis.wert == pytest.approx(17.01)
    assert [s.art for s in h.schritte] == ["basis", "anpassung", "anpassung", "ergebnis"]
    assert h.schritte[2].begruendung == "Hauptstraße 40 m"
    assert "16,96" in h.ergebnis.rechenweg_text and "− 0,25" in h.ergebnis.rechenweg_text


def test_anpassung_ohne_begruendung_ist_unzulaessig():
    """Jeder Zu- oder Abschlag braucht eine Begründung."""
    with pytest.raises(ValueError):
        Anpassung(name="Ausstattung", betrag=0.2, begruendung=" ")


def test_basis_ohne_wert_ergibt_kein_ergebnis():
    """Fehlt der Basiswert, gibt es kein Ergebnis, aber eine Erklärung."""
    h = herleiten(Wert(wert=None, einheit="€/m²", herkunft="berechnet", rechenweg_text="keine Comps"), [])
    assert h.ergebnis.wert is None and "Basiswert fehlt" in h.ergebnis.rechenweg_text
