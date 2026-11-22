"""Eigene Unterlagen: Dateityp am Inhalt erkennen, Text seitenweise lesen, in Abschnitte teilen, mit SQLite FTS5
suchen; Exposé-Parser (regelbasiert) und Prüfung der Modell-Ergänzungen. Alle Dokumente synthetisch (Musterstadt)."""
import datetime as dt

import pytest
from pdf_fakes import pdf
from sqlmodel import Session

from mietmarkt.db import engine
from mietmarkt.dokumente import abschnitte, art_erkennen, indexieren, seiten_lesen, suchen
from mietmarkt.expose import ergaenzen, parsen, zahl
from mietmarkt.modelle import Dokument, Herkunft, Projekt

EXPOSE = [("Musterweg 4, 12345 Musterstadt\nSchöne 3-Zimmer-Wohnung im Neubau\nWohnfläche: ca. 72,5 m²\n"
          "Kaltmiete: 1.250 €\nBaujahr 2025"),
          "Ausstattung: Balkon, Aufzug und Einbauküche\nRuhige Lage am Lindenpark"]


@pytest.mark.parametrize(("kopf", "art"), [(b"%PDF-1.4\n...", "pdf"), (b"\x89PNG\r\n\x1a\n...", "png"),
                                           (b"\xff\xd8\xff\xe0...", "jpg"), ("Wohnfläche 70 m²".encode(), "txt"),
                                           (b"MZ\x90\x00\x03\x00", None), (b"text\x00mit null", None)])
def test_art_am_inhalt_erkennen(kopf, art):
    """Der Dateityp kommt aus dem Inhalt, nicht aus Name oder Content-Type; Binärdaten sind kein Text."""
    assert art_erkennen(kopf) == art


def test_abschnitte_mit_ueberlappung():
    """Etwa 800 Zeichen je Abschnitt, Grenzen an Wortgrenzen, benachbarte Abschnitte überlappen."""
    text = " ".join(f"Wort{i}" for i in range(400))  # 3.089 Zeichen, Vorschub rund 650 je Abschnitt
    teile = abschnitte(text)
    assert len(teile) == 5 and all(len(t) <= 800 for t in teile)
    assert teile[0].split()[-1] in teile[1]  # Überlappung: das Ende des einen steht im nächsten
    assert " ".join(teile).count("Wort399") >= 1 and abschnitte("") == []


def test_pdf_seitenweise_lesen(tmp_path):
    """Jede PDF-Seite wird ein Text (Seitenzahl = Position + 1); TXT ist eine Seite."""
    (tmp_path / "e.pdf").write_bytes(pdf(EXPOSE))
    (tmp_path / "n.txt").write_text("Notiz: Aufzug fehlt", encoding="utf-8")
    assert seiten_lesen(tmp_path / "e.pdf", "pdf")[1].startswith("Ausstattung: Balkon")
    assert seiten_lesen(tmp_path / "n.txt", "txt") == ["Notiz: Aufzug fehlt"]


@pytest.fixture
def s(tmp_path):
    """Leere Datenbank mit zwei Projekten. Ausgabe: Session."""
    e = engine(tmp_path / "d.db")
    with Session(e) as s:
        for n in (1, 2):
            s.add(Projekt(name=f"P{n}", adresse="Musterweg 1", plz="12345", ort="Musterstadt", lat=51.3, lon=9.4,
                          stichtag=dt.date(2026, 11, 4), analysiert_am=dt.date(2026, 11, 4)))
        s.commit()
        yield s


def dokument(s, projekt_id: int, name: str, seiten: list[str]) -> Dokument:
    """Legt ein Dokument an und indexiert es. Ausgabe: Dokument."""
    d = Dokument(projekt_id=projekt_id, dateiname=name, pfad=f"uploads/{name}", art="pdf", seiten=len(seiten),
                 hochgeladen_am=dt.datetime.now(dt.UTC))
    s.add(d)
    s.commit()
    indexieren(s, d, seiten)
    return d


def test_fts5_suche_mit_dokument_seite_und_ausschnitt(s):
    """Treffer nennen Datei, Seite und Textausschnitt; Umlaute und Groß-/Kleinschreibung sind egal; fremde Projekte
    und nicht freigegebene Dokumente bleiben unsichtbar."""
    d = dokument(s, 1, "expose.pdf", EXPOSE)
    fremd = dokument(s, 2, "fremd.pdf", ["Balkon im fremden Projekt"])
    treffer = suchen(s, 1, "Gibt es einen BALKON?", {d.id, fremd.id})
    assert [(t["datei"], t["seite"]) for t in treffer] == [("expose.pdf", 2)]
    assert "Balkon, Aufzug" in treffer[0]["ausschnitt"]
    assert suchen(s, 1, "Wohnflache", {d.id})[0]["seite"] == 1  # ohne Umlaut gefunden
    assert suchen(s, 1, "Balkon", set()) == []


@pytest.mark.parametrize("frage", ['"; DROP TABLE x; --', "NEAR(a b) OR *", "Balkon AND", ")(", ""])
def test_suche_mit_sonderzeichen_stuerzt_nicht_ab(s, frage):
    """Modelltext wird nie als FTS5-Syntax ausgewertet: nur Wörter, je in Anführungszeichen."""
    d = dokument(s, 1, "expose.pdf", EXPOSE)
    assert isinstance(suchen(s, 1, frage, {d.id}), list)


def test_zahl_im_deutschen_format():
    """1.250 → 1250, 72,5 → 72,5, 1.250,50 → 1250,5; kein Zahltext → None."""
    assert (zahl("1.250"), zahl("72,5"), zahl("1.250,50"), zahl("3"), zahl("ca.")) == (1250, 72.5, 1250.5, 3, None)


