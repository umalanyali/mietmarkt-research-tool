"""Analyse-Graph mit Fake-Modellen: läuft komplett ohne Netz (Geodienste über respx) und ohne API-Schlüssel."""
import asyncio
import json
import re

import httpx
import pytest
import respx
from ki_fakes import befunde, bericht, entscheidung, ki, modelle
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from sqlmodel import Session

from mietmarkt.agenten.bericht import anzeigen
from mietmarkt.agenten.graph import (
    MAX_RUNDEN,
    Entscheidung,
    _leitplanken,
    baue_graph,
    lauf_konfig,
    startzustand,
)
from mietmarkt.agenten.werkzeuge import werkzeuge
from mietmarkt.db import engine
from mietmarkt.demo import seed
from mietmarkt.geo import dienste
from mietmarkt.konfig import Konfig
from mietmarkt.modelle import Projekt

KONFIG = Konfig(_env_file=None, anthropic_api_key="test", ki_budget_eur_pro_lauf=0.5, ki_eur_je_usd=1.0)
ANPASSUNG = {"name": "Neubau-Zuschlag", "betrag": 0.5, "begruendung": "Erstbezug mit Aufzug"}
ANNEHMEN = {"aktion": "annehmen"}

BERICHT = bericht()
# Das Demo-Projekt hat DG-Wohnungen: Haupt-Ansatz und getrennte DG-Herleitung in einer Antwort
HERLEITEN = ki(werkzeuge=(("mietansatz_herleiten", {"basis": "regel_eg", "anpassungen": [ANPASSUNG]}),
                          ("mietansatz_herleiten", {"basis": "dg", "anpassungen": []})))


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


def voller_lauf(*nach_freigabe: AIMessage):
    """Skript: Standort → Marktdaten → Mietansatz → Freigabe → Prüfung → Bericht. Ausgabe: Modelle.

    Eingabe: Antworten des starken Modells nach der ersten Freigabe (Standard: Prüfung ohne Befund, Bericht).
    """
    return modelle(
        stark=[entscheidung("standort"), entscheidung("marktdaten"), entscheidung("mietansatz"), HERLEITEN,
               ki("Mietansatz siehe Herleitung."), *(nach_freigabe or (befunde("hinweis"), BERICHT))],
        schnell=[ki(werkzeuge=(("lage", {}), ("umfeld", {}))), ki("Haltestelle Lindenplatz in 2 min zu Fuß."),
                 ki(werkzeuge=(("kennzahlen", {}),)), ki("12 Comps, Median 99,99 €/m².")])


def graph(m, db, k=KONFIG):
    """Graph mit Checkpointer im Speicher (interrupt() braucht einen). Eingabe: Modelle, Engine, Konfig."""
    return baue_graph(m, db, k, InMemorySaver())


def laufen(g, eingabe, lauf_id="lauf-1", freigaben=(ANNEHMEN,)):
    """Führt den Graphen aus; hält er zur Freigabe an, antwortet der „Nutzer“ der Reihe nach mit `freigaben`.

    Eingabe: Graph, Startzustand oder None (fortsetzen), Lauf-ID, Fortsetzungswerte. Ausgabe: Endzustand.
    """
    async def los():
        """Startet und setzt nach jedem Interrupt mit Command(resume=…) fort. Ausgabe: Endzustand."""
        konf = lauf_konfig(lauf_id)
        ende = await g.ainvoke(eingabe, konf)
        for f in freigaben:
            if (await g.aget_state(konf)).next != ("freigabe",):
                break
            ende = await g.ainvoke(Command(resume=f), konf)
        return ende
    return asyncio.run(los())


