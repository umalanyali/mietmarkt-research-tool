"""Zahlen und Belege im Bericht: Der Bericht-Agent schreibt Sätze mit Belegen und Zahlen nur als Platzhalter
{{wert:ID}}; Python setzt die echten Werte samt Fußnote zur Herkunft ein. Freie Zahlen (auch Zahlwörter) und Sätze
ohne Beleg werden entfernt und markiert (CLAUDE.md Regel 1)."""
import re

from ..format import de
from .pruefung import ZAHL

PLATZHALTER = re.compile(r"\{\{\s*wert:\s*([^}]*?)\s*\}\}")
# Zahlwörter und Brüche zählen wie Ziffern, auch zusammengesetzt (einundzwanzig, zweihundertfünfzig, dreitausend).
# Nur ganze Wörter nach der Zahlwort-Grammatik, sonst träfe „acht“ auch „Pacht“. „ein/eine“ allein fehlt (Artikel),
# „Viertel“ nur als Bruch („ein Viertel“), sonst ist es meist ein Stadtviertel.
_E = "zwei|drei|vier|fünf|sechs|sieben|acht|neun"
_ZIG = "zwanzig|dreißig|vierzig|fünfzig|sechzig|siebzig|achtzig|neunzig"
_TEEN = "zehn|elf|zwölf|dreizehn|vierzehn|fünfzehn|sechzehn|siebzehn|achtzehn|neunzehn"
_U100 = f"(?:(?:ein|{_E})und)?(?:{_ZIG})|{_TEEN}|ein|{_E}"
_H = f"(?:ein|{_E})?hundert(?:und)?(?:{_U100})?"
_T = f"(?:{_H}|{_U100})?tausend(?:und)?(?:{_H}|{_U100})?"
# Endungen: Ordinalzahl (zehnte), Bruch (Zehntel), Vielfaches (dreifache), „-mal“
_WORT = (f"(?:{_T}|{_H}|(?:(?:ein|{_E})und)?(?:{_ZIG})|{_TEEN}|{_E})(?:s?te[nrms]?|s?tel|fache?[nrms]?|mal)?|"
         # unregelmäßig: dritte, siebte (nicht „achte“: meist das Verb), Achtel, eins, zweieinhalb, anderthalb
         f"(?:dritt|siebt)e[nrms]?|(?:dritt|sieb|ach)tel|eins|(?:ein|{_E})einhalb|anderthalb")
ZAHLWORT = re.compile(rf"\b(?!viertel\b)(?:{_WORT}|million(?:en)?|milliarden?|dutzend|hälfte|drittel|doppelt|"
                      r"(?:ein|eine[mr]?)\s+viertel)\b|[½¼¾⅓⅔⁰¹²³⁴⁵⁶⁷⁸⁹](?<!m²)", re.IGNORECASE)
# Quellen- und Verfahrenshinweise, die als Klammerzusatz in Rechenwegen stehen und unter „Methoden“ einmal erklärt
# werden: (Muster für den Klammerinhalt, Text der Methode; {} = erste Gruppe bzw. ganzer Inhalt). Andere Klammern – Formeln, „keine Zu- oder Abschläge“,
# Zeiträume – bleiben in der Fußnote.
VERFAHREN = [(re.compile(r"routing\.openstreetmap\.de, abgerufen am [\d.]+"), "Wegezeit laut OSRM, {}"),
             (re.compile(r"inklusiv"), "Quartile: lineare Interpolation, inklusiv"),
             (re.compile(r"Grenze (± \d+ %)"), "Abweichung auffällig ab mehr als {}"),
             (re.compile(r"Haversine, Erdradius [\d.]+ km"), "Luftlinie nach {}")]
KLAMMER = re.compile(r" ?\(([^()]+)\)")
# Nach diesen Präpositionen steht die Einheit im Dativ Plural: „bei 36 Tagen“ statt „bei 36 Tage“
DATIV = re.compile(r"\b(?:bei|nach|von|mit|in|seit|aus|zu|binnen|innerhalb von|vor)\s+$", re.IGNORECASE)
UNBEKANNT = "[?]"


OHNE_TAUSENDER = {"Jahr"}  # Einheiten, deren Zahlen nie Tausenderpunkte tragen (2024, nicht 2.024)


