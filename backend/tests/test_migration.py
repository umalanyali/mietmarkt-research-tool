"""Schema-Nachzug beim Öffnen der Datenbank: neue Modellspalten kommen in bestehende Tabellen, ohne Datenverlust."""
import sqlite3

import pytest
from sqlmodel import Session, select

from mietmarkt.db import engine
from mietmarkt.demo import seed
from mietmarkt.modelle import Lauf, Projekt


def test_fehlende_spalten_werden_ergaenzt_daten_bleiben(tmp_path):
    """Eine Datenbank aus der Zeit vor vermarktungsstart, mietwachstum_pa und lauf.ergebnis: nach engine() sind die
    Spalten da (leer), Projekte und Läufe unverändert lesbar."""
    pfad = tmp_path / "alt.db"
    seed(engine(pfad))
    with sqlite3.connect(pfad) as c:
        vorher = c.execute("select id, name, lat from projekt order by id").fetchall()
        c.execute("insert into lauf (id, projekt_id, gestartet_am) values ('l1', 1, '2026-11-01 10:00:00')")
        for tabelle, spalte in (("projekt", "vermarktungsstart"), ("projekt", "mietwachstum_pa"), ("lauf", "ergebnis")):
            c.execute(f"alter table {tabelle} drop column {spalte}")
    e = engine(pfad)
    with Session(e) as s:
        projekte = s.exec(select(Projekt).order_by(Projekt.id)).all()
        assert [(p.id, p.name, p.lat) for p in projekte] == vorher
        assert projekte[0].vermarktungsstart is None and s.get(Lauf, "l1").ergebnis is None


def test_pflichtspalte_ohne_standard_bricht_mit_klarer_meldung_ab(tmp_path):
    """Eine fehlende NOT-NULL-Spalte ohne Standardwert lässt sich nicht anhängen: Start bricht verständlich ab."""
    pfad = tmp_path / "alt.db"
    engine(pfad)
    with sqlite3.connect(pfad) as c:
        c.execute("alter table projekt drop column ortsteil")
    with pytest.raises(RuntimeError, match="projekt.ortsteil"):
        engine(pfad)