@respx.mock
def test_voller_lauf_ohne_netz(db):
    """Der Supervisor schickt der Reihe nach alle drei Agenten los; nach Freigabe folgen Prüfung und Bericht."""
    geodienste_mocken()
    m = voller_lauf()
    ende = laufen(graph(m, db, KONFIG), startzustand(1))
    assert list(ende["ergebnisse"]) == ["standort", "marktdaten", "mietansatz", "pruefung"]
    assert [e["naechster"] for e in ende["entscheidungen"]] == ["standort", "marktdaten", "mietansatz"]
    assert m.stark.i == 7 and m.schnell.i == 4 and ende.get("abbruch") is None and ende["bericht"]
    # Werkzeugergebnisse tragen ihre Herkunft: Wegezeit von OSRM berechnet, Zu-/Abschlag vom Modell (ki)
    umfeld = ende["ergebnisse"]["standort"]["werkzeuge"][1]
    assert umfeld["name"] == "umfeld" and umfeld["ergebnis"]["pois"][0]["zu_fuss"]["herkunft"] == "berechnet"
    schritte = ende["ergebnisse"]["mietansatz"]["werkzeuge"][0]["ergebnis"]["schritte"]
    assert [s["wert"]["herkunft"] for s in schritte] == ["berechnet", "ki", "berechnet", "berechnet"]


@respx.mock
def test_unbelegte_zahl_wird_markiert(db):
    """„12“ ist durch das Werkzeug belegt, „99,99“ nicht: nur diese Zahl bekommt Herkunft ki und einen Warnhinweis."""
    geodienste_mocken()
    ende = laufen(graph(voller_lauf(), db, KONFIG), startzustand(1))
    assert [m["fundstelle"] for m in ende["ergebnisse"]["marktdaten"]["markierungen"]] == ["99,99"]
    assert ende["ergebnisse"]["standort"]["markierungen"] == []


@respx.mock
def test_kosten_je_aufruf(db):
    """Jeder Modellaufruf schreibt Token und Euro mit; die Summe ergibt sich aus der Preistabelle."""
    geodienste_mocken()
    ende = laufen(graph(voller_lauf(), db, KONFIG), startzustand(1))
    assert len(ende["kosten"]) == 11
    # 7 Aufrufe Sonnet (100 × 2 $ + 50 × 10 $ je Mio.) + 4 Aufrufe Haiku (100 × 0,10 $ + 50 × 0,50 $ je Mio.)
    assert sum(k["eur"]["wert"] for k in ende["kosten"]) == pytest.approx(7 * 0.0007 + 4 * 0.000035)


def test_leitplanke_mietansatz_erst_nach_standort_und_marktdaten(db):
    """P1: Will der Supervisor den Mietansatz, solange Standort oder Marktdaten fehlen, schickt der Code zuerst den
    fehlenden Agenten – sonst entstünde ein Bericht ohne Lage."""
    m = modelle(stark=[entscheidung("marktdaten"), entscheidung("mietansatz"), entscheidung("fertig", rueckfrage="Weiter?")],
                schnell=[ki("Marktdaten."), ki("Standort.")])
    ende = laufen(graph(m, db, KONFIG), startzustand(1))
    assert list(ende["ergebnisse"]) == ["marktdaten", "standort"]
    assert ende["entscheidungen"][1]["naechster"] == "standort" and "Leitplanke" in ende["entscheidungen"][1]["begruendung"]


def test_rueckfrage_haelt_an_und_antwort_geht_an_den_supervisor(db):
    """Fehlt etwas, stellt der Supervisor eine Rückfrage und der Lauf hält an. Die Antwort des Nutzers steht danach
    in den Ergebnissen für Supervisor und Agenten; Zahlen aus der Antwort gelten als belegt (Angabe des Nutzers)."""
    m = modelle(stark=[entscheidung("fertig", rueckfrage="Welches Baujahr hat das Projekt?"), entscheidung("marktdaten"),
                       entscheidung("fertig", rueckfrage="Sonst noch etwas?")],
                schnell=[ki("Baujahr 2027 laut Nutzer.")])
    g, konf = graph(m, db), lauf_konfig("lauf-r")
    asyncio.run(g.ainvoke(startzustand(1), konf))
    stand = asyncio.run(g.aget_state(konf))
    assert stand.next == ("rueckfrage",) and stand.interrupts[0].value == {"art": "rueckfrage",
                                                                         "frage": "Welches Baujahr hat das Projekt?"}
    asyncio.run(g.ainvoke(Command(resume={"antwort": "Baujahr 2027"}), konf))
    stand = asyncio.run(g.aget_state(konf))
    assert stand.next == ("rueckfrage",) and stand.values["antworten"] == ["Baujahr 2027"]
    assert "Antwort: Baujahr 2027" in stand.values["nachrichten"][1].text
    assert stand.values["ergebnisse"]["marktdaten"]["markierungen"] == []


