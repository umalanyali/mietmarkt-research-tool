"""Bericht: Platzhalter {{wert:ID}} füllt Python mit Wert und Fußnote; freie Zahlen des Modells fliegen raus.
Export als Markdown und PowerPoint."""
import datetime as dt
import io
import re

from pptx import Presentation

from mietmarkt.agenten.bericht import fuellen, werte_katalog
from mietmarkt.export import markdown, pptx
from mietmarkt.modelle import Projekt

KATALOG = {
    "kennzahlen.comps.median": {"wert": 16.9612, "einheit": "€/m²", "herkunft": "berechnet",
                                "rechenweg_text": "Median der sortierten €/m²"},
    "kennzahlen.marktkennzahlen.1": {"wert": 17.4, "einheit": "€/m²", "herkunft": "import", "quelle_id": 3,
                                     "bezeichnung": "Angebotsmiete Neubau"},
}
QUELLEN = {3: "RIWIS, Stand Q3/2026"}


def saetze(*texte: str, belege: tuple[str, ...] = ("projekt",)) -> list[dict]:
    """Sätze eines Abschnitts wie vom Bericht-Agenten, je mit Belegen. Ausgabe: Liste von dicts."""
    return [{"text": t, "belege": list(belege)} for t in texte]


def fuellen_(abschnitte: dict[str, list[dict]]) -> dict:
    """fuellen mit Test-Katalog und dem Beleg „projekt“. Ausgabe: Bericht."""
    return fuellen(abschnitte, KATALOG, QUELLEN, {"projekt"})


def test_platzhalter_werden_mit_wert_und_fussnote_gefuellt():
    """Gleiche ID → gleiche Fußnote; die Fußnote nennt Herkunft und Rechenweg bzw. Quelle."""
    b = fuellen_({"markt": saetze("Median {{wert:kennzahlen.comps.median}}, Marktwert "
                                  "{{wert:kennzahlen.marktkennzahlen.1}}, erneut {{wert:kennzahlen.comps.median}}.")})
    assert b["abschnitte"]["markt"] == "Median 16,96 €/m²[^1], Marktwert 17,40 €/m²[^2], erneut 16,96 €/m²[^1]."
    assert [(f["nr"], f["herkunft"]) for f in b["fussnoten"]] == [(1, "berechnet"), (2, "import")]
    assert "Median der sortierten" in b["fussnoten"][0]["verweis"] and "RIWIS" in b["fussnoten"][1]["verweis"]
    assert b["markierungen"] == []


def test_bericht_enthaelt_keine_zahl_ausser_aus_platzhaltern():
    """Freie Zahlen, Zahlwörter und unbekannte IDs ersetzt Python durch [?] und markiert sie – im Text bleibt keine
    Ziffer, die nicht aus einem Platzhalter (Wert oder Fußnotenzeichen) stammt."""
    b = fuellen_({"markt": saetze("Rund 14,50 €/m² bei 12 Comps, Median {{wert:kennzahlen.comps.median}}.",
                                  "Drei Kitas, Veränderung über zwölf Monate, ein Viertel im DG."),
                  "lage": saetze("Unbekannt: {{ wert:gibt.es.nicht }}.")})
    ohne_platzhalter = re.sub(r"16,96 €/m²\[\^1\]", "", " ".join(b["abschnitte"].values()))
    assert not re.search(r"[0-9]", ohne_platzhalter)
    assert [m["fundstelle"] for m in b["markierungen"]] == ["14,50", "12", "Drei", "zwölf", "ein Viertel",
                                                           "{{wert:gibt.es.nicht}}"]


def test_aussage_ohne_beleg_wird_gestrichen():
    """Ein Satz ohne gültigen Beleg (keine Katalog-ID, kein bekannter Beleg) fällt weg und wird markiert;
    ein Platzhalter im Satz zählt als Beleg."""
    b = fuellen_({"lage": [{"text": "Die Comps tragen kein Stichtagsdatum.", "belege": []},
                              {"text": "Vermutlich veraltet.", "belege": ["ergebnis:erfunden"]},
                              {"text": "Median {{wert:kennzahlen.comps.median}}.", "belege": []},
                              {"text": "Laut Projektdaten Neubau.", "belege": ["projekt"]}]})
    assert b["abschnitte"]["lage"] == "Median 16,96 €/m²[^1]. Laut Projektdaten Neubau."
    assert [(m["fundstelle"], m["grund"]) for m in b["markierungen"]] == [
        ("Die Comps tragen kein Stichtagsdatum.", "Aussage ohne Beleg entfernt"),
        ("Vermutlich veraltet.", "Aussage ohne Beleg entfernt")]