def test_expose_parser_mit_seitenangabe():
    """Der Parser findet Wohnfläche, Kaltmiete, Zimmer, Baujahr und Ausstattung je mit Seite und Zitat."""
    aus = parsen(EXPOSE, "expose.pdf", quelle_id=7)
    f = aus["felder"]
    assert (f["wohnflaeche"].wert, f["kaltmiete"].wert, f["zimmer"].wert, f["baujahr"].wert) == (72.5, 1250, 3, 2025)
    assert f["wohnflaeche"].herkunft == Herkunft.IMPORT and f["wohnflaeche"].fundstelle == "S. 1"
    assert "„Wohnfläche: ca. 72,5 m²“" in f["wohnflaeche"].rechenweg_text and f["kaltmiete"].quelle_id == 7
    assert [(a["merkmal"], a["fundstelle"]) for a in aus["ausstattung"]] == [
        ("Balkon", "S. 2"), ("Aufzug", "S. 2"), ("Einbauküche", "S. 2")]


def test_parser_laesst_unbekanntes_leer():
    """Steht ein Feld nicht im Text, bleibt es leer (None) – erst dann darf das Modell ergänzen."""
    assert parsen(["Nur ein Satz ohne Angaben."], "x.pdf", None)["felder"]["kaltmiete"] is None


def test_ergaenzung_des_modells_wird_am_text_geprueft():
    """Eine Modell-Ergänzung gilt nur, wenn das Zitat wörtlich auf der genannten Seite steht und die Zahl im Zitat
    vorkommt; sie trägt Herkunft ki und die Seite."""
    seiten = ["Monatliche Miete netto kalt 1.180 Euro, zzgl. Nebenkosten"]
    w = ergaenzen("kaltmiete", "1.180", 1, "Miete netto kalt 1.180 Euro", seiten, "e.pdf", 7)
    assert w.wert == 1180 and w.herkunft == Herkunft.KI and w.fundstelle == "S. 1" and w.einheit == "€"
    assert ergaenzen("kaltmiete", "1.280", 1, "Miete netto kalt 1.180 Euro", seiten, "e.pdf", 7) is None  # Zahl falsch
    assert ergaenzen("kaltmiete", "1.180", 1, "Kaltmiete 1.180 €", seiten, "e.pdf", 7) is None  # Zitat erfunden
    assert ergaenzen("kaltmiete", "1.180", 2, "Miete netto kalt 1.180 Euro", seiten, "e.pdf", 7) is None  # Seite falsch


def test_fundstellen_falsch_fehlend_und_richtig():
    """Prüf-Agent: Eine Fundstelle, die in keinem Suchtreffer steht, und eine Aussage aus den Treffern ohne Fundstelle
    werden Befunde; korrekt belegte Sätze und Sätze aus anderen Werkzeugergebnissen nicht."""
    from mietmarkt.agenten.dokumente import fundstellen_befunde
    treffer = {"treffer": [{"datei": "expose.pdf", "seite": 2, "ausschnitt": "Kaltmiete 1.250 € inklusive Stellplatz"}]}
    ergebnisse = {"marktdaten": {"text": "Die Kaltmiete liegt bei 1.250 € [Quelle: expose.pdf, S. 2]. "
                                         "Laut Exposé kostet die Wohnung 1.250 €. Es gibt 12 Comps. "
                                         "Ein Stellplatz kostet extra [Quelle: expose.pdf, S. 7].",
                                 "werkzeuge": [{"name": "dokumente_suchen", "status": "success", "ergebnis": treffer},
                                               {"name": "kennzahlen", "status": "success", "ergebnis": {"n": "12 Comps"}}]},
                  "standort": {"text": "Kaltmiete 1.250 €.", "werkzeuge": []}}  # ohne Suche: nicht geprüft
    befunde = fundstellen_befunde(ergebnisse)
    assert [b["text"].split(" (")[0] for b in befunde] == ["Aussage aus den Unterlagen ohne Fundstelle",
                                                         "Fundstelle steht in keinem Suchtreffer"]
    assert all(b["pruefung"] == "fundstelle" and "(marktdaten)" in b["text"] for b in befunde)


def test_ablesung_nur_mit_zahl_und_ausschnitt_im_bild():
    """Vision: Herkunft abgelesen mit Ausschnitt; Werte ohne Zahl oder mit Ausschnitt außerhalb fallen heraus."""
    from mietmarkt.agenten.dokumente import ablesung
    gut = ablesung({"bezeichnung": "Leerstand", "wert": "2,1", "einheit": "%", "ausschnitt": [10, 5, 20, 8],
                    "diagramm": True}, (40, 20), "t.png", 3)
    assert (gut.wert, gut.herkunft, gut.ausschnitt) == (2.1, Herkunft.ABGELESEN, [10, 5, 20, 8])
    assert "rd., aus Diagramm" in gut.rechenweg_text
    from mietmarkt.agenten.bericht import anzeigen
    assert anzeigen(gut.model_dump(mode="json")) == "rd. 2,1 %"  # aus Diagrammen nur ungefähr
    for falsch in ({"wert": "k. A.", "ausschnitt": [0, 0, 5, 5]}, {"wert": "2", "ausschnitt": [30, 0, 20, 5]},
                   {"wert": "2", "ausschnitt": [0, 0, 0, 5]}, {"wert": "2", "ausschnitt": [1, 2]}):
        assert ablesung({"bezeichnung": "x", **falsch}, (40, 20), "t.png", 3) is None
