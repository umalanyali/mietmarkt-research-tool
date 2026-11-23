"""Unterlagen des Nutzers: Dateityp am Inhalt erkennen, Text seitenweise lesen, in überlappende Abschnitte teilen und
im SQLite-Volltextindex (FTS5) ablegen und durchsuchen. Rechnet nichts; die Agenten zitieren Datei und Seite."""
import io
import multiprocessing
import re
from pathlib import Path

import pdfplumber
from PIL import Image
from sqlalchemy import Engine, bindparam, text
from sqlmodel import Session

from .modelle import Dokument

MAX_KANTE = 8000  # Pixel; größere Bilder nimmt die Anthropic-API nicht an
MAX_SEITEN = 100  # mehr ist für ein Exposé untypisch und bremst pdfplumber (Schutz vor präparierten PDFs)
PDF_ZEIT_S = 30  # länger braucht ein echtes Exposé nicht; präparierte PDFs (Flate-Bomben) halten sonst den Server auf
# shortcut: kein Speicherlimit für den Unterprozess (RLIMIT_AS lässt macOS nicht zu, Windows kennt es nicht); eine
# Flate-Bombe kann binnen PDF_ZEIT_S viel Speicher belegen. Aufrüsten, falls Unterlagen aus fremden Quellen kommen.
KOEPFE = {b"%PDF-": "pdf", b"\x89PNG\r\n\x1a\n": "png", b"\xff\xd8\xff": "jpg"}


class DokumentUnlesbar(Exception):
    """Die Datei lässt sich nicht als Unterlage lesen (beschädigt, zu groß, falscher Inhalt)."""


def art_erkennen(daten: bytes) -> str | None:
    """Dateityp aus den ersten Bytes. Eingabe: Dateiinhalt. Ausgabe: pdf | png | jpg | txt oder None.

    Warum am Inhalt: Dateiname und Content-Type bestimmt der Absender. Text ist, was keine Null-Bytes enthält und sich
    als UTF-8 oder cp1252 lesen lässt.
    """
    for kopf, art in KOEPFE.items():
        if daten.startswith(kopf):
            return art
    if b"\x00" in daten:
        return None
    for kodierung in ("utf-8", "cp1252"):
        try:
            daten.decode(kodierung)
            return "txt"
        except UnicodeDecodeError:
            continue
    return None


def bildgroesse(daten: bytes) -> tuple[int, int]:
    """Breite und Höhe eines Bildes. Eingabe: Dateiinhalt (PNG/JPG). Ausgabe: (Breite, Höhe) in Pixeln.

    Wirft DokumentUnlesbar, wenn Pillow das Bild nicht lesen kann oder es größer als MAX_KANTE ist. verify() prüft die
    Struktur, ohne alle Pixel zu dekodieren; Pillows Grenze gegen Dekompressionsbomben gilt zusätzlich.
    """
    try:
        with Image.open(io.BytesIO(daten)) as bild:
            bild.verify()
            groesse = bild.size
    except Exception as f:  # Pillow meldet beschädigte Dateien mit vielen Typen
        raise DokumentUnlesbar(f"Bild nicht lesbar ({type(f).__name__})") from f
    if max(groesse) > MAX_KANTE:
        raise DokumentUnlesbar(f"Bild größer als {MAX_KANTE} Pixel")
    return groesse


def seiten_lesen(pfad: Path, art: str) -> list[str]:
    """Text je Seite. Eingabe: Datei, Art. Ausgabe: Liste (PDF je Seite, TXT eine Seite, Bilder leer).

    Wirft DokumentUnlesbar bei beschädigtem PDF oder mehr als MAX_SEITEN Seiten.
    """
    if art == "txt":
        roh = pfad.read_bytes()
        try:
            return [roh.decode("utf-8")]
        except UnicodeDecodeError:
            return [roh.decode("cp1252")]
    if art != "pdf":
        return []
    # Eigener Prozess statt Thread: nur einen Prozess kann man nach dem Zeitlimit wirklich beenden (das with-Ende
    # ruft terminate()), und sein Speicher ist danach wieder frei. „spawn“ startet ohne Kopie des Serverzustands.
    with multiprocessing.get_context("spawn").Pool(1) as pool:
        try:
            return pool.apply_async(_pdf_seiten, (pfad,)).get(timeout=PDF_ZEIT_S)
        except multiprocessing.TimeoutError:
            raise DokumentUnlesbar(f"PDF nicht lesbar (Zeitlimit {PDF_ZEIT_S} s überschritten)") from None


