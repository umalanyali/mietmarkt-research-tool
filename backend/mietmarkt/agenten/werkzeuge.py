"""Werkzeuge der Agenten. Jedes ruft nur Fachfunktionen aus mietmarkt auf und gibt JSON mit Werten samt Herkunft
zurück; das Modell rechnet nie selbst (CLAUDE.md Regel 1). Die Docstrings der @tool-Funktionen sieht das Modell
als Werkzeugbeschreibung."""
import json
from typing import Annotated, Literal

from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import InjectedState
from sqlalchemy import Engine
from sqlmodel import Session, select

from ..comps import filtern, im_umkreis
from ..geo import dienste
from ..geo.umfeld import umfeld as geo_umfeld
from ..kennzahlen import comps_kennzahlen, eur_qm
from ..konfig import Konfig
from ..mietansatz import BASIS_TEXT, Anpassung, Basis, fachregeln_pruefen, herleiten
from ..modelle import Comp, Herkunft, Marktkennzahl, Projekt

# InjectedState: LangGraph setzt die Projekt-ID aus dem Zustand ein. Das Modell sieht den Parameter nicht und
# kann so kein fremdes Projekt abfragen.
ProjektId = Annotated[int, InjectedState("projekt_id")]


def _json(daten: object) -> str:
    """Werkzeugergebnis als JSON-Text (Umlaute lesbar). Eingabe: dict/list. Ausgabe: str."""
    return json.dumps(daten, ensure_ascii=False, default=str)


HINWEIS_PORTALDATEN = ("Importierte Portal-Daten wurden nicht an das Modell gegeben (Lizenzschutz). Freigabe: "
                       "KI_PORTALDATEN_SENDEN=true in .env. Sage dem Nutzer, dass das Ergebnis ohne sie entstanden ist.")


