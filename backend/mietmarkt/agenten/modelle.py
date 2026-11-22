"""Die zwei Sprachmodell-Rollen des Laufs: „stark“ (Supervisor, Mietansatz) und „schnell“ (Standort, Marktdaten).
Tests reichen hier Fake-Modelle hinein; nur aus_konfig() spricht mit der Anthropic-API."""
from dataclasses import dataclass

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel

from ..konfig import Konfig


@dataclass
class Modelle:
    """Beide Rollen samt Modellname (der Name bestimmt den Preis in kosten.PREISE_USD)."""

    stark: BaseChatModel
    schnell: BaseChatModel
    name_stark: str
    name_schnell: str


def aus_konfig(k: Konfig) -> Modelle:
    """Echte Claude-Modelle laut .env. Eingabe: Konfig (mit Schlüssel). Ausgabe: Modelle.

    Keine temperature: die aktuellen Claude-Modelle lehnen Sampling-Parameter ab.
    """
    def anlegen(name: str) -> ChatAnthropic:
        """Ein Modell mit festem Antwortlimit. Eingabe: Modell-ID. Ausgabe: ChatAnthropic."""
        return ChatAnthropic(model=name, api_key=k.anthropic_api_key, max_tokens=4096, max_retries=2)

    return Modelle(stark=anlegen(k.modell_stark), schnell=anlegen(k.modell_schnell),
                   name_stark=k.modell_stark, name_schnell=k.modell_schnell)
