"""Backend mit Fake-Modellen für das Playwright-Skript frontend/skripte/lauf.mjs: Demo-Datenbank im Temp-Ordner,
ein geskripteter Lauf bis zum Bericht, kein API-Schlüssel und kein Netz zu Anthropic. Startet nur mit KI_FAKE=1."""
import os
import signal
import sys
import tempfile
from pathlib import Path

import uvicorn
from ki_fakes import befunde, bericht, entscheidung, ki, modelle
from sqlmodel import Session

from api import main
from mietmarkt.db import engine
from mietmarkt.demo import seed
from mietmarkt.konfig import Konfig


def skript():
    """Ein Lauf: Standort, Marktdaten, Mietansatz (hält an der Freigabe), Prüfung, Bericht. Ausgabe: Modelle.

    Die Liste wird der Reihe nach verbraucht; deshalb genau ein Lauf je Serverstart.
    """
    return modelle(
        stark=[entscheidung("standort"), entscheidung("marktdaten"), entscheidung("mietansatz"), ki(werkzeuge=(
            ("mietansatz_herleiten", {"basis": "regel_eg", "anpassungen": [
                {"name": "Energiestandard", "betrag": 0.3, "begruendung": "Effizienzhaus 40 statt 55 bei den Comps"}]}),
            ("mietansatz_herleiten", {"basis": "dg", "anpassungen": []}))),
            ki("Basis aus den Regelgeschoss-Comps, Zuschlag für den besseren Energiestandard."),
            befunde("hinweis"), bericht()],
        schnell=[ki("Der Standort liegt ruhig, Haltestellen sind fußläufig erreichbar."),
                 ki(werkzeuge=(("kennzahlen", {}),)), ki("Die Comps im Umkreis sind ausgewertet.")])


def starten(port: int) -> None:
    """Startet die API mit Fake-Modellen auf 127.0.0.1:port. Eingabe: Port. Ausgabe: keine (läuft bis Strg+C)."""
    # Temp-Ordner wird nach dem Beenden gelöscht (Datenbank, Checkpoints, Uploads). uvicorn löst SIGTERM nach dem
    # Herunterfahren erneut aus; ohne eigenen Handler endete der Prozess dann, bevor „with“ aufräumt
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    with tempfile.TemporaryDirectory(prefix="mietmarkt-fake-", ignore_cleanup_errors=True) as pfad:
        _mit_ordner(Path(pfad), port)


def _mit_ordner(ordner: Path, port: int) -> None:
    """Richtet Datenbank und Overrides im Ordner ein und startet uvicorn. Eingabe: Ordner, Port. Ausgabe: keine."""
    e = engine(ordner / "fake.db")
    seed(e)
    m = skript()

    def fake_sitzung():
        """Sitzung auf die Fake-Datenbank. Ausgabe: Session (als Generator)."""
        with Session(e) as s:
            yield s

    main.app.dependency_overrides.update({
        main.sitzung: fake_sitzung,
        # Platzhalter-Schlüssel nur, damit die App „KI konfiguriert“ meldet; er verlässt den Prozess nie
        main.konfig: lambda: Konfig(_env_file=None, anthropic_api_key="fake"),
        main.ki_modelle: lambda: m,
        main.checkpoint_pfad: lambda: ordner / "checkpoints.db",
    })
    uvicorn.run(main.app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    if os.environ.get("KI_FAKE") != "1":
        sys.exit("Nur für Tests: mit KI_FAKE=1 starten")
    starten(int(os.environ.get("FAKE_PORT", "8010")))
