"""FastAPI-Anwendung. Die Endpunkte lesen aus der Datenbank und reichen Berechnungen an das Fachpaket `mietmarkt` weiter."""
import datetime as dt
import json
import logging
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from pydantic import BaseModel
from sqlmodel import Session, select
from starlette.background import BackgroundTask

from mietmarkt import __version__
from mietmarkt.agenten.ereignisse import ereignisse
from mietmarkt.agenten.graph import Antwort, Freigabe, baue_graph, lauf_konfig, startzustand
from mietmarkt.agenten.modelle import Modelle, aus_konfig
from mietmarkt.comps import im_umkreis
from mietmarkt.db import datenbankpfad, engine
from mietmarkt.dokumente import DokumentUnlesbar, art_erkennen, bildgroesse, indexieren, ordner, seiten_lesen
from mietmarkt.export import markdown, pptx
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
    comps_kennzahlen,
    eur_qm,
    preisklassen_auswertung,
    tage_online,
)
from mietmarkt.konfig import Konfig
from mietmarkt.modelle import CompBasis, Dokument, Lauf, Marktkennzahl, Projekt, ProjektBasis, Quelle, Wert

app = FastAPI(title="Mietmarkt Research", version=__version__)
# Nur Anfragen an localhost: schützt vor DNS-Rebinding (eine fremde Domain, die auf 127.0.0.1 zeigt)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])
logger = logging.getLogger("mietmarkt.laeufe")


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


def konfig() -> Konfig:
    """Einstellungen aus .env, je Anfrage neu gelesen (Schlüssel nachtragen wirkt ohne Neustart). Ausgabe: Konfig."""
    return Konfig()


KonfigDep = Annotated[Konfig, Depends(konfig)]


def ki_modelle(k: KonfigDep) -> Modelle | None:
    """Claude-Modelle laut Konfig. Eingabe: Konfig. Ausgabe: Modelle, oder None ohne Schlüssel/Preis (kein Absturz)."""
    return None if k.ki_problem else aus_konfig(k)


def checkpoint_pfad() -> Path:
    """Datei des LangGraph-Checkpointers neben der Datenbank. Ausgabe: Pfad (daten/checkpoints.db)."""
    return datenbankpfad().parent / "checkpoints.db"


@app.get("/api/gesundheit")
def gesundheit(k: KonfigDep) -> dict[str, str | bool]:
    """Lebenszeichen für Startskript und Tests. Eingabe: keine. Ausgabe: status, version und ob die KI eingerichtet ist."""
    return {"status": "ok", "version": __version__, "ki": k.ki_konfiguriert}


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
    for c in im_umkreis(s, p):
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
    alle_comps = im_umkreis(s, p)
    klassen = [(k.kategorie, k.wert) for k in werte if k.gruppe == "preisklassen"]
    return KennzahlenAus(
        kennzahlen=werte,
        quellen=list(s.exec(select(Quelle).where(Quelle.projekt_id == p.id).order_by(Quelle.id)).all()),
        comps=comps_kennzahlen(alle_comps, p.stichtag),
        preisklassen=preisklassen_auswertung(klassen),
    )


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_BILD_BYTES = 5 * 1024 * 1024  # Grenze der Anthropic-API je Bild


class DokumentAus(BaseModel):
    """Angelegtes Dokument."""

    id: int
    dateiname: str
    art: str
    seiten: int
    abschnitte: int
    ki_freigabe: bool


