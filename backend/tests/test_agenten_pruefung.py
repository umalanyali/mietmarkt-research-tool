"""Zahlenprüfung: Jede Zahl in einer Agenten-Antwort muss aus einem Werkzeugergebnis stammen (CLAUDE.md Regel 1)."""
from mietmarkt.agenten.pruefung import zahlen_pruefen


def test_belegte_zahl_im_deutschen_format_ist_ok():
    """12,35 im Text ist durch 12.3456 im Werkzeugergebnis belegt (auf die gezeigten Stellen gerundet)."""
    assert zahlen_pruefen("Der Median liegt bei 12,35 €/m².", [{"wert": 12.3456}]) == []


def test_gerundete_und_tausender_zahlen_sind_ok():
    """Gerundete Ganzzahlen und deutsche Tausenderpunkte werden erkannt."""
    assert zahlen_pruefen("rund 12 €/m² bei 1.234 Einwohnern", [{"a": 12.3456, "b": 1234}]) == []


def test_zahl_aus_rechenweg_text_ist_belegt():
    """Auch Zahlen in Texten der Werkzeugergebnisse (Rechenweg) zählen als Beleg."""
    assert zahlen_pruefen("Ø 12,35 €/m²", [{"rechenweg_text": "Summe 4.321,00 € / 350,0 m² = 12,35 €/m²"}]) == []


def test_erfundene_zahl_wird_als_ki_markiert():
    """Eine Zahl ohne Beleg wird markiert: Herkunft ki, mit Warnhinweis im Rechenweg."""
    m = zahlen_pruefen("12 Comps, Median 99,99 €/m²", [{"anzahl": 12}])
    assert [x["fundstelle"] for x in m] == ["99,99"]
    assert m[0]["wert"]["wert"] == 99.99 and m[0]["wert"]["herkunft"] == "ki"
    assert "in keinem Werkzeugergebnis belegt" in m[0]["wert"]["rechenweg_text"]


def test_koordinaten_und_nummern_belegen_nichts():
    """C: Koordinaten, Comp-Nummern und IDs sind keine Belege – „14 €/m²“ ist nicht durch lon 13,6 gedeckt."""
    assert [m["fundstelle"] for m in zahlen_pruefen("Mietansatz 14 €/m²", [{"lat": 52.52, "lon": 13.6}])] == ["14"]
    belege = [{"comps": [{"nr": 16, "quelle_id": 16}], "mittel": 13.42}]
    assert [m["fundstelle"] for m in zahlen_pruefen("rund 16 €/m²", belege)] == ["16"]


def test_ganze_zahl_aus_gerundetem_wert_bleibt_belegt():
    """C: Gerundete Kennzahlen bleiben belegt, wenn sie aus einem fachlichen Feld stammen."""
    assert zahlen_pruefen("rund 13 €/m², 3 min zu Fuß", [{"mittel": 13.42, "zu_fuss": {"wert": 2.6}}]) == []


def test_kaufmaennisch_gerundet():
    """G: 0,285 wird kaufmännisch zu 0,29 und 2,5 zu 3 gerundet (nicht binär bzw. auf die gerade Zahl)."""
    assert zahlen_pruefen("0,29 €/m² und rund 3 Anfragen", [{"a": 0.285, "b": 2.5}]) == []


def test_vorzeichen_muss_stimmen():
    """G: Ein Abschlag von −0,30 belegt keinen Zuschlag „+ 0,30“; ohne Vorzeichen im Text zählt der Betrag."""
    assert [m["fundstelle"] for m in zahlen_pruefen("Zuschlag + 0,30 €/m²", [{"betrag": -0.3}])] == ["+ 0,30"]
    assert zahlen_pruefen("Abschlag von 0,30 €/m²", [{"betrag": -0.3}]) == []
    assert zahlen_pruefen("Abschlag − 0,30 €/m²", ["16,96 − 0,30 = 16,66 €/m²"]) == []


def test_bindestrich_ist_kein_minus():
    """G: „2-Zimmer“ oder „12-14“ enthalten kein negatives Vorzeichen."""
    assert zahlen_pruefen("2-Zimmer, 12-14 €/m²", [{"zimmer": 2, "von": 12, "bis": 14}]) == []


def test_spanne_mit_bindestrich_ist_kein_minus():
    """Live-Fund: „13,9 - 24,1 €/m²“ ist eine Spanne, kein negativer Wert (Bindestrich mit Leerzeichen nach Zahl)."""
    assert zahlen_pruefen("Spanne 13,9 - 24,1 €/m²", [{"min": 13.9, "max": 24.1}]) == []