def _pdf_seiten(pfad: Path) -> list[str]:
    """Text je PDF-Seite, läuft im Unterprozess von seiten_lesen. Eingabe: Datei. Ausgabe: Liste.

    Wirft DokumentUnlesbar bei beschädigtem PDF oder mehr als MAX_SEITEN Seiten.
    """
    try:
        with pdfplumber.open(pfad) as pdf:
            if len(pdf.pages) > MAX_SEITEN:
                raise DokumentUnlesbar(f"mehr als {MAX_SEITEN} Seiten")
            return [seite.extract_text() or "" for seite in pdf.pages]
    except DokumentUnlesbar:
        raise
    except Exception as f:  # pdfminer wirft viele eigene Typen; für den Nutzer zählt nur „nicht lesbar“
        raise DokumentUnlesbar(f"PDF nicht lesbar ({type(f).__name__})") from f


def abschnitte(text: str, laenge: int = 800, ueberlappung: int = 150) -> list[str]:
    """Teilt Text in Abschnitte von höchstens `laenge` Zeichen an Wortgrenzen; jeder beginnt mit den letzten
    rund `ueberlappung` Zeichen des vorigen, damit ein Satz an der Grenze in beiden auffindbar bleibt.

    Eingabe: Text, Länge, Überlappung. Ausgabe: Abschnitte (leer bei leerem Text).
    """
    woerter, teile, i = text.split(), [], 0
    while i < len(woerter):
        teil, n, j = [], 0, i
        while j < len(woerter) and n + len(woerter[j]) + bool(teil) <= laenge:
            n += len(woerter[j]) + bool(teil)
            teil.append(woerter[j])
            j += 1
        if not teil:  # ein einzelnes Wort länger als `laenge`
            teil, j = [woerter[j][:laenge]], j + 1
        teile.append(" ".join(teil))
        if j >= len(woerter):
            break
        k, m = j, 0
        while k - 1 > i and m + len(woerter[k - 1]) + 1 <= ueberlappung:
            k -= 1
            m += len(woerter[k]) + 1
        i = k
    return teile


def ordner(e: Engine) -> Path:
    """Datenordner neben der Datenbankdatei (dort liegt uploads/). Eingabe: Engine. Ausgabe: Pfad."""
    return Path(e.url.database).parent


def indexieren(s: Session, d: Dokument, seiten: list[str]) -> int:
    """Legt die Abschnitte eines Dokuments im Volltextindex ab. Eingabe: Sitzung, Dokument, Text je Seite.
    Ausgabe: Anzahl Abschnitte."""
    zeilen = [{"t": a, "d": d.id, "p": d.projekt_id, "s": nr} for nr, seite in enumerate(seiten, 1)
              for a in abschnitte(seite)]
    if zeilen:
        s.exec(text("INSERT INTO abschnitt (text, dokument_id, projekt_id, seite) VALUES (:t, :d, :p, :s)"),
               params=zeilen)
        s.commit()
    return len(zeilen)


def suchen(s: Session, projekt_id: int, frage: str, dokument_ids: set[int], n: int = 5) -> list[dict]:
    """Volltextsuche in den Unterlagen eines Projekts. Eingabe: Sitzung, Projekt, Frage, erlaubte Dokumente, Anzahl.

    Ausgabe: bis zu n Treffer {datei, seite, ausschnitt}, bester zuerst (BM25), je Datei und Seite einer.
    Die Frage wird nie als FTS5-Syntax ausgewertet: jedes Wort steht in Anführungszeichen, verknüpft mit OR.
    """
    woerter = re.findall(r"\w{2,}", frage)
    if not woerter or not dokument_ids:
        return []
    abfrage = text("SELECT d.dateiname, a.seite, a.text FROM abschnitt a JOIN dokument d ON d.id = a.dokument_id "
                   "WHERE abschnitt MATCH :q AND a.projekt_id = :p AND a.dokument_id IN :ids "
                   "ORDER BY bm25(abschnitt) LIMIT :n").bindparams(bindparam("ids", expanding=True))
    zeilen = s.exec(abfrage, params={"q": " OR ".join(f'"{w}"' for w in woerter), "p": projekt_id,
                                     "ids": list(dokument_ids), "n": n * 3}).all()
    treffer, gesehen = [], set()
    for datei, seite, ausschnitt in zeilen:
        if (datei, seite) not in gesehen:
            gesehen.add((datei, seite))
            treffer.append({"datei": datei, "seite": int(seite), "ausschnitt": ausschnitt})
    return treffer[:n]
