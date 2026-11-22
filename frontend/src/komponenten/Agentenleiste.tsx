// Agentenleiste im Dashboard: Schritte des Analyse-Laufs, offene Freigabe, Tokens und Kosten (Beispieldaten bis M6).
import { useState } from "react";
import { lauf, zeitleiste } from "../daten/agentenDaten";
import { euro, sekunden, statusText } from "./Bausteine";

/**
 * Agentenleiste: Schritte des Analyse-Laufs mit Status, Hinweis auf offene Freigabe, Tokens und Kosten;
 * „Details“ klappt eine Tabelle je Agent auf. Eingabe: keine (Beispieldaten). Ausgabe: Abschnitt.
 */
export function Agentenleiste() {
  const [offen, setOffen] = useState(false);
  const wartend = zeitleiste.find((s) => s.status === "rueckfrage");
  return (
    <section className={`d-agenten${offen ? " offen" : ""}`} aria-labelledby="d-agenten-titel">
      <div className="d-agenten-zeile">
        <h2 id="d-agenten-titel" className="d-agenten-titel">
          Analyse {lauf.id}
        </h2>
        <ol className="d-schritte">
          {zeitleiste.map((s) => (
            <li key={s.id} className={`d-schritt s-${s.status}`} title={s.zusammenfassung || statusText(s.status)}>
              <span className="d-schritt-punkt" aria-hidden="true" />
              {s.agent}
              <span className="e-sr"> – {statusText(s.status)}</span>
            </li>
          ))}
        </ol>
        {wartend && (
          <a href="#d-freigabe" className="d-agenten-hinweis">
            {wartend.agent} wartet auf dich
          </a>
        )}
        <span className="d-leise d-agenten-kosten">
          {lauf.tokens.toLocaleString("de-DE")} Tokens · {euro(lauf.kostenEur)}
        </span>
        <button type="button" className="d-link" aria-expanded={offen} onClick={() => setOffen((o) => !o)}>
          {offen ? "Weniger" : "Details"}
        </button>
      </div>
      {offen && (
        <table className="e-tabelle d-agenten-tabelle">
          <thead>
            <tr>
              <th scope="col">Agent</th>
              <th scope="col">Status</th>
              <th scope="col">Ergebnis</th>
              <th scope="col">Werkzeuge</th>
              <th className="z" scope="col">Dauer</th>
              <th className="z" scope="col">Tokens</th>
              <th className="z" scope="col">Kosten</th>
            </tr>
          </thead>
          <tbody>
            {zeitleiste
              .filter((s) => s.status !== "wartet")
              .map((s) => (
                <tr key={s.id}>
                  <th scope="row">{s.agent}</th>
                  <td className={s.status === "rueckfrage" ? "d-akzent" : ""}>{statusText(s.status)}</td>
                  <td className="d-umbruch">{s.zusammenfassung}</td>
                  <td className="d-umbruch d-leise">{s.werkzeuge.map((w) => w.name).join(", ") || "–"}</td>
                  <td className="z">{sekunden(s.dauerS)}</td>
                  <td className="z">{s.tokens ? s.tokens.toLocaleString("de-DE") : "–"}</td>
                  <td className="z">{s.tokens ? euro(s.kostenEur) : "–"}</td>
                </tr>
              ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

