"""Übersetzt den LangGraph-Strom (graph.astream mit stream_mode ["updates", "messages"]) in einfache Ereignisse
für die Oberfläche: Agent gestartet, Werkzeugaufruf, Werkzeugergebnis, Text, Agent fertig, Kosten, Rückfrage, Abbruch."""
from langchain_core.messages import AIMessage

from .graph import AGENTEN, lesen


def ereignisse(modus: str, daten: object) -> list[dict]:
    """Ereignisse zu einem Element des Stroms.

    Eingabe: Modus und Daten, wie astream sie liefert – bei "updates" {knoten: Änderung}, bei "messages"
    (Nachrichtenstück, Metadaten). Ausgabe: Liste von dicts mit Schlüssel "typ" (oft leer).
    """
    if modus == "messages":
        # Text der Agenten Stück für Stück; der Supervisor antwortet in JSON und wird nicht mitgestreamt
        stueck, meta = daten
        agent = meta.get("langgraph_node")
        return [{"typ": "text", "agent": agent, "text": stueck.text}] \
            if agent in AGENTEN and isinstance(stueck, AIMessage) and stueck.text else []
    aus = []
    for knoten, update in daten.items():
        update = update or {}
        if knoten == "supervisor":
            aus += [{"typ": "agent_gestartet", "agent": d["naechster"], "auftrag": d["auftrag"],
                     "begruendung": d["begruendung"], "markierungen": d["markierungen"]}
                    for d in update.get("entscheidungen", []) if d["naechster"] != "fertig"]
            aus += [{"typ": "rueckfrage", "text": r} for r in update.get("offene_rueckfragen", [])]
        elif knoten in AGENTEN:
            aus += [{"typ": "werkzeugaufruf", "agent": knoten, "werkzeug": a["name"], "argumente": a["args"]}
                    for n in update.get("nachrichten", []) for a in getattr(n, "tool_calls", [])]
        elif knoten.endswith("_werkzeuge"):
            aus += [{"typ": "werkzeugergebnis", "agent": knoten.removesuffix("_werkzeuge"), "werkzeug": n.name,
                     "ergebnis": lesen(n.content)} for n in update.get("nachrichten", [])]
        elif knoten == "validierung":
            aus += [{"typ": "agent_fertig", "agent": a, "text": r["text"], "markierungen": r["markierungen"]}
                    for a, r in update["ergebnisse"].items()]
        aus += [{"typ": "kosten", **k} for k in update.get("kosten", [])]
        if update.get("abbruch"):
            aus.append({"typ": "abbruch", "grund": update["abbruch"]})
    return aus
