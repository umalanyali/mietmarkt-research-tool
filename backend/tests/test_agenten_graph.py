"""Analyse-Graph mit Fake-Modellen: läuft komplett ohne Netz (Geodienste über respx) und ohne API-Schlüssel."""
import asyncio
import json

import httpx
import pytest
import respx
from ki_fakes import entscheidung, ki, modelle
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from sqlmodel import Session

from mietmarkt.agenten.graph import MAX_RUNDEN, baue_graph, lauf_konfig, startzustand
from mietmarkt.agenten.werkzeuge import werkzeuge
from mietmarkt.db import engine
from mietmarkt.demo import seed
from mietmarkt.geo import dienste
from mietmarkt.konfig import Konfig
from mietmarkt.modelle import Projekt

KONFIG = Konfig(_env_file=None, anthropic_api_key="test", ki_budget_eur_pro_lauf=0.5, ki_eur_je_usd=1.0)
ANPASSUNG = {"name": "Neubau-Zuschlag", "betrag": 0.5, "begruendung": "Erstbezug mit Aufzug"}


@pytest.fixture
def db(tmp_path):
    """Demo-Datenbank (Projekt 1 mit 12 Comps im Umkreis). Ausgabe: Engine."""
    e = engine(tmp_path / "lauf.db")
    seed(e)
    for d in (dienste.PHOTON_DROSSEL, dienste.NOMINATIM_DROSSEL, dienste.OVERPASS_DROSSEL, dienste.ROUTING_DROSSEL):
        d.zuruecksetzen()
    return e


def geodienste_mocken():
    """Overpass liefert eine Haltestelle, OSRM 120 s zu Fuß und 60 s mit dem Rad."""
    respx.post(dienste.OVERPASS_URL).mock(return_value=httpx.Response(200, json={"elements": [
        {"type": "node", "lat": 51.3130, "lon": 9.4800, "tags": {"highway": "bus_stop", "name": "Lindenplatz"}}]}))
    for profil, dauer in (("fuss", 120.0), ("rad", 60.0)):
        respx.get(url__startswith=dienste.ROUTING_URL[profil]).mock(
            return_value=httpx.Response(200, json={"code": "Ok", "durations": [[0, dauer]], "distances": [[0, 150.0]]}))


def voller_lauf():
    """Skript für einen vollständigen Lauf: Standort → Marktdaten → Mietansatz → fertig. Ausgabe: Modelle."""
    return modelle(
        stark=[entscheidung("standort"), entscheidung("marktdaten"), entscheidung("mietansatz"),
               ki(werkzeuge=(("mietansatz_herleiten", {"basis": "regel_eg", "anpassungen": [ANPASSUNG]}),)),
               ki("Mietansatz siehe Herleitung."), entscheidung("fertig")],
        schnell=[ki(werkzeuge=(("lage", {}), ("umfeld", {}))), ki("Haltestelle Lindenplatz in 2 min zu Fuß."),
                 ki(werkzeuge=(("kennzahlen", {}),)), ki("12 Comps, Median 99,99 €/m².")])


def laufen(graph, eingabe, lauf_id="lauf-1"):
    """Führt den Graphen bis zum Ende aus. Eingabe: Graph, Startzustand oder None (fortsetzen). Ausgabe: Endzustand."""
    return asyncio.run(graph.ainvoke(eingabe, lauf_konfig(lauf_id)))


@respx.mock
def test_voller_lauf_ohne_netz(db):
    """Der Supervisor schickt der Reihe nach alle drei Agenten los; jeder ruft nur seine Werkzeuge."""
    geodienste_mocken()
    m = voller_lauf()
    ende = laufen(baue_graph(m, db, KONFIG), startzustand(1))
    assert list(ende["ergebnisse"]) == ["standort", "marktdaten", "mietansatz"]
    assert [e["naechster"] for e in ende["entscheidungen"]] == ["standort", "marktdaten", "mietansatz", "fertig"]
    assert m.stark.i == 6 and m.schnell.i == 4 and ende.get("abbruch") is None
    # Werkzeugergebnisse tragen ihre Herkunft: Wegezeit von OSRM berechnet, Zu-/Abschlag vom Modell (ki)
    umfeld = ende["ergebnisse"]["standort"]["werkzeuge"][1]
    assert umfeld["name"] == "umfeld" and umfeld["ergebnis"]["pois"][0]["zu_fuss"]["herkunft"] == "berechnet"
    schritte = ende["ergebnisse"]["mietansatz"]["werkzeuge"][0]["ergebnis"]["schritte"]
    assert [s["wert"]["herkunft"] for s in schritte] == ["berechnet", "ki", "berechnet"]


