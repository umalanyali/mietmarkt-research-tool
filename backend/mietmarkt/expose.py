"""Exposé-Auswertung: Ein regelbasierter Parser liest Wohnfläche, Kaltmiete, Zimmer, Baujahr und Ausstattung aus dem
Text einer Unterlage. Was er nicht findet, darf das Modell ergänzen; jede Ergänzung wird hier am Originaltext geprüft
(Zitat auf der genannten Seite, Zahl im Zitat), sonst verworfen."""
import re

from .modelle import Herkunft, Wert

# Feld → (Einheit, Muster). Die erste Gruppe ist die Zahl; group(0) wird als Zitat in den Rechenweg übernommen.
FELDER = {
    "wohnflaeche": ("m²", re.compile(r"Wohnfl(?:ä|ae)che[^\d\n]{0,20}(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:m²|m2|qm)", re.IGNORECASE)),
    "kaltmiete": ("€", re.compile(r"Kaltmiete[^\d\n]{0,20}(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?)\s*(?:€|EUR|Euro)", re.IGNORECASE)),
    "zimmer": ("Zimmer", re.compile(r"(\d(?:,5)?)\s*-?\s*Zimmer|Zimmer(?:anzahl)?:?\s*(\d(?:,5)?)", re.IGNORECASE)),
    "baujahr": ("Jahr", re.compile(r"Baujahr:?\s*((?:19|20)\d{2})", re.IGNORECASE)),
}
# Merkmal → Wortstamm mit Mehrzahl/Beugung. Gesucht wird das ganze Wort oder der Kopf eines Kompositums (das letzte
# Glied: „Dachgarten“ ist ein Garten, „Gartenseite“ nicht, „Tiefgaragenstellplatz“ ist ein Stellplatz). Ausnahme:
# Kellerabteil und Kellerraum zählen als Keller.
AUSSTATTUNG = {"Balkon": r"balkon(?:e|en)?", "Terrasse": r"terrassen?", "Loggia": r"loggi(?:a|en)",
               "Garten": r"g[aä]rten", "Aufzug": r"aufz[uü]ge?", "Einbauküche": r"einbauküchen?",
               "Fußbodenheizung": r"fußbodenheizung(?:en)?", "Tiefgarage": r"tiefgaragen?",
               "Stellplatz": r"stellpl[aä]tz(?:e|en)?", "Keller": r"keller(?:n|abteile?|r[aä]ume?)?", "barrierefrei": r"barrierefrei(?:e|er|es|en)?"}
# Verneinung im selben Satzteil: davor („keine Einbauküche“, „ohne Garten“, „nicht barrierefrei“) oder danach
# („Einbauküche ist nicht enthalten“). Satzteile enden an Satzzeichen und Kommas, damit „Kein Keller, aber Balkon“
# nur den Keller verneint.
_NEIN_DAVOR = re.compile(r"\b(?:kein(?:e|en|er|em|es)?|ohne|nicht)\b", re.IGNORECASE)
_NEIN_DANACH = re.compile(r"\b(?:nicht\s+(?:enthalten|vorhanden|möglich)|fehlt|entfällt)\b", re.IGNORECASE)
_ZAHLTEXT = re.compile(r"\d[\d.,]*\d|\d")


def zahl(text: str) -> float | None:
    """Erste Zahl im deutschen Format. Eingabe: Text. Ausgabe: Zahl oder None („1.250“ ist 1250, „72,5“ ist 72,5)."""
    m = _ZAHLTEXT.search(text)
    if not m:
        return None
    roh = m.group(0)
    if "," in roh:
        roh = roh.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", roh):
        roh = roh.replace(".", "")
    return float(roh)


def _norm(text: str) -> str:
    """Für den Textvergleich: Leerraum zusammengefasst, Groß-/Kleinschreibung egal. Ausgabe: Text."""
    return " ".join(text.split()).casefold()


