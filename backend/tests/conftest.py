"""Gemeinsame Testhilfen: synthetische Comps aus Musterstadt, ohne Datenbank."""
import datetime as dt

import pytest

from mietmarkt.modelle import Comp

STICHTAG = dt.date(2026, 11, 4)


def comp(nr: int, typ: str = "Regel", zimmer: float = 2, wfl: float = 60.0, kalt: float = 1000.0, tage: int | None = 20,
         anfragen: int | None = 10, baujahr: int | None = 2025, lat: float = 51.3127, lon: float = 9.4797) -> Comp:
    """Baut einen Comp mit sinnvollen Standardwerten. Eingabe: abweichende Felder. Ausgabe: Comp (nicht gespeichert)."""
    online = None if tage is None else STICHTAG - dt.timedelta(days=tage)
    return Comp(projekt_id=1, nr=nr, objekt=f"Musterweg {nr}", anbieter="Beispiel Wohnbau", typ=typ, zimmer=zimmer,
                baujahr=baujahr, wohnflaeche=wfl, kaltmiete=kalt, online_seit=online, anfragen=anfragen,
                lat=lat, lon=lon, herkunft="import")


@pytest.fixture
def stichtag() -> dt.date:
    """Einheitlicher Stichtag der Tests."""
    return STICHTAG
