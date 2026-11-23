"""Synthetischer Demo-Datensatz „Musterstadt“: lädt musterstadt.yaml in die Datenbank (ersetzt den vorhandenen Bestand)."""
import datetime as dt
from pathlib import Path

import yaml
from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, select

from ..modelle import Comp, Marktkennzahl, Projekt, Quelle, Wohnung

DATEI = Path(__file__).with_name("musterstadt.yaml")


def _datum(text: str) -> dt.date:
    """ISO-Datum aus der YAML-Datei. Eingabe: „2026-11-04“. Ausgabe: date."""
    return dt.date.fromisoformat(str(text))


def seed(e: Engine) -> int:
    """Ersetzt den Datenbestand durch den Demo-Datensatz.

    Eingabe: Engine. Ausgabe: Anzahl angelegter Projekte.
    Wiederholbar: Tabellen werden vorher geleert, damit keine Dubletten entstehen.
    """
    SQLModel.metadata.drop_all(e)
    SQLModel.metadata.create_all(e)
    with e.begin() as c:  # der Volltextindex ist keine SQLModel-Tabelle und wird eigens geleert
        c.exec_driver_sql("DELETE FROM abschnitt")
    with Session(e) as s:
        return len(_laden(s))


def demo_oeffnen(s: Session) -> int:
    """Stellt sicher, dass der Demo-Standort da ist, ohne andere Projekte anzufassen.

    Eingabe: Sitzung. Ausgabe: ID des Demo-Projekts „Lindenquartier“ (das erste in musterstadt.yaml).
    Fehlt die Demo, werden alle Demo-Projekte ergänzt; sonst ändert sich nichts.
    """
    vorhanden = s.exec(select(Projekt).where(Projekt.demo).order_by(Projekt.id)).first()
    return vorhanden.id if vorhanden else _laden(s)[0]


def _laden(s: Session) -> list[int]:
    """Fügt alle Projekte aus musterstadt.yaml samt Quellen, Comps, Kennzahlen und Wohnungen hinzu.

    Eingabe: offene Sitzung. Ausgabe: IDs der angelegten Projekte in Dateireihenfolge (gespeichert).
    """
    daten = yaml.safe_load(DATEI.read_text(encoding="utf-8"))
    ids = []
    for p in daten["projekte"]:
        daten_felder = ("stichtag", "analysiert_am", "vermarktungsstart")
        projekt = Projekt(**{k: v for k, v in p.items() if k not in ("quellen", "comps", "kennzahlen", "wohnungsmix",
                                                                     *daten_felder)},
                          **{k: _datum(p[k]) for k in daten_felder if p.get(k)}, demo=True)
        s.add(projekt)
        s.flush()  # vergibt die Projekt-ID, die Quellen, Comps, Kennzahlen und Wohnungen brauchen
        ids.append(projekt.id)
        for w in p.get("wohnungsmix", []):
            s.add(Wohnung(projekt_id=projekt.id, **w))
        quelle_id = {}
        for q in p.get("quellen", []):
            quelle = Quelle(projekt_id=projekt.id, **{**q, "abgerufen_am": _datum(q["abgerufen_am"])})
            s.add(quelle)
            s.flush()
            quelle_id[q["name"]] = quelle.id
        for c in p.get("comps", []):
            felder = {k: v for k, v in c.items() if k not in ("quelle", "online_seit")}
            s.add(Comp(projekt_id=projekt.id, quelle_id=quelle_id[c["quelle"]], online_seit=_datum(c["online_seit"]), **felder))
        for k in p.get("kennzahlen", []):
            felder = {x: v for x, v in k.items() if x != "quelle"}
            s.add(Marktkennzahl(projekt_id=projekt.id, quelle_id=quelle_id[k["quelle"]], **felder))
    s.commit()
    return ids
