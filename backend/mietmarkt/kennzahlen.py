"""Kennzahlen zu Vergleichsangeboten: €/m², Anzahl, Median, Quartile, flächengewichteter Mittelwert, Anfragen je Monat.
Jede Funktion liefert neben der Zahl den Rechenweg als Text."""
import datetime as dt
import statistics

from pydantic import BaseModel

from .format import de
from .modelle import Comp, Herkunft, Wert

MIN_TAGE_ANFRAGEN = 7  # darunter ist „Anfragen je Monat“ nicht belastbar


def _berechnet(wert: float | None, einheit: str, rechenweg: str) -> Wert:
    """Kurzform für einen berechneten Wert. Eingabe: Zahl, Einheit, Rechenweg. Ausgabe: Wert."""
    return Wert(wert=wert, einheit=einheit, herkunft=Herkunft.BERECHNET, rechenweg_text=rechenweg)


def eur_qm(c: Comp) -> Wert:
    """Kaltmiete je m². Eingabe: Comp. Ausgabe: Wert in €/m²; ohne Zahl, wenn die Wohnfläche nicht positiv ist."""
    if c.wohnflaeche <= 0:
        return _berechnet(None, "€/m²", f"Wohnfläche {de(c.wohnflaeche, 1)} m² – kein €/m² berechenbar")
    return _berechnet(c.kaltmiete / c.wohnflaeche, "€/m²",
                      f"{de(c.kaltmiete)} € / {de(c.wohnflaeche, 1)} m² = {de(c.kaltmiete / c.wohnflaeche)} €/m²")


def kennzahlen_eur_qm(comps: list[Comp]) -> dict[str, Wert]:
    """Kennzahlen über die €/m² einer Comp-Auswahl.

    Eingabe: Comps.
    Ausgabe: anzahl, median, q1, q3 (Quartile, inklusiv interpoliert) und mittel_flaechengewichtet
    (Σ Kaltmiete / Σ Wohnfläche), je als Wert mit Rechenweg.
    """
    # Comps ohne positive Wohnfläche lassen sich nicht in €/m² umrechnen und bleiben außen vor
    raus = [c for c in comps if c.wohnflaeche <= 0]
    comps = [c for c in comps if c.wohnflaeche > 0]
    hinweis = f" (ohne {', '.join(f'Nr. {c.nr}' for c in raus)}: Wohnfläche 0)" if raus else ""
    nrn = ", ".join(str(c.nr) for c in comps)
    anzahl = _berechnet(len(comps), "", f"{len(comps)} Comps (Nr. {nrn})" if comps else "keine Comps")
    if not comps:
        leer = "keine Comps in der Auswahl"
        return {"anzahl": anzahl, **{k: _berechnet(None, "€/m²", leer) for k in ("median", "q1", "q3", "mittel_flaechengewichtet")}}

    werte = sorted(c.kaltmiete / c.wohnflaeche for c in comps)
    liste = "; ".join(de(w) for w in werte)
    # Bei einem einzigen Wert sind Median und Quartile dieser Wert; statistics.quantiles braucht mindestens zwei
    q1, _, q3 = statistics.quantiles(werte, n=4, method="inclusive") if len(werte) > 1 else (werte[0],) * 3
    median = statistics.median(werte)
    summe_kalt = sum(c.kaltmiete for c in comps)
    summe_flaeche = sum(c.wohnflaeche for c in comps)
    return {
        "anzahl": anzahl,
        "median": _berechnet(median, "€/m²", f"Median der sortierten €/m² ({liste}): {de(median)}"),
        "q1": _berechnet(q1, "€/m²", f"25-%-Quartil, lineare Interpolation (inklusiv) über {liste}: {de(q1)}"),
        "q3": _berechnet(q3, "€/m²", f"75-%-Quartil, lineare Interpolation (inklusiv) über {liste}: {de(q3)}"),
        "mittel_flaechengewichtet": _berechnet(
            summe_kalt / summe_flaeche, "€/m²",
            f"Σ Kaltmiete {de(summe_kalt)} € / Σ Wohnfläche {de(summe_flaeche, 1)} m² = {de(summe_kalt / summe_flaeche)} €/m² "
            f"(n = {len(comps)}){hinweis}",
        ),
    }


def tage_online(c: Comp, stichtag: dt.date) -> Wert:
    """Tage zwischen „online seit“ und Stichtag.

    Eingabe: Comp, Stichtag. Ausgabe: Wert in Tagen; ohne Zahl, wenn das Datum fehlt oder nach dem Stichtag liegt.
    """
    if c.online_seit is None:
        return _berechnet(None, "Tage", "kein Datum „online seit“")
    tage = (stichtag - c.online_seit).days
    if tage < 0:
        return _berechnet(None, "Tage", f"online seit {c.online_seit:%d.%m.%Y} liegt nach dem Stichtag {stichtag:%d.%m.%Y}")
    return _berechnet(tage, "Tage", f"Stichtag {stichtag:%d.%m.%Y} − online seit {c.online_seit:%d.%m.%Y} = {tage} Tage")