@app.post("/api/projekte/{projekt_id}/dokumente", status_code=201)
async def dokument_hochladen(projekt_id: int, s: Sitzung, datei: UploadFile,
                             ki_freigabe: Annotated[bool, Form()] = False) -> DokumentAus:
    """Nimmt eine eigene Unterlage an (PDF, PNG/JPG, Text), legt sie unter daten/uploads/ ab und indexiert den Text.

    Eingabe: Projekt-ID, Datei, ki_freigabe (darf das Dokument an die KI; Standard nein). Ausgabe: DokumentAus.
    404 ohne Projekt, 413 zu groß, 415 anderer Dateityp, 422 unlesbar. Der Typ kommt aus dem Inhalt; der
    Dateiname dient nur der Anzeige, gespeichert wird unter einem zufälligen Namen.
    """
    _projekt(s, projekt_id)
    daten = await datei.read(MAX_UPLOAD_BYTES + 1)
    art = art_erkennen(daten)
    if len(daten) > MAX_UPLOAD_BYTES or (art in ("png", "jpg") and len(daten) > MAX_BILD_BYTES):
        raise HTTPException(status_code=413, detail="Datei zu groß (höchstens 10 MB, Bilder 5 MB)")
    if art is None:
        raise HTTPException(status_code=415, detail="Nur PDF, PNG, JPG oder Text")
    name = Path(datei.filename or "").name[:200] or "unterlage"
    pfad = Path("uploads") / str(projekt_id) / f"{uuid.uuid4().hex}.{art}"
    ziel = ordner(s.get_bind()) / pfad
    try:
        if art in ("png", "jpg"):
            bildgroesse(daten)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(daten)
        seiten = seiten_lesen(ziel, art)
    except DokumentUnlesbar as f:
        ziel.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(f)) from f
    heute = dt.date.today()
    quelle = Quelle(projekt_id=projekt_id, name=name, art="datei", datei=name, stand=f"{heute:%d.%m.%Y}",
                    abgerufen_am=heute)
    s.add(quelle)
    s.flush()
    d = Dokument(projekt_id=projekt_id, quelle_id=quelle.id, dateiname=name, pfad=pfad.as_posix(), art=art,
                 seiten=len(seiten), ki_freigabe=ki_freigabe, hochgeladen_am=dt.datetime.now(dt.UTC))
    s.add(d)
    s.commit()
    s.refresh(d)
    return DokumentAus(id=d.id, dateiname=name, art=art, seiten=d.seiten, abschnitte=indexieren(s, d, seiten),
                       ki_freigabe=ki_freigabe)


@app.post("/api/projekte/{projekt_id}/laeufe", status_code=201)
def lauf_starten(projekt_id: int, s: Sitzung, k: KonfigDep) -> dict[str, str]:
    """Legt einen Agenten-Lauf an; er beginnt, sobald jemand seine Ereignisse abruft.

    Eingabe: Projekt-ID. Ausgabe: {"lauf_id": …}. 404 ohne Projekt, 503 ohne Anthropic-Schlüssel.
    """
    _projekt(s, projekt_id)
    if k.ki_problem:
        raise HTTPException(status_code=503, detail=k.ki_problem)
    lauf = Lauf(id=uuid.uuid4().hex, projekt_id=projekt_id, gestartet_am=dt.datetime.now(dt.UTC))
    s.add(lauf)
    s.commit()
    return {"lauf_id": lauf.id}


# Läufe, deren Ereignisstrom gerade läuft. Ein zweiter Abruf desselben Laufs (Tab, Neuverbindung) bekäme sonst
# denselben Checkpoint und würde jeden Modellaufruf ein zweites Mal bezahlen. Ein Prozess (uvicorn) genügt dafür.
aktive_laeufe: set[str] = set()


def _sse(ereignis: dict) -> str:
    """Ein Ereignis im Server-Sent-Events-Format. Eingabe: dict mit "typ". Ausgabe: Textblock."""
    return f"event: {ereignis['typ']}\ndata: {json.dumps(ereignis, ensure_ascii=False, default=str)}\n\n"


def _lauf(s: Session, lauf_id: str) -> Lauf:
    """Lädt einen Lauf oder meldet 404. Eingabe: Sitzung, Lauf-ID. Ausgabe: Lauf."""
    lauf = s.get(Lauf, lauf_id)
    if lauf is None:
        raise HTTPException(status_code=404, detail=f"Lauf {lauf_id} nicht gefunden")
    return lauf


