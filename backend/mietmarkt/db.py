"""Datenbankanbindung (SQLite über SQLModel). Standardpfad: daten/mietmarkt.db im Repository, änderbar per MIETMARKT_DB."""
import os
from pathlib import Path

from sqlalchemy import Engine, inspect
from sqlmodel import SQLModel, create_engine

from . import modelle  # noqa: F401 – registriert die Tabellen bei SQLModel.metadata

REPO = Path(__file__).resolve().parents[2]


def datenbankpfad() -> Path:
    """Pfad der Datenbankdatei. Eingabe: keine (liest MIETMARKT_DB). Ausgabe: Path."""
    return Path(os.environ.get("MIETMARKT_DB", REPO / "daten" / "mietmarkt.db"))


def engine(pfad: Path | None = None) -> Engine:
    """Öffnet die Datenbank, legt fehlende Tabellen an und ergänzt fehlende Spalten (spalten_nachziehen).

    Eingabe: optional ein Pfad (Standard: datenbankpfad()).
    Ausgabe: SQLAlchemy-Engine.
    """
    pfad = pfad or datenbankpfad()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    e = create_engine(f"sqlite:///{pfad}")
    SQLModel.metadata.create_all(e)
    spalten_nachziehen(e)
    with e.begin() as c:
        c.exec_driver_sql(FTS_TABELLE)
    return e


def spalten_nachziehen(e: Engine) -> None:
    """Hängt Spalten an, die ein Modell neu hat und die Tabelle noch nicht (create_all tut das nicht).

    Eingabe: Engine. Ausgabe: keine. ALTER TABLE ADD COLUMN lässt vorhandene Zeilen unverändert; neue Spalten sind
    darin leer. Eine Pflichtspalte ohne Standardwert lässt sich so nicht füllen: dann RuntimeError mit Namen.
    """
    vorhanden = inspect(e)
    with e.begin() as c:
        for tabelle in SQLModel.metadata.sorted_tables:
            da = {s["name"] for s in vorhanden.get_columns(tabelle.name)}
            for spalte in (s for s in tabelle.columns if s.name not in da):
                if not spalte.nullable and spalte.server_default is None:
                    raise RuntimeError(f"Spalte {tabelle.name}.{spalte.name} fehlt in der Datenbank und ist Pflicht "
                                       "ohne Standardwert; bitte von Hand migrieren (vorher daten/ sichern).")
                c.exec_driver_sql(f'ALTER TABLE "{tabelle.name}" ADD COLUMN "{spalte.name}" '
                                  f"{spalte.type.compile(dialect=e.dialect)}")


# Volltextindex der Unterlagen (SQLite FTS5, kein Embedding-Dienst). SQLModel kennt keine virtuellen Tabellen,
# daher von Hand. unicode61 remove_diacritics: „Wohnflache“ findet „Wohnfläche“; UNINDEXED-Spalten nur zum Filtern.
FTS_TABELLE = ("CREATE VIRTUAL TABLE IF NOT EXISTS abschnitt USING fts5(text, dokument_id UNINDEXED, "
               "projekt_id UNINDEXED, seite UNINDEXED, tokenize='unicode61 remove_diacritics 2')")
