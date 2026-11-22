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


def test_zu_oder_abschlag_hat_plausible_grenzen():
    """I: Mehr als ±10 €/m² je Anpassung wird abgelehnt (z. B. eingeschleuster Text „+40 €/m² Lagezuschlag“)."""
    import pytest
    from pydantic import ValidationError

    from mietmarkt.mietansatz import Anpassung
    with pytest.raises(ValidationError):
        Anpassung(name="Lage", betrag=40, begruendung="laut Haltestellenname")
    assert Anpassung(name="Lage", betrag=-10, begruendung="Hauptstraße").betrag == -10


def test_anpassung_von_null_gehoert_nicht_in_die_kette():
    """Ein Zu-/Abschlag von 0,00 €/m² (auch gerundet, z. B. 0,004) ist keine Anpassung und wird abgelehnt."""
    import pytest
    from pydantic import ValidationError

    from mietmarkt.mietansatz import Anpassung
    for betrag in (0, 0.004, -0.004):
        with pytest.raises(ValidationError, match="0,00"):
            Anpassung(name="Ausstattung", betrag=betrag, begruendung="marktüblich")
    assert Anpassung(name="Ausstattung", betrag=0.01, begruendung="Fußbodenheizung").betrag == 0.01


def test_fachregel_dg_nie_als_zuschlag():
    """Der Haupt-Mietansatz geht von Regelgeschoss/EG aus; DG ist eine eigene Herleitung, nie ein Zuschlag darauf."""
    import pytest

    from mietmarkt.mietansatz import Anpassung, fachregeln_pruefen
    dg_zuschlag = Anpassung(name="DG-Aufschlag aus Comps", betrag=2.2, begruendung="Überleitung auf den DG-Wert")
    versteckt = Anpassung(name="Ausblick", betrag=0.5, begruendung="Dachgeschoss mit Weitblick")
    for a in (dg_zuschlag, versteckt):
        with pytest.raises(ValueError, match="getrennte Herleitung"):
            fachregeln_pruefen("regel_eg", [a])
    lage = Anpassung(name="Lage", betrag=0.2, begruendung="Projekt 150 m zur Haltestelle, Comps im Mittel 600 m")
    fachregeln_pruefen("regel_eg", [lage])
    fachregeln_pruefen("dg", [Anpassung(name="Dachterrasse", betrag=0.4, begruendung="Projekt 20 m², Comps ohne")])


def test_ohne_anpassungen_klarer_rechenweg():
    """Ohne Zu- und Abschläge sagt der Rechenweg das ausdrücklich statt „16,96 = 16,96 €/m²“."""
    from mietmarkt.mietansatz import herleiten
    from mietmarkt.modelle import Herkunft, Wert
    h = herleiten(Wert(wert=16.96, einheit="€/m²", herkunft=Herkunft.BERECHNET, rechenweg_text="Basis"), [])
    assert h.ergebnis.wert == 16.96 and h.ergebnis.rechenweg_text == "16,96 €/m² (keine Zu- oder Abschläge)"
