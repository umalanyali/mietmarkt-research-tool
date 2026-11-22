"""K: Importierte Portal-Daten (RIWIS, VALUE, Portal-Exporte) gehen standardmäßig nicht an Anthropic.
Erlaubt sind Demo-Daten und selbst erfasste Werte; der Schalter KI_PORTALDATEN_SENDEN gibt alles frei."""
import datetime as dt
import json

import pytest
from conftest import comp
from sqlmodel import Session

from mietmarkt.agenten.werkzeuge import werkzeuge
from mietmarkt.db import engine
from mietmarkt.demo import seed
from mietmarkt.konfig import Konfig
from mietmarkt.modelle import Marktkennzahl, Projekt


@pytest.fixture
def db(tmp_path):
    """Demo-Daten plus ein echtes Projekt mit einem importierten und einem selbst erfassten Comp. Ausgabe: (Engine, ID)."""
    e = engine(tmp_path / "portal.db")
    seed(e)
    with Session(e) as s:
        p = Projekt(name="Feldweg 3", adresse="Feldweg 3", plz="99998", ort="Fernstadt", lat=53.0, lon=10.0,
                    stichtag=dt.date(2026, 11, 22), analysiert_am=dt.date(2026, 11, 22))
        s.add(p)
        s.commit()
        importiert, selbst = comp(1, lat=53.001, lon=10.0), comp(2, lat=53.002, lon=10.0)
        selbst.herkunft = "manuell"
        for c in (importiert, selbst):
            c.projekt_id = p.id
            s.add(c)
        s.add(Marktkennzahl(projekt_id=p.id, gruppe="weitere", bezeichnung="Kaufkraftindex", kategorie="",
                            gebiet="Fernstadt", wert=101.5, einheit="", herkunft="import"))
        s.commit()
        return e, p.id


def kennzahlen(e, projekt_id, senden: bool) -> dict:
    """Ruft das Werkzeug kennzahlen direkt auf. Ausgabe: Ergebnis als dict."""
    k = Konfig(_env_file=None, anthropic_api_key="test", ki_portaldaten_senden=senden)
    werkzeug = next(w for w in werkzeuge(e, k)["marktdaten"] if w.name == "kennzahlen")
    return json.loads(werkzeug.invoke({"projekt_id": projekt_id}))


def test_ohne_freigabe_nur_selbst_erfasste_werte(db):
    """Standard: Der importierte Comp und die importierte Marktkennzahl bleiben lokal; das Werkzeug sagt das offen."""
    e, pid = db
    aus = kennzahlen(e, pid, senden=False)
    assert aus["comps"]["anzahl"]["wert"] == 1 and aus["marktkennzahlen"] == []
    assert aus["zurueckgehalten"] == {"comps": 1, "marktkennzahlen": 1}
    assert "KI_PORTALDATEN_SENDEN" in aus["hinweis"]


def test_mit_freigabe_alles(db):
    """KI_PORTALDATEN_SENDEN=true gibt importierte Daten frei."""
    e, pid = db
    aus = kennzahlen(e, pid, senden=True)
    assert aus["comps"]["anzahl"]["wert"] == 2 and len(aus["marktkennzahlen"]) == 1 and "zurueckgehalten" not in aus


def test_demo_daten_immer_erlaubt(db):
    """Demo-Projekte sind synthetisch und gehen auch ohne Freigabe vollständig an das Modell."""
    e, _ = db
    aus = kennzahlen(e, 1, senden=False)
    assert aus["comps"]["anzahl"]["wert"] == 12 and aus["marktkennzahlen"] and "zurueckgehalten" not in aus