def werkzeuge(e: Engine, k: Konfig) -> dict[str, list[BaseTool]]:
    """Alle Werkzeuge, gruppiert nach Agent. Eingabe: Datenbank-Engine, Konfig. Ausgabe: {agent: [Werkzeuge]}.

    Jedes Werkzeug öffnet eine eigene Sitzung, weil LangGraph Werkzeuge auch parallel ausführen kann.
    """

    def freigegeben[T: (Comp, Marktkennzahl)](p: Projekt, eintraege: list[T]) -> tuple[list[T], int]:
        """Was das Modell sehen darf. Eingabe: Projekt, Comps oder Marktkennzahlen. Ausgabe: (erlaubte, Anzahl zurückgehalten).

        Ohne Freigabe nur Demo-Daten und selbst erfasste Werte (Herkunft manuell); alles Importierte bleibt lokal –
        auch für Kennzahlen und Mietansatz, denn auch daraus berechnete Werte stammen aus den Portal-Daten.
        """
        if p.demo or k.ki_portaldaten_senden:
            return eintraege, 0
        erlaubt = [x for x in eintraege if x.herkunft == Herkunft.MANUELL]
        return erlaubt, len(eintraege) - len(erlaubt)

    def mit_hinweis(daten: dict, **zurueckgehalten: int) -> dict:
        """Ergänzt Zählung und Hinweis, wenn etwas zurückgehalten wurde. Eingabe: Ergebnis, Anzahlen. Ausgabe: dict."""
        if any(zurueckgehalten.values()):
            daten |= {"zurueckgehalten": zurueckgehalten, "hinweis": HINWEIS_PORTALDATEN}
        return daten

    @tool
    def lage(projekt_id: ProjektId) -> str:
        """Adresse, Ortsteil und Koordinaten des Projekts aus der Datenbank (beim Anlegen festgelegt) sowie der
        Analyse-Umkreis. Grundlage für alle Standortaussagen; geokodiert wird nichts."""
        # Bewusst kein Geokodieren: die Koordinaten stehen fest, und fiktive Demo-Adressen findet kein Geodienst
        with Session(e) as s:
            p = s.get(Projekt, projekt_id)
        return _json({"adresse": p.adresse, "plz": p.plz, "ort": p.ort, "ortsteil": p.ortsteil, "lat": p.lat,
                      "lon": p.lon, "umkreis_km": p.umkreis_km,
                      "quelle": "Projekt in der Datenbank (Koordinaten aus Nominatim beim Anlegen bzw. Demo-Datensatz)"})

    @tool
    async def umfeld(projekt_id: ProjektId) -> str:
        """ÖPNV, Supermärkte, Schulen, Kitas und Ärzte im Umkreis von 1 km um das Projekt: Luftlinie in km,
        Wegezeiten zu Fuß und mit dem Rad in Minuten (OSRM; fehlt das Routing, steht dort Methode „Luftlinie“)."""
        with Session(e) as s:
            p = s.get(Projekt, projekt_id)
            try:
                ergebnis = await geo_umfeld(p.lat, p.lon, s)
            except dienste.DienstNichtErreichbar as f:
                return _json({"fehler": str(f)})
        return _json(ergebnis.model_dump())

    @tool
    def comps_filtern(projekt_id: ProjektId, baujahr_ab: int | None = None,
                      typen: list[Literal["Regel", "EG", "DG"]] | None = None) -> str:
        """Vergleichsangebote (Comps) im Umkreis des Projekts, optional ab einem Baujahr und nur bestimmte
        Geschosstypen. Je Comp Fläche, Kaltmiete und €/m² mit Rechenweg; dazu der Rechenweg des Filters."""
        with Session(e) as s:
            p = s.get(Projekt, projekt_id)
            comps, ohne = freigegeben(p, im_umkreis(s, p))
        auswahl = filtern(comps, baujahr_ab=baujahr_ab, typen=set(typen) if typen else None)
        return _json(mit_hinweis({"rechenweg_text": auswahl.rechenweg_text, "comps": [
            {"nr": c.nr, "objekt": c.objekt, "typ": c.typ, "zimmer": c.zimmer, "baujahr": c.baujahr,
             "wohnflaeche_m2": c.wohnflaeche, "kaltmiete_eur": c.kaltmiete, "eur_qm": eur_qm(c).model_dump(),
             "herkunft": c.herkunft, "quelle_id": c.quelle_id} for c in auswahl.comps]}, comps=ohne))

    @tool
    def kennzahlen(projekt_id: ProjektId) -> str:
        """Kennzahlen der Comps im Umkreis (Anzahl, Median, Quartile, Ø flächengewichtet, Regelgeschoss/EG und DG,
        Anfragen je Monat) sowie die importierten Marktkennzahlen des Projekts (RIWIS, VALUE …) mit Quelle."""
        with Session(e) as s:
            p = s.get(Projekt, projekt_id)
            comps, comps_ohne = freigegeben(p, im_umkreis(s, p))
            markt, markt_ohne = freigegeben(p, list(s.exec(select(Marktkennzahl).where(Marktkennzahl.projekt_id == p.id))))
            werte = {name: w.model_dump() for name, w in comps_kennzahlen(comps, p.stichtag).items()}
            return _json(mit_hinweis({"comps": werte, "marktkennzahlen": [
                {"bezeichnung": m.bezeichnung, "kategorie": m.kategorie, "gebiet": m.gebiet, "wert": m.wert,
                 "einheit": m.einheit, "herkunft": m.herkunft, "quelle_id": m.quelle_id} for m in markt]},
                comps=comps_ohne, marktkennzahlen=markt_ohne))

    @tool
    def mietansatz_herleiten(projekt_id: ProjektId, basis: Basis, anpassungen: list[Anpassung]) -> str:
        """Rechnet einen Mietansatz in €/m²: Basis aus den Comps plus Zu- (+) und Abschläge (−), die Python addiert.
        basis regel_eg = Haupt-Mietansatz (Ø flächengewichtet Regelgeschoss/EG). basis dg = eigene DG-Herleitung
        (Ø flächengewichtet DG-Comps); DG ist nie ein Zuschlag auf regel_eg. Jede Anpassung braucht einen belegten
        Unterschied zwischen Projekt und Comps und nennt ihn in der Begründung; ohne belegten Unterschied kein Merkmal.
        Anpassungen tragen die Herkunft ki (Vorschlag der KI)."""
        fachregeln_pruefen(basis, [Anpassung.model_validate(a) for a in anpassungen])
        with Session(e) as s:
            p = s.get(Projekt, projekt_id)
            comps, ohne = freigegeben(p, im_umkreis(s, p))
        roh = comps_kennzahlen(comps, p.stichtag)[basis]
        basiswert = roh.model_copy(update={"rechenweg_text": f"{BASIS_TEXT[basis]}: {roh.rechenweg_text}"})
        herleitung = herleiten(basiswert, [Anpassung.model_validate(a) for a in anpassungen], Herkunft.KI)
        return _json(mit_hinweis({"basis": basis, **herleitung.model_dump()}, comps=ohne))

    return {"standort": [lage, umfeld], "marktdaten": [comps_filtern, kennzahlen],
            "mietansatz": [kennzahlen, mietansatz_herleiten]}
