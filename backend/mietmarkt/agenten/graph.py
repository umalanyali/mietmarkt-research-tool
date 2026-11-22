"""Der Analyse-Graph (LangGraph): Ein Supervisor schickt nacheinander den Standort-, Marktdaten- und Mietansatz-Agenten
los. Jeder Agent arbeitet in einer Schleife „Modell → Werkzeuge → Modell“, bis er ohne Werkzeugaufruf antwortet;
danach prüft der Knoten „validierung“ jede Zahl seiner Antwort gegen die Werkzeugergebnisse.

Ablauf:  START → supervisor → <agent> ⇄ <agent>_werkzeuge → validierung → supervisor → … → END
Nach jedem Schritt sichert der Checkpointer den Zustand unter thread_id = Lauf-ID; so lässt sich ein Lauf nach
einem Absturz oder Neustart mit ainvoke(None, …) an derselben Stelle fortsetzen."""
import json
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from sqlalchemy import Engine
from sqlmodel import Session

from ..format import de
from ..konfig import Konfig
from ..modelle import Projekt
from .kosten import kosten_eur
from .modelle import Modelle
from .pruefung import zahlen_pruefen
from .werkzeuge import werkzeuge
from .zustand import AnalyseZustand

AGENTEN = ("standort", "marktdaten", "mietansatz")
MAX_RUNDEN = 6  # Leitplanke: höchstens so viele Supervisor-Entscheidungen je Lauf

_ZAHLENREGEL = ("Rechne nie selbst. Nenne nur Zahlen, die wörtlich in Werkzeugergebnissen stehen, in deren Einheit, "
                "gerundet höchstens auf die dortigen Nachkommastellen. Antworte knapp auf Deutsch.")
PROMPTS = {
    "supervisor": "Du koordinierst eine Neubau-Mietmarktanalyse. Wähle den nächsten Agenten: standort (Lage, Umfeld, "
                  "Wegezeiten), marktdaten (Comps und Kennzahlen im Umkreis), mietansatz (Zu-/Abschläge auf die "
                  "Comps-Basis) oder fertig. Eine vollständige Analyse braucht alle drei Agenten; wähle fertig erst, "
                  "wenn alle gelaufen sind, oder wenn etwas fehlt, das nur der Nutzer weiß – dann mit Rückfrage. "
                  "Gib jedem Agenten einen kurzen Auftrag.",
    "standort": "Du beschreibst Lage und Umfeld des Projekts mit den Werkzeugen lage (Adresse und Koordinaten aus der "
                "Datenbank) und umfeld. Geokodiere keine Adressen. " + _ZAHLENREGEL,
    "marktdaten": "Du fasst die Marktdaten im Umkreis zusammen (Werkzeuge kennzahlen, comps_filtern). Gibt es keine "
                  "Comps, sage das deutlich. " + _ZAHLENREGEL,
    "mietansatz": "Du schlägst einen Mietansatz vor und holst dazu zuerst die Kennzahlen. Fachregeln: "
                  "1) Der Haupt-Mietansatz geht immer von Regelgeschoss/EG aus (basis regel_eg). "
                  "2) DG ist eine getrennte Herleitung mit basis dg, nie ein Zuschlag auf Regelgeschoss/EG. "
                  "3) Ein Zu- oder Abschlag braucht einen belegten Unterschied zwischen Projekt und Comps und nennt ihn "
                  "in der Begründung (was hat das Projekt, was die Comps). Vermutungen wie „Comps vermutlich ähnlich "
                  "gelegen“ sind kein Grund. Ohne belegten Unterschied gibt es kein Merkmal – dann bleibt es bei der "
                  "Basis. 4) Merkmale ohne Wirkung (0,00) lässt du weg. "
                  "Die Rechnung macht ausschließlich das Werkzeug mietansatz_herleiten. "
                  + _ZAHLENREGEL,
}


class Entscheidung(BaseModel):
    """Strukturierte Antwort des Supervisors (kein freier Text, damit der Code sicher verzweigen kann)."""

    naechster: Literal["standort", "marktdaten", "mietansatz", "fertig"]
    auftrag: str = Field(description="Kurzer Arbeitsauftrag an den Agenten")
    begruendung: str = Field(description="Warum dieser Schritt jetzt dran ist")
    rueckfrage: str | None = Field(default=None, description="Frage an den Nutzer, falls etwas fehlt")


