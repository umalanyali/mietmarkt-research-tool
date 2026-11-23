// Agentenleiste im Dashboard: Zeitleiste des laufenden Analyse-Laufs (Status, Werkzeuge, Dauer, Token, Kosten),
// Rückfragen, Laufliste mit Fortsetzen pausierter Läufe und der Hinweis, wenn die KI nicht eingerichtet ist.
import { useState } from "react";
import type { LaufInfo, Ladezustand } from "../api";
import type { useLauf } from "../lauf";
import { euro, sekunden, statusText } from "./Bausteine";

const NAMEN: Record<string, string> = {
  supervisor: "Supervisor", standort: "Standort", marktdaten: "Marktdaten", expose: "Exposé", vision: "Bilder",
  mietansatz: "Mietansatz", freigabe: "Freigabe", rueckfrage: "Rückfrage", pruefung: "Prüfung", bericht: "Bericht",
};
const LAUF_STATUS = { fertig: "fertig", abgebrochen: "abgebrochen", offen: "pausiert oder unterbrochen" };

/** Kurzform einer Lauf-ID für die Anzeige. Eingabe: ID. Ausgabe: erste 6 Zeichen. */
const kurz = (id: string) => id.slice(0, 6);

/** Werkzeugdaten als lesbarer, gekürzter JSON-Text. Eingabe: beliebige Daten. Ausgabe: Text. */
const json = (d: unknown) => JSON.stringify(d, null, 1).slice(0, 4000);

/**
 * Agentenleiste. Eingabe: Lauf aus useLauf, Laufliste des Projekts, ob die KI eingerichtet ist (null = unbekannt).
 * Ausgabe: Abschnitt; „Details“ klappt Zeitleiste-Tabelle und Laufliste auf.
 */
