"""Externe Geodienste: Photon (Autovervollständigung), Nominatim (Geokodieren, Rückwärtssuche), Overpass (Umfeld),
OSRM (Wegezeiten zu Fuß/Rad). Jede Anfrage läuft über den Cache, Nominatim/Overpass/OSRM zusätzlich über eine Drossel.
Nominatim wird bewusst nicht für die Autovervollständigung genutzt (Nutzungsrichtlinie)."""
import asyncio
import datetime as dt
import threading
import time
from collections.abc import Callable

import httpx
from pydantic import BaseModel, Field
from sqlmodel import Session

from . import cache

USER_AGENT = "MietmarktResearch/0.1 (privates Projekt)"  # CLAUDE.md Regel 6
ATTRIBUTION = "© OpenStreetMap-Mitwirkende"
PHOTON_URL = "https://photon.komoot.io/api/"
NOMINATIM_URL = "https://nominatim.openstreetmap.org"
# Bewusst ohne Rückfall-Server: die erreichbare Alternative läge außerhalb der EU (Datenschutz, Befund S5)
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT_S = 25  # Rechenzeit-Limit, das Overpass sich selbst setzt ([timeout:25])
# Der OSRM-Demo-Server (router.project-osrm.org) kennt nur das Autoprofil und liefert für „foot“ Autozeiten.
# Die FOSSGIS-Instanzen sprechen dieselbe OSRM-API, aber mit echten Fuß- und Radprofilen.
ROUTING_URL = {"fuss": "https://routing.openstreetmap.de/routed-foot", "rad": "https://routing.openstreetmap.de/routed-bike"}
BBOX_DE = "5.87,47.27,15.04,55.06"  # Deutschland: West, Süd, Ost, Nord


class DienstNichtErreichbar(Exception):
    """Ein externer Dienst antwortet nicht oder mit Fehler."""

    def __init__(self, dienst: str, grund: str):
        """Eingabe: Dienstname, Grund (Fehlermeldung). Ausgabe: Ausnahme mit lesbarem Text."""
        super().__init__(f"{dienst} nicht erreichbar: {grund}")
        self.dienst = dienst


class Drossel:
    """Mindestabstand zwischen zwei Anfragen an denselben Dienst, prozessweit (ein Objekt je Dienst)."""

    def __init__(self, abstand_s: float):
        """Eingabe: Mindestabstand in Sekunden. Ausgabe: Drossel ohne bisherige Anfrage."""
        self.abstand_s = abstand_s
        self._letzte = 0.0
        # threading.Lock statt asyncio.Lock: gilt auch über Threads und Ereignisschleifen hinweg (Befund P5)
        self._sperre = threading.Lock()

    def zuruecksetzen(self) -> None:
        """Vergisst die letzte Anfrage (für Tests). Eingabe: keine. Ausgabe: keine."""
        self._letzte = 0.0

    async def warte(self) -> None:
        """Wartet, bis die eigene Anfrage an der Reihe ist. Eingabe: keine. Ausgabe: keine.

        Jeder Aufruf reserviert unter der Sperre den nächsten freien Zeitpunkt und schläft danach außerhalb der
        Sperre – so blockiert das Warten keine Ereignisschleife und zwei Aufrufe bekommen nie denselben Zeitpunkt.
        """
        with self._sperre:
            start = max(time.monotonic(), self._letzte + self.abstand_s)
            self._letzte = start
        await asyncio.sleep(start - time.monotonic())


PHOTON_DROSSEL = Drossel(0.5)  # Photon: kein festes Limit, aber Regel 6 (gedrosselt); Tippen ist ohnehin entprellt
NOMINATIM_DROSSEL = Drossel(1.0)  # Nominatim: höchstens 1 Anfrage pro Sekunde
OVERPASS_DROSSEL = Drossel(1.0)
ROUTING_DROSSEL = Drossel(1.0)


# Eine laufende Anfrage je Schlüssel: gleichzeitige gleiche Anfragen warten auf die erste (Befund P2)
_laufend: dict[tuple[int, str], asyncio.Lock] = {}


async def _abrufen[T](s: Session, dienst: str, url: str, auswerten: Callable[[object, dt.date], T], *, params: dict | None = None,
                      daten: dict | None = None, drossel: Drossel | None = None, timeout: float = 10.0) -> T:
    """Fragt einen Dienst ab, mit Cache, optionaler Drossel und Auswertung.

    Eingabe: Sitzung (Cache), Dienstname, URL, Auswertungsfunktion für JSON und Abrufdatum, Query-Parameter oder Formulardaten
    (dann POST), Drossel, Timeout in s.
    Ausgabe: ausgewertete Antwort. Netzwerkfehler und Antworten, die sich nicht auswerten lassen, werden zu
    DienstNichtErreichbar und landen nicht im Cache.
    """
    anfrage = {"url": url, "params": params, "daten": daten}
    schluessel = (id(asyncio.get_running_loop()), cache.schluessel(anfrage))
    sperre = _laufend.setdefault(schluessel, asyncio.Lock())
    async with sperre:
        try:
            treffer = cache.lesen(s, dienst, anfrage)
            if treffer is not None:
                return auswerten(treffer[0], treffer[1].astimezone().date())
            if drossel:
                await drossel.warte()
            try:
                async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT, "Accept-Language": "de"}, timeout=timeout) as c:
                    antwort = await (c.post(url, data=daten) if daten is not None else c.get(url, params=params))
                    antwort.raise_for_status()
                    json = antwort.json()
                ergebnis = auswerten(json, dt.date.today())  # erst prüfen, dann cachen: eine kaputte Antwort soll nicht 30 Tage bleiben
            except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as e:
                raise DienstNichtErreichbar(dienst, str(e) or type(e).__name__) from e
            cache.schreiben(s, dienst, anfrage, json)
            return ergebnis
        finally:
            if not sperre.locked() or len(_laufend) > 1000:
                _laufend.pop(schluessel, None)