def startzustand(projekt_id: int) -> dict:
    """Leerer Zustand für einen neuen Lauf. Eingabe: Projekt-ID. Ausgabe: dict für graph.ainvoke/astream."""
    return {"projekt_id": projekt_id, "nachrichten": [], "aktiver_agent": None, "ergebnisse": {},
            "entscheidungen": [], "offene_rueckfragen": [], "kosten": [], "abbruch": None}


def lauf_konfig(lauf_id: str) -> dict:
    """LangGraph-Konfiguration eines Laufs. Eingabe: Lauf-ID. Ausgabe: config-dict.

    thread_id ordnet die Checkpoints dem Lauf zu; recursion_limit begrenzt die Schritte als zweite Leitplanke.
    """
    return {"configurable": {"thread_id": lauf_id}, "recursion_limit": 80}


def _projektdaten(p: Projekt) -> str:
    """Stammdaten als Text; zählen bei der Zahlenprüfung als Beleg. Eingabe: Projekt. Ausgabe: Text."""
    return (f"Projekt: {p.name}, {p.adresse}, {p.plz} {p.ort} ({p.ortsteil}); Segment {p.segment}; "
            f"Umkreis {de(p.umkreis_km, 1)} km; Stichtag {p.stichtag:%d.%m.%Y}.")


def _ergebnistexte(z: AnalyseZustand) -> str:
    """Bisherige Antworten der Agenten. Eingabe: Zustand. Ausgabe: Text (oder Hinweis, dass noch nichts vorliegt)."""
    return "\n".join(f"[{a}] {r['text']}" for a, r in z["ergebnisse"].items()) or "Noch keine Ergebnisse."


def _leitplanken(d: Entscheidung, z: AnalyseZustand) -> Entscheidung:
    """Regeln im Code, die das Modell nicht aushebeln kann. Eingabe: Entscheidung, Zustand. Ausgabe: ggf. geändert.

    1. „fertig“ vor allen drei Agenten nur mit Rückfrage – wer früher aufhört, muss dem Nutzer sagen, warum.
    2. Mietansatz erst nach den Marktdaten.
    """
    fehlend = [a for a in AGENTEN if a not in z["ergebnisse"]]
    if d.naechster == "fertig" and not d.rueckfrage and fehlend:
        return d.model_copy(update={"naechster": fehlend[0], "auftrag": "Bearbeite deinen Teil der Analyse.",
                                    "begruendung": f"Leitplanke: {fehlend[0]} fehlt noch, „fertig“ nur mit Rückfrage "
                                                   f"(Modell wollte fertig: {d.begruendung})"})
    if d.naechster == "mietansatz" and "marktdaten" not in z["ergebnisse"]:
        return d.model_copy(update={"naechster": "marktdaten",
                                    "begruendung": "Leitplanke: Mietansatz erst nach den Marktdaten "
                                                   f"(Modell wollte mietansatz: {d.begruendung})"})
    return d


