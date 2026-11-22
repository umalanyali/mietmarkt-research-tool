"""FastAPI-Anwendung. Die Endpunkte lesen aus der Datenbank und reichen Berechnungen an das Fachpaket `mietmarkt` weiter."""
import datetime as dt
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from mietmarkt import __version__
from mietmarkt.comps import filtern
from mietmarkt.db import engine
from mietmarkt.geo import entfernung_km
from mietmarkt.geo.dienste import (
    ATTRIBUTION,
    DienstNichtErreichbar,
    Vorschlag,
    geokodieren,
    rueckwaerts,
    vorschlaege,
)
from mietmarkt.geo.umfeld import Umfeld, umfeld
from mietmarkt.kennzahlen import (
    Preisklassen,
    anfragen_je_monat,
    eur_qm,
    kennzahlen_eur_qm,
    preisklassen_auswertung,
    tage_online,
    zusammenfassung,
)
from mietmarkt.modelle import Comp, CompBasis, Marktkennzahl, Projekt, ProjektBasis, Quelle, Wert

app = FastAPI(title="Mietmarkt Research", version=__version__)


@app.exception_handler(RequestValidationError)
async def _eingabefehler(_: Request, e: RequestValidationError) -> JSONResponse:
    """422 ohne die abgelehnte Eingabe. Eingabe: Anfrage, Fehler. Ausgabe: Feld und Grund je Fehler.

    Warum: Die Eingabe kann NaN enthalten (nicht als JSON darstellbar → sonst 500) oder sehr lang sein.
    """
    return JSONResponse(status_code=422, content={"detail": [{"loc": f["loc"], "msg": f["msg"]} for f in e.errors()]})
_engine = None


def sitzung() -> Iterator[Session]:
    """Datenbanksitzung je Anfrage; die Engine wird beim ersten Zugriff geöffnet. Eingabe: keine. Ausgabe: Session."""
    global _engine
    _engine = _engine or engine()
    with Session(_engine) as s:
        yield s


Sitzung = Annotated[Session, Depends(sitzung)]


def _projekt(s: Session, projekt_id: int) -> Projekt:
    """Lädt ein Projekt oder meldet 404. Eingabe: Sitzung, ID. Ausgabe: Projekt."""
    projekt = s.get(Projekt, projekt_id)
    if projekt is None:
        raise HTTPException(status_code=404, detail=f"Projekt {projekt_id} nicht gefunden")
    return projekt


def _comps_im_umkreis(s: Session, p: Projekt) -> list[Comp]:
    """Alle Comps im Umkreis des Projekts, egal zu welchem Projekt sie importiert wurden – aber nur aus Projekten
    derselben Art: Demo-Projekte sehen Demo-Comps, echte Adressen nie (die Demo-Kartenlage ist nur Kulisse).

    Eingabe: Sitzung, Projekt. Ausgabe: Comps nach Nummer sortiert. Marktdaten gibt es nur, wo Daten im Umkreis liegen.
    """
    alle = s.exec(select(Comp).join(Projekt).where(Projekt.demo == p.demo).order_by(Comp.nr)).all()
    return filtern(list(alle), zentrum=(p.lat, p.lon), radius_km=p.umkreis_km).comps


def _dienst_fehler(e: DienstNichtErreichbar) -> HTTPException:
    """Ausfall eines externen Dienstes als 503. Eingabe: Ausnahme. Ausgabe: HTTPException."""
    return HTTPException(status_code=503, detail=str(e))


class Vorschlaege(BaseModel):
    """Adressvorschläge mit Quellenhinweis."""

    vorschlaege: list[Vorschlag]
    attribution: str = ATTRIBUTION


class ProjektDetail(ProjektBasis):
    """Projekt mit Datenstand je Quelle."""

    id: int
    quellen: list[Quelle]


class CompAus(CompBasis):
    """Comp mit berechneten Werten (nicht gespeichert, sondern je Anfrage aus den Rohdaten gerechnet)."""

    id: int
    eur_qm: Wert
    tage_online: Wert
    anfragen_monat: Wert
    entfernung_km: Wert | None


class KennzahlenAus(BaseModel):
    """Alle Kennzahlen eines Projekts: Marktwerte, Quellen, Comps-Zusammenfassung, Preisklassen-Auswertung."""

    kennzahlen: list[Marktkennzahl]
    quellen: list[Quelle]
    comps: dict[str, Wert]
    preisklassen: Preisklassen


@app.get("/api/gesundheit")
def gesundheit() -> dict[str, str]:
    """Lebenszeichen für Startskript und Tests. Eingabe: keine. Ausgabe: {"status": "ok", "version": …}."""
    return {"status": "ok", "version": __version__}


@app.get("/api/projekte")
def projekte(s: Sitzung) -> list[Projekt]:
    """Alle Projekte, zuletzt analysierte zuerst. Eingabe: keine. Ausgabe: Projektliste."""
    return list(s.exec(select(Projekt).order_by(Projekt.analysiert_am.desc(), Projekt.id.desc())).all())