# ------------------------------------------------------------------ Photon: Autovervollständigung


class Vorschlag(BaseModel):
    """Ein Adressvorschlag aus Photon; kommt beim Anlegen eines Projekts vom Browser zurück, daher mit Grenzen."""

    label: str = Field(max_length=200)
    strasse: str = Field(max_length=200)
    plz: str = Field(max_length=10)
    ort: str = Field(max_length=200)
    ortsteil: str = Field(max_length=200)
    # Deutschland samt Rand (bbox); schließt auch NaN und Unendlich aus
    lat: float = Field(ge=47.0, le=55.2, allow_inf_nan=False)
    lon: float = Field(ge=5.8, le=15.1, allow_inf_nan=False)


async def vorschlaege(q: str, s: Session) -> list[Vorschlag]:
    """Adressvorschläge in Deutschland. Eingabe: Suchtext, Sitzung. Ausgabe: bis zu 5 Vorschläge."""
    return await _abrufen(s, "photon", PHOTON_URL, lambda d, _: _vorschlaege_aus(d), drossel=PHOTON_DROSSEL,
                          params={"q": q, "lang": "de", "limit": 5, "bbox": BBOX_DE})


def _vorschlaege_aus(daten: dict) -> list[Vorschlag]:
    """Photon-Antwort in Vorschläge umwandeln. Eingabe: GeoJSON. Ausgabe: Vorschläge (KeyError bei fremdem Format)."""
    ergebnis = []
    for f in daten["features"]:
        p = f.get("properties", {})
        lon, lat = f["geometry"]["coordinates"]
        strasse = " ".join(x for x in (p.get("street") or p.get("name", ""), p.get("housenumber", "")) if x)
        ort = p.get("city") or p.get("town") or p.get("village") or p.get("county", "")
        label = ", ".join(x for x in (strasse, f"{p.get('postcode', '')} {ort}".strip()) if x)
        ergebnis.append(Vorschlag(label=label, strasse=strasse, plz=p.get("postcode", ""), ort=ort,
                                  ortsteil=p.get("district") or p.get("locality") or "", lat=lat, lon=lon))
    return ergebnis


# ------------------------------------------------------------------ Nominatim: Geokodieren, Rückwärtssuche


class Ort(BaseModel):
    """Eine geokodierte Adresse."""

    adresse: str
    plz: str
    ort: str
    ortsteil: str
    lat: float
    lon: float


def _ort(treffer: dict) -> Ort:
    """Nominatim-Treffer in Ort umwandeln. Eingabe: Treffer mit address-Block. Ausgabe: Ort."""
    a = treffer.get("address", {})
    adresse = " ".join(x for x in (a.get("road", ""), a.get("house_number", "")) if x)
    return Ort(adresse=adresse, plz=a.get("postcode", ""),
               ort=a.get("city") or a.get("town") or a.get("village") or a.get("municipality", ""),
               ortsteil=a.get("suburb") or a.get("city_district") or a.get("quarter") or a.get("borough", ""),
               lat=float(treffer["lat"]), lon=float(treffer["lon"]))


async def geokodieren(text: str, s: Session) -> Ort | None:
    """Endgültiges Geokodieren einer Adresse in Deutschland. Eingabe: Adresstext, Sitzung. Ausgabe: Ort oder None."""
    return await _abrufen(s, "nominatim", f"{NOMINATIM_URL}/search", lambda t, _: _ort(t[0]) if t else None,
                          drossel=NOMINATIM_DROSSEL,
                          params={"q": text, "format": "jsonv2", "addressdetails": 1, "limit": 1, "countrycodes": "de"})


async def rueckwaerts(lat: float, lon: float, s: Session) -> Ort | None:
    """Adresse zu Koordinaten. Eingabe: lat, lon, Sitzung. Ausgabe: Ort oder None."""
    return await _abrufen(s, "nominatim", f"{NOMINATIM_URL}/reverse", lambda t, _: _ort(t) if t and "lat" in t else None,
                          drossel=NOMINATIM_DROSSEL, params={"lat": lat, "lon": lon, "format": "jsonv2", "addressdetails": 1})


# ------------------------------------------------------------------ Overpass: Umfeld


