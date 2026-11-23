"""Prüfungen rund um Unterlagen des Nutzers: Ablesungen des Vision-Agenten gegen das Bild prüfen und Aussagen der
Agenten finden, die aus Dokumenten stammen, aber keine (oder eine falsche) Fundstelle [Quelle: Datei, S. X] nennen."""
import json
import re

from ..expose import zahl
from ..modelle import Herkunft, Wert
from .pruefung import ZAHL

QUELLE = re.compile(r"\[Quelle:\s*([^\],]+?),\s*S\.\s*(\d+)\]")


def ablesung(a: dict, groesse: tuple[int, int], datei: str, quelle_id: int | None) -> Wert | None:
    """Ein vom Vision-Agenten abgelesener Wert, wenn er prüfbar ist.

    Eingabe: Ablesung {bezeichnung, wert (Text), einheit, ausschnitt [x, y, Breite, Höhe], diagramm}, Bildgröße
    (Breite, Höhe), Dateiname, Quelle. Ausgabe: Wert mit Herkunft abgelesen und Bildausschnitt, oder None, wenn der
    Wert keine Zahl ist oder der Ausschnitt nicht im Bild liegt.
    """
    x = zahl(a["wert"])
    aus = a.get("ausschnitt") or []
    if x is None or len(aus) != 4 or min(aus) < 0 or not (aus[2] and aus[3]) or \
            aus[0] + aus[2] > groesse[0] or aus[1] + aus[3] > groesse[1]:
        return None
    art = "rd., aus Diagramm" if a.get("diagramm") else "aus Tabelle"
    return Wert(wert=x, einheit=a.get("einheit", ""), herkunft=Herkunft.ABGELESEN, quelle_id=quelle_id,
                ausschnitt=list(aus), fundstelle=f"Ausschnitt x {aus[0]}, y {aus[1]}, {aus[2]} × {aus[3]} px",
                # Die Bezeichnung stammt vom Modell (ein präpariertes Bild kann sie vorgeben) und gehört daher nicht
                # in Rechenweg und Fußnote; „vom Modell abgelesen“ macht sichtbar, dass niemand den Wert geprüft hat
                rechenweg_text=f"vom Modell abgelesen ({art}) aus {datei}, Ausschnitt x {aus[0]}, y {aus[1]}, "
                               f"{aus[2]} × {aus[3]} px – bitte am Bildausschnitt prüfen")


def _aus_dokument(satz: str, doktext: str, andere: str) -> bool:
    """Stammt ein Satz erkennbar aus den Suchtreffern? Eingabe: Satz, Text der Treffer, übrige Werkzeugergebnisse.

    Ausgabe: True, wenn er vier aufeinanderfolgende Wörter oder eine Zahl mit einem Treffer teilt, die nur dort
    stehen (nicht auch in Kennzahlen, anderen Werkzeugergebnissen oder Projektdaten). Eine Heuristik: Umformulierungen ohne Zahl erkennt sie nicht.
    """
    def vierer(t: str) -> set[tuple[str, ...]]:
        """Alle Folgen von vier Wörtern. Ausgabe: Menge."""
        w = re.findall(r"\w+", t.casefold())
        return {tuple(w[i:i + 4]) for i in range(len(w) - 3)}
    # Eine gemeinsame Wortfolge belegt die Herkunft nur, wenn sie ein inhaltliches Wort (ab 4 Buchstaben, keine Zahl)
    # enthält, das in keiner anderen Quelle steht. Sonst ist sie aus Werkzeugergebnissen oder Projektdaten erklärbar:
    # „99998 Musterstadt Ortsteil Südhang“ setzt sich aus den getrennten Feldern von „lage“ zusammen.
    bekannt = set(re.findall(r"\w+", andere.casefold()))
    if any(any(len(w) >= 4 and not w.isdigit() and w not in bekannt for w in folge)
           for folge in vierer(satz) & vierer(doktext)):
        return True
    return any(z in doktext and z not in andere for _, z in ZAHL.findall(satz))


def fundstellen_befunde(ergebnisse: dict, projektdaten: str = "") -> list[dict]:
    """Aussagen aus Unterlagen ohne gültige Fundstelle, im Code ermittelt (Prüf-Agent).

    Eingabe: Ergebnisse der Agenten, Projektdaten, wie die Agenten sie sehen (Adresse, Vermarktungsstart …). Ausgabe: Befunde (pruefung „fundstelle“, warnung) je Satz eines Agenten, der
    dokumente_suchen benutzt hat: Fundstelle, die in keinem seiner Treffer vorkommt, oder Aussage aus den Treffern
    ohne Fundstelle.
    """
    aus = []
    for agent, r in ergebnisse.items():
        suche = [w["ergebnis"] for w in r["werkzeuge"] if w["name"] == "dokumente_suchen" and w["status"] != "error"
                 and isinstance(w["ergebnis"], dict)]
        treffer = [t for e in suche for t in e.get("treffer", [])]
        if not treffer:
            continue
        erlaubt = {(t["datei"], t["seite"]) for t in treffer}
        doktext = " ".join(t["ausschnitt"] for t in treffer)
        andere = " ".join([projektdaten] + [json.dumps(w["ergebnis"], ensure_ascii=False) for w in r["werkzeuge"]
                                            if w["name"] != "dokumente_suchen"])
        # Satzende nicht innerhalb eckiger Klammern: „[Quelle: x.pdf, S. 2]“ enthält selbst einen Punkt
        for satz in re.split(r"(?<=[.!?])\s+(?![^\[]*\])", r["text"]):
            zitate = {(d.strip(), int(n)) for d, n in QUELLE.findall(satz)}
            if zitate - erlaubt:
                grund = "Fundstelle steht in keinem Suchtreffer"
            elif not zitate and _aus_dokument(satz, doktext, andere):
                grund = "Aussage aus den Unterlagen ohne Fundstelle"
            else:
                continue
            aus.append({"pruefung": "fundstelle", "schweregrad": "warnung", "markierungen": [],
                        "text": f"{grund} ({agent}): „{' '.join(satz.split())[:160]}“"})
    return aus