def _ausfuehren(lauf: Lauf, e, k: Konfig, m: Modelle, pfad: Path, fortsetzung: Command | None) -> StreamingResponse:
    """Führt einen Lauf aus bzw. fort und streamt seine Ereignisse; zum Schluss „fertig“ mit Endstand.

    Eingabe: Lauf, Engine, Konfig, Modelle, Checkpoint-Datei, Command(resume=Freigabe) oder None.
    Ausgabe: text/event-stream (409, wenn der Lauf schon läuft). Ohne Fortsetzung startet ein neuer Lauf, ein
    unterbrochener (Absturz, Neustart, abgerissene Verbindung) geht am letzten Checkpoint weiter, und ein
    angehaltener meldet erneut „wartet_auf_freigabe“. Hält der Lauf an, endet der Strom ohne „fertig“.
    """
    lauf_id, projekt_id = lauf.id, lauf.projekt_id
    if lauf_id in aktive_laeufe:
        raise HTTPException(status_code=409, detail="Dieser Lauf läuft bereits")
    # Eintragen ohne await dazwischen: zwei gleichzeitige Anfragen können nicht beide durch die Prüfung kommen
    aktive_laeufe.add(lauf_id)

    async def _ablauf() -> AsyncIterator[str]:
        """Führt den Graphen aus bzw. fort. Ausgabe: Text je Ereignis."""
        async with AsyncSqliteSaver.from_conn_string(str(pfad)) as cp:
            graph, konf = baue_graph(m, e, k, cp), lauf_konfig(lauf_id)
            stand = await graph.aget_state(konf)
            # stand.values leer: noch nie gelaufen; stand.next nicht leer: unterbrochen oder angehalten
            if fortsetzung or not stand.values or stand.next:
                eingabe = fortsetzung or (None if stand.values else startzustand(projekt_id))
                try:
                    async for modus, daten in graph.astream(eingabe, konf, stream_mode=["updates", "messages"]):
                        for ereignis in ereignisse(modus, daten):
                            yield _sse(ereignis)
                except Exception as f:  # jeder Fehler wird gemeldet; der Lauf lässt sich später fortsetzen
                    # Details (evtl. Pfade, Antwortkörper) nur ins lokale Log; der Browser bekommt eine feste Meldung
                    logger.exception("Lauf %s unterbrochen", lauf_id)
                    yield _sse({"typ": "fehler", "meldung": f"Lauf unterbrochen ({type(f).__name__}). Erneuter Abruf "
                                                            "setzt ihn am letzten Schritt fort; Details im Server-Log."})
                    return
            stand = await graph.aget_state(konf)
            if stand.next:  # wartet auf Freigabe oder Antwort; das Ereignis ist schon gesendet, der Checkpoint bleibt
                return
            ende = stand.values
            schluss = {"typ": "fertig", "status": "abgebrochen" if ende.get("abbruch") else "fertig",
                       "abbruch": ende.get("abbruch"),
                       "rueckfragen": [{"frage": f, "antwort": a} for f, a in
                                       zip(ende["rueckfragen"], ende.get("antworten", []), strict=False)],
                       "kosten_eur": sum(x["eur"]["wert"] for x in ende["kosten"]),
                       "ergebnisse": {a: {"text": r["text"], "markierungen": r["markierungen"]}
                                      for a, r in ende["ergebnisse"].items()},
                       "freigabe": ende.get("freigabe"), "bericht": ende.get("bericht")}
            # Erst speichern, dann senden (bricht die Verbindung beim Senden ab, ist der Endstand trotzdem da).
            # Danach wird der Checkpoint nicht mehr gebraucht; so wächst checkpoints.db nicht mit jedem Lauf.
            with Session(e) as s2:
                beendet = s2.get(Lauf, lauf_id)
                beendet.ergebnis = json.dumps(schluss, ensure_ascii=False, default=str)
                s2.commit()
            await cp.adelete_thread(lauf_id)
            yield _sse(schluss)

    # Freigeben als Hintergrundaufgabe der Antwort, nicht im Generator: Trennt der Browser die Verbindung, bevor der
    # erste Block gesendet ist, startet der Generator nie (kein finally) – die Hintergrundaufgabe läuft trotzdem (S1)
    return StreamingResponse(_ablauf(), media_type="text/event-stream",
                             background=BackgroundTask(aktive_laeufe.discard, lauf_id))


ModelleDep = Annotated[Modelle | None, Depends(ki_modelle)]
PfadDep = Annotated[Path, Depends(checkpoint_pfad)]


@app.get("/api/laeufe/{lauf_id}/ereignisse")
async def lauf_ereignisse(lauf_id: str, s: Sitzung, k: KonfigDep, m: ModelleDep, pfad: PfadDep) -> StreamingResponse:
    """Führt den Lauf aus und streamt seine Ereignisse (Server-Sent Events).

    Eingabe: Lauf-ID. Ausgabe: text/event-stream; ein beendeter Lauf liefert nur den Endstand (ohne Modell und
    Schlüssel). 404 unbekannt, 503 ohne KI, 409 läuft schon.
    """
    lauf = _lauf(s, lauf_id)
    if lauf.ergebnis:
        return StreamingResponse(iter([_sse(json.loads(lauf.ergebnis))]), media_type="text/event-stream")
    if m is None:
        raise HTTPException(status_code=503, detail=k.ki_problem)
    return _ausfuehren(lauf, s.get_bind(), k, m, pfad, None)