def _vorhanden(text: str, stamm: str) -> bool:
    """Steht ein Ausstattungsmerkmal unverneint im Text? Eingabe: Text einer Seite, Wortstamm aus AUSSTATTUNG.
    Ausgabe: True, wenn ein Satzteil das Merkmal als Wort oder Kompositum-Kopf nennt, ohne es zu verneinen."""
    muster = re.compile(rf"\b\w*?(?:{stamm})\b", re.IGNORECASE)
    for teil in re.split(r"[.;:!?,\n]", text):
        for m in muster.finditer(teil):
            if not _NEIN_DAVOR.search(teil[:m.start()]) and not _NEIN_DANACH.search(teil[m.end():]):
                return True
    return False


def parsen(seiten: list[str], datei: str, quelle_id: int | None) -> dict:
    """Regelbasierte Auswertung. Eingabe: Text je Seite, Dateiname, Quelle (für Fußnoten).

    Ausgabe: {"felder": {feld: Wert oder None}, "ausstattung": [{merkmal, fundstelle, herkunft}]}. Gefundene Werte
    tragen Herkunft import (aus der Unterlage gelesen), Seite und Zitat.
    """
    felder = {}
    for feld, (einheit, muster) in FELDER.items():
        felder[feld] = None
        for nr, seite in enumerate(seiten, 1):
            if m := muster.search(seite):
                felder[feld] = Wert(wert=zahl(next(g for g in m.groups() if g)), einheit=einheit,
                                    herkunft=Herkunft.IMPORT, quelle_id=quelle_id, fundstelle=f"S. {nr}",
                                    rechenweg_text=f"{datei}, S. {nr}: „{' '.join(m.group(0).split())}“")
                break
    ausstattung = []
    for merkmal, stamm in AUSSTATTUNG.items():
        nr = next((nr for nr, seite in enumerate(seiten, 1) if _vorhanden(seite, stamm)), None)
        if nr:
            ausstattung.append({"merkmal": merkmal, "fundstelle": f"S. {nr}", "herkunft": Herkunft.IMPORT.value})
    return {"felder": felder, "ausstattung": ausstattung}


def ergaenzen(feld: str, wert_text: str, seite: int, zitat: str, seiten: list[str], datei: str,
              quelle_id: int | None) -> Wert | None:
    """Prüft eine Ergänzung des Modells für ein leeres Feld. Eingabe: Feld, Wert als Text, Seite, wörtliches Zitat,
    Text je Seite, Dateiname, Quelle. Ausgabe: Wert mit Herkunft ki und Seite, oder None, wenn das Zitat nicht auf
    der Seite steht oder die Zahl nicht im Zitat vorkommt (erfundene Angaben fallen so heraus)."""
    if not 1 <= seite <= len(seiten) or not zitat.strip() or _norm(zitat) not in _norm(seiten[seite - 1]):
        return None
    x = zahl(wert_text)
    if x is None or all(zahl(z) != x for z in _ZAHLTEXT.findall(zitat)):
        return None
    return Wert(wert=x, einheit=FELDER[feld][0], herkunft=Herkunft.KI, quelle_id=quelle_id, fundstelle=f"S. {seite}",
                rechenweg_text=f"vom Modell ergänzt aus {datei}, S. {seite}: „{' '.join(zitat.split())}“")


def merkmal_ergaenzen(merkmal: str, seite: int, zitat: str, seiten: list[str]) -> dict | None:
    """Prüft ein vom Modell ergänztes Ausstattungsmerkmal. Eingabe: Merkmal, Seite, Zitat, Text je Seite.
    Ausgabe: {merkmal, fundstelle, herkunft ki} oder None, wenn Zitat oder Merkmal nicht im Text stehen."""
    if not 1 <= seite <= len(seiten) or _norm(zitat) not in _norm(seiten[seite - 1]) or \
            _norm(merkmal) not in _norm(zitat):
        return None
    return {"merkmal": merkmal, "fundstelle": f"S. {seite}", "herkunft": Herkunft.KI.value}
