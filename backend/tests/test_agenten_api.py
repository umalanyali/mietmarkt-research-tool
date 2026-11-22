"""Lauf-API: Start, Ereignisstrom (Server-Sent Events) und „KI nicht konfiguriert“ – mit Fake-Modellen."""
import json

import pytest
from fastapi.testclient import TestClient
from ki_fakes import entscheidung, ki, modelle
from sqlmodel import Session

from api import main
from mietmarkt.db import engine
from mietmarkt.demo import seed
from mietmarkt.konfig import Konfig


@pytest.fixture
def client(tmp_path):
    """API mit Demo-Datenbank, Fake-Modellen und eigener Checkpoint-Datei. Ausgabe: TestClient."""
    e = engine(tmp_path / "api.db")
    seed(e)

    def test_sitzung():
        """Sitzung auf die Testdatenbank. Ausgabe: Session (als Generator)."""
        with Session(e) as s:
            yield s

    main.app.dependency_overrides.update({
        main.sitzung: test_sitzung,
        main.konfig: lambda: Konfig(_env_file=None, anthropic_api_key="test"),
        main.ki_modelle: lambda: modelle(stark=[entscheidung("marktdaten"), entscheidung("fertig", rueckfrage="Weiter?")],
                                         schnell=[ki(werkzeuge=(("kennzahlen", {}),)), ki("12 Comps im Umkreis.")]),
        main.checkpoint_pfad: lambda: tmp_path / "checkpoints.db",
    })
    yield TestClient(main.app, base_url="http://localhost")
    main.app.dependency_overrides.clear()


def ereignisse(antwort) -> list[dict]:
    """Zerlegt einen SSE-Strom. Eingabe: Antwort. Ausgabe: Liste der Ereignisse (data als dict)."""
    return [json.loads(z.removeprefix("data: ")) for z in antwort.text.splitlines() if z.startswith("data: ")]


def test_lauf_starten_und_ereignisse_streamen(client):
    """Ein Lauf liefert Agentenstart, Werkzeugaufruf und -ergebnis, Agent fertig, Kosten und zum Schluss „fertig“."""
    antwort = client.post("/api/projekte/1/laeufe")
    assert antwort.status_code == 201
    lauf_id = antwort.json()["lauf_id"]
    strom = client.get(f"/api/laeufe/{lauf_id}/ereignisse")
    assert strom.headers["content-type"].startswith("text/event-stream")
    typen = [e["typ"] for e in ereignisse(strom)]
    for typ in ("agent_gestartet", "werkzeugaufruf", "werkzeugergebnis", "agent_fertig", "kosten"):
        assert typ in typen
    assert typen[-1] == "fertig"
    assert typen.index("agent_gestartet") < typen.index("werkzeugaufruf") < typen.index("agent_fertig")
    ende = ereignisse(strom)[-1]
    assert ende["status"] == "fertig" and ende["kosten_eur"] > 0


def test_beendeter_lauf_liefert_nur_das_ergebnis(client):
    """Ein zweiter Abruf eines fertigen Laufs startet nichts neu, sondern meldet nur den Endstand aus dem Checkpoint."""
    lauf_id = client.post("/api/projekte/1/laeufe").json()["lauf_id"]
    client.get(f"/api/laeufe/{lauf_id}/ereignisse")
    assert [e["typ"] for e in ereignisse(client.get(f"/api/laeufe/{lauf_id}/ereignisse"))] == ["fertig"]


def test_unbekannter_lauf_und_projekt_sind_404(client):
    """Unbekannte IDs ergeben 404."""
    assert client.get("/api/laeufe/gibt-es-nicht/ereignisse").status_code == 404
    assert client.post("/api/projekte/999/laeufe").status_code == 404


def test_ohne_schluessel_ki_nicht_konfiguriert(client):
    """Ohne ANTHROPIC_API_KEY startet die App trotzdem; ein Lauf meldet 503 „KI nicht konfiguriert“."""
    main.app.dependency_overrides[main.konfig] = lambda: Konfig(_env_file=None, anthropic_api_key=None)
    antwort = client.post("/api/projekte/1/laeufe")
    assert antwort.status_code == 503 and antwort.json()["detail"] == "KI nicht konfiguriert"
    assert client.get("/api/gesundheit").json()["ki"] is False


