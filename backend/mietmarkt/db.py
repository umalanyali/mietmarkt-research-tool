"""Datenbankanbindung (SQLite über SQLModel). Standardpfad: daten/mietmarkt.db im Repository, änderbar per MIETMARKT_DB."""
import os
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import SQLModel, create_engine

from . import modelle  # noqa: F401 – registriert die Tabellen bei SQLModel.metadata

REPO = Path(__file__).resolve().parents[2]


def datenbankpfad() -> Path:
    """Pfad der Datenbankdatei. Eingabe: keine (liest MIETMARKT_DB). Ausgabe: Path."""
    return Path(os.environ.get("MIETMARKT_DB", REPO / "daten" / "mietmarkt.db"))


def engine(pfad: Path | None = None) -> Engine:
    """Öffnet die Datenbank und legt fehlende Tabellen an.

    Eingabe: optional ein Pfad (Standard: datenbankpfad()).
    Ausgabe: SQLAlchemy-Engine.
    """
    pfad = pfad or datenbankpfad()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    e = create_engine(f"sqlite:///{pfad}")
    SQLModel.metadata.create_all(e)
    with e.begin() as c:
        c.exec_driver_sql(FTS_TABELLE)
    return e


# Volltextindex der Unterlagen (SQLite FTS5, kein Embedding-Dienst). SQLModel kennt keine virtuellen Tabellen,
# daher von Hand. unicode61 remove_diacritics: „Wohnflache“ findet „Wohnfläche“; UNINDEXED-Spalten nur zum Filtern.
FTS_TABELLE = ("CREATE VIRTUAL TABLE IF NOT EXISTS abschnitt USING fts5(text, dokument_id UNINDEXED, "
               "projekt_id UNINDEXED, seite UNINDEXED, tokenize='unicode61 remove_diacritics 2')")