def werte_katalog(z: dict) -> dict[str, dict]:
    """Alle Werte, die der Bericht nennen darf. Eingabe: Zustand des Graphen. Ausgabe: {ID: Wert als dict}.

    Quelle sind die erfolgreichen Werkzeugergebnisse (ID = Werkzeug und Pfad, z. B. kennzahlen.comps.median) und die
    freigegebenen Herleitungen (mietansatz.<basis>.…). Die Herleitung des Modells selbst bleibt außen vor: Hat der
    Nutzer Werte geändert, gelten nur die geänderten.
    """
    katalog: dict[str, dict] = {}

    def sammeln(pfad: str, daten: object) -> None:
        """Geht verschachtelte Daten durch; ein dict mit Zahl und Herkunft ist ein Wert. Ausgabe: keine."""
        if isinstance(daten, dict):
            if isinstance(daten.get("wert"), int | float) and not isinstance(daten["wert"], bool) and "herkunft" in daten:
                katalog[pfad] = daten
                return
            for k, v in daten.items():
                sammeln(f"{pfad}.{k}", v)
        elif isinstance(daten, list):
            for i, v in enumerate(daten, 1):
                sammeln(f"{pfad}.{i}", v)

    for r in z["ergebnisse"].values():
        for w in r["werkzeuge"]:
            if w["status"] != "error" and w["name"] != "mietansatz_herleiten":
                sammeln(w["name"], w["ergebnis"])
    if z.get("freigabe") and z["freigabe"].get("herleitungen"):
        sammeln("mietansatz", z["freigabe"]["herleitungen"])
    return katalog


def _stellen(w: dict) -> int:
    """Nachkommastellen für die Anzeige. Eingabe: Wert. Ausgabe: die Stellen der Quelle, falls angegeben (Feld
    `stellen` importierter Kennzahlen), sonst 2 bei Euro, 0 bei ganzen Zahlen und 1 bei allem anderen."""
    if w.get("stellen") is not None:
        return w["stellen"]
    if w.get("einheit", "").startswith("€"):
        return 2
    return 0 if float(w["wert"]).is_integer() else 1


def anzeigen(w: dict) -> str:
    """Wert mit Einheit, wie er im Text steht. Eingabe: Wert als dict. Ausgabe: z. B. „16,96 €/m²“.

    Entfernungen erscheinen gerundet: unter 1 km als „rd. 230 m“ (auf 10 m), sonst „rd. 1,2 km“.
    """
    if w.get("einheit") == "km":
        m = round(w["wert"] * 100) * 10  # auf 10 m
        return f"rd. {de(m, 0)} m" if m < 1000 else f"rd. {de(w['wert'], 1)} km"
    zahl = de(w["wert"], _stellen(w))
    if w.get("einheit") in OHNE_TAUSENDER:
        zahl = zahl.replace(".", "")  # im deutschen Format ist der Punkt nur Tausendertrenner
    text = f"{zahl} {w.get('einheit', '')}".rstrip()
    # Aus Diagrammen abgelesene Werte sind nur ungefähr (die Ablesung schreibt „Diagramm“ in den Rechenweg)
    return f"rd. {text}" if w.get("herkunft") == "abgelesen" and "Diagramm" in w.get("rechenweg_text", "") else text


def beschreibung(w: dict, quellen: dict[int, str]) -> str:
    """Woher ein Wert kommt: Rechenweg bzw. Bezeichnung mit Zeitraum und Gebiet, dazu die Quelle mit Stand.

    Eingabe: Wert als dict, {quelle_id: Bezeichnung}. Ausgabe: Text für Fußnote und Werte-Katalog. Warum Zeitraum
    und Gebiet: ohne sie ordnet das Modell eine Kennzahl leicht dem falschen Gebiet zu.
    """
    teile = [w.get("rechenweg_text") or w.get("bezeichnung", ""), w.get("kategorie", ""), w.get("gebiet", "")]
    if w.get("quelle_id") is not None:
        teile.append(f"Quelle: {quellen.get(w['quelle_id'], f'Nr. {w["quelle_id"]}')}")
    return ", ".join(t for t in teile if t)