def test_leere_antwort_wird_abgelehnt(db):
    """Eine leere Antwort ist ungültig; der Lauf wartet weiter auf die Rückfrage."""
    from pydantic import ValidationError
    g, konf = graph(modelle(stark=[entscheidung("fertig", rueckfrage="Baujahr?")], schnell=[]), db), lauf_konfig("r")
    asyncio.run(g.ainvoke(startzustand(1), konf))
    with pytest.raises(ValidationError):
        asyncio.run(g.ainvoke(Command(resume={"antwort": "  "}), konf))
    assert asyncio.run(g.aget_state(konf)).next == ("rueckfrage",)


def test_budget_bricht_den_lauf_ab(db):
    """Übersteigt der Verbrauch das Budget, startet kein weiterer Modellaufruf."""
    teuer = Konfig(_env_file=None, anthropic_api_key="test", ki_budget_eur_pro_lauf=0.001, ki_eur_je_usd=1.0)
    m = modelle(stark=[entscheidung("standort", eingabe=1000, ausgabe=1000)], schnell=[ki("nie erreicht")])
    ende = laufen(graph(m, db, teuer), startzustand(1))
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
    ende = laufen(graph(voller_lauf(), db, KONFIG), startzustand(1))
    lage = ende["ergebnisse"]["standort"]["werkzeuge"][0]
    with Session(db) as s:
        p = s.get(Projekt, 1)
    assert lage["name"] == "lage" and (lage["ergebnis"]["lat"], lage["ergebnis"]["lon"]) == (p.lat, p.lon)
    assert "Datenbank" in lage["ergebnis"]["quelle"]


def test_leitplanke_fertig_erst_nach_allen_agenten(db):
    """H: Wählt der Supervisor „fertig“ ohne Rückfrage, obwohl Agenten fehlen, schickt der Code den nächsten fehlenden."""
    m = modelle(stark=[entscheidung("marktdaten"), entscheidung("fertig"), entscheidung("fertig"),
                       ki("Ohne Werkzeug."), ki("Nach dem Hinweis weiter ohne."),
                       entscheidung("fertig", rueckfrage="Welche Basis?")],
                schnell=[ki("Marktdaten."), ki("Standort.")])
    ende = laufen(graph(m, db, KONFIG), startzustand(1))
    assert list(ende["ergebnisse"]) == ["marktdaten", "standort", "mietansatz"]
    assert "Leitplanke" in ende["entscheidungen"][1]["begruendung"]


def test_rundenlimit_ohne_weiteren_modellaufruf(db):
    """H: Nach MAX_RUNDEN Entscheidungen endet der Lauf, ohne das starke Modell noch einmal zu bezahlen."""
    m = modelle(stark=[entscheidung("standort", rueckfrage=None)] * MAX_RUNDEN, schnell=[ki("Standort.")] * MAX_RUNDEN)
    ende = laufen(graph(m, db, KONFIG), startzustand(1))
    assert m.stark.i == MAX_RUNDEN and len(ende["kosten"]) == 2 * MAX_RUNDEN
    assert ende["entscheidungen"][-1]["naechster"] == "fertig" and "Leitplanke" in ende["entscheidungen"][-1]["begruendung"]
    assert "Runden" in ende["abbruch"]  # P8: kein stilles „fertig“ ohne Bericht


def test_gescheiterter_werkzeugaufruf_belegt_nichts(db):
    """D: Scheitert ein Aufruf (leere Begründung), stehen die Zahlen des Modells nur in der Fehlermeldung – kein Beleg."""
    falsch = {"basis": "regel_eg", "anpassungen": [{"name": "Lage", "betrag": 0.8, "begruendung": ""}]}
    m = modelle(stark=[entscheidung("standort"), entscheidung("marktdaten"), entscheidung("mietansatz"),
                       ki(werkzeuge=(("mietansatz_herleiten", falsch),)), ki("Zuschlag 0,80 €/m²."),
                       ki("Keine gültige Herleitung."), entscheidung("fertig", rueckfrage="Standort?")],
                schnell=[ki("Standort."), ki("Marktdaten.")])
    ende = laufen(graph(m, db, KONFIG), startzustand(1))
    werkzeug = ende["ergebnisse"]["mietansatz"]["werkzeuge"][0]
    assert werkzeug["status"] == "error"
    assert [x["fundstelle"] for x in ende["ergebnisse"]["mietansatz"]["markierungen"]] == ["0,80"]