def test_entfernung_gerundet_in_metern_mit_passender_fussnote():
    """Unter 1 km: „rd. 230 m“ (auf 10 m); die Fußnote nennt den genauen Wert und die Rundung im Text."""
    k = {"umfeld.pois.1.luftlinie": {"wert": 0.2297, "einheit": "km", "herkunft": "berechnet",
                                     "rechenweg_text": "Luftlinie (Haversine, Erdradius 6.371 km) von A nach B: 0,23 km"},
         "umfeld.pois.2.luftlinie": {"wert": 1.234, "einheit": "km", "herkunft": "berechnet",
                                     "rechenweg_text": "Luftlinie (Haversine, Erdradius 6.371 km) von A nach C: 1,23 km"}}
    b = fuellen({"lage": saetze("Haltestelle {{wert:umfeld.pois.1.luftlinie}}, Markt {{wert:umfeld.pois.2.luftlinie}}.")},
                k, {}, {"projekt"})
    assert b["abschnitte"]["lage"] == "Haltestelle rd. 230 m[^1], Markt rd. 1,2 km[^2]."
    assert b["fussnoten"][0]["verweis"].endswith("0,23 km; im Text rd. 230 m")


def test_nur_verfahrenshinweise_werden_methoden():
    """Gleiche Fußnoten bekommen eine Nummer. Unter Methoden stehen nur Quellen- und Verfahrenshinweise (OSRM,
    Haversine, Quartil inklusiv, Grenze ± 15 %); Formeln und andere Klammern bleiben vollständig in der Fußnote."""
    osrm = {"wert": 3.8, "einheit": "min", "herkunft": "berechnet", "rechenweg_text": "Fußweg 288 m laut OSRM "
            "(routing.openstreetmap.de, abgerufen am 22.11.2026): 3,8 min"}
    fort = {"wert": 17.24, "einheit": "€/m²", "herkunft": "berechnet", "rechenweg_text": "16,96 × (1 + 2,0 %)^(10/12) "
            "= 17,24 €/m² (Stichtag 04.11.2026 bis Vermarktungsstart 01.09.2027, 10 Monate)"}
    k = {"a": osrm, "b": osrm | {"rechenweg_text": osrm["rechenweg_text"].replace("288", "300")}, "c": dict(osrm),
         "q1": {"wert": 16.72, "einheit": "€/m²", "herkunft": "berechnet",
                "rechenweg_text": "25-%-Quartil, lineare Interpolation (inklusiv) über 15,35; 16,48: 16,72"},
         "ab": {"wert": -4.0, "einheit": "%", "herkunft": "berechnet",
                "rechenweg_text": "(16,96 − 17,66) / 17,66 × 100 = -4,0 % (Grenze ± 15 %)"},
         "luft": {"wert": 0.23, "einheit": "km", "herkunft": "berechnet",
                  "rechenweg_text": "Luftlinie (Haversine, Erdradius 6.371 km) von A nach B: 0,23 km"},
         "fort": fort, "basis": {"wert": 16.96, "einheit": "€/m²", "herkunft": "berechnet",
                                 "rechenweg_text": "16,96 €/m² (keine Zu- oder Abschläge)"}}
    b = fuellen({"lage": saetze(" ".join(f"{{{{wert:{i}}}}}" for i in k))}, k, {}, {"projekt"})
    assert b["abschnitte"]["lage"].startswith("3,8 min[^1] 3,8 min[^2] 3,8 min[^1]")
    assert [m["text"] for m in b["methoden"]] == [
        "Wegezeit laut OSRM, routing.openstreetmap.de, abgerufen am 22.11.2026",
        "Quartile: lineare Interpolation, inklusiv", "Abweichung auffällig ab mehr als ± 15 %",
        "Luftlinie nach Haversine, Erdradius 6.371 km"]
    verweise = {f["ids"][0]: f["verweis"] for f in b["fussnoten"]}
    assert verweise["a"] == "Fußweg 288 m laut OSRM [M1]: 3,8 min"
    assert verweise["ab"] == "(16,96 − 17,66) / 17,66 × 100 = -4,0 % [M3]"
    assert verweise["fort"] == fort["rechenweg_text"] and verweise["basis"] == "16,96 €/m² (keine Zu- oder Abschläge)"