class Poi(BaseModel):
    """Ein Ort im Umfeld."""

    kategorie: str
    name: str
    lat: float
    lon: float


# Reihenfolge = Anzeige-Reihenfolge; Filter in Overpass-QL
KATEGORIEN = {
    "ÖPNV": ['node["highway"="bus_stop"]', 'node["railway"~"^(station|halt|tram_stop)$"]'],
    "Supermarkt": ['nwr["shop"="supermarket"]'],
    "Schule": ['nwr["amenity"="school"]'],
    "Kita": ['nwr["amenity"="kindergarten"]'],
    "Arzt": ['nwr["amenity"~"^(doctors|clinic)$"]', 'nwr["healthcare"="doctor"]'],
}


def _kategorie(tags: dict) -> str | None:
    """Ordnet OSM-Tags einer Kategorie zu. Eingabe: Tags. Ausgabe: Kategorie oder None."""
    if tags.get("highway") == "bus_stop" or tags.get("railway") in ("station", "halt", "tram_stop"):
        return "ÖPNV"
    if tags.get("shop") == "supermarket":
        return "Supermarkt"
    if tags.get("amenity") == "school":
        return "Schule"
    if tags.get("amenity") == "kindergarten":
        return "Kita"
    if tags.get("amenity") in ("doctors", "clinic") or tags.get("healthcare") == "doctor":
        return "Arzt"
    return None


async def umfeld_pois(lat: float, lon: float, s: Session, radius_m: int = 1000) -> list[Poi]:
    """Haltestellen, Supermärkte, Schulen, Kitas und Ärzte im Radius.

    Eingabe: Mittelpunkt, Sitzung, Radius in m. Ausgabe: POIs in Antwort-Reihenfolge; Wege/Flächen über ihren Mittelpunkt.
    """
    teile = "".join(f"{f}(around:{radius_m},{lat},{lon});" for filter_ in KATEGORIEN.values() for f in filter_)
    abfrage = f"[out:json][timeout:{OVERPASS_TIMEOUT_S}];({teile});out center tags;"
    # Client wartet länger als das Server-Limit, weil Warteschlange und Übertragung dazukommen
    return await _abrufen(s, "overpass", OVERPASS_URL, lambda d, _: _pois_aus(d), daten={"data": abfrage}, drossel=OVERPASS_DROSSEL,
                          timeout=OVERPASS_TIMEOUT_S + 15)


def _pois_aus(daten: dict) -> list[Poi]:
    """Overpass-Antwort in POIs umwandeln. Eingabe: JSON. Ausgabe: POIs; ValueError bei gemeldetem Abbruch."""
    # Überlast meldet Overpass oft mit HTTP 200 und einer Bemerkung statt eines Fehlerstatus (Befund P3)
    if "error" in daten.get("remark", ""):
        raise ValueError(daten["remark"])
    pois = []
    for e in daten["elements"]:
        tags = e.get("tags", {})
        kategorie = _kategorie(tags)
        punkt = e if "lat" in e else e.get("center")
        if kategorie and punkt:
            pois.append(Poi(kategorie=kategorie, name=tags.get("name", kategorie), lat=punkt["lat"], lon=punkt["lon"]))
    return pois


# ------------------------------------------------------------------ OSRM: Wegezeiten


Zeit = tuple[float, float, dt.date]  # Dauer in s, Weg in m, Abrufdatum


def _zeiten_aus(d: dict, stand: dt.date) -> list[Zeit | None]:
    """OSRM-Tabelle in (Dauer, Weg, Abrufdatum) je Ziel.

    Eingabe: JSON, Abrufdatum. Ausgabe: Liste; None für nicht routbare Ziele (OSRM liefert dort null).
    """
    return [None if dauer is None or weg is None else (dauer, weg, stand)
            for dauer, weg in zip(d["durations"][0][1:], d["distances"][0][1:], strict=True)]


async def wegezeiten(start: tuple[float, float], ziele: list[tuple[float, float]],
                     s: Session) -> dict[str, list[Zeit | None] | None]:
    """Dauer (s) und Weglänge (m) vom Start zu jedem Ziel, je Profil fuss/rad.

    Eingabe: Start (lat, lon), Ziele, Sitzung. Ausgabe: je Profil eine Liste (Dauer, Weg, Abrufdatum) – None für ein nicht
    routbares Ziel – oder None für das ganze Profil, wenn der Dienst ausfällt; dann rechnet der Aufrufer mit Luftlinie.
    """
    if not ziele:
        return {"fuss": [], "rad": []}
    punkte = ";".join(f"{lon},{lat}" for lat, lon in [start, *ziele])  # OSRM erwartet lon,lat
    ergebnis: dict[str, list[Zeit | None] | None] = {}
    for profil, basis in ROUTING_URL.items():
        try:
            ergebnis[profil] = await _abrufen(
                s, f"osrm-{profil}", f"{basis}/table/v1/driving/{punkte}", _zeiten_aus,
                drossel=ROUTING_DROSSEL, params={"sources": 0, "annotations": "duration,distance"})
        except DienstNichtErreichbar:
            ergebnis[profil] = None
    return ergebnis
