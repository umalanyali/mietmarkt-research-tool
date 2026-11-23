"""Tests für das Übernehmen des Umfelds aus einer echten Datenbank in den Fake-Server (README-Aufnahmen ohne Overpass)."""
import datetime as dt

import pytest
from fake_server import umfeld_uebernehmen
from sqlmodel import Session

from mietmarkt.db import engine
from mietmarkt.demo import seed
from mietmarkt.modelle import Projekt, UmfeldCache


def _quelle(pfad, abgerufen_am: dt.date, lat: float) -> None:
    """Legt eine Quelldatenbank mit einem Umfeld-Eintrag an. Eingabe: Pfad, Abrufdatum, Breitengrad. Ausgabe: keine."""
    with Session(engine(pfad)) as s:
        s.add(UmfeldCache(projekt_id=7, lat=lat, lon=9.4797, abgerufen_am=abgerufen_am, umfeld_json='{"x": 1}'))
        s.commit()


def test_umfeld_wird_zum_projekt_mit_gleichen_koordinaten_kopiert(tmp_path):
    """Der Eintrag mit den Koordinaten des Demo-Projekts landet unter dessen ID in der Fake-Datenbank."""
    ziel = engine(tmp_path / "ziel.db")
    seed(ziel)
    with Session(ziel) as s:
        demo = s.get(Projekt, 1)
    _quelle(tmp_path / "quelle.db", dt.date.today(), demo.lat)
    umfeld_uebernehmen(tmp_path / "quelle.db", ziel)
    with Session(ziel) as s:
        assert s.get(UmfeldCache, 1).umfeld_json == '{"x": 1}'


@pytest.mark.parametrize(("alter", "lat"), [(31, None), (0, 50.0)])
def test_veraltetes_oder_fremdes_umfeld_bricht_ab(tmp_path, alter, lat):
    """Älter als 30 Tage oder andere Koordinaten: Abbruch statt stillem Overpass-Abruf während der Aufnahme."""
    ziel = engine(tmp_path / "ziel.db")
    seed(ziel)
    with Session(ziel) as s:
        demo = s.get(Projekt, 1)
    _quelle(tmp_path / "quelle.db", dt.date.today() - dt.timedelta(days=alter), lat or demo.lat)
    with pytest.raises(SystemExit):
        umfeld_uebernehmen(tmp_path / "quelle.db", ziel)
