"""Plausibilitätsprüfungen einer Analyse (Werkzeuge des Prüf-Agenten): Ausreißer per IQR, Anzahl und Alter der Comps,
Abweichung des Mietansatzes von Kennzahlen. Jede Prüfung meldet „auffaellig“ und ihre Werte mit Rechenweg."""
import datetime as dt

from .format import de
from .kennzahlen import _berechnet, eur_qm, kennzahlen_eur_qm
from .modelle import Comp, Wert

MIN_COMPS = 5
MIN_IQR = 4  # darunter sind Quartile und IQR nicht aussagekräftig
MAX_ALTER_TAGE = 365  # „älter als 12 Monate“: online seit mehr als 365 Tagen vor dem Stichtag
MAX_ABWEICHUNG_PROZENT = 15


def ausreisser_iqr(comps: list[Comp]) -> dict:
    """Comps, deren €/m² außerhalb von Q1 − 1,5 × IQR bis Q3 + 1,5 × IQR liegen (Tukey).

    Eingabe: Comps. Ausgabe: dict mit auffaellig, pruefbar, untergrenze, obergrenze (Werte) und ausreisser
    (nr, eur_qm); unter MIN_IQR Comps „nicht prüfbar“.
    """
    n = len([c for c in comps if c.wohnflaeche > 0])
    if n < MIN_IQR:
        return {"pruefung": "ausreisser_iqr", "auffaellig": False, "pruefbar": False, "ausreisser": [],
                "rechenweg_text": f"{n} Comps – weniger als {MIN_IQR}, Ausreißer nicht prüfbar"}
    k = kennzahlen_eur_qm(comps)
    q1, q3 = k["q1"].wert, k["q3"].wert
    iqr = q3 - q1
    unten, oben = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    raus = [c for c in comps if c.wohnflaeche > 0 and not unten <= c.kaltmiete / c.wohnflaeche <= oben]
    return {"pruefung": "ausreisser_iqr", "auffaellig": bool(raus), "pruefbar": True,
            "untergrenze": _berechnet(unten, "€/m²", f"Q1 {de(q1)} − 1,5 × IQR {de(iqr)} = {de(unten)} €/m²").model_dump(),
            "obergrenze": _berechnet(oben, "€/m²", f"Q3 {de(q3)} + 1,5 × IQR {de(iqr)} = {de(oben)} €/m²").model_dump(),
            "ausreisser": [{"nr": c.nr, "eur_qm": eur_qm(c).model_dump()} for c in raus]}


def anzahl(comps: list[Comp]) -> dict:
    """Genug Comps für einen Vergleich? Eingabe: Comps. Ausgabe: dict mit auffaellig (< MIN_COMPS) und anzahl (Wert)."""
    n = len(comps)
    return {"pruefung": "anzahl", "auffaellig": n < MIN_COMPS,
            "anzahl": _berechnet(n, "", f"{n} Comps im Umkreis, Mindestzahl {MIN_COMPS}").model_dump()}


def alter(comps: list[Comp], stichtag: dt.date) -> dict:
    """Veraltete Angebote. Eingabe: Comps, Stichtag.

    Ausgabe: dict mit auffaellig, veraltet (nr, online_seit, tage als Wert) und ohne_datum (Nummern, Alter unbekannt).
    """
    veraltet = [c for c in comps if c.online_seit and (stichtag - c.online_seit).days > MAX_ALTER_TAGE]
    return {"pruefung": "alter", "auffaellig": bool(veraltet),
            "veraltet": [{"nr": c.nr, "online_seit": c.online_seit.isoformat(), "tage": _berechnet(
                (stichtag - c.online_seit).days, "Tage",
                f"{stichtag:%d.%m.%Y} − {c.online_seit:%d.%m.%Y} = {(stichtag - c.online_seit).days} Tage "
                f"(Grenze {MAX_ALTER_TAGE})").model_dump()} for c in veraltet],
            "ohne_datum": [c.nr for c in comps if c.online_seit is None]}


def abgleich(ansatz: Wert, kennzahlen: dict[str, Wert]) -> dict:
    """Abweichung des Mietansatzes von Kennzahlen in €/m². Eingabe: Ansatz, {Bezeichnung: Kennzahl}.

    Ausgabe: dict mit auffaellig (irgendeine Abweichung über MAX_ABWEICHUNG_PROZENT) und vergleiche je Kennzahl;
    Kennzahlen ohne Zahl entfallen.
    """
    vergleiche = []
    for name, k in kennzahlen.items():
        if k.wert is None or ansatz.wert is None or k.wert == 0:
            continue
        p = (ansatz.wert - k.wert) / k.wert * 100
        # round: (12,65 − 11) / 11 × 100 ergibt 15,000000000000002 – genau 15 % ist nicht „mehr als 15 %“ (P4)
        vergleiche.append({"kennzahl": name, "wert": k.model_dump(),
                           "auffaellig": abs(round(p, 6)) > MAX_ABWEICHUNG_PROZENT,
                           "abweichung": _berechnet(p, "%", f"({de(ansatz.wert)} − {de(k.wert)}) / {de(k.wert)} × 100 = "
                                                            f"{de(p, 1)} % (Grenze ± {MAX_ABWEICHUNG_PROZENT} %)").model_dump()})
    return {"pruefung": "abgleich", "auffaellig": any(v["auffaellig"] for v in vergleiche), "ansatz": ansatz.model_dump(),
            "vergleiche": vergleiche}
