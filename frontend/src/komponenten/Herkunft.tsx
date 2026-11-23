// Herkunft einer Zahl als kleines Kennzeichen (import, manuell, ki, abgelesen, berechnet); ein Klick zeigt Quelle,
// Rechenweg bzw. Fundstelle (CLAUDE.md Regel 1: jede angezeigte Zahl hat eine Herkunft und einen Verweis).
import { useId, useState } from "react";
import type { Herkunft, Quelle, Wert } from "../api";

const KURZ: Record<Herkunft, string> = { import: "Imp", manuell: "Man", ki: "KI", abgelesen: "Abg", berechnet: "Ber" };

type MitHerkunft = Pick<Wert, "herkunft" | "rechenweg_text"> & Partial<Pick<Wert, "fundstelle" | "ausschnitt">>;

/**
 * Kennzeichen mit aufklappbarer Erklärung. Eingabe: Wert (oder Kennzahl) und optional seine Quelle.
 * Ausgabe: Knopf plus Erklärung; Escape oder ein zweiter Klick schließt sie.
 */
export function HerkunftMarke({ wert, quelle }: { wert: MitHerkunft; quelle?: Quelle }) {
  const [offen, setOffen] = useState(false);
  const id = useId();
  return (
    <span className="e-herkunft" onKeyDown={(e) => e.key === "Escape" && setOffen(false)}>
      <button
        type="button"
        className={`e-herkunft-marke h-${wert.herkunft}`}
        aria-expanded={offen}
        aria-controls={id}
        aria-label={`Herkunft: ${wert.herkunft}`}
        onClick={() => setOffen((o) => !o)}
      >
        {KURZ[wert.herkunft]}
      </button>
      {offen && (
        <span id={id} role="note" className="e-herkunft-erklaerung">
          <strong>{wert.herkunft}</strong>
          {quelle && (
            <span>
              Quelle: {quelle.name}
              {quelle.stand && ` · Stand ${quelle.stand}`}
              {quelle.seite && ` · ${quelle.seite}`}
            </span>
          )}
          {wert.rechenweg_text && <span>{wert.herkunft === "berechnet" ? "Rechenweg" : "Hinweis"}: {wert.rechenweg_text}</span>}
          {wert.fundstelle && <span>Fundstelle: {wert.fundstelle}</span>}
          {wert.ausschnitt && <span>Bildausschnitt: {wert.ausschnitt.join(" × ")} px (x, y, Breite, Höhe)</span>}
          {!quelle && !wert.rechenweg_text && !wert.fundstelle && <span>Kein Verweis hinterlegt.</span>}
        </span>
      )}
    </span>
  );
}
