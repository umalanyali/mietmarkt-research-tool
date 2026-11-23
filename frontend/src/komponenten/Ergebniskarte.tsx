// Ergebniskarte nach einem beendeten Lauf: was herausgekommen ist (freigegebener Mietansatz, Befunde, Unterlagen,
// Kosten) und was als Nächstes zu tun ist (Bericht ansehen, als Markdown oder PowerPoint herunterladen).
import { useEffect, useRef, useState } from "react";
import type { Herkunft } from "../api";
import { de } from "../format";
import type { LaufZustand } from "../lauf";
import { HerkunftMarke } from "./Herkunft";

// Ausschnitt des Berichts, wie ihn agenten/bericht.py liefert (nur die Felder, die hier erscheinen)
interface Bericht {
  abschnitte: Record<string, string>;
  fussnoten: { nr: number; herkunft: Herkunft; verweis: string }[];
  methoden: { nr: string; text: string }[];
  befunde: { pruefung: string; schweregrad: "hinweis" | "warnung" | "kritisch"; text: string; markierungen: unknown[] }[];
}

const BASIS = { regel_eg: "Regelgeschoss/EG", dg: "Dachgeschoss" } as const;
const ABSCHNITTE = { lage: "Lage", markt: "Markt", mietansatz: "Mietansatz", risiken: "Risiken" } as const;
const RANG = { kritisch: 0, warnung: 1, hinweis: 2 } as const;

/** Fußnotenzeichen „[^3]“ aus dem Markdown als „[3]“. Eingabe: Text. Ausgabe: Text. */
const lesbar = (text: string) => text.replace(/\[\^(\w+)\]/g, "[$1]");

/** Aufgeklappter Bericht: Abschnitte, Methoden, Fußnoten (reiner Text, kein HTML aus Modelltext). Eingabe: Bericht. */
function BerichtText({ b }: { b: Bericht }) {
  return (
    <div className="d-bericht" id="d-bericht">
      {(Object.keys(ABSCHNITTE) as (keyof typeof ABSCHNITTE)[]).map(
        (k) =>
          b.abschnitte[k] && (
            <section key={k}>
              <h4>{ABSCHNITTE[k]}</h4>
              <p>{lesbar(b.abschnitte[k])}</p>
            </section>
          ),
      )}
      {b.methoden.length > 0 && (
        <section>
          <h4>Methoden</h4>
          <ul>{b.methoden.map((m) => <li key={m.nr}>{`[${m.nr}] ${m.text}`}</li>)}</ul>
        </section>
      )}
      <section>
        <h4>Herkunft der Zahlen</h4>
        <ol className="d-fussnoten">{b.fussnoten.map((f) => <li key={f.nr}>{`[${f.nr}] ${f.herkunft} – ${f.verweis}`}</li>)}</ol>
      </section>
    </div>
  );
}

/**
 * Karte mit dem Ergebnis eines beendeten Laufs. Eingabe: Lauf-ID und Zustand nach „fertig“ bzw. Abbruch.
 * Ausgabe: Mietansatz je Basis (zum Stichtag und fortgeschrieben), Befunde, übernommene Unterlagen, Kosten und
 * die Export-Links; bei Abbruch nur Grund und Kosten.
 */
