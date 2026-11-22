"""Lauf-API: Start, Ereignisstrom (Server-Sent Events) und „KI nicht konfiguriert“ – mit Fake-Modellen."""
import json

import pytest
from fastapi.testclient import TestClient
from ki_fakes import befunde, bericht, entscheidung, ki, modelle
from sqlmodel import Session, select

from api import main
from mietmarkt.db import engine
from mietmarkt.demo import seed
from mietmarkt.konfig import Konfig
from mietmarkt.modelle import Wohnung


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
        # Kurzer Lauf bis zum Ende: Marktdaten, dann eine unlesbare Supervisor-Antwort (Abbruch)
        main.ki_modelle: lambda: modelle(stark=[entscheidung("marktdaten"), ki("Ich weiß nicht weiter.")],
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
    assert ende["status"] == "abgebrochen" and ende["kosten_eur"] > 0  # Skript endet mit unlesbarer Antwort


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


@pytest.fixture
def mit_freigabe(client):
    """Ein Skript bis zum Bericht; dieselben Fake-Modelle für alle Anfragen (das Skript läuft über mehrere Abrufe).
    Ausgabe: Modelle."""
    m = modelle(stark=[entscheidung("standort"), entscheidung("marktdaten"), entscheidung("mietansatz"), ki(werkzeuge=(
        ("mietansatz_herleiten", {"basis": "regel_eg", "anpassungen": []}),
        ("mietansatz_herleiten", {"basis": "dg", "anpassungen": []}))), ki("Basis ohne Zu- und Abschläge."),
        befunde("hinweis"), bericht()],
        schnell=[ki("Standort."), ki(werkzeuge=(("kennzahlen", {}),)), ki("12 Comps im Umkreis.")])
    main.app.dependency_overrides[main.ki_modelle] = lambda: m
    return m


def test_lauf_wartet_auf_freigabe_und_setzt_fort(client, mit_freigabe):
    """Der Strom endet mit „wartet_auf_freigabe“ samt Vorschlag; ein erneuter Abruf zeigt ihn wieder, ohne Modell-
    aufruf. POST /freigabe setzt fort: Freigabe, Prüfung, Bericht, zum Schluss „fertig“ mit Bericht."""
    lauf_id = client.post("/api/projekte/1/laeufe").json()["lauf_id"]
    erst = ereignisse(client.get(f"/api/laeufe/{lauf_id}/ereignisse"))
    assert erst[-1]["typ"] == "wartet_auf_freigabe"
    assert erst[-1]["vorschlag"]["herleitungen"]["regel_eg"]["schritte"][0]["art"] == "basis"
    aufrufe = mit_freigabe.stark.i
    assert ereignisse(client.get(f"/api/laeufe/{lauf_id}/ereignisse"))[-1]["typ"] == "wartet_auf_freigabe"
    assert mit_freigabe.stark.i == aufrufe
    weiter = ereignisse(client.post(f"/api/laeufe/{lauf_id}/freigabe", json={"aktion": "annehmen"}))
    typen = [e["typ"] for e in weiter]
    assert typen.index("freigabe") < typen.index("pruefung") < typen.index("bericht") < typen.index("fertig")
    assert weiter[-1]["status"] == "fertig" and weiter[-1]["bericht"]["fussnoten"]
    assert [b["schweregrad"] for b in weiter[typen.index("pruefung")]["befunde"]] == ["hinweis"]


def test_bericht_export_markdown_und_pptx(client, mit_freigabe):
    """Nach dem Lauf liegt der Bericht als Markdown und PowerPoint zum Herunterladen bereit; vorher 404."""
    lauf_id = client.post("/api/projekte/1/laeufe").json()["lauf_id"]
    client.get(f"/api/laeufe/{lauf_id}/ereignisse")
    assert client.get(f"/api/laeufe/{lauf_id}/bericht.md").status_code == 404
    client.post(f"/api/laeufe/{lauf_id}/freigabe", json={"aktion": "annehmen"})
    md = client.get(f"/api/laeufe/{lauf_id}/bericht.md")
    assert md.status_code == 200 and md.text.startswith("# Mietmarktbericht: ") and "attachment" in md.headers["content-disposition"]
    folien = client.get(f"/api/laeufe/{lauf_id}/bericht.pptx")
    assert folien.status_code == 200 and folien.content[:2] == b"PK"  # .pptx ist ein ZIP-Archiv
    assert "presentationml" in folien.headers["content-type"]


def test_freigabe_nur_wenn_der_lauf_wartet(client, mit_freigabe):
    """Unbekannter Lauf 404; nicht gestartet oder schon fertig 409; unvollständige Freigabe 422 (Lauf wartet weiter)."""
    assert client.post("/api/laeufe/gibt-es-nicht/freigabe", json={"aktion": "annehmen"}).status_code == 404
    lauf_id = client.post("/api/projekte/1/laeufe").json()["lauf_id"]
    assert client.post(f"/api/laeufe/{lauf_id}/freigabe", json={"aktion": "annehmen"}).status_code == 409
    client.get(f"/api/laeufe/{lauf_id}/ereignisse")
    assert client.post(f"/api/laeufe/{lauf_id}/freigabe", json={"aktion": "ablehnen"}).status_code == 422
    # Basis, die im Vorschlag nicht vorkommt (hier: unbekannter Schlüssel) → 422, der Lauf wartet weiter
    assert client.post(f"/api/laeufe/{lauf_id}/freigabe", json={"aktion": "aendern", "aenderungen": {
        "og": {"basiswert": 16}}}).status_code == 422
    assert client.post(f"/api/laeufe/{lauf_id}/freigabe", json={"aktion": "annehmen"}).status_code == 200
    assert client.post(f"/api/laeufe/{lauf_id}/freigabe", json={"aktion": "annehmen"}).status_code == 409


def test_rueckfrage_beantworten(client):
    """Bei einer Rückfrage endet der Strom mit „wartet_auf_antwort“. POST /antwort setzt fort (Ereignis „antwort“);
    eine Freigabe passt dann nicht (409), eine leere Antwort ist ungültig (422)."""
    m = modelle(stark=[entscheidung("fertig", rueckfrage="Welches Baujahr?"), ki("unlesbar")], schnell=[])
    main.app.dependency_overrides[main.ki_modelle] = lambda: m
    lauf_id = client.post("/api/projekte/1/laeufe").json()["lauf_id"]
    alle = ereignisse(client.get(f"/api/laeufe/{lauf_id}/ereignisse"))
    assert {"typ": "rueckfrage", "text": "Welches Baujahr?"} in alle
    assert alle[-1] == {"typ": "wartet_auf_antwort", "art": "rueckfrage", "frage": "Welches Baujahr?"}
    assert client.post(f"/api/laeufe/{lauf_id}/freigabe", json={"aktion": "annehmen"}).status_code == 409
    assert client.post(f"/api/laeufe/{lauf_id}/antwort", json={"antwort": ""}).status_code == 422
    weiter = ereignisse(client.post(f"/api/laeufe/{lauf_id}/antwort", json={"antwort": "Baujahr 2027"}))
    assert {"typ": "antwort", "antwort": "Baujahr 2027"} in weiter
    assert weiter[-1]["typ"] == "fertig"
    assert client.post(f"/api/laeufe/{lauf_id}/antwort", json={"antwort": "nochmal"}).status_code == 409


def test_aenderung_fuer_basis_ohne_herleitung(client):
    """Ein Projekt ohne DG-Wohnungen hat nur den Haupt-Ansatz: eine Änderung für dg wird mit 422 abgelehnt."""
    s = next(main.app.dependency_overrides[main.sitzung]())  # Sitzung auf die Testdatenbank des Fixtures
    for w in s.exec(select(Wohnung).where(Wohnung.typ == "DG")):
        s.delete(w)
    s.commit()
    m = modelle(stark=[entscheidung("standort"), entscheidung("marktdaten"), entscheidung("mietansatz"), ki(werkzeuge=(
        ("mietansatz_herleiten", {"basis": "regel_eg", "anpassungen": []}),)), ki("Nur Haupt-Ansatz.")],
        schnell=[ki("Standort."), ki("12 Comps.")])
    main.app.dependency_overrides[main.ki_modelle] = lambda: m
    lauf_id = client.post("/api/projekte/1/laeufe").json()["lauf_id"]
    assert ereignisse(client.get(f"/api/laeufe/{lauf_id}/ereignisse"))[-1]["typ"] == "wartet_auf_freigabe"
    antwort = client.post(f"/api/laeufe/{lauf_id}/freigabe", json={"aktion": "aendern",
                                                                   "aenderungen": {"dg": {"basiswert": 19}}})
    assert antwort.status_code == 422 and "dg" in antwort.json()["detail"]


def test_export_ohne_projekt_ist_404(client, mit_freigabe):
    """P16: Wurde das Projekt gelöscht, liefert der Export 404 statt eines Absturzes."""
    from mietmarkt.modelle import Projekt
    lauf_id = client.post("/api/projekte/1/laeufe").json()["lauf_id"]
    client.get(f"/api/laeufe/{lauf_id}/ereignisse")
    client.post(f"/api/laeufe/{lauf_id}/freigabe", json={"aktion": "annehmen"})
    s = next(main.app.dependency_overrides[main.sitzung]())
    s.delete(s.get(Projekt, 1))
    s.commit()
    assert client.get(f"/api/laeufe/{lauf_id}/bericht.md").status_code == 404


def test_lauf_wird_auch_ohne_gestarteten_strom_freigegeben(client, tmp_path):
    """S1: Bricht der Browser ab, bevor der Strom beginnt, läuft der Generator nie. Die Freigabe des Laufs hängt
    deshalb an einer Hintergrundaufgabe der Antwort, die Starlette auch dann ausführt."""
    import asyncio

    from mietmarkt.modelle import Lauf
    s = next(main.app.dependency_overrides[main.sitzung]())
    lauf = Lauf(id="s1", projekt_id=1, gestartet_am=__import__("datetime").datetime.now(__import__("datetime").UTC))
    s.add(lauf)
    s.commit()
    antwort = main._ausfuehren(lauf, s.get_bind(), Konfig(_env_file=None, anthropic_api_key="test"),
                               modelle(stark=[], schnell=[]), tmp_path / "cp.db", None)
    assert "s1" in main.aktive_laeufe
    asyncio.run(antwort.background())
    assert "s1" not in main.aktive_laeufe
