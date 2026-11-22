"""Entfernung zwischen zwei Koordinaten als Luftlinie (Haversine), ohne externen Dienst."""
import math

from ..format import de
from ..modelle import Herkunft, Wert

ERDRADIUS_KM = 6371.0


def entfernung_km(lat1: float, lon1: float, lat2: float, lon2: float) -> Wert:
    """Luftlinie nach der Haversine-Formel.

    Eingabe: zwei Punkte in Grad (WGS84).
    Ausgabe: Wert in km mit Rechenweg.
    """
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    km = 2 * ERDRADIUS_KM * math.asin(math.sqrt(a))
    return Wert(
        wert=km,
        einheit="km",
        herkunft=Herkunft.BERECHNET,
        rechenweg_text=f"Luftlinie (Haversine, Erdradius {de(ERDRADIUS_KM, 0)} km) von {de(lat1, 4)}/{de(lon1, 4)} "
        f"nach {de(lat2, 4)}/{de(lon2, 4)}: {de(km)} km",
    )
