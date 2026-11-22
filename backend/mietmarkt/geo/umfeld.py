"""Umfeld eines Standorts: Orte aus Overpass, Luftlinie (Python) und Wegezeiten (OSRM) zu den nächsten je Kategorie.
Fällt das Routing aus, bleibt die Luftlinie, gekennzeichnet als Methode „Luftlinie“."""
import datetime as dt
from typing import Literal

from pydantic import BaseModel
from sqlmodel import Session

from ..format import de
from ..modelle import Herkunft, Wert
from .dienste import ATTRIBUTION, KATEGORIEN, umfeld_pois, wegezeiten
from .distanz import entfernung_km

JE_KATEGORIE = 3  # nur die nächsten Orte bekommen Wegezeiten, das hält die Routing-Anfragen klein
Methode = Literal["Route", "Luftlinie"]


class UmfeldPoi(BaseModel):
    """Ein Ort mit Entfernung und, wenn verfügbar, Wegezeiten."""

    kategorie: str
    name: str
    lat: float
    lon: float
    luftlinie: Wert
    zu_fuss: Wert | None
    rad: Wert | None
    methode_fuss: Methode
    methode_rad: Methode


class Umfeld(BaseModel):
    """Ergebnis für die Oberfläche, mit Quellenhinweis."""

    pois: list[UmfeldPoi]
    radius_m: int
    attribution: str = ATTRIBUTION


def _minuten(profil: str, dauer_s: float, weg_m: float, stand: dt.date) -> Wert:
    """Wegezeit als Wert. Eingabe: Profilname, Dauer in s, Weglänge in m, Abrufdatum. Ausgabe: Wert in Minuten mit Rechenweg."""
    return Wert(wert=dauer_s / 60, einheit="min", herkunft=Herkunft.BERECHNET,
                rechenweg_text=f"{profil} {de(weg_m, 0)} m laut OSRM (routing.openstreetmap.de, abgerufen am "
                               f"{stand:%d.%m.%Y}): {de(dauer_s / 60, 1)} min")


async def umfeld(lat: float, lon: float, s: Session, radius_m: int = 1000) -> Umfeld:
    """Die nächsten Orte je Kategorie mit Luftlinie und Wegezeiten.

    Eingabe: Standort, Sitzung, Radius in m. Ausgabe: Umfeld, sortiert nach Kategorie und Entfernung.
    Wirft DienstNichtErreichbar, wenn Overpass ausfällt; ein Routing-Ausfall führt nur zur Luftlinie.
    """
    alle = [(p, entfernung_km(lat, lon, p.lat, p.lon)) for p in await umfeld_pois(lat, lon, s, radius_m)]
    auswahl = []
    for kategorie in KATEGORIEN:
        naechste = sorted((x for x in alle if x[0].kategorie == kategorie), key=lambda x: x[1].wert)
        auswahl.extend(naechste[:JE_KATEGORIE])
    zeiten = await wegezeiten((lat, lon), [(p.lat, p.lon) for p, _ in auswahl], s)
    pois = []
    for i, (p, luft) in enumerate(auswahl):
        # None: Dienst ausgefallen (ganzes Profil) oder Ziel nicht routbar (einzelner Eintrag) – beides heißt Luftlinie
        fuss = zeiten["fuss"][i] if zeiten["fuss"] else None
        rad = zeiten["rad"][i] if zeiten["rad"] else None
        pois.append(UmfeldPoi(
            kategorie=p.kategorie, name=p.name, lat=p.lat, lon=p.lon, luftlinie=luft,
            zu_fuss=_minuten("Fußweg", *fuss) if fuss else None, rad=_minuten("Radweg", *rad) if rad else None,
            methode_fuss="Route" if fuss else "Luftlinie", methode_rad="Route" if rad else "Luftlinie",
        ))
    return Umfeld(pois=pois, radius_m=radius_m)
