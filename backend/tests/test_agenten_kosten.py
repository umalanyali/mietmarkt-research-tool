"""Kosten je Modellaufruf: Token aus usage_metadata mal Listenpreis, umgerechnet in Euro."""
import pytest

from mietmarkt.agenten.kosten import kosten_eur


def test_sonnet_je_million_token():
    """Sonnet 5.5: 2 $ Eingabe + 10 $ Ausgabe je Million Token; Kurs 0,9 € je $ → 10,80 €."""
    k = kosten_eur("claude-sonnet-5-5", 1_000_000, 1_000_000, eur_je_usd=0.9)
    assert k.wert == pytest.approx(10.8) and k.einheit == "€" and k.herkunft == "berechnet"
    assert "claude-sonnet-5-5" in k.rechenweg_text


def test_haiku_teurer_ueber_100k_eingabe():
    """Haiku 5.5 kostet über 100.000 Eingabe-Token je Aufruf mehr (0,50 statt 0,10 $ je Million)."""
    assert kosten_eur("claude-haiku-5-5", 100_000, 0, eur_je_usd=1.0).wert == pytest.approx(0.01)
    assert kosten_eur("claude-haiku-5-5", 200_000, 0, eur_je_usd=1.0).wert == pytest.approx(0.10)


def test_unbekanntes_modell_ist_fehler():
    """Ohne Preis lässt sich das Budget nicht einhalten – daher ein klarer Fehler statt 0 €."""
    with pytest.raises(ValueError, match="Kein Preis"):
        kosten_eur("claude-unbekannt", 10, 10, eur_je_usd=1.0)