def fuellen(abschnitte: dict[str, list[dict]], katalog: dict[str, dict], quellen: dict[int, str],
            belege: set[str]) -> dict:
    """Setzt den Berichtstext zusammen.

    Eingabe: {Abschnitt: [{text, belege}]} vom Modell, Werte-Katalog, {quelle_id: Bezeichnung}, gültige Belege
    außerhalb des Katalogs (z. B. projekt, ergebnis:standort, befund:1).
    Ausgabe: {"abschnitte": {Abschnitt: Text mit [^n]}, "fussnoten": [{nr, ids, herkunft, verweis}],
    "methoden": [{nr, text}], "markierungen": [{fundstelle, grund}]}.
    Ein Satz ohne gültigen Beleg (ein Platzhalter darin zählt als Beleg) fällt weg; freie Zahlen werden zu [?].
    """
    nummern: dict[tuple[str, str], int] = {}  # (Herkunft, Verweis) → Nr.: gleiche Fußnoten nur einmal
    ids: dict[int, list[str]] = {}
    markierungen = []

    def frei(text: str) -> str:
        """Text zwischen Platzhaltern: jede Zahl darin hat keine Herkunft und wird zu [?]. Ausgabe: Text."""
        def raus(m: re.Match) -> str:
            markierungen.append({"fundstelle": m.group(0).strip(), "grund": "Zahl ohne Platzhalter entfernt"})
            return UNBEKANNT
        return ZAHLWORT.sub(raus, ZAHL.sub(raus, text))

    def wert(id_: str, davor: str) -> str:
        """Ein Platzhalter. Eingabe: ID, Text davor (für den Dativ der Einheit). Ausgabe: Wert mit Fußnotenzeichen
        oder [?] bei unbekannter ID."""
        if id_ not in katalog:
            markierungen.append({"fundstelle": f"{{{{wert:{id_}}}}}", "grund": "Platzhalter ohne Wert im Katalog"})
            return UNBEKANNT
        w = katalog[id_]
        nr = nummern.setdefault((w["herkunft"], verweis(w)), len(nummern) + 1)
        if id_ not in ids.setdefault(nr, []):
            ids[nr].append(id_)
        text = anzeigen(w)
        if DATIV.search(davor) and w.get("einheit", "").endswith("e"):  # Tage, Monate, Jahre
            text += "n"
        return f"{text}[^{nr}]"

    def verweis(w: dict) -> str:
        """Beschreibung und ggf. Rundung im Text. Ausgabe: Text für die Fußnote."""
        text = beschreibung(w, quellen)
        return f"{text}; im Text {anzeigen(w)}" if w.get("einheit") == "km" else text

    aus = {}
    for name, saetze in abschnitte.items():
        texte = []
        for satz in saetze:
            genannt = {t.strip() for t in PLATZHALTER.findall(satz["text"])}
            # Risiken eng: nur Befunde der Prüfung und Katalogwerte, kein Ergebnistext eines Agenten und keine
            # Projektdaten (dort landeten sonst Vorbehalte der Agenten als Risiko)
            erlaubt = {b for b in belege if b.startswith("befund:")} if name == "risiken" else belege
            if not (genannt | set(satz["belege"])) & (set(katalog) | erlaubt):
                markierungen.append({"fundstelle": satz["text"], "grund": "Aussage ohne Beleg entfernt"})
                continue
            # split mit einer Klammergruppe: gerade Stellen sind freier Text, ungerade die IDs der Platzhalter
            teile = PLATZHALTER.split(satz["text"])
            texte.append("".join(wert(t.strip(), teile[i - 1]) if i % 2 else frei(t) for i, t in enumerate(teile)))
        if name == "risiken" and not texte and not any(b.startswith("befund:") for b in belege):
            texte.append("Die Plausibilitätsprüfung ergab keine Befunde.")  # Python-Satz: belegt durch die Prüfung
        aus[name] = " ".join(texte)

    fussnoten = [{"nr": nr, "ids": ids[nr], "herkunft": h, "verweis": v} for (h, v), nr in nummern.items()]
    # Verfahrenshinweise aus VERFAHREN (z. B. „Haversine, Erdradius 6.371 km“) einmal als Methode, in der Fußnote [Mn]
    methoden: list[dict] = []
    for f in fussnoten:
        for inhalt in KLAMMER.findall(f["verweis"]):
            treffer = next(((m, t) for muster, t in VERFAHREN if (m := muster.fullmatch(inhalt))), None)
            text = treffer and treffer[1].format(treffer[0].group(treffer[0].lastindex or 0))
            if text and all(m["inhalt"] != inhalt for m in methoden):
                methoden.append({"nr": f"M{len(methoden) + 1}", "inhalt": inhalt, "text": text})
    for f in fussnoten:
        for m in methoden:
            f["verweis"] = f["verweis"].replace(f" ({m['inhalt']})", f" [{m['nr']}]")
    return {"abschnitte": aus, "fussnoten": fussnoten, "markierungen": markierungen,
            "methoden": [{"nr": m["nr"], "text": m["text"]} for m in methoden]}
