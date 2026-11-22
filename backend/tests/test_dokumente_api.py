"""Upload eigener Unterlagen: POST /api/projekte/{id}/dokumente für PDF, PNG/JPG und Text; Ablage unter daten/uploads/."""
import io

import pytest
from fastapi.testclient import TestClient
from pdf_fakes import pdf
from PIL import Image
from sqlmodel import Session, select

from api import main
from mietmarkt.db import engine
from mietmarkt.demo import seed
from mietmarkt.dokumente import suchen
from mietmarkt.modelle import Dokument, Quelle


@pytest.fixture
def umgebung(tmp_path):
    """API auf einer Demo-Datenbank im Testordner (Uploads landen in tmp_path/uploads). Ausgabe: (Client, Engine)."""
    e = engine(tmp_path / "api.db")
    seed(e)

    def test_sitzung():
        """Sitzung auf die Testdatenbank. Ausgabe: Session (als Generator)."""
        with Session(e) as s:
            yield s

    main.app.dependency_overrides[main.sitzung] = test_sitzung
    yield TestClient(main.app, base_url="http://localhost"), e
    main.app.dependency_overrides.clear()


def hochladen(client, name: str, daten: bytes, projekt: int = 1, **form):
    """Lädt eine Datei hoch. Ausgabe: Antwort."""
    return client.post(f"/api/projekte/{projekt}/dokumente", files={"datei": (name, daten)}, data=form)


def png(breite: int = 40, hoehe: int = 20) -> bytes:
    """Kleines PNG. Ausgabe: Dateiinhalt."""
    puffer = io.BytesIO()
    Image.new("RGB", (breite, hoehe), (243, 241, 236)).save(puffer, "PNG")
    return puffer.getvalue()


def test_pdf_hochladen_speichert_und_indexiert(umgebung, tmp_path):
    """Ein PDF wird unter zufälligem Namen in uploads/<projekt>/ abgelegt, als Quelle eingetragen und durchsuchbar."""
    client, e = umgebung
    antwort = hochladen(client, "Exposé Musterweg.pdf", pdf(["Wohnfläche 72,5 m²", "Balkon nach Süden"]),
                        ki_freigabe="true")
    assert antwort.status_code == 201
    d = antwort.json()
    assert (d["dateiname"], d["art"], d["seiten"], d["ki_freigabe"]) == ("Exposé Musterweg.pdf", "pdf", 2, True)
    with Session(e) as s:
        dok = s.get(Dokument, d["id"])
        assert (tmp_path / dok.pfad).is_file() and dok.pfad.startswith("uploads/1/") and "Expos" not in dok.pfad
        assert s.get(Quelle, dok.quelle_id).datei == "Exposé Musterweg.pdf"
        assert suchen(s, 1, "Balkon", {dok.id})[0]["seite"] == 2


def test_bild_und_text_werden_angenommen(umgebung):
    """PNG wird gespeichert (ohne Text, den liest später der Vision-Agent), TXT wird eine Seite."""
    client, _ = umgebung
    assert hochladen(client, "tabelle.png", png()).json()["art"] == "png"
    t = hochladen(client, "notiz.txt", b"Aufzug fehlt im Haus").json()
    assert (t["art"], t["seiten"], t["abschnitte"], t["ki_freigabe"]) == ("txt", 1, 1, False)


@pytest.mark.parametrize(("name", "daten", "status"), [
    ("tarnung.pdf", b"MZ\x90\x00\x03\x00\x00\x00" * 10, 415),  # Programmdatei mit PDF-Namen
    ("gross.txt", b"a" * (main.MAX_UPLOAD_BYTES + 1), 413),
    ("kaputt.pdf", b"%PDF-1.4\nnichts als Unsinn", 422),
    ("kaputt.png", b"\x89PNG\r\n\x1a\nkein Bild", 422),
])
def test_ungueltige_dateien_werden_abgelehnt(umgebung, tmp_path, name, daten, status):
    """Typ am Inhalt, Größengrenze, unlesbare Dateien – abgelehnt, ohne eine Datei zu hinterlassen."""
    client, _ = umgebung
    assert hochladen(client, name, daten).status_code == status
    assert not list((tmp_path / "uploads").rglob("*.*"))


def test_dateiname_mit_pfad_bleibt_nur_anzeige(umgebung, tmp_path):
    """„../../x.txt“ landet nicht außerhalb von uploads/: gespeichert wird unter zufälligem Namen."""
    client, e = umgebung
    d = hochladen(client, "../../boese.txt", b"Text").json()
    assert d["dateiname"] == "boese.txt"
    with Session(e) as s:
        assert all(x.pfad.startswith("uploads/1/") for x in s.exec(select(Dokument)))
    assert not (tmp_path.parent / "boese.txt").exists()


def test_unbekanntes_projekt_404(umgebung):
    """Hochladen in ein fehlendes Projekt ergibt 404."""
    client, _ = umgebung
    assert hochladen(client, "a.txt", b"Text", projekt=999).status_code == 404