@app.get("/api/adressen/vorschlaege")
async def adressvorschlaege(s: Sitzung, q: Annotated[str, Query(min_length=3, max_length=200)]) -> Vorschlaege:
    """Adressvorschläge in Deutschland über Photon. Eingabe: Suchtext ab 3 Zeichen. Ausgabe: Vorschläge oder 503."""
    try:
        return Vorschlaege(vorschlaege=await vorschlaege(q, s))
    except DienstNichtErreichbar as e:
        raise _dienst_fehler(e) from e


@app.post("/api/projekte", status_code=201)
async def projekt_anlegen(v: Vorschlag, s: Sitzung) -> Projekt:
    """Legt ein Projekt aus einem gewählten Vorschlag an.

    Eingabe: Vorschlag aus /api/adressen/vorschlaege. Ausgabe: neues Projekt (oder das vorhandene mit derselben Adresse).
    Die endgültige Adresse kommt von Nominatim; findet es den Text nicht, die Rückwärtssuche auf die Koordinaten.
    """
    try:
        ort = await geokodieren(v.label, s) or await rueckwaerts(v.lat, v.lon, s)
    except DienstNichtErreichbar as e:
        raise _dienst_fehler(e) from e
    # Ohne Nominatim-Treffer bleiben die Angaben des Vorschlags (Photon)
    felder = ort.model_dump() if ort else {"adresse": v.strasse, "plz": v.plz, "ort": v.ort, "ortsteil": v.ortsteil,
                                           "lat": v.lat, "lon": v.lon}
    # Nur echte Projekte mit Straße und Hausnummer zusammenführen; Orte ohne Straße und Demo-Projekte nie (Befund P4)
    if felder["adresse"]:
        vorhanden = s.exec(select(Projekt).where(Projekt.adresse == felder["adresse"], Projekt.plz == felder["plz"],
                                                 Projekt.ort == felder["ort"], Projekt.demo == False)).first()
        if vorhanden:
            return vorhanden
    heute = dt.date.today()
    p = Projekt(name=felder["adresse"] or v.label, stichtag=heute, analysiert_am=heute, **felder)
    s.add(p)
    s.commit()
    s.refresh(p)
    return p


@app.get("/api/projekte/{projekt_id}/umfeld")
async def projekt_umfeld(projekt_id: int, s: Sitzung) -> Umfeld:
    """Haltestellen, Nahversorgung, Schulen, Kitas, Ärzte im Umkreis von 1 km mit Wegezeiten. Eingabe: Projekt-ID."""
    p = _projekt(s, projekt_id)
    try:
        return await umfeld(p.lat, p.lon, s)
    except DienstNichtErreichbar as e:
        raise _dienst_fehler(e) from e


@app.get("/api/projekte/{projekt_id}")
def projekt(projekt_id: int, s: Sitzung) -> ProjektDetail:
    """Ein Projekt mit seinen Quellen. Eingabe: Projekt-ID. Ausgabe: ProjektDetail oder 404."""
    p = _projekt(s, projekt_id)
    quellen = s.exec(select(Quelle).where(Quelle.projekt_id == p.id).order_by(Quelle.id)).all()
    return ProjektDetail(**p.model_dump(), quellen=list(quellen))


@app.get("/api/projekte/{projekt_id}/comps")
def comps(projekt_id: int, s: Sitzung) -> list[CompAus]:
    """Comps im Umkreis des Projekts mit €/m², Tagen online, Anfragen je Monat und Luftlinie zum Standort.

    Eingabe: Projekt-ID. Ausgabe: Comps nach Nummer sortiert.
    """
    p = _projekt(s, projekt_id)
    ergebnis = []
    for c in _comps_im_umkreis(s, p):
        ergebnis.append(CompAus(
            **c.model_dump(),
            eur_qm=eur_qm(c),
            tage_online=tage_online(c, p.stichtag),
            anfragen_monat=anfragen_je_monat([c], p.stichtag),
            entfernung_km=None if c.lat is None or c.lon is None else entfernung_km(p.lat, p.lon, c.lat, c.lon),
        ))
    return ergebnis


@app.get("/api/projekte/{projekt_id}/kennzahlen")
def kennzahlen(projekt_id: int, s: Sitzung) -> KennzahlenAus:
    """Marktkennzahlen des Projekts plus berechnete Zusammenfassungen.

    Eingabe: Projekt-ID. Ausgabe: KennzahlenAus; Projekte ohne Daten liefern leere Listen und Werte ohne Zahl.
    """
    p = _projekt(s, projekt_id)
    werte = list(s.exec(select(Marktkennzahl).where(Marktkennzahl.projekt_id == p.id).order_by(Marktkennzahl.id)).all())
    alle_comps = _comps_im_umkreis(s, p)
    klassen = [(k.kategorie, k.wert) for k in werte if k.gruppe == "preisklassen"]
    return KennzahlenAus(
        kennzahlen=werte,
        quellen=list(s.exec(select(Quelle).where(Quelle.projekt_id == p.id).order_by(Quelle.id)).all()),
        comps={**zusammenfassung(alle_comps, p.stichtag), **kennzahlen_eur_qm(alle_comps)},
        preisklassen=preisklassen_auswertung(klassen),
    )