@pytest.mark.parametrize("feld", ["modell_stark", "modell_schnell"])
def test_modell_ohne_preis_wird_vor_jedem_aufruf_abgelehnt(client, feld):
    """A: Ohne Preis kein Budget – ein solcher Lauf startet gar nicht erst (503), statt unbezahlt mitzuzählen."""
    main.app.dependency_overrides[main.konfig] = lambda: Konfig(_env_file=None, anthropic_api_key="test",
                                                               **{feld: "claude-sonnet-5-5-20261101"})
    antwort = client.post("/api/projekte/1/laeufe")
    assert antwort.status_code == 503 and "Kein Preis" in antwort.json()["detail"]


def test_ki_problem_der_konfig():
    """A: Die Konfig nennt den Grund, warum die KI nicht nutzbar ist (oder None)."""
    assert Konfig(_env_file=None, anthropic_api_key=None).ki_problem == "KI nicht konfiguriert"
    assert "claude-x" in Konfig(_env_file=None, anthropic_api_key="test", modell_schnell="claude-x").ki_problem
    assert Konfig(_env_file=None, anthropic_api_key="test").ki_problem is None


def test_laufender_lauf_kann_nicht_doppelt_starten(client):
    """B: Läuft ein Lauf schon (zweiter Tab, Neuverbindung), gibt es 409 statt eines zweiten, bezahlten Durchgangs."""
    lauf_id = client.post("/api/projekte/1/laeufe").json()["lauf_id"]
    main.aktive_laeufe.add(lauf_id)
    try:
        assert client.get(f"/api/laeufe/{lauf_id}/ereignisse").status_code == 409
    finally:
        main.aktive_laeufe.discard(lauf_id)
    client.get(f"/api/laeufe/{lauf_id}/ereignisse")
    assert lauf_id not in main.aktive_laeufe  # nach dem Strom wieder frei


def test_fertiger_lauf_braucht_keinen_schluessel_und_raeumt_auf(client, tmp_path):
    """Sicherheit 6/7: Der Endstand liegt danach in der Tabelle lauf, der Checkpoint ist gelöscht, und der Abruf
    eines fertigen Laufs geht auch ohne Schlüssel."""
    import asyncio

    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    lauf_id = client.post("/api/projekte/1/laeufe").json()["lauf_id"]
    client.get(f"/api/laeufe/{lauf_id}/ereignisse")

    async def checkpoint():
        """Liest den letzten Checkpoint des Laufs. Ausgabe: Checkpoint-Tupel oder None."""
        async with AsyncSqliteSaver.from_conn_string(str(tmp_path / "checkpoints.db")) as cp:
            return await cp.aget_tuple({"configurable": {"thread_id": lauf_id}})

    assert asyncio.run(checkpoint()) is None
    main.app.dependency_overrides[main.konfig] = lambda: Konfig(_env_file=None, anthropic_api_key=None)
    main.app.dependency_overrides[main.ki_modelle] = lambda: None
    ende = ereignisse(client.get(f"/api/laeufe/{lauf_id}/ereignisse"))
    assert [e["typ"] for e in ende] == ["fertig"] and ende[0]["ergebnisse"]["marktdaten"]["text"]


def test_fehlermeldung_ohne_interna(client):
    """Sicherheit 8: Ein Absturz wird als feste Meldung mit Fehlerart gestreamt, Details nur ins lokale Log."""
    main.app.dependency_overrides[main.ki_modelle] = lambda: modelle(stark=[entscheidung("marktdaten")], schnell=[],
                                                                     schnell_fehler=True)
    lauf_id = client.post("/api/projekte/1/laeufe").json()["lauf_id"]
    fehler = ereignisse(client.get(f"/api/laeufe/{lauf_id}/ereignisse"))[-1]
    assert fehler["typ"] == "fehler" and "RuntimeError" in fehler["meldung"]
    assert "simulierter Absturz" not in fehler["meldung"]


def test_text_wird_in_stuecken_gestreamt(client):
    """J: Wie beim echten Claude kommt der Agententext in Stücken; zusammengesetzt ergibt er die Schlussantwort."""
    lauf_id = client.post("/api/projekte/1/laeufe").json()["lauf_id"]
    alle = ereignisse(client.get(f"/api/laeufe/{lauf_id}/ereignisse"))
    stuecke = [e["text"] for e in alle if e["typ"] == "text" and e["agent"] == "marktdaten"]
    assert len(stuecke) > 1 and "".join(stuecke) == "12 Comps im Umkreis."
