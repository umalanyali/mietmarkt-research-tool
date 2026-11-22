// Einfarbige Linien-Symbole als SVG (keine bunten Icons, keine Emojis). Farbe kommt über currentColor aus dem CSS.

/** Stern für „merken“. Eingabe: gefuellt (gemerkt ja/nein). Ausgabe: SVG. */
export function SternSymbol({ gefuellt }: { gefuellt: boolean }) {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" aria-hidden="true">
      <path
        d="M8 1.6l1.95 4.1 4.45.55-3.27 3.08.83 4.42L8 11.6l-3.96 2.15.83-4.42L1.6 6.25l4.45-.55z"
        fill={gefuellt ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth="1.1"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Sechs Punkte als Ziehgriff der Merkliste. Eingabe: keine. Ausgabe: SVG. */
export function GriffSymbol() {
  return (
    <svg width="10" height="14" viewBox="0 0 10 14" aria-hidden="true">
      {[2, 7, 12].map((y) => (
        <g key={y} fill="currentColor">
          <circle cx="3" cy={y} r="1" />
          <circle cx="7" cy={y} r="1" />
        </g>
      ))}
    </svg>
  );
}

/** Lupe für Suchfelder. Eingabe: keine. Ausgabe: SVG. */
export function SucheSymbol() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="7" cy="7" r="4.6" fill="none" stroke="currentColor" strokeWidth="1.3" />
      <path d="M10.4 10.4L14 14" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  );
}

/** Ortsmarke für die Vorschlagsliste. Eingabe: keine. Ausgabe: SVG. */
export function PinSymbol() {
  return (
    <svg width="12" height="16" viewBox="0 0 12 16" aria-hidden="true">
      <path d="M6 15s5-5.2 5-9A5 5 0 0 0 1 6c0 3.8 5 9 5 9z" fill="none" stroke="currentColor" strokeWidth="1.3" />
      <circle cx="6" cy="6" r="1.8" fill="currentColor" />
    </svg>
  );
}
