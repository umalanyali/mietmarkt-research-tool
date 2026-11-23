"""Datenmodell von Mietmarkt Research: Tabellen (SQLModel) für Projekt, Quelle, Comp, Marktkennzahl
und der Baustein „Wert mit Herkunft“, den jede Fachfunktion zurückgibt."""
import datetime as dt
from enum import StrEnum

from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class Herkunft(StrEnum):
    """Woher eine Zahl stammt (CLAUDE.md Regel 1)."""

    IMPORT = "import"
    MANUELL = "manuell"
    KI = "ki"
    ABGELESEN = "abgelesen"
    BERECHNET = "berechnet"


class Wert(BaseModel):
    """Eine Zahl mit Einheit, Herkunft und Verweis auf Quelle oder Rechenweg."""

    wert: float | None
    einheit: str = ""
    herkunft: Herkunft
    quelle_id: int | None = None
    rechenweg_text: str = ""
    fundstelle: str = ""  # Stelle in einer Unterlage des Nutzers, z. B. „S. 2“
    ausschnitt: list[int] | None = None  # bei Werten aus Bildern: [x, y, Breite, Höhe] in Pixeln


class ProjektBasis(SQLModel):
    """Felder eines Projekts; Grundlage für Tabelle und API-Antworten (SQLModel-Muster: Basis ohne Tabelle)."""

    name: str
    adresse: str
    plz: str
    ort: str
    ortsteil: str = ""
    lat: float
    lon: float
    stichtag: dt.date
    analysiert_am: dt.date
    segment: str = "Wohnen · Neubau"
    umkreis_km: float = 2.0
    vermarktung: str = "Miete"
    vermarktungsstart: dt.date | None = None  # Ziel der Fortschreibung des Mietansatzes
    mietwachstum_pa: float | None = None  # g für die Fortschreibung, z. B. 0.02; None = MIETWACHSTUM_PA aus .env
    demo: bool = False  # Teil des synthetischen Demo-Datensatzes


class Projekt(ProjektBasis, table=True):
    """Ein analysierter Standort."""

    id: int | None = Field(default=None, primary_key=True)


class Quelle(SQLModel, table=True):
    """Herkunft importierter oder erfasster Daten: Datei, Dienst oder manuelle Erfassung."""

    id: int | None = Field(default=None, primary_key=True)
    projekt_id: int = Field(foreign_key="projekt.id", index=True)
    name: str  # z. B. „Marktbericht“, „Angebotsstatistik“, „Statistikamt Musterstadt“
    art: str  # datei | dienst | manuell
    datei: str | None = None
    stand: str = ""  # Datenstand laut Quelle, z. B. „11/2026“ oder „Q3/2026“
    abgerufen_am: dt.date
    seite: str | None = None


class CompBasis(SQLModel):
    """Felder eines Vergleichsangebots; Grundlage für Tabelle und API-Antworten."""

    projekt_id: int = Field(foreign_key="projekt.id", index=True)
    nr: int
    objekt: str
    anbieter: str = ""
    typ: str  # Regel | EG | DG
    zimmer: float
    baujahr: int | None = None
    wohnflaeche: float
    kaltmiete: float
    ebk: bool = False
    online_seit: dt.date | None = None
    anfragen: int | None = None
    lat: float | None = None
    lon: float | None = None
    gemerkt: bool = False
    herkunft: Herkunft = Herkunft.IMPORT
    quelle_id: int | None = Field(default=None, foreign_key="quelle.id")
    fundstelle: str = ""  # z. B. „Zeile 4“ oder „S. 1“


class Comp(CompBasis, table=True):
    """Ein Vergleichsangebot (Inserat). Abgeleitete Zahlen wie €/m² werden nicht gespeichert, sondern berechnet."""

    id: int | None = Field(default=None, primary_key=True)


class Marktkennzahl(SQLModel, table=True):
    """Ein Marktwert aus Import, Screenshot oder manueller Erfassung, mit Herkunft (Felder wie in Wert)."""

    id: int | None = Field(default=None, primary_key=True)
    projekt_id: int = Field(foreign_key="projekt.id", index=True)
    gruppe: str  # soziodemografie | zeitreihe | preisklassen | angebot | angebot_tabelle | weitere
    bezeichnung: str
    kategorie: str = ""  # x-Wert, Klasse oder Zimmerzahl, je nach Gruppe
    gebiet: str = ""
    wert: float | None
    einheit: str = ""
    stellen: int = 0  # Nachkommastellen für die Anzeige
    herkunft: Herkunft
    quelle_id: int | None = Field(default=None, foreign_key="quelle.id")
    rechenweg_text: str = ""


class GeoCache(SQLModel, table=True):
    """Zwischenspeicher für Antworten externer Geodienste (30 Tage gültig), damit jede Anfrage nur einmal rausgeht."""

    id: int | None = Field(default=None, primary_key=True)
    dienst: str = Field(index=True)
    anfrage_hash: str = Field(index=True)
    antwort_json: str
    abgerufen_am: dt.datetime


class UmfeldCache(SQLModel, table=True):
    """Letztes erfolgreiches Umfeld je Projekt (30 Tage gültig), damit ein Lauf ohne Overpass auskommt."""

    projekt_id: int = Field(foreign_key="projekt.id", primary_key=True)
    lat: float  # Koordinaten beim Abruf: ändern sie sich, gilt der Eintrag nicht mehr
    lon: float
    abgerufen_am: dt.date  # Datum der Overpass-Daten, nicht des Speicherns
    umfeld_json: str


class Wohnung(SQLModel, table=True):
    """Eine Wohnungsart im Wohnungsmix des Projekts (Projektdaten, vom Nutzer erfasst)."""

    id: int | None = Field(default=None, primary_key=True)
    projekt_id: int = Field(foreign_key="projekt.id", index=True)
    typ: str  # Regel | EG | DG, wie bei den Comps
    zimmer: float
    wohnflaeche: float  # je Wohnung in m²
    anzahl: int


class Dokument(SQLModel, table=True):
    """Eine vom Nutzer hochgeladene Unterlage (PDF, Bild, Text). Die Datei liegt unter daten/uploads/, nie im Repo."""

    id: int | None = Field(default=None, primary_key=True)
    projekt_id: int = Field(foreign_key="projekt.id", index=True)
    quelle_id: int | None = Field(default=None, foreign_key="quelle.id")  # für Fußnoten „Quelle: …“
    dateiname: str  # Originalname, nur zur Anzeige (bereinigt); gespeichert wird unter einem zufälligen Namen
    pfad: str  # relativ zum Datenordner, z. B. uploads/1/3f2a….pdf
    art: str  # pdf | png | jpg | txt (am Inhalt erkannt)
    seiten: int = 0
    # Darf an die KI? Hochgeladene Unterlagen können Portal-Inhalte sein (z. B. Exposés); ohne Freigabe und ohne
    # KI_PORTALDATEN_SENDEN bleiben sie lokal (wie importierte Portal-Daten)
    ki_freigabe: bool = False
    hochgeladen_am: dt.datetime


class Lauf(SQLModel, table=True):
    """Ein Agenten-Lauf zu einem Projekt. Zwischenstände und Ergebnisse liegen im LangGraph-Checkpointer
    (daten/checkpoints.db) unter thread_id = id; diese Tabelle ordnet den Lauf nur dem Projekt zu."""

    id: str = Field(primary_key=True)
    projekt_id: int = Field(foreign_key="projekt.id", index=True)
    gestartet_am: dt.datetime
    ergebnis: str | None = None  # Endstand (Ereignis „fertig“ als JSON); danach wird der Checkpoint gelöscht
