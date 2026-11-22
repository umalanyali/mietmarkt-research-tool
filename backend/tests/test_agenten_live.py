"""Echter Lauf mit Claude. Kostet Geld und braucht ANTHROPIC_API_KEY; läuft nur mit `pytest -m live -s`."""
import asyncio

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from sqlmodel import Session

from mietmarkt.agenten.graph import baue_graph, lauf_konfig, startzustand
from mietmarkt.agenten.modelle import aus_konfig
from mietmarkt.db import engine
from mietmarkt.demo import seed
from mietmarkt.export import markdown
from mietmarkt.format import de
from mietmarkt.konfig import Konfig
from mietmarkt.modelle import Projekt


def bericht(ende: dict) -> str:
    """Lesbare Zusammenfassung eines Laufs. Eingabe: Endzustand. Ausgabe: mehrzeiliger Text.

    Zeigt Supervisor-Entscheidungen, je Agent die Werkzeuge, unbelegte Zahlen und Kosten, das Mietansatz-Ergebnis,
    Rückfragen und einen Abbruchgrund.
    """
    zeilen = ["", "Supervisor:"]
    for i, d in enumerate(ende["entscheidungen"], 1):
        unbelegt = ", ".join(m["fundstelle"] for m in d["markierungen"]) or "keine"
        zeilen.append(f"  {i}. {d['naechster']} – {d['begruendung']} [unbelegte Zahlen: {unbelegt}]"
                      + (f" Rückfrage: {d['rueckfrage']}" if d["rueckfrage"] else ""))
    zeilen.append("Agenten:")
    for agent, r in ende["ergebnisse"].items():
        eur = sum(k["eur"]["wert"] for k in ende["kosten"] if k["agent"] == agent)
        unbelegt = ", ".join(m["fundstelle"] for m in r["markierungen"]) or "keine"
        zeilen += [f"  {agent}: Werkzeuge {[w['name'] for w in r['werkzeuge']]}, {de(eur, 4)} €, unbelegte Zahlen: {unbelegt}",
                   f"    {r['text'][:300]}"]
    aufrufe = [w for w in ende["ergebnisse"].get("mietansatz", {}).get("werkzeuge", []) if w["name"] == "mietansatz_herleiten"]
    zeilen.append("Mietansatz:" + ("" if aufrufe else " nicht berechnet"))
    for n, w in enumerate(aufrufe, 1):  # jede Herleitung, auch abgelehnte (z. B. Anpassung von 0,00)
        if w["status"] == "error":
            zeilen.append(f"  {n}. abgelehnt: {str(w['ergebnis'])[:200]}")
            continue
        zeilen.append(f"  {n}. Basis {w['argumente']['basis']}: {w['ergebnis']['ergebnis']['rechenweg_text']}")
        zeilen += [f"     {s['wert']['rechenweg_text'].split(' (')[0]}  {s['name']} [{s['wert']['herkunft']}]: {s['begruendung']}"
                   for s in w["ergebnis"]["schritte"] if s["art"] == "anpassung"]
    gesamt = sum(k["eur"]["wert"] for k in ende["kosten"])
    supervisor = sum(k["eur"]["wert"] for k in ende["kosten"] if k["agent"] == "supervisor")
    for n, befunde in enumerate(ende.get("pruefungen", []), 1):
        zeilen.append(f"Prüfung {n}: " + ("; ".join(f"{b['schweregrad']} ({b['pruefung']}): {b['text']}" for b in befunde)
                                        or "keine Befunde"))
    b = ende.get("bericht")
    if b:
        zeilen += ["Bericht:"] + [f"  [{k}] {t}" for k, t in b["abschnitte"].items()]
        zeilen += [f"  [^{f['nr']}] {f['herkunft']}: {f['verweis'][:120]}" for f in b["fussnoten"]]
        zeilen.append(f"  Frei im ersten Entwurf (korrigiert): {b['korrektur'] or 'keine'}")
        zeilen.append(f"  Danach noch entfernt [?]: {[m['fundstelle'] for m in b['markierungen']] or 'keine'}")
    zeilen += [f"Kosten: {de(gesamt, 4)} € gesamt ({len(ende['kosten'])} Modellaufrufe, davon Supervisor {de(supervisor, 4)} €)",
               f"Rückfragen: {list(zip(ende['rueckfragen'], ende['antworten'], strict=False)) or 'keine'}",
               f"Abbruch: {ende.get('abbruch') or 'nein'}"]
    return "\n".join(zeilen)


@pytest.mark.live
def test_echter_lauf_mit_claude(tmp_path):
    """Demo-Projekt Lindenquartier mit echten Modellen und dem Budget aus .env: alle drei Agenten liefern, jeder
    Vorschlag wird angenommen, am Ende steht ein Bericht."""
    k = Konfig()
    if not k.ki_konfiguriert:
        pytest.skip("ANTHROPIC_API_KEY fehlt in .env")
    e = engine(tmp_path / "live.db")
    seed(e)
    async def lauf():
        """Startet, nimmt jeden Mietansatz-Vorschlag an und beantwortet Rückfragen neutral (höchstens fünf
        Unterbrechungen). Ausgabe: Endzustand."""
        g, konf = baue_graph(aus_konfig(k), e, k, InMemorySaver()), lauf_konfig("live")
        ende = await g.ainvoke(startzustand(1), konf)
        antworten = {"freigabe": {"aktion": "annehmen"},
                     "rueckfrage": {"antwort": "Keine weiteren Angaben, bitte mit den vorhandenen Daten fortfahren."}}
        for _ in range(5):
            naechster = (await g.aget_state(konf)).next
            if naechster not in (("freigabe",), ("rueckfrage",)):
                break
            ende = await g.ainvoke(Command(resume=antworten[naechster[0]]), konf)
        return ende

    ende = asyncio.run(lauf())
    print(bericht(ende))
    if ende.get("bericht"):
        with Session(e) as s:
            print("\n----- bericht.md -----\n" + markdown(s.get(Projekt, 1), ende["bericht"]))
    assert {"standort", "marktdaten", "mietansatz"} <= set(ende["ergebnisse"]), "nicht alle Agenten liefen (s. Bericht)"
    assert ende.get("bericht"), "kein Bericht (s. Bericht)"
    assert sum(x["eur"]["wert"] for x in ende["kosten"]) > 0
