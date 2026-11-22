"""Cache für Antworten externer Geodienste in der Tabelle geocache (Gültigkeit 30 Tage)."""
import datetime as dt
import hashlib
import json

from sqlmodel import Session, delete, select

from ..modelle import GeoCache

GUELTIG = dt.timedelta(days=30)


def schluessel(anfrage: dict) -> str:
    """Stabiler Schlüssel einer Anfrage. Eingabe: URL, Parameter, Daten als dict. Ausgabe: SHA-256 als Hex."""
    return hashlib.sha256(json.dumps(anfrage, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def lesen(s: Session, dienst: str, anfrage: dict) -> tuple[object, dt.datetime] | None:
    """Gültige Antwort aus dem Cache. Eingabe: Sitzung, Dienstname, Anfrage. Ausgabe: (JSON-Daten, Abrufzeit) oder None."""
    eintrag = s.exec(select(GeoCache).where(GeoCache.dienst == dienst, GeoCache.anfrage_hash == schluessel(anfrage))).first()
    if eintrag is None or dt.datetime.now(dt.UTC) - eintrag.abgerufen_am > GUELTIG:
        return None
    return json.loads(eintrag.antwort_json), eintrag.abgerufen_am


def schreiben(s: Session, dienst: str, anfrage: dict, antwort: object) -> None:
    """Speichert oder erneuert eine Antwort und löscht abgelaufene Einträge, damit die Tabelle nicht endlos wächst.

    Eingabe: Sitzung, Dienstname, Anfrage, JSON-Daten. Ausgabe: keine.
    """
    s.exec(delete(GeoCache).where(GeoCache.abgerufen_am < dt.datetime.now(dt.UTC) - GUELTIG))
    h = schluessel(anfrage)
    eintrag = s.exec(select(GeoCache).where(GeoCache.dienst == dienst, GeoCache.anfrage_hash == h)).first()
    eintrag = eintrag or GeoCache(dienst=dienst, anfrage_hash=h, antwort_json="", abgerufen_am=dt.datetime.now(dt.UTC))
    eintrag.antwort_json = json.dumps(antwort, ensure_ascii=False)
    eintrag.abgerufen_am = dt.datetime.now(dt.UTC)
    s.add(eintrag)
    s.commit()
