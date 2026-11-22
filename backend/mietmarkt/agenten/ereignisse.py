"""Übersetzt den LangGraph-Strom (graph.astream mit stream_mode ["updates", "messages"]) in einfache Ereignisse
für die Oberfläche: Agent gestartet, Werkzeugaufruf, Werkzeugergebnis, Text, Agent fertig, Kosten, Rückfrage,
wartet auf Freigabe bzw. Antwort, Freigabe, Antwort, Prüfung, Bericht, Abbruch."""
from langchain_core.messages import AIMessage

from .graph import AGENTEN, DOKUMENT_AGENTEN, lesen


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
        if knoten == "__interrupt__":  # der Graph hält an; update ist ein Tupel von Interrupt-Objekten
            aus += [{"typ": "wartet_auf_freigabe" if i.value["art"] == "mietansatz" else "wartet_auf_antwort", **i.value}
                    for i in update]
            continue
        update = update or {}
        if knoten == "supervisor":
            aus += [{"typ": "agent_gestartet", "agent": d["naechster"], "auftrag": d["auftrag"],
                     "begruendung": d["begruendung"], "markierungen": d["markierungen"]}
                    for d in update.get("entscheidungen", []) if d["naechster"] != "fertig"]
            aus += [{"typ": "rueckfrage", "text": r} for r in update.get("rueckfragen", [])]
        elif knoten in AGENTEN:
            aus += [{"typ": "werkzeugaufruf", "agent": knoten, "werkzeug": a["name"], "argumente": a["args"]}
                    for n in update.get("nachrichten", []) for a in getattr(n, "tool_calls", [])]
        elif knoten.endswith("_werkzeuge"):
            aus += [{"typ": "werkzeugergebnis", "agent": knoten.removesuffix("_werkzeuge"), "werkzeug": n.name,
                     "ergebnis": lesen(n.content)} for n in update.get("nachrichten", [])]
        elif knoten == "validierung":
            aus += [{"typ": "agent_fertig", "agent": a, "text": r["text"], "markierungen": r["markierungen"]}
                    for a, r in update["ergebnisse"].items()]
        elif knoten == "rueckfrage":
            aus.append({"typ": "antwort", "antwort": update["antworten"][-1]})
        elif knoten in DOKUMENT_AGENTEN and "ergebnisse" in update:
            # Exposé- und Vision-Agent: der Code ruft ihre Auswertung selbst auf, es gibt keinen Werkzeugaufruf davor
            r = update["ergebnisse"][knoten]
            aus += [{"typ": "werkzeugergebnis", "agent": knoten, "werkzeug": w["name"], "ergebnis": w["ergebnis"]}
                    for w in r["werkzeuge"]]
            aus.append({"typ": "agent_fertig", "agent": knoten, "text": r["text"], "markierungen": r["markierungen"]})
        elif knoten == "freigabe":
            aus.append({"typ": "freigabe", **update["freigabe"]})
        elif knoten == "pruefung" and "pruefungen" in update:
            aus += [{"typ": "werkzeugergebnis", "agent": "pruefung", "werkzeug": w["name"], "ergebnis": w["ergebnis"]}
                    for w in update["ergebnisse"]["pruefung"]["werkzeuge"]]
            # „freigabe“ im Update heißt: sie wurde verworfen, der Lauf geht zum Supervisor zurück
            aus.append({"typ": "pruefung", "befunde": update["pruefungen"][-1], "zurueck": "freigabe" in update})
        elif knoten in ("bericht", "bericht_korrektur") and update.get("bericht"):
            # Mit Entwurf ist der Bericht vorläufig: die Korrekturrunde folgt und schickt ihn erneut
            aus.append({"typ": "bericht", "vorlaeufig": "entwurf" in update["bericht"],
                        **{k: v for k, v in update["bericht"].items() if k != "entwurf"}})
        aus += [{"typ": "kosten", **k} for k in update.get("kosten", [])]
        if update.get("abbruch"):
            aus.append({"typ": "abbruch", "grund": update["abbruch"]})
    return aus
