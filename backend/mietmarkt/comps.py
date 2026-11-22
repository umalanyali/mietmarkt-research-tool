"""Auswahl von Vergleichsangeboten nach Radius, Baujahr und Typ, mit nachvollziehbarem Rechenweg."""
from pydantic import BaseModel

from .format import de
from .geo import entfernung_km
from .modelle import Comp


class Auswahl(BaseModel):
    """Ergebnis eines Filters: die verbleibenden Comps und wie es dazu kam."""

    comps: list[Comp]
    rechenweg_text: str


def filtern(comps: list[Comp], *, zentrum: tuple[float, float] | None = None, radius_km: float | None = None,
            baujahr_ab: int | None = None, typen: set[str] | None = None) -> Auswahl:
    """Filtert Comps; alle angegebenen Bedingungen gelten zugleich.

    Eingabe: Comps; optional Zentrum + Radius (Luftlinie), Mindestbaujahr, erlaubte Typen (Regel/EG/DG).
    Ausgabe: Auswahl mit Rechenweg, der je Bedingung die ausgeschlossenen Nummern nennt.
    """
    bedingungen = []
    if zentrum is not None and radius_km is not None:
        bedingungen.append((f"Radius {de(radius_km, 1)} km", lambda c: c.lat is not None and c.lon is not None
                            and entfernung_km(*zentrum, c.lat, c.lon).wert <= radius_km))
    if baujahr_ab is not None:
        bedingungen.append((f"Baujahr ab {baujahr_ab}", lambda c: c.baujahr is not None and c.baujahr >= baujahr_ab))
    if typen:
        bedingungen.append((f"Typ {'/'.join(sorted(typen))}", lambda c: c.typ in typen))
    if not bedingungen:
        return Auswahl(comps=list(comps), rechenweg_text=f"{len(comps)} Comps, ohne Filter")

    rest, schritte = list(comps), [f"{len(comps)} Comps"]
    for name, passt in bedingungen:
        raus = [c for c in rest if not passt(c)]
        rest = [c for c in rest if passt(c)]
        nrn = ", ".join(f"Nr. {c.nr}" for c in raus)
        schritte.append(f"{name}: {len(rest)} übrig" + (f" (ausgeschlossen: {nrn})" if raus else ""))
    return Auswahl(comps=rest, rechenweg_text="; ".join(schritte))