@respx.mock
def test_unbelegte_zahl_wird_markiert(db):
    """„12“ ist durch das Werkzeug belegt, „99,99“ nicht: nur diese Zahl bekommt Herkunft ki und einen Warnhinweis."""
    geodienste_mocken()
    ende = laufen(baue_graph(voller_lauf(), db, KONFIG), startzustand(1))
    assert [m["fundstelle"] for m in ende["ergebnisse"]["marktdaten"]["markierungen"]] == ["99,99"]
    assert ende["ergebnisse"]["standort"]["markierungen"] == []


@respx.mock
def test_kosten_je_aufruf(db):
    """Jeder Modellaufruf schreibt Token und Euro mit; die Summe ergibt sich aus der Preistabelle."""
    geodienste_mocken()
    ende = laufen(baue_graph(voller_lauf(), db, KONFIG), startzustand(1))
    assert len(ende["kosten"]) == 10
    # 6 Aufrufe Sonnet (100 × 2 $ + 50 × 10 $ je Mio.) + 4 Aufrufe Haiku (100 × 0,10 $ + 50 × 0,50 $ je Mio.)
    assert sum(k["eur"]["wert"] for k in ende["kosten"]) == pytest.approx(6 * 0.0007 + 4 * 0.000035)


def test_leitplanke_mietansatz_erst_nach_marktdaten(db):
    """Will der Supervisor den Mietansatz ohne Marktdaten, schickt der Code zuerst den Marktdaten-Agenten."""
    m = modelle(stark=[entscheidung("mietansatz"), entscheidung("fertig", rueckfrage="Weiter?")],
                schnell=[ki("Keine Werkzeuge nötig.")])
    ende = laufen(baue_graph(m, db, KONFIG), startzustand(1))
    assert list(ende["ergebnisse"]) == ["marktdaten"]
    assert "Leitplanke" in ende["entscheidungen"][0]["begruendung"]


def test_rueckfrage_des_supervisors(db):
    """Fehlt etwas, endet der Supervisor mit einer offenen Rückfrage an den Nutzer."""
    m = modelle(stark=[entscheidung("fertig", rueckfrage="Welches Baujahr hat das Projekt?")], schnell=[])
    ende = laufen(baue_graph(m, db, KONFIG), startzustand(1))
    assert ende["offene_rueckfragen"] == ["Welches Baujahr hat das Projekt?"]


def test_budget_bricht_den_lauf_ab(db):
    """Übersteigt der Verbrauch das Budget, startet kein weiterer Modellaufruf."""
    teuer = Konfig(_env_file=None, anthropic_api_key="test", ki_budget_eur_pro_lauf=0.001, ki_eur_je_usd=1.0)
    m = modelle(stark=[entscheidung("standort", eingabe=1000, ausgabe=1000)], schnell=[ki("nie erreicht")])
    ende = laufen(baue_graph(m, db, teuer), startzustand(1))
    assert "Budget" in ende["abbruch"] and m.schnell.i == 0 and m.stark.i == 1