def anfragen_je_monat(comps: list[Comp], stichtag: dt.date) -> Wert:
    """Anfragen je Monat als Mittel der Einzelwerte (Anfragen / Tage online × 30).

    Eingabe: Comps, Stichtag. Inserate unter 7 Tagen online oder ohne Angaben zählen nicht.
    Ausgabe: Wert je Inserat und Monat mit Rechenweg (welche Comps zählen, welche nicht).
    """
    einzel, ohne = [], []
    for c in comps:
        tage = tage_online(c, stichtag).wert
        if tage is None or c.anfragen is None or tage < MIN_TAGE_ANFRAGEN:
            ohne.append(f"Nr. {c.nr}")
        else:
            einzel.append((c.nr, c.anfragen / tage * 30))
    rest = f"; nicht gezählt (unter {MIN_TAGE_ANFRAGEN} Tagen online oder ohne Angaben): {', '.join(ohne)}" if ohne else ""
    if not einzel:
        return _berechnet(None, "Anfragen/Monat", "kein Inserat mit ausreichend Tagen online" + rest)
    mittel = sum(w for _, w in einzel) / len(einzel)
    teile = " + ".join(de(w, 1) for _, w in einzel)
    return _berechnet(mittel, "Anfragen/Monat", f"({teile}) / {len(einzel)} = {de(mittel, 1)} je Inserat{rest}")


def zusammenfassung(comps: list[Comp], stichtag: dt.date) -> dict[str, Wert]:
    """Kopfzahlen der Comps-Tabelle.

    Eingabe: Comps, Stichtag.
    Ausgabe: regel_eg und dg (je Ø flächengewichtet, getrennt nach Geschosslage), deren Anzahl (regel_eg_n, dg_n)
    sowie anfragen_monat.
    """
    # Dachgeschosse erzielen andere Mieten; Regelgeschoss und EG werden gemeinsam betrachtet
    regel_eg = kennzahlen_eur_qm([c for c in comps if c.typ in ("Regel", "EG")])
    dg = kennzahlen_eur_qm([c for c in comps if c.typ == "DG"])
    return {
        "regel_eg": regel_eg["mittel_flaechengewichtet"],
        "regel_eg_n": regel_eg["anzahl"],
        "dg": dg["mittel_flaechengewichtet"],
        "dg_n": dg["anzahl"],
        "anfragen_monat": anfragen_je_monat(comps, stichtag),
    }


def comps_kennzahlen(comps: list[Comp], stichtag: dt.date) -> dict[str, Wert]:
    """Alle Comps-Kennzahlen auf einen Blick (für API und Agenten-Werkzeuge).

    Eingabe: Comps, Stichtag. Ausgabe: zusammenfassung() und kennzahlen_eur_qm() in einem dict.
    """
    return {**zusammenfassung(comps, stichtag), **kennzahlen_eur_qm(comps)}


class Preisklassen(BaseModel):
    """Auswertung einer Preisklassen-Verteilung."""

    summe: Wert
    staerkste: str | None
    anteil: Wert


def preisklassen_auswertung(klassen: list[tuple[str, float | None]]) -> Preisklassen:
    """Summe aller Angebote und Anteil der stärksten Klasse.

    Eingabe: (Klasse, Anzahl) je Preisklasse; Anzahl None = Wert fehlt.
    Ausgabe: Preisklassen mit Summe, Name der stärksten Klasse und deren Anteil in %; fehlende Klassen stehen im Rechenweg.
    """
    fehlend = [k for k, n in klassen if n is None]
    klassen = [(k, n) for k, n in klassen if n is not None]
    hinweis = f" ({', '.join(f'{k} fehlt' for k in fehlend)})" if fehlend else ""
    summe = sum(n for _, n in klassen)
    if not summe:
        return Preisklassen(summe=_berechnet(0, "", "keine Preisklassen"), staerkste=None,
                            anteil=_berechnet(None, "%", "keine Preisklassen"))
    klasse, n = max(klassen, key=lambda k: k[1])
    return Preisklassen(
        summe=_berechnet(summe, "", " + ".join(de(n_, 0) for _, n_ in klassen) + f" = {de(summe, 0)} Angebote{hinweis}"),
        staerkste=klasse,
        anteil=_berechnet(n / summe * 100, "%", f"{de(n, 0)} / {de(summe, 0)} = {de(n / summe * 100, 1)} % in Klasse {klasse}"),
    )
