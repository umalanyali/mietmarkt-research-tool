// Deutsche Zahlenformate für die Anzeige. Nur Darstellung – Kennzahlen werden hier nie berechnet.

/** Zahl mit festen Nachkommastellen (de-DE). Eingabe: Wert, Stellen. Ausgabe: Text, „–“ wenn kein Wert. */
export function de(wert: number | null | undefined, stellen = 2): string {
  if (wert === null || wert === undefined || Number.isNaN(wert)) return "–";
  return wert.toLocaleString("de-DE", { minimumFractionDigits: stellen, maximumFractionDigits: stellen });
}

/** Ganze Zahl mit Tausenderpunkt. Eingabe: Wert. Ausgabe: Text, „–“ wenn kein Wert. */
export function ganz(wert: number | null | undefined): string {
  return de(wert, 0);
}