def test_zwischentext_wird_mitgeprueft(db):
    """E: Text, den ein Agent neben einem Werkzeugaufruf schreibt, wird ebenso geprüft wie die Schlussantwort."""
    m = modelle(stark=[entscheidung("marktdaten"), entscheidung("fertig", rueckfrage="Weiter?")],
                schnell=[ki("Der Median dürfte bei 14,50 €/m² liegen.", werkzeuge=(("kennzahlen", {}),)), ki("Fertig.")])
    ende = laufen(graph(m, db, KONFIG), startzustand(1))
    assert "14,50" in [x["fundstelle"] for x in ende["ergebnisse"]["marktdaten"]["markierungen"]]


def test_unlesbare_supervisor_antwort_bricht_ab(db):
    """J: Liefert der Supervisor kein gültiges JSON, endet der Lauf mit Abbruchgrund – der Aufruf ist trotzdem gebucht."""
    m = modelle(stark=[ki("Ich denke, der Standort zuerst.")], schnell=[])
    ende = laufen(graph(m, db, KONFIG), startzustand(1))
    assert "nicht lesbar" in ende["abbruch"] and len(ende["kosten"]) == 1


@respx.mock
def test_supervisor_begruendung_wird_geprueft(db):
    """Auch Begründung, Auftrag und Rückfrage des Supervisors laufen durch die Zahlenprüfung.

    „12“ ist durch die Kennzahlen des Marktdaten-Agenten belegt, „99,9“ steht in keinem Werkzeugergebnis.
    """
    geodienste_mocken()
    m = voller_lauf()
    m.stark.responses[2] = entscheidung("mietansatz", begruendung="Basis aus 12 Comps, Spanne bis 99,9 €/m².")
    ende = laufen(graph(m, db, KONFIG), startzustand(1))
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


def vorschlag_abwarten(m, db):
    """Lauf bis zur Freigabe. Eingabe: Modelle, Engine. Ausgabe: (Graph, Konfig, Zustand am Interrupt)."""
    g, konf = graph(m, db), lauf_konfig("lauf-f")
    asyncio.run(g.ainvoke(startzustand(1), konf))
    return g, konf, asyncio.run(g.aget_state(konf))


def weiter(g, konf, freigabe):
    """Setzt den Lauf nach dem Interrupt mit der Entscheidung des Nutzers fort. Ausgabe: Zustand danach."""
    asyncio.run(g.ainvoke(Command(resume=freigabe), konf))
    return asyncio.run(g.aget_state(konf))


@respx.mock
def test_lauf_haelt_vor_der_freigabe_an(db):
    """Nach dem Mietansatz pausiert der Lauf; der Vorschlag (Basis, Zu-/Abschläge, Begründung) liegt im Interrupt.
    Prüfung und Bericht laufen erst nach der Freigabe."""
    geodienste_mocken()
    m = voller_lauf()
    _, _, stand = vorschlag_abwarten(m, db)
    assert stand.next == ("freigabe",) and m.stark.i == 5
    v = stand.interrupts[0].value["vorschlag"]
    assert set(v["herleitungen"]) == {"regel_eg", "dg"} and v["begruendung"] == "Mietansatz siehe Herleitung."
    h = v["herleitungen"]["regel_eg"]
    assert [s["art"] for s in h["schritte"]] == ["basis", "anpassung", "ergebnis", "fortschreibung"]
    assert h["schritte"][1]["begruendung"] == "Erstbezug mit Aufzug"
    # Demo: Stichtag 04.11.2026, Vermarktungsstart 01.09.2027 (10 Monate), g = 2 %
    assert h["fortgeschrieben"]["wert"] == pytest.approx(h["ergebnis"]["wert"] * 1.02 ** (10 / 12))


