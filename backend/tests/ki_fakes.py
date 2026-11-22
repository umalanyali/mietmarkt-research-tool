"""Geskriptete Sprachmodelle für Agenten-Tests: laufen ohne Netz und ohne API-Schlüssel."""
import json
import re

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import RunnableLambda
from pydantic import Field, ValidationError

from mietmarkt.agenten.modelle import Modelle


class FakeModell(FakeMessagesListChatModel):
    """Gibt die vorgegebenen Antworten der Reihe nach zurück; `i` zählt die Aufrufe.

    Ergänzt, was das echte ChatAnthropic kann und der Fake nicht: Werkzeuge binden und strukturierte Ausgabe.
    Anders als das Original beginnt es nach der letzten Antwort nicht von vorn, sondern scheitert – so fällt
    jeder unerwartete zusätzliche Modellaufruf im Test auf.
    """

    fehler: bool = False  # True: jeder Aufruf scheitert (simuliert einen Absturz mitten im Lauf)
    aufrufe: list = Field(default_factory=list)  # Eingaben je Aufruf (Nachrichtenlisten), für Prüfungen im Test

    def bind_tools(self, tools, **kwargs):
        """Werkzeuge werden ignoriert; die Antworten enthalten die Werkzeugaufrufe schon. Ausgabe: das Modell selbst."""
        return self

    def _naechste(self) -> AIMessage:
        """Nächste vorgegebene Antwort. Ausgabe: AIMessage (oder Fehler bei Absturz-Simulation/Skriptende)."""
        if self.fehler:
            raise RuntimeError("simulierter Absturz")
        if self.i >= len(self.responses):
            raise AssertionError(f"Unerwarteter Modellaufruf Nr. {self.i + 1}: Skript hat nur {len(self.responses)}")
        self.i += 1
        return self.responses[self.i - 1]

    def _generate(self, messages, *args, **kwargs):
        """Antwort am Stück (ohne Streaming). Ausgabe: ChatResult."""
        self.aufrufe.append(messages)
        return ChatResult(generations=[ChatGeneration(message=self._naechste())])

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        """Antwort in Stücken wie bei ChatAnthropic (LangGraph streamt im Modus „messages“).

        Text Wort für Wort; Werkzeugaufrufe und Tokenverbrauch hängen am letzten Stück. Ausgabe: Stücke.
        """
        self.aufrufe.append(messages)
        antwort = self._naechste()
        woerter = re.findall(r"\S+\s*", antwort.text) or [""]
        for i, wort in enumerate(woerter):
            letztes = i == len(woerter) - 1
            stueck = AIMessageChunk(content=wort, tool_call_chunks=[
                {"name": a["name"], "args": json.dumps(a["args"]), "id": a["id"], "index": n}
                for n, a in enumerate(antwort.tool_calls)] if letztes else [],
                usage_metadata=antwort.usage_metadata if letztes else None)
            if run_manager:
                run_manager.on_llm_new_token(wort, chunk=ChatGenerationChunk(message=stueck))
            yield ChatGenerationChunk(message=stueck)

    def with_structured_output(self, schema, *, include_raw=False, method=None, **kwargs):
        """Strukturierte Ausgabe wie bei method="json_schema": Antworttext ist JSON. Ausgabe: Runnable."""
        async def auswerten(eingabe):
            """Ruft das Modell und liest das JSON. Eingabe: Nachrichten. Ausgabe: raw/parsed wie bei LangChain."""
            roh = await self.ainvoke(eingabe)
            try:
                geparst, fehler = schema.model_validate_json(roh.text), None
            except ValidationError as f:  # wie das echte Modell mit include_raw: parsed None statt Ausnahme
                geparst, fehler = None, f
            return {"raw": roh, "parsed": geparst, "parsing_error": fehler} if include_raw else geparst
        return RunnableLambda(lambda x: None, afunc=auswerten)


def ki(text: str = "", werkzeuge: tuple[tuple[str, dict], ...] = (), eingabe: int = 100, ausgabe: int = 50) -> AIMessage:
    """Eine Modellantwort mit Text, Werkzeugaufrufen und Tokenverbrauch. Ausgabe: AIMessage."""
    aufrufe = [{"name": n, "args": a, "id": f"aufruf-{n}-{i}", "type": "tool_call"} for i, (n, a) in enumerate(werkzeuge)]
    return AIMessage(content=text, tool_calls=aufrufe,
                     usage_metadata={"input_tokens": eingabe, "output_tokens": ausgabe, "total_tokens": eingabe + ausgabe})


def entscheidung(naechster: str, auftrag: str = "Bitte bearbeiten.", rueckfrage: str | None = None,
                 eingabe: int = 100, ausgabe: int = 50, begruendung: str | None = None) -> AIMessage:
    """Antwort des Supervisors als JSON (strukturierte Ausgabe). Ausgabe: AIMessage."""
    return ki(json.dumps({"naechster": naechster, "auftrag": auftrag, "begruendung": begruendung or f"als Nächstes {naechster}",
                          "rueckfrage": rueckfrage}), eingabe=eingabe, ausgabe=ausgabe)


def befunde(*schweregrade: str) -> AIMessage:
    """Antwort des Prüf-Agenten (strukturierte Ausgabe) mit je einem Befund je Schweregrad. Ausgabe: AIMessage."""
    return ki(json.dumps({"befunde": [{"pruefung": "abgleich", "schweregrad": g, "text": f"Befund {g}."}
                                      for g in schweregrade]}))


def bericht(**abschnitte: str | list[dict]) -> AIMessage:
    """Antwort des Bericht-Agenten (strukturierte Ausgabe): je Abschnitt Sätze mit Belegen. Ein Text wird ein Satz
    mit Beleg „projekt“ (unter Risiken „befund:1“); fehlende Abschnitte bekommen Standardtext. Ausgabe: AIMessage."""
    texte = {"lage": "Ruhige Lage am Lindenplatz.", "markt": "Median {{wert:kennzahlen.comps.median}}.",
             "mietansatz": "Ansatz {{wert:mietansatz.regel_eg.ergebnis}}.", "risiken": "Keine kritischen Befunde."}
    texte |= abschnitte
    # Unter Risiken zählt nur ein Befund als Beleg; die Test-Skripte haben stets mindestens einen
    return ki(json.dumps({k: v if isinstance(v, list) else [{"text": v, "belege": ["befund:1" if k == "risiken"
                                                                                 else "projekt"]}]
                          for k, v in texte.items()}))


def modelle(stark: list[AIMessage], schnell: list[AIMessage], *, schnell_fehler: bool = False) -> Modelle:
    """Fake-Modelle mit echten Modellnamen (für die Preistabelle). Ausgabe: Modelle."""
    return Modelle(stark=FakeModell(responses=stark), schnell=FakeModell(responses=schnell, fehler=schnell_fehler),
                   name_stark="claude-sonnet-5-5", name_schnell="claude-haiku-5-5")
