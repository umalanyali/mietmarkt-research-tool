"""Zustand des Analyse-Graphen. LangGraph reicht dieses dict von Knoten zu Knoten weiter; jeder Knoten gibt nur
die Felder zurück, die er ändert. Wie eine Änderung eingearbeitet wird, legt der „Reducer“ je Feld fest
(Annotated[Typ, reducer]): ohne Reducer wird überschrieben, mit operator.add angehängt."""
import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


def _zusammenfuehren(alt: dict, neu: dict) -> dict:
    """Reducer für Ergebnisse: neue Agenten-Ergebnisse ergänzen bzw. ersetzen alte; None löscht eines (der Agent gilt
    dann als nicht erledigt, z. B. nach abgelehnter Freigabe). Ausgabe: zusammengeführtes dict."""
    return {k: v for k, v in {**alt, **neu}.items() if v is not None}


class AnalyseZustand(TypedDict):
    """Alles, was der Lauf weiß. Wird nach jedem Schritt im Checkpointer gesichert (Wiederaufnahme nach Neustart)."""

    projekt_id: int
    # Arbeitsgespräch des gerade aktiven Agenten (Auftrag, Modellantworten, Werkzeugergebnisse).
    # add_messages hängt an; der Supervisor leert es mit RemoveMessage, bevor er den nächsten Agenten losschickt.
    nachrichten: Annotated[list[AnyMessage], add_messages]
    aktiver_agent: str | None
    # je Agent: {"text", "werkzeuge": [{name, argumente, ergebnis}], "markierungen": [unbelegte Zahlen]}
    ergebnisse: Annotated[dict[str, dict], _zusammenfuehren]
    entscheidungen: Annotated[list[dict], operator.add]  # jede Supervisor-Entscheidung mit Begründung
    rueckfragen: Annotated[list[str], operator.add]  # Fragen des Supervisors an den Nutzer
    antworten: Annotated[list[str], operator.add]  # Antworten des Nutzers, gleiche Reihenfolge
    kosten: Annotated[list[dict], operator.add]  # je Modellaufruf: agent, modell, Token, eur (Wert)
    vorschlag: dict | None  # letzte Herleitung (regel_eg) des Mietansatz-Agenten samt Begründung, wartet auf Freigabe
    # Entscheidung des Nutzers {aktion, aenderungen, kommentar, herleitung}; herleitung ist der gültige Mietansatz
    # (None nach Ablehnen). Ein kritischer Prüfbefund setzt das ganze Feld zurück auf None.
    freigabe: dict | None
    pruefungen: Annotated[list[list[dict]], operator.add]  # Befunde je Prüfrunde; die Länge zählt die Runden
    bericht: dict | None  # gefüllter Bericht {abschnitte, fussnoten, markierungen, befunde, herleitung}
    abbruch: str | None  # gesetzt, wenn der Lauf vorzeitig endet (z. B. Budget)