@respx.mock
def test_freigabe_annehmen(db):
    """Annehmen übernimmt den Vorschlag unverändert (Zuschlag bleibt Herkunft ki); danach Prüfung und Bericht."""
    geodienste_mocken()
    g, konf, _ = vorschlag_abwarten(voller_lauf(), db)
    z = weiter(g, konf, ANNEHMEN).values
    h = z["freigabe"]["herleitungen"]["regel_eg"]
    assert [s["wert"]["herkunft"] for s in h["schritte"]] == ["berechnet", "ki", "berechnet", "berechnet"]
    assert anzeigen(h["ergebnis"]) in z["bericht"]["abschnitte"]["mietansatz"]
    assert set(z["freigabe"]["herleitungen"]) == {"regel_eg", "dg"}


@respx.mock
def test_freigabe_aendern_macht_werte_manuell(db):
    """Geänderte Werte bekommen Herkunft manuell, unverändert übernommene behalten ki; Python rechnet neu."""
    geodienste_mocken()
    g, konf, _ = vorschlag_abwarten(voller_lauf(), db)
    balkon = {"name": "Balkon", "betrag": 0.3, "begruendung": "Alle Einheiten mit Balkon, Comps ohne"}
    z = weiter(g, konf, {"aktion": "aendern", "kommentar": "Basis laut eigener Erhebung",
                         "aenderungen": {"regel_eg": {"basiswert": 16.5, "anpassungen": [ANPASSUNG, balkon]}}}).values
    h = z["freigabe"]["herleitungen"]["regel_eg"]
    assert [s["wert"]["herkunft"] for s in h["schritte"]] == ["manuell", "ki", "manuell", "berechnet", "berechnet"]
    assert h["fortgeschrieben"]["wert"] == pytest.approx(17.3 * 1.02 ** (10 / 12))  # Fortschreibung neu gerechnet
    assert z["freigabe"]["herleitungen"]["dg"]["schritte"][0]["wert"]["herkunft"] == "berechnet"  # DG unverändert
    assert h["ergebnis"]["wert"] == pytest.approx(17.3) and "16,50 + 0,50 + 0,30" in h["ergebnis"]["rechenweg_text"]
    assert "17,30 €/m²" in z["bericht"]["abschnitte"]["mietansatz"]  # der Bericht nutzt die geänderten Werte


@respx.mock
def test_freigabe_ablehnen_geht_mit_kommentar_zurueck(db):
    """Ablehnen schickt den Lauf zum Supervisor; der Kommentar steht im neuen Auftrag an den Mietansatz-Agenten,
    und der neue Vorschlag wird wieder zur Freigabe vorgelegt."""
    geodienste_mocken()
    m = voller_lauf(entscheidung("mietansatz"), ki("Ohne Zuschlag.", werkzeuge=(
        ("mietansatz_herleiten", {"basis": "regel_eg", "anpassungen": []}),
        ("mietansatz_herleiten", {"basis": "dg", "anpassungen": []}))), ki("Basis ohne Zuschlag."),
        befunde("hinweis"), BERICHT)
    g, konf, _ = vorschlag_abwarten(m, db)
    stand = weiter(g, konf, {"aktion": "ablehnen", "kommentar": "Kein Neubau-Zuschlag, die Comps sind auch Neubau."})
    assert stand.next == ("freigabe",) and "mietansatz" in stand.values["ergebnisse"]
    assert "Kein Neubau-Zuschlag" in stand.values["nachrichten"][1].text
    assert stand.interrupts[0].value["vorschlag"]["begruendung"] == "Basis ohne Zuschlag."
    z = weiter(g, konf, ANNEHMEN).values
    assert len(z["entscheidungen"]) == 4 and z["bericht"] and m.stark.i == len(m.stark.responses)


@respx.mock
def test_unvollstaendige_freigabe_wird_abgelehnt(db):
    """„aendern“ ohne Änderungen oder „ablehnen“ ohne Kommentar ist ungültig; der Lauf wartet weiter."""
    from pydantic import ValidationError
    geodienste_mocken()
    g, konf, _ = vorschlag_abwarten(voller_lauf(), db)
    for falsch in ({"aktion": "aendern"}, {"aktion": "ablehnen"}, {"aktion": "aendern", "aenderungen": {"regel_eg": {
            "anpassungen": [{"name": "DG", "betrag": 2, "begruendung": "Dachgeschoss"}]}}}):
        with pytest.raises(ValidationError):
            asyncio.run(g.ainvoke(Command(resume=falsch), konf))
        assert asyncio.run(g.aget_state(konf)).next == ("freigabe",)


