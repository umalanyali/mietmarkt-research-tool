"""Deutsche Zahlenformate für Rechenwege (Text). Rechnet nichts, formatiert nur."""
from decimal import ROUND_HALF_UP, Decimal


def de(zahl: float, stellen: int = 2) -> str:
    """Zahl im deutschen Format, kaufmännisch gerundet. Eingabe: Zahl, Nachkommastellen. Ausgabe: z. B. „1.234,56“.

    Decimal über str(): 2,675 ist als float 2,67499…, binär gerundet also 2,67; kaufmännisch (wie die
    Zahlenprüfung) 2,68.
    """
    gerundet = Decimal(str(zahl)).quantize(Decimal(1).scaleb(-stellen), rounding=ROUND_HALF_UP)
    text = f"{gerundet:,.{stellen}f}"
    return text.replace(",", "§").replace(".", ",").replace("§", ".")