async def _fortsetzen(s: Session, lauf_id: str, knoten: str, wert: dict, k: Konfig, m: Modelle | None,
                      pfad: Path) -> StreamingResponse:
    """Setzt einen Lauf fort, der an `knoten` angehalten ist (freigabe oder rueckfrage).

    Eingabe: Sitzung, Lauf-ID, Knoten, Fortsetzungswert, Konfig, Modelle, Checkpoint-Datei.
    Ausgabe: Ereignisstrom wie /ereignisse. 404 unbekannt, 503 ohne KI, 409 wartet dort nicht (nicht gestartet,
    läuft, wartet auf etwas anderes oder beendet).
    """
    lauf = _lauf(s, lauf_id)
    if m is None:
        raise HTTPException(status_code=503, detail=k.ki_problem)
    async with AsyncSqliteSaver.from_conn_string(str(pfad)) as cp:
        stand = await baue_graph(m, s.get_bind(), k, cp).aget_state(lauf_konfig(lauf_id))
    if lauf.ergebnis or stand.next != (knoten,):
        art = "eine Freigabe" if knoten == "freigabe" else "eine Antwort"
        raise HTTPException(status_code=409, detail=f"Lauf wartet nicht auf {art}")
    if knoten == "freigabe":  # Änderungen nur für Basen, die der Vorschlag enthält (sonst gingen sie still verloren)
        fremd = set(wert.get("aenderungen") or {}) - set(stand.interrupts[0].value["vorschlag"]["herleitungen"])
        if fremd:
            raise HTTPException(status_code=422, detail=f"Keine Herleitung für {', '.join(sorted(fremd))} im Vorschlag")
    return _ausfuehren(lauf, s.get_bind(), k, m, pfad, Command(resume=wert))


@app.post("/api/laeufe/{lauf_id}/freigabe")
async def lauf_freigabe(lauf_id: str, f: Freigabe, s: Sitzung, k: KonfigDep, m: ModelleDep,
                        pfad: PfadDep) -> StreamingResponse:
    """Entscheidung des Nutzers zum Mietansatz-Vorschlag; setzt den angehaltenen Lauf fort und streamt weiter.

    Eingabe: Lauf-ID, {aktion: annehmen | aendern | ablehnen, aenderungen?, kommentar?}. Ausgabe: text/event-stream.
    422 bei unvollständiger Freigabe; sonst wie _fortsetzen.
    """
    return await _fortsetzen(s, lauf_id, "freigabe", f.model_dump(), k, m, pfad)


@app.post("/api/laeufe/{lauf_id}/antwort")
async def lauf_antwort(lauf_id: str, a: Antwort, s: Sitzung, k: KonfigDep, m: ModelleDep,
                       pfad: PfadDep) -> StreamingResponse:
    """Antwort des Nutzers auf eine Rückfrage des Supervisors; der Lauf geht beim Supervisor weiter.

    Eingabe: Lauf-ID, {antwort}. Ausgabe: text/event-stream. 422 bei leerer Antwort; sonst wie _fortsetzen.
    """
    return await _fortsetzen(s, lauf_id, "rueckfrage", a.model_dump(), k, m, pfad)


@app.get("/api/laeufe/{lauf_id}/bericht.{art}")
def bericht_export(lauf_id: str, art: Literal["md", "pptx"], s: Sitzung) -> Response:
    """Bericht eines fertigen Laufs zum Herunterladen. Eingabe: Lauf-ID, md oder pptx. Ausgabe: Datei oder 404."""
    lauf = _lauf(s, lauf_id)
    b = json.loads(lauf.ergebnis).get("bericht") if lauf.ergebnis else None
    if not b:
        raise HTTPException(status_code=404, detail="Kein Bericht: Lauf ist nicht fertig oder endete ohne Bericht")
    p = _projekt(s, lauf.projekt_id)  # 404, falls das Projekt inzwischen gelöscht ist
    kopf = {"Content-Disposition": f'attachment; filename="mietmarktbericht-{lauf_id[:8]}.{art}"'}
    if art == "md":
        return Response(markdown(p, b), media_type="text/markdown; charset=utf-8", headers=kopf)
    return Response(pptx(p, b), headers=kopf,
                    media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")