def test_risiken_nur_mit_befund_oder_katalogwert():
    """Unter Risiken gelten nur befund:N und Katalog-IDs als Beleg; Ergebnistexte der Agenten oder Projektdaten
    reichen dort nicht. Bleibt nichts und gab es keine Befunde, sagt Python das selbst."""
    belege = {"projekt", "ergebnis:marktdaten", "befund:1"}
    b = fuellen({"risiken": [{"text": "Umkreis der Comps nicht ersichtlich.", "belege": ["ergebnis:marktdaten"]},
                             {"text": "Wenige DG-Comps.", "belege": ["befund:1"]},
                             {"text": "Median {{wert:kennzahlen.comps.median}}.", "belege": []}],
                 "markt": [{"text": "Laut Marktdaten-Agent.", "belege": ["ergebnis:marktdaten"]}]}, KATALOG, QUELLEN, belege)
    assert b["abschnitte"]["risiken"] == "Wenige DG-Comps. Median 16,96 €/m²[^1]."
    assert b["abschnitte"]["markt"] == "Laut Marktdaten-Agent."
    leer = fuellen({"risiken": [{"text": "Vermutung.", "belege": ["projekt"]}]}, KATALOG, QUELLEN, {"projekt"})
    assert leer["abschnitte"]["risiken"] == "Die Plausibilitätsprüfung ergab keine Befunde."


def test_einheit_im_dativ_nach_praeposition():
    """„bei 36 Tagen“, aber „beträgt 36 Tage“: nach einer Präposition mit Dativ bekommt die Einheit ihr -n."""
    k = {"d": {"wert": 36, "einheit": "Tage", "herkunft": "import", "bezeichnung": "Vermarktungsdauer"}}
    b = fuellen({"markt": saetze("Dauer bei {{wert:d}}, sie beträgt {{wert:d}}, nach {{wert:d}}.")}, k, {}, {"projekt"})
    assert b["abschnitte"]["markt"] == "Dauer bei 36 Tagen[^1], sie beträgt 36 Tage[^1], nach 36 Tagen[^1]."


def test_katalog_aus_werkzeugergebnissen_und_freigabe():
    """Jeder Wert mit Herkunft aus erfolgreichen Werkzeugergebnissen wird eine ID; der Mietansatz kommt aus der
    Freigabe (geänderte Werte), nie aus dem ursprünglichen Vorschlag des Modells."""
    wert = {"wert": 16.96, "einheit": "€/m²", "herkunft": "berechnet", "rechenweg_text": "x"}
    zustand = {"ergebnisse": {
        "marktdaten": {"werkzeuge": [
            {"name": "kennzahlen", "status": "success", "ergebnis": {"comps": {"median": wert, "q1": {"wert": None}}}},
            {"name": "comps_filtern", "status": "error", "ergebnis": "Fehler 99"}]},
        "mietansatz": {"werkzeuge": [{"name": "mietansatz_herleiten", "status": "success",
                                      "ergebnis": {"ergebnis": wert | {"wert": 99.0}}}]}},
        "freigabe": {"herleitungen": {"regel_eg": {"ergebnis": wert | {"wert": 17.46}}}}}
    k = werte_katalog(zustand)
    assert set(k) == {"kennzahlen.comps.median", "mietansatz.regel_eg.ergebnis"}
    assert k["mietansatz.regel_eg.ergebnis"]["wert"] == 17.46