export function Ergebniskarte({ laufId, zustand }: { laufId: string; zustand: LaufZustand }) {
  const [offen, setOffen] = useState(false);
  const karte = useRef<HTMLElement>(null);
  // Beim Erscheinen in den Blick holen: nach „Annehmen“ steht man sonst unten bei der Freigabe-Karte
  // Klammern nötig: Chrome gibt bei „smooth“ ein Promise zurück, das React sonst für eine Aufräumfunktion hält
  useEffect(() => {
    karte.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  }, []);
  const kosten = <p className="d-klein">Kosten des Laufs: {de(zustand.kostenEur)} €</p>;
  if (zustand.ende === "abgebrochen") {
    return (
      <section ref={karte} className="d-karte d-ergebnis" aria-labelledby="d-ergebnis-titel">
        <h3 id="d-ergebnis-titel">Lauf abgebrochen</h3>
        <p>{zustand.meldung ?? "ohne Grund"}. Es gibt keinen Bericht; „Analyse starten“ beginnt einen neuen Lauf.</p>
        {kosten}
      </section>
    );
  }
  const b = zustand.bericht as Bericht | null;
  const befunde = [...(b?.befunde ?? [])].sort((x, y) => RANG[x.schweregrad] - RANG[y.schweregrad]);
  const unterlagen = zustand.schritte
    .filter((s) => (s.agent === "expose" || s.agent === "vision") && s.text)
    .flatMap((s) => s.text.split("\n").filter((z) => z.trim()));

  return (
    <section ref={karte} className="d-karte d-ergebnis" aria-labelledby="d-ergebnis-titel">
      <div className="d-ergebnis-kopf">
        <div>
          <h3 id="d-ergebnis-titel">Ergebnis des Laufs</h3>
          <p className="d-leise d-klein">Mietansatz freigegeben, geprüft und als Bericht belegt. Nächster Schritt: Bericht lesen und exportieren.</p>
        </div>
        {b && (
          <div className="d-ergebnis-knoepfe">
            <button type="button" className="e-knopf e-knopf-primaer" aria-expanded={offen} aria-controls="d-bericht" onClick={() => setOffen((o) => !o)}>
              Bericht ansehen
            </button>
            <a className="e-knopf" href={`/api/laeufe/${laufId}/bericht.md`} download>
              Markdown
            </a>
            <a className="e-knopf" href={`/api/laeufe/${laufId}/bericht.pptx`} download>
              PowerPoint
            </a>
          </div>
        )}
      </div>

      <div className="d-ergebnis-raster">
        <div>
          <h4>Freigegebener Mietansatz</h4>
          {zustand.herleitungen ? (
            <table className="e-tabelle" aria-label="Freigegebener Mietansatz">
              <thead>
                <tr>
                  <th scope="col">Basis</th>
                  <th scope="col">zum Stichtag</th>
                  <th scope="col">fortgeschrieben</th>
                </tr>
              </thead>
              <tbody>
                {(Object.keys(BASIS) as (keyof typeof BASIS)[]).map((k) => {
                  const h = zustand.herleitungen![k];
                  return (
                    h && (
                      <tr key={k}>
                        <th scope="row">{BASIS[k]}</th>
                        <td>
                          {de(h.ergebnis.wert)} {h.ergebnis.einheit} <HerkunftMarke wert={h.ergebnis} />
                        </td>
                        <td>
                          {h.fortgeschrieben ? (
                            <>
                              <strong>{de(h.fortgeschrieben.wert)} {h.fortgeschrieben.einheit}</strong> <HerkunftMarke wert={h.fortgeschrieben} />
                            </>
                          ) : (
                            "–"
                          )}
                        </td>
                      </tr>
                    )
                  );
                })}
              </tbody>
            </table>
          ) : (
            <p className="d-leise">Kein freigegebener Mietansatz.</p>
          )}
          {kosten}
        </div>

        <div>
          <h4>{`Befunde der Prüfung (${befunde.length})`}</h4>
          {befunde.length === 0 && <p className="d-leise">Keine Befunde.</p>}
          <ul className="d-befunde">
            {befunde.map((x, i) => (
              <li key={i} className={`b-${x.schweregrad}`}>
                <strong>{x.schweregrad}</strong> {x.text}
                {x.markierungen.length > 0 && <span className="d-leise"> (enthält ungeprüfte Zahlen)</span>}
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h4>Aus den Unterlagen</h4>
          {unterlagen.length === 0 ? (
            <p className="d-leise">Keine Unterlagen ausgewertet (keine mit Häkchen „KI darf lesen“).</p>
          ) : (
            <ul className="d-befunde">
              {unterlagen.map((z, i) => {
                // „datei: Balkon [Quelle: datei, S. 1]; …“ → Datei einmal vorn, je Merkmal nur die Fundstelle
                const [datei, rest] = z.includes(": ") ? [z.slice(0, z.indexOf(": ")), z.slice(z.indexOf(": ") + 2)] : ["", z];
                return (
                  <li key={i}>
                    {datei && <strong>{datei}</strong>} {rest.replace(/\s*\[Quelle: [^,\]]+, ([^\]]+)\]/g, " ($1)")}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>

      {offen && b && <BerichtText b={b} />}
    </section>
  );
}
