"""Demo-Datensatz Musterstadt: Seed in eine leere Datenbank, wiederholbar, jede Zahl mit Herkunft und Quelle."""
import datetime as dt
import subprocess
import sys

from sqlmodel import Session, select

from mietmarkt.db import engine
from mietmarkt.demo import demo_oeffnen, seed
from mietmarkt.modelle import Comp, Marktkennzahl, Projekt, Quelle


def test_seed_legt_projekte_comps_und_kennzahlen_an(tmp_path):
    """Drei Projekte; Lindenquartier mit 12 Comps, Quellen und Kennzahlen."""
    e = engine(tmp_path / "t.db")
    seed(e)
    with Session(e) as s:
        projekte = s.exec(select(Projekt)).all()
        assert [p.name for p in projekte] == ["Lindenquartier", "Hafenblock", "Am Stadtpark"]
        linden = projekte[0]
        assert len(s.exec(select(Comp).where(Comp.projekt_id == linden.id)).all()) == 12
        assert s.exec(select(Marktkennzahl).where(Marktkennzahl.gruppe == "soziodemografie")).first() is not None


def test_jede_zahl_hat_herkunft_und_quelle(tmp_path):
    """Regel 1: alle Kennzahlen und Comps verweisen auf eine Quelle des eigenen Projekts."""
    e = engine(tmp_path / "t.db")
    seed(e)
    with Session(e) as s:
        quellen = {q.id: q.projekt_id for q in s.exec(select(Quelle)).all()}
        for k in s.exec(select(Marktkennzahl)).all():
            assert k.herkunft and quellen.get(k.quelle_id) == k.projekt_id, k.bezeichnung
        for c in s.exec(select(Comp)).all():
            assert quellen.get(c.quelle_id) == c.projekt_id and c.fundstelle


def test_seed_ist_wiederholbar(tmp_path):
    """Zweimal seeden ergibt denselben Bestand, keine Dubletten."""
    e = engine(tmp_path / "t.db")
    seed(e)
    seed(e)
    with Session(e) as s:
        assert len(s.exec(select(Comp)).all()) == 12


def test_befehl_seed_auf_der_kommandozeile(tmp_path):
    """python -m mietmarkt.demo seed --db <pfad> legt die Datenbank an."""
    pfad = tmp_path / "cli.db"
    lauf = subprocess.run([sys.executable, "-m", "mietmarkt.demo", "seed", "--db", str(pfad)], capture_output=True, text=True, check=False)
    assert lauf.returncode == 0, lauf.stderr
    assert pfad.exists() and "3 Projekte" in lauf.stdout


def test_demo_oeffnen_ergaenzt_ohne_zu_loeschen(tmp_path):
    """demo_oeffnen legt die Demo nur an, wenn sie fehlt, und lässt eigene Projekte stehen."""
    e = engine(tmp_path / "t.db")
    with Session(e) as s:
        s.add(Projekt(name="Eigenes", adresse="Musterweg 1", plz="99999", ort="Hafenstadt", ortsteil="Mitte", lat=51.0,
                      lon=9.0, stichtag=dt.date(2026, 11, 4), analysiert_am=dt.date(2026, 11, 4)))
        s.commit()
        erste = demo_oeffnen(s)
        zweite = demo_oeffnen(s)
        namen = [p.name for p in s.exec(select(Projekt)).all()]
        assert erste == zweite and s.get(Projekt, erste).name == "Lindenquartier"
    assert namen == ["Eigenes", "Lindenquartier", "Hafenblock", "Am Stadtpark"]