@respx.mock
def test_kritischer_befund_fuehrt_zurueck_zum_supervisor(db):
    """Meldet die Prüfung „kritisch“, geht es zum Supervisor statt zum Bericht; die Freigabe verfällt, der Mietansatz
    wird neu hergeleitet und freigegeben. Erst die zweite, unkritische Prüfung führt zum Bericht."""
    geodienste_mocken()
    m = voller_lauf(befunde("warnung", "kritisch"), entscheidung("mietansatz"), HERLEITEN, ki("Neu hergeleitet."),
                    befunde("hinweis"), BERICHT)
    z = laufen(graph(m, db), startzustand(1), freigaben=(ANNEHMEN, ANNEHMEN))
    assert [[b["schweregrad"] for b in p] for p in z["pruefungen"]] == [["warnung", "kritisch"], ["hinweis"]]
    assert [e["naechster"] for e in z["entscheidungen"]] == ["standort", "marktdaten", "mietansatz", "mietansatz"]
    assert z["bericht"] and m.stark.i == len(m.stark.responses)


@respx.mock
def test_zweiter_kritischer_befund_endet_im_bericht(db):
    """Leitplanke: Nach MAX_PRUEFRUNDEN geht es auch bei „kritisch“ zum Bericht; der Befund steht unter Risiken."""
    geodienste_mocken()
    m = voller_lauf(befunde("kritisch"), entscheidung("mietansatz"), HERLEITEN, ki("Neu."), befunde("kritisch"), BERICHT)
    z = laufen(graph(m, db), startzustand(1), freigaben=(ANNEHMEN, ANNEHMEN))
    assert len(z["pruefungen"]) == 2 and z["bericht"]["befunde"][0]["schweregrad"] == "kritisch"
    assert m.stark.i == len(m.stark.responses)


FREI = bericht(lage="Rund 300 m zur Haltestelle.",
               mietansatz="Ansatz {{wert:mietansatz.regel_eg.ergebnis}} statt 18,00 €/m².")


@respx.mock
def test_freie_zahlen_werden_einmal_korrigiert(db):
    """Schreibt der Bericht-Agent Zahlen selbst, bekommt er einen Korrekturauftrag mit genau diesen Zahlen; der
    korrigierte Text gilt, ohne Markierung. Der Korrekturaufruf wird gebucht."""
    geodienste_mocken()
    m = voller_lauf(befunde("hinweis"), FREI, BERICHT)
    z = laufen(graph(m, db), startzustand(1))
    assert z["bericht"]["korrektur"] == ["300", "18,00"] and z["bericht"]["markierungen"] == []
    assert z["bericht"]["abschnitte"]["lage"] == "Ruhige Lage am Lindenplatz."
    hinweis = m.stark.aufrufe[-1][-1].text  # letzte Nachricht des Korrekturaufrufs
    assert "„300“" in hinweis and "„18,00“" in hinweis
    assert [k["agent"] for k in z["kosten"]][-2:] == ["bericht", "bericht"] and m.stark.i == len(m.stark.responses)


@respx.mock
def test_bericht_nur_mit_zahlen_aus_platzhaltern(db):
    """Bleiben nach der Korrektur freie Zahlen, ersetzt Python sie durch [?] und markiert sie; die Werte aus
    Platzhaltern tragen Fußnoten mit Herkunft."""
    geodienste_mocken()
    z = laufen(graph(voller_lauf(befunde("hinweis"), FREI, FREI), db), startzustand(1))
    b = z["bericht"]
    assert [x["fundstelle"] for x in b["markierungen"]] == ["300", "18,00"]
    assert [f["ids"] for f in b["fussnoten"]] == [["kennzahlen.comps.median"], ["mietansatz.regel_eg.ergebnis"]]
    text = " ".join(b["abschnitte"].values())
    for f in b["fussnoten"]:  # Werte und Fußnotenzeichen entfernen: dann bleibt keine Ziffer übrig
        text = text.replace(f"[^{f['nr']}]", "")
    for w in (z["freigabe"]["herleitungen"]["regel_eg"]["ergebnis"], z["ergebnisse"]["marktdaten"]["werkzeuge"][0]["ergebnis"]["comps"]["median"]):
        text = text.replace(anzeigen(w), "")
    assert not re.search(r"[0-9]", text), text