def baue_graph(m: Modelle, e: Engine, k: Konfig, checkpointer: BaseCheckpointSaver | None = None):
    """Baut und kompiliert den Graphen.

    Eingabe: Modelle (echt oder Fake), Datenbank-Engine, Konfig (Budget, Kurs), optional ein Checkpointer.
    Ausgabe: kompilierter Graph (ainvoke/astream wie jede LangChain-Runnable).
    """
    wz = werkzeuge(e, k)
    rollen = {"supervisor": (m.stark, m.name_stark), "standort": (m.schnell, m.name_schnell),
              "marktdaten": (m.schnell, m.name_schnell), "mietansatz": (m.stark, m.name_stark)}
    # json_schema statt Werkzeugaufruf: aktuelle Claude-Modelle lehnen erzwungenes tool_choice ab.
    # include_raw liefert die Rohantwort mit, damit der Tokenverbrauch auch hier zählt.
    entscheider = m.stark.with_structured_output(Entscheidung, method="json_schema", include_raw=True)

    def kosten(agent: str, antwort: AIMessage) -> dict:
        """Verbrauch eines Aufrufs. Eingabe: Agent, Modellantwort. Ausgabe: Eintrag für zustand.kosten."""
        modell = rollen[agent][1]
        u = antwort.usage_metadata or {}
        eur = kosten_eur(modell, u.get("input_tokens", 0), u.get("output_tokens", 0), eur_je_usd=k.ki_eur_je_usd)
        return {"agent": agent, "modell": modell, "eingabe_tokens": u.get("input_tokens", 0),
                "ausgabe_tokens": u.get("output_tokens", 0), "eur": eur.model_dump()}

    def budget_erschoepft(z: AnalyseZustand) -> str | None:
        """Prüft vor jedem Modellaufruf das Budget. Eingabe: Zustand. Ausgabe: Abbruchgrund oder None."""
        summe = sum(x["eur"]["wert"] for x in z["kosten"])
        if summe >= k.ki_budget_eur_pro_lauf:
            return f"Budget von {de(k.ki_budget_eur_pro_lauf)} € erreicht ({de(summe, 4)} € verbraucht)"
        return None

    async def supervisor(z: AnalyseZustand) -> dict:
        """Knoten: entscheidet über den nächsten Agenten und gibt ihm ein frisches Arbeitsgespräch.

        Eingabe: Zustand. Ausgabe: Änderungen (Entscheidung, Kosten, aktiver Agent, neue Nachrichten).
        """
        if grund := budget_erschoepft(z):
            return {"abbruch": grund}
        if len(z["entscheidungen"]) >= MAX_RUNDEN:  # vor dem Aufruf prüfen: die siebte Runde wird nicht bezahlt
            schluss = Entscheidung(naechster="fertig", auftrag="", begruendung=f"Leitplanke: höchstens {MAX_RUNDEN} Runden")
            return {"entscheidungen": [schluss.model_dump() | {"markierungen": []}], "aktiver_agent": None}
        with Session(e) as s:
            p = s.get(Projekt, z["projekt_id"])
        lage = f"{_projektdaten(p)}\n\nBisherige Ergebnisse:\n{_ergebnistexte(z)}"
        antwort = await entscheider.ainvoke([SystemMessage(PROMPTS["supervisor"]), HumanMessage(lage)])
        update = {"kosten": [kosten("supervisor", antwort["raw"])]}
        if antwort["parsed"] is None:
            return {**update, "abbruch": "Antwort des Supervisors war nicht lesbar"}
        d = _leitplanken(antwort["parsed"], z)
        # Auch der Supervisor nennt Zahlen (Begründung, Auftrag, Rückfrage); sie erscheinen in der Oberfläche und
        # werden daher wie Agenten-Antworten gegen Projektdaten und Werkzeugergebnisse geprüft
        belege = [_projektdaten(p)] + [w["ergebnis"] for r in z["ergebnisse"].values() for w in r["werkzeuge"]
                                       if w["status"] != "error"]
        markierungen = zahlen_pruefen("\n".join(filter(None, (d.begruendung, d.auftrag, d.rueckfrage))), belege)
        update |= {"entscheidungen": [d.model_dump() | {"markierungen": markierungen}],
                   "aktiver_agent": None if d.naechster == "fertig" else d.naechster}
        if d.rueckfrage:
            update["offene_rueckfragen"] = [d.rueckfrage]
        if d.naechster != "fertig":
            # Jeder Agent beginnt mit leerem Gespräch: Projektdaten (Beleg für Zahlen) und Auftrag samt bisheriger
            # Ergebnisse. REMOVE_ALL_MESSAGES weist den Reducer add_messages an, die alte Liste zu verwerfen.
            update["nachrichten"] = [RemoveMessage(id=REMOVE_ALL_MESSAGES), HumanMessage(_projektdaten(p)),
                                     HumanMessage(f"Auftrag: {d.auftrag}\n\nBisherige Ergebnisse:\n{_ergebnistexte(z)}")]
        return update

    def agent_knoten(agent: str):
        """Erzeugt den Modell-Knoten eines Agenten. Eingabe: Agentenname. Ausgabe: async Knotenfunktion."""
        gebunden = rollen[agent][0].bind_tools(wz[agent])  # das Modell kennt nur die Werkzeuge seines Agenten

        async def knoten(z: AnalyseZustand) -> dict:
            """Knoten: ein Modellaufruf; enthält die Antwort Werkzeugaufrufe, führt der Werkzeug-Knoten sie aus.

            Eingabe: Zustand. Ausgabe: neue Modellantwort und Kosten (oder Abbruch bei erschöpftem Budget).
            """
            if grund := budget_erschoepft(z):
                return {"abbruch": grund}
            antwort = await gebunden.ainvoke([SystemMessage(PROMPTS[agent]), *z["nachrichten"]])
            return {"nachrichten": [antwort], "kosten": [kosten(agent, antwort)]}

        return knoten

    def nach_agent(agent: str):
        """Verzweigung nach dem Modell-Knoten. Eingabe: Agentenname. Ausgabe: Funktion Zustand → nächster Knoten."""
        def weiter(z: AnalyseZustand) -> str:
            """Abbruch → Ende; Werkzeugaufrufe → Werkzeug-Knoten; sonst ist der Agent fertig → validierung."""
            if z.get("abbruch"):
                return END
            return f"{agent}_werkzeuge" if z["nachrichten"][-1].tool_calls else "validierung"
        return weiter

    def validierung(z: AnalyseZustand) -> dict:
        """Knoten: sammelt Antwort und Werkzeugergebnisse des Agenten und markiert unbelegte Zahlen.

        Eingabe: Zustand. Ausgabe: Ergebnis des aktiven Agenten. Belege sind die Projektdaten und alle erfolgreichen
        Werkzeugergebnisse dieses Laufs – nicht die Texte anderer Agenten (unbelegte Zahlen sollen nicht weiterwandern)
        und keine Fehlermeldungen (die enthalten die Argumente des Modells). Geprüft werden alle Texte des Agenten,
        auch die, die er neben einem Werkzeugaufruf geschrieben hat: sie erscheinen ebenfalls in der Oberfläche.
        """
        nachrichten = z["nachrichten"]
        aufrufe = {a["id"]: a["args"] for n in nachrichten if isinstance(n, AIMessage) for a in n.tool_calls}
        eigene = [{"name": t.name, "argumente": aufrufe.get(t.tool_call_id, {}), "ergebnis": lesen(t.content),
                   "status": t.status} for t in nachrichten if isinstance(t, ToolMessage)]
        frueher = [w for r in z["ergebnisse"].values() for w in r["werkzeuge"]]
        belege = [nachrichten[0].text] + [w["ergebnis"] for w in eigene + frueher if w["status"] != "error"]
        texte = "\n".join(n.text for n in nachrichten if isinstance(n, AIMessage) and n.text)
        return {"ergebnisse": {z["aktiver_agent"]: {"text": nachrichten[-1].text, "werkzeuge": eigene,
                                                    "markierungen": zahlen_pruefen(texte, belege)}}}

    g = StateGraph(AnalyseZustand)
    g.add_node("supervisor", supervisor)
    g.add_node("validierung", validierung)
    for agent in AGENTEN:
        g.add_node(agent, agent_knoten(agent))
        # ToolNode führt die Werkzeugaufrufe der letzten Modellantwort aus und hängt je Aufruf eine ToolMessage an.
        # handle_tool_errors: ein Fehler (z. B. leere Begründung) geht als Text ans Modell zurück, statt abzubrechen.
        g.add_node(f"{agent}_werkzeuge", ToolNode(wz[agent], messages_key="nachrichten", handle_tool_errors=True))
        g.add_conditional_edges(agent, nach_agent(agent), [f"{agent}_werkzeuge", "validierung", END])
        g.add_edge(f"{agent}_werkzeuge", agent)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", lambda z: END if z.get("abbruch") or not z["aktiver_agent"]
                            else z["aktiver_agent"], [*AGENTEN, END])
    g.add_edge("validierung", "supervisor")
    return g.compile(checkpointer=checkpointer)


def lesen(inhalt: str) -> object:
    """Werkzeugergebnis zurück in Daten. Eingabe: JSON-Text (oder Fehlermeldung). Ausgabe: dict/list oder Text."""
    try:
        return json.loads(inhalt)
    except (TypeError, ValueError):
        return inhalt
