"""FastAPI-Anwendung. Die Endpunkte reichen nur an das Fachpaket `mietmarkt` weiter."""
from fastapi import FastAPI

from mietmarkt import __version__

app = FastAPI(title="Mietmarkt Research", version=__version__)


@app.get("/api/gesundheit")
def gesundheit() -> dict[str, str]:
    """Lebenszeichen für Startskript und Tests.

    Eingabe: keine.
    Ausgabe: {"status": "ok", "version": <Paketversion>}.
    """
    return {"status": "ok", "version": __version__}