export function Agentenleiste({ lauf, laeufe, ki }: { lauf: ReturnType<typeof useLauf>; laeufe: Ladezustand<LaufInfo[]>; ki: boolean | null }) {
  const [offen, setOffen] = useState(false);
  const [antwort, setAntwort] = useState("");
  const z = lauf.zustand;
  const liste = laeufe.status === "bereit" ? laeufe.daten : [];
  const pausiert = !lauf.laufId ? liste.find((l) => l.status === "offen") : undefined;
  const tokens = z.schritte.reduce((s, x) => s + x.tokens, 0);
  const live = z.schritte.find((s) => s.status === "arbeitet" && s.text);

  return (
    <>
      {ki === false && (
        <div className="d-hinweis-leiste" role="status">
          <strong>KI nicht konfiguriert.</strong> Für Analyse-Läufe <code>ANTHROPIC_API_KEY</code> in <code>.env</code> eintragen; Daten, Karte und
          Kennzahlen funktionieren ohne.
        </div>
      )}
      <section className={`d-agenten${offen ? " offen" : ""}`} aria-labelledby="d-agenten-titel">
        <div className="d-agenten-zeile">
          <h2 id="d-agenten-titel" className="d-agenten-titel">
            Analyse {lauf.laufId ? kurz(lauf.laufId) : ""}
          </h2>
          <ol className="d-schritte">
            {z.schritte.length === 0 && <li className="d-leise">{pausiert ? "Ein Lauf ist pausiert." : "Noch kein Lauf geöffnet."}</li>}
            {z.schritte.map((s) => (
              <li key={s.agent} className={`d-schritt s-${s.status}`} title={s.text || statusText(s.status)}>
                <span className="d-schritt-punkt" aria-hidden="true" />
                {NAMEN[s.agent] ?? s.agent}
                <span className="e-sr"> – {statusText(s.status)}</span>
              </li>
            ))}
          </ol>
          {z.offen?.art === "mietansatz" && (
            <a href="#d-freigabe" className="d-agenten-hinweis">
              Freigabe wartet auf dich
            </a>
          )}
          {z.schritte.length > 0 && (
            <span className="d-leise d-agenten-kosten">
              {tokens.toLocaleString("de-DE")} Token · {euro(z.kostenEur)}
            </span>
          )}
          {pausiert ? (
            <button type="button" className="e-knopf" disabled={!ki} onClick={() => lauf.oeffnen(pausiert.id)}>
              Fortsetzen
            </button>
          ) : (
            <button type="button" className="e-knopf" disabled={!ki || lauf.aktiv || !!z.offen} onClick={() => lauf.starten()}>
              {lauf.aktiv ? "Läuft …" : "Analyse starten"}
            </button>
          )}
          <button type="button" className="d-link" aria-expanded={offen} onClick={() => setOffen((o) => !o)}>
            {offen ? "Weniger" : "Details"}
          </button>
        </div>

        {live && (
          <p className="d-agenten-live">
            <strong>{NAMEN[live.agent] ?? live.agent}:</strong> {live.text}
          </p>
        )}
        {z.meldung && (
          <p className="d-agenten-meldung" role="alert">
            {z.meldung}{" "}
            {!z.ende && lauf.laufId && !lauf.aktiv && (
              <button type="button" className="d-link" onClick={() => lauf.oeffnen(lauf.laufId!)}>
                Fortsetzen
              </button>
            )}
          </p>
        )}
        {z.offen?.art === "rueckfrage" && (
          <form
            className="d-rueckfrage"
            onSubmit={(e) => {
              e.preventDefault();
              lauf.antworten(antwort.trim()).then(() => setAntwort(""));
            }}
          >
            <label>
              Rückfrage: {z.offen.frage}
              <input value={antwort} maxLength={2000} onChange={(e) => setAntwort(e.target.value)} />
            </label>
            <button type="submit" className="e-knopf" disabled={lauf.aktiv || !antwort.trim()}>
              Antworten
            </button>
          </form>
        )}

        {offen && (
          <>
            {z.schritte.length > 0 && (
              <table className="e-tabelle d-agenten-tabelle">
                <thead>
                  <tr>
                    <th scope="col">Agent</th>
                    <th scope="col">Status</th>
                    <th scope="col">Ergebnis</th>
                    <th scope="col">Werkzeuge</th>
                    <th className="z" scope="col">Dauer</th>
                    <th className="z" scope="col">Token</th>
                    <th className="z" scope="col">Kosten</th>
                  </tr>
                </thead>
                <tbody>
                  {z.schritte.map((s) => (
                    <tr key={s.agent}>
                      <th scope="row">{NAMEN[s.agent] ?? s.agent}</th>
                      <td className={s.status === "rueckfrage" ? "d-akzent" : ""}>{statusText(s.status)}</td>
                      <td className="d-umbruch">{s.text}</td>
                      <td className="d-umbruch">
                        {s.werkzeuge.length === 0
                          ? "–"
                          : s.werkzeuge.map((w, i) => (
                              <details key={i} className="d-werkzeug">
                                <summary>{w.name}</summary>
                                {w.argumente !== undefined && <pre>Argumente: {json(w.argumente)}</pre>}
                                <pre>{w.ergebnis === undefined ? "läuft …" : `Ergebnis: ${json(w.ergebnis)}`}</pre>
                              </details>
                            ))}
                      </td>
                      <td className="z">{sekunden(s.dauerS)}</td>
                      <td className="z">{s.tokens ? s.tokens.toLocaleString("de-DE") : "–"}</td>
                      <td className="z">{s.tokens ? euro(s.kostenEur) : "–"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <h3 className="d-klein d-leise">Läufe dieses Projekts</h3>
            {liste.length === 0 ? (
              <p className="d-leise d-klein">Noch keine Läufe.</p>
            ) : (
              <ul className="d-laufliste">
                {liste.map((l) => (
                  <li key={l.id}>
                    <span>
                      {kurz(l.id)} · {new Date(l.gestartet_am).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" })} · {LAUF_STATUS[l.status]}
                    </span>
                    <button type="button" className="d-link" disabled={lauf.aktiv || (l.status === "offen" && !ki) || l.id === lauf.laufId} onClick={() => lauf.oeffnen(l.id)}>
                      {l.status === "offen" ? "Fortsetzen" : "Ansehen"}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </section>
    </>
  );
}