def test_fehlende_dg_herleitung_wird_einmal_nachgefordert(db):
    """Das Projekt hat DG-Wohnungen: Fehlt die DG-Herleitung, schickt der Code den Agenten einmal mit einem Hinweis
    zurück. Liefert er sie dann, enthält der Vorschlag beide Basen."""
    nur_regel = ki(werkzeuge=(("mietansatz_herleiten", {"basis": "regel_eg", "anpassungen": []}),))
    nur_dg = ki(werkzeuge=(("mietansatz_herleiten", {"basis": "dg", "anpassungen": []}),))
    m = modelle(stark=[entscheidung("standort"), entscheidung("marktdaten"), entscheidung("mietansatz"), nur_regel,
                       ki("Nur Regel."), nur_dg, ki("Jetzt mit DG.")], schnell=[ki("Standort."), ki("Marktdaten.")])
    g, konf = graph(m, db), lauf_konfig("dg")
    asyncio.run(g.ainvoke(startzustand(1), konf))
    stand = asyncio.run(g.aget_state(konf))
    assert stand.next == ("freigabe",) and set(stand.interrupts[0].value["vorschlag"]["herleitungen"]) == {"regel_eg", "dg"}
    assert any(n.text.startswith("Leitplanke: Es fehlt") for n in stand.values["nachrichten"])


def test_ohne_haupt_ansatz_keine_freigabe_und_kein_fertig(db):
    """Review P2: Leitet der Agent auch nach dem Hinweis keinen Haupt-Ansatz her, gibt es nichts freizugeben; der
    Mietansatz gilt als fehlend, „fertig“ ohne Rückfrage wird zum erneuten Mietansatz-Auftrag."""
    nur_dg = ki(werkzeuge=(("mietansatz_herleiten", {"basis": "dg", "anpassungen": []}),))
    m = modelle(stark=[entscheidung("standort"), entscheidung("marktdaten"), entscheidung("mietansatz"), nur_dg,
                       ki("Nur DG."), ki("Immer noch."), entscheidung("fertig", rueckfrage="Basis unklar?")],
                schnell=[ki("Standort."), ki("Marktdaten.")])
    g, konf = graph(m, db), lauf_konfig("p2")
    asyncio.run(g.ainvoke(startzustand(1), konf))
    z = asyncio.run(g.aget_state(konf)).values
    assert z["vorschlag"] is None and z["freigabe"] is None
    fertig = Entscheidung(naechster="fertig", auftrag="", begruendung="alles da")
    assert _leitplanken(fertig, z).naechster == "mietansatz"  # ohne Freigabe zählt der Mietansatz als fehlend


@respx.mock
def test_absturz_in_der_korrektur_verliert_keine_kosten(db):
    """P6: Die Korrektur ist ein eigener Knoten. Stürzt ihr Modellaufruf ab, ist der erste Bericht-Aufruf schon
    gebucht und gesichert; beim Fortsetzen läuft nur die Korrektur erneut."""
    geodienste_mocken()
    m = voller_lauf(befunde("hinweis"), FREI)  # Antwort für die Korrektur fehlt im Skript → Absturz
    g, konf = graph(m, db), lauf_konfig("p6")
    asyncio.run(g.ainvoke(startzustand(1), konf))
    with pytest.raises(AssertionError, match="Unerwarteter Modellaufruf"):
        asyncio.run(g.ainvoke(Command(resume=ANNEHMEN), konf))
    stand = asyncio.run(g.aget_state(konf))
    assert stand.next == ("bericht_korrektur",) and stand.values["kosten"][-1]["agent"] == "bericht"
    m.stark.responses.append(BERICHT)  # „Netz wieder da“: Fortsetzen ruft nur noch die Korrektur
    asyncio.run(g.ainvoke(None, konf))
    z = asyncio.run(g.aget_state(konf)).values
    assert z["bericht"]["markierungen"] == [] and z["bericht"]["korrektur"] == ["300", "18,00"]
    assert "entwurf" not in z["bericht"]