@respx.mock
def test_wiederaufnahme_nach_neustart(db, tmp_path):
    """Stürzt der Lauf im Marktdaten-Agenten ab, setzt ein neuer Graph (neuer Prozess) am letzten Checkpoint fort.

    Erledigte Schritte laufen nicht noch einmal: der Standort-Agent wird im zweiten Anlauf nicht mehr gefragt.
    """
    geodienste_mocken()
    pfad = str(tmp_path / "checkpoints.db")

    async def erster_anlauf():
        """Standort fertig, dann Absturz beim Marktdaten-Agenten. Ausgabe: keine."""
        m = modelle(stark=[entscheidung("standort"), entscheidung("marktdaten")],
                    schnell=[ki(werkzeuge=(("umfeld", {}),)), ki("Lage gut.")])
        async with AsyncSqliteSaver.from_conn_string(pfad) as cp:
            g = baue_graph(m, db, KONFIG, cp)
            # Absturz simulieren: ab jetzt scheitert jeder Aufruf des schnellen Modells
            async for update in g.astream(startzustand(1), lauf_konfig("lauf-x"), stream_mode="updates"):
                if "validierung" in update:  # Standort-Agent ist fertig und gesichert
                    m.schnell.fehler = True
            raise AssertionError("hätte abstürzen müssen")

    with pytest.raises(RuntimeError, match="simulierter Absturz"):
        asyncio.run(erster_anlauf())

    async def zweiter_anlauf():
        """Neuer Graph, neue Modelle, gleiche Checkpoint-Datei: fortsetzen mit Eingabe None. Ausgabe: Endzustand."""
        m = modelle(stark=[entscheidung("fertig", rueckfrage="Mietansatz gewünscht?")], schnell=[ki("12 Comps.")])
        async with AsyncSqliteSaver.from_conn_string(pfad) as cp:
            return await baue_graph(m, db, KONFIG, cp).ainvoke(None, lauf_konfig("lauf-x")), m

    ende, m = asyncio.run(zweiter_anlauf())
    assert list(ende["ergebnisse"]) == ["standort", "marktdaten"]
    assert ende["ergebnisse"]["standort"]["text"] == "Lage gut."
    assert m.schnell.i == 1 and m.stark.i == 1


@respx.mock
def test_standort_nutzt_projektkoordinaten_statt_geokodierung(db):
    """Der Standort-Agent liest Lage und Koordinaten aus der Datenbank; er hat kein Geokodier-Werkzeug.

    respx lässt keine ungemockte Anfrage durch: ein Aufruf von Nominatim würde den Test scheitern lassen.
    """
    geodienste_mocken()
    assert [w.name for w in werkzeuge(db, KONFIG)["standort"]] == ["lage", "umfeld"]
    ende = laufen(baue_graph(voller_lauf(), db, KONFIG), startzustand(1))
    lage = ende["ergebnisse"]["standort"]["werkzeuge"][0]
    with Session(db) as s:
        p = s.get(Projekt, 1)
    assert lage["name"] == "lage" and (lage["ergebnis"]["lat"], lage["ergebnis"]["lon"]) == (p.lat, p.lon)
    assert "Datenbank" in lage["ergebnis"]["quelle"]


def test_leitplanke_fertig_erst_nach_allen_agenten(db):
    """H: Wählt der Supervisor „fertig“ ohne Rückfrage, obwohl Agenten fehlen, schickt der Code den nächsten fehlenden."""
    m = modelle(stark=[entscheidung("marktdaten"), entscheidung("fertig"), entscheidung("fertig"),
                       ki("Ohne Werkzeug."), entscheidung("fertig")],
                schnell=[ki("Marktdaten."), ki("Standort.")])
    ende = laufen(baue_graph(m, db, KONFIG), startzustand(1))
    assert list(ende["ergebnisse"]) == ["marktdaten", "standort", "mietansatz"]
    assert "Leitplanke" in ende["entscheidungen"][1]["begruendung"]


def test_rundenlimit_ohne_weiteren_modellaufruf(db):
    """H: Nach MAX_RUNDEN Entscheidungen endet der Lauf, ohne das starke Modell noch einmal zu bezahlen."""
    m = modelle(stark=[entscheidung("standort", rueckfrage=None)] * MAX_RUNDEN, schnell=[ki("Standort.")] * MAX_RUNDEN)
    ende = laufen(baue_graph(m, db, KONFIG), startzustand(1))
    assert m.stark.i == MAX_RUNDEN and len(ende["kosten"]) == 2 * MAX_RUNDEN
    assert ende["entscheidungen"][-1]["naechster"] == "fertig" and "Leitplanke" in ende["entscheidungen"][-1]["begruendung"]


