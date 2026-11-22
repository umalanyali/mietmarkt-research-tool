"""Deutsche Zahlenformate für Rechenwege (Text). Rechnet nichts, formatiert nur."""


def de(zahl: float, stellen: int = 2) -> str:
    """Zahl im deutschen Format. Eingabe: Zahl, Nachkommastellen. Ausgabe: z. B. „1.234,56“."""
    text = f"{zahl:,.{stellen}f}"
    return text.replace(",", "§").replace(".", ",").replace("§", ".")
