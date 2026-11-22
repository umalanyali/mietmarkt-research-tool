"""Einstellungen aus der Datei .env im Repository (pydantic-settings): Anthropic-Schlüssel, Modelle, Budget.
Fehlt der Schlüssel, läuft die App ohne KI weiter und meldet „KI nicht konfiguriert“."""
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from .agenten.kosten import PREISE_USD
from .db import REPO


class Konfig(BaseSettings):
    """Werte aus .env oder Umgebungsvariablen (Groß-/Kleinschreibung egal, z. B. ANTHROPIC_API_KEY)."""

    model_config = SettingsConfigDict(env_file=REPO / ".env", extra="ignore")

    # SecretStr: der Schlüssel erscheint nie in repr(), Logs oder Fehlermeldungen (CLAUDE.md Regel 4)
    anthropic_api_key: SecretStr | None = None
    modell_stark: str = "claude-sonnet-5-5"
    modell_schnell: str = "claude-haiku-5-5"
    ki_budget_eur_pro_lauf: float = 0.50
    ki_eur_je_usd: float = 0.86  # Umrechnungskurs für die Kostenanzeige; Anthropic rechnet in US-Dollar ab
    # Importierte Portal-Daten (RIWIS, VALUE, Portal-Exporte) gehen nur mit ausdrücklicher Freigabe an Anthropic,
    # denn ihre Lizenz erlaubt die Weitergabe an Dritte oft nicht. Demo-Daten und selbst erfasste Werte immer.
    ki_portaldaten_senden: bool = False
    # Mietwachstum g p. a. für die Fortschreibung des Mietansatzes bis zum Vermarktungsstart, wenn das Projekt
    # keinen eigenen Wert hat (0.02 = 2 %)
    mietwachstum_pa: float = 0.02

    @property
    def ki_konfiguriert(self) -> bool:
        """Ob ein Schlüssel eingetragen ist. Eingabe: keine. Ausgabe: True/False (leerer Eintrag zählt als fehlend)."""
        return bool(self.anthropic_api_key and self.anthropic_api_key.get_secret_value().strip())

    @property
    def ki_problem(self) -> str | None:
        """Warum die KI nicht nutzbar ist. Eingabe: keine. Ausgabe: Meldung oder None.

        Ein Modell ohne Preis wird vor jedem Aufruf abgelehnt: sonst wären Aufrufe bezahlt, aber das Budget sähe 0 €.
        """
        if not self.ki_konfiguriert:
            return "KI nicht konfiguriert"
        ohne_preis = [m for m in (self.modell_stark, self.modell_schnell) if m not in PREISE_USD]
        if ohne_preis:
            return f"Kein Preis für {', '.join(ohne_preis)} in mietmarkt/agenten/kosten.py – Budget nicht prüfbar"
        return None