def test_gescheiterter_werkzeugaufruf_belegt_nichts(db):
    """D: Scheitert ein Aufruf (leere Begründung), stehen die Zahlen des Modells nur in der Fehlermeldung – kein Beleg."""
    falsch = {"basis": "regel_eg", "anpassungen": [{"name": "Lage", "betrag": 0.8, "begruendung": ""}]}
    m = modelle(stark=[entscheidung("marktdaten"), entscheidung("mietansatz"),
                       ki(werkzeuge=(("mietansatz_herleiten", falsch),)), ki("Zuschlag 0,80 €/m²."),
                       entscheidung("fertig", rueckfrage="Standort?")],
                schnell=[ki("Marktdaten.")])
    ende = laufen(baue_graph(m, db, KONFIG), startzustand(1))
    werkzeug = ende["ergebnisse"]["mietansatz"]["werkzeuge"][0]
    assert werkzeug["status"] == "error"
    assert [x["fundstelle"] for x in ende["ergebnisse"]["mietansatz"]["markierungen"]] == ["0,80"]


def test_zwischentext_wird_mitgeprueft(db):
    """E: Text, den ein Agent neben einem Werkzeugaufruf schreibt, wird ebenso geprüft wie die Schlussantwort."""
    m = modelle(stark=[entscheidung("marktdaten"), entscheidung("fertig", rueckfrage="Weiter?")],
                schnell=[ki("Der Median dürfte bei 14,50 €/m² liegen.", werkzeuge=(("kennzahlen", {}),)), ki("Fertig.")])
    ende = laufen(baue_graph(m, db, KONFIG), startzustand(1))
    assert "14,50" in [x["fundstelle"] for x in ende["ergebnisse"]["marktdaten"]["markierungen"]]


def test_unlesbare_supervisor_antwort_bricht_ab(db):
    """J: Liefert der Supervisor kein gültiges JSON, endet der Lauf mit Abbruchgrund – der Aufruf ist trotzdem gebucht."""
    m = modelle(stark=[ki("Ich denke, der Standort zuerst.")], schnell=[])
    ende = laufen(baue_graph(m, db, KONFIG), startzustand(1))
    assert "nicht lesbar" in ende["abbruch"] and len(ende["kosten"]) == 1


@respx.mock
def test_supervisor_begruendung_wird_geprueft(db):
    """Auch Begründung, Auftrag und Rückfrage des Supervisors laufen durch die Zahlenprüfung.

    „16,96“ ist durch die Herleitung belegt (Basis), „99,9“ steht in keinem Werkzeugergebnis.
    """
    geodienste_mocken()
    m = voller_lauf()
    m.stark.responses[-1] = entscheidung("fertig", begruendung="Mietansatz auf Basis 16,96 €/m², Spanne bis 99,9 €/m².")
    ende = laufen(baue_graph(m, db, KONFIG), startzustand(1))
    assert [x["fundstelle"] for x in ende["entscheidungen"][-1]["markierungen"]] == ["99,9"]
    assert ende["entscheidungen"][0]["markierungen"] == []


def test_herleitung_mit_dg_basis(db):
    """Für DG gibt es eine eigene Basis (Ø flächengewichtet der DG-Comps); andere Basen gibt es nicht mehr."""
    werkzeug = next(w for w in werkzeuge(db, KONFIG)["mietansatz"] if w.name == "mietansatz_herleiten")
    assert werkzeug.tool_call_schema.model_json_schema()["properties"]["basis"]["enum"] == ["regel_eg", "dg"]
    aus = json.loads(werkzeug.invoke({"projekt_id": 1, "basis": "dg", "anpassungen": []}))
    assert aus["basis"] == "dg" and "DG" in aus["schritte"][0]["wert"]["rechenweg_text"]
    with pytest.raises(ValueError, match="getrennte Herleitung"):  # im Graphen: Fehlermeldung zurück ans Modell
        werkzeug.invoke({"projekt_id": 1, "basis": "regel_eg", "anpassungen": [
            {"name": "DG-Aufschlag", "betrag": 2.2, "begruendung": "Überleitung auf DG"}]})