def test_export_markdown_und_pptx():
    """Markdown mit Abschnitten, Fußnoten und Methoden; PowerPoint mit Titel-, vier Abschnitts- und Herkunftsfolie."""
    p = Projekt(name="Lindenquartier", adresse="Lindenstraße 1", plz="34117", ort="Musterstadt", lat=51.3, lon=9.4,
                stichtag=dt.date(2026, 11, 4), analysiert_am=dt.date(2026, 11, 4))
    b = fuellen_({"lage": saetze("Ruhige Lage."), "markt": saetze("Median {{wert:kennzahlen.comps.median}}."),
                  "mietansatz": saetze("Siehe Kette."), "risiken": saetze("Wenige Comps.")})
    b["methoden"] = [{"nr": "M1", "text": "Haversine"}]
    md = markdown(p, b)
    assert md.startswith("# Mietmarktbericht: Lindenquartier") and "## Risiken" in md
    assert "[^1]: berechnet – Median der sortierten €/m²" in md and "- [M1] Haversine" in md
    folien = Presentation(io.BytesIO(pptx(p, b))).slides
    texte = [" ".join(s.text_frame.text for s in f.shapes if s.has_text_frame) for f in folien]
    assert len(texte) == 6 and "Lindenquartier" in texte[0] and "16,96 €/m² [1]" in texte[2]
    assert "Herkunft" in texte[5] and "[1] berechnet" in texte[5] and "[M1] Haversine" in texte[5]


def test_kaufmaennisch_gerundet_und_stellen_der_quelle():
    """P7: de() rundet kaufmännisch (2,675 → 2,68 statt binär 2,67); eine Quelle mit `stellen` bestimmt die Anzeige."""
    from mietmarkt.agenten.bericht import anzeigen
    from mietmarkt.format import de
    assert (de(2.675), de(1234.565), de(0.125)) == ("2,68", "1.234,57", "0,13")
    assert anzeigen({"wert": 2.345, "einheit": "%", "herkunft": "import", "stellen": 2}) == "2,35 %"
    assert anzeigen({"wert": 2.345, "einheit": "%", "herkunft": "berechnet"}) == "2,3 %"


def test_markdown_maskiert_modelltext_und_erklaert_markierungen():
    """S3: Links, Bilder und HTML aus Modell- oder Importtext werden im Markdown maskiert, die eigenen Fußnoten-
    zeichen bleiben. P17: Gab es Markierungen, erklärt der Export „[?]“ und gestrichene Aussagen."""
    p = Projekt(name="Lindenquartier [x](javascript:y)", adresse="Lindenstraße 1", plz="34117", ort="Musterstadt",
                lat=51.3, lon=9.4, stichtag=dt.date(2026, 11, 4), analysiert_am=dt.date(2026, 11, 4))
    b = fuellen_({"lage": saetze("Siehe ![bild](https://fremd.example/p?d=1) und <img src=x>."),
                  "markt": saetze("Median {{wert:kennzahlen.comps.median}}, rund 14,50 €/m²."),
                  "risiken": [{"text": "Unbelegt.", "belege": []}]})
    md = markdown(p, b)
    for wirksam in (r"(?<!\\)!(?<!\\)\[", r"(?<!\\)\]\(", r"(?<!\\)<img"):  # nur unmaskiert wirkt es
        assert not re.search(wirksam, md), wirksam
    assert "16,96 €/m²[^1]" in md and "[^1]: berechnet" in md
    # Nur maskiert, was wirken würde: harmlose Klammern bleiben lesbar
    assert "Lindenquartier \\[x\\](javascript:y)" in md and "Siehe \\!\\[bild\\](https" in md
    assert "rund [?] €/m²" in md and "(2-mal)" in md  # [?] und runde Klammern bleiben unmaskiert
    assert "[?] steht für eine Zahl ohne Herkunft" in md and "1 Aussage ohne Beleg gestrichen" in md


def test_fussnote_nennt_zeitraum_gebiet_und_quelle():
    """Importierte Kennzahlen: Bezeichnung, Zeitraum (kategorie), Gebiet und Quelle mit Stand in der Fußnote."""
    k = {"bau": {"wert": 1240, "einheit": "Wohnungen", "herkunft": "manuell", "quelle_id": 7,
                 "bezeichnung": "Baufertigstellungen Wohnungen", "kategorie": "2025", "gebiet": "Stadt"}}
    b = fuellen({"markt": saetze("{{wert:bau}} fertiggestellt.")}, k, {7: "Statistisches Landesamt, Stand 2025"},
                {"projekt"})
    assert b["abschnitte"]["markt"] == "1.240 Wohnungen[^1] fertiggestellt."
    assert b["fussnoten"][0]["verweis"] == ("Baufertigstellungen Wohnungen, 2025, Stadt, "
                                            "Quelle: Statistisches Landesamt, Stand 2025")
