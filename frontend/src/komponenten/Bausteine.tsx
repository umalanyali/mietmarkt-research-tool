/*
 * Wiederverwendbare Bausteine des Dashboards: Comps- und VALUE-Tabelle, Freigabe-Karte, Herleitungskette, Zustände.
 * Struktur und Verhalten stehen hier, das Aussehen in d.css (Klassen mit Präfix „e-“).
 */
import { useState } from "react";
import { de, ganz } from "../../format";
import type { Comp } from "../../daten/beispiel";
import { valueTabelle } from "../../daten/beispiel";
import { SternSymbol } from "../../komponenten/Symbole";
import { ENTF_KURZ, ENTF_LANG } from "./hooks";
import { freigabe, herleitung, mietansatzErgebnis, type AgentSchritt } from "./agentenDaten";

// ------------------------------------------------------------------ Stern

/** Stern-Knopf zum Merken. Eingabe: an (gemerkt), Name für Screenreader, Klick-Handler. Ausgabe: Knopf. */
export function EStern({ an, name, onKlick }: { an: boolean; name: string; onKlick: () => void }) {
  return (
    <button
      type="button"
      className="e-stern"
      aria-pressed={an}
      aria-label={an ? `${name} von der Merkliste nehmen` : `${name} merken`}
      onClick={(e) => {
        e.stopPropagation();
        onKlick();
      }}
    >
      <SternSymbol gefuellt={an} />
    </button>
  );
}

// ------------------------------------------------------------------ Comps

interface CompsProps {
  comps: Comp[];
  gemerkt: Set<number>;
  onStern: (nr: number) => void;
  ausgewaehlt: number | null;
  onAuswahl: (nr: number) => void;
  ausgeschlossen?: Set<number>;
}

/**
 * Tabelle der Vergleichsangebote. Eingabe: Comps, gemerkte und vorgeschlagen ausgeschlossene Nummern, Auswahl-Handler.
 * Ausgabe: Tabelle; Klick oder Enter auf eine Zeile wählt den Comp (hebt ihn auf der Karte hervor).
 */
export function CompsTabelle({ comps, gemerkt, onStern, ausgewaehlt, onAuswahl, ausgeschlossen }: CompsProps) {
  return (
    <div className="e-tabelle-rahmen">
      <table className="e-tabelle e-comps">
        <thead>
          <tr>
            <th className="z" scope="col">#</th>
            <th scope="col">Objekt</th>
            <th scope="col">Typ</th>
            <th className="z" scope="col">Zi.</th>
            <th className="z" scope="col">Bj.</th>
            <th className="z" scope="col">Wfl.</th>
            <th className="z" scope="col">€/m²</th>
            <th className="z" scope="col">Kalt</th>
            <th scope="col">EBK</th>
            <th className="z" scope="col">Tage</th>
            <th className="z" scope="col">Anfr.</th>
            <th className="z" scope="col" title="Anfragen je Monat, ab 7 Tagen online">Anfr./M.</th>
            <th className="z" scope="col">km</th>
            <th scope="col"><span className="e-sr">Merken</span></th>
          </tr>
        </thead>
        <tbody>
          {comps.map((c) => {
            const raus = ausgeschlossen?.has(c.nr);
            return (
              <tr
                key={c.nr}
                className={[ausgewaehlt === c.nr ? "aktiv" : "", raus ? "raus" : "", gemerkt.has(c.nr) ? "gemerkt" : ""].join(" ")}
                onClick={() => onAuswahl(c.nr)}
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && onAuswahl(c.nr)}
                aria-selected={ausgewaehlt === c.nr}
              >
                <td className="z e-nr">{c.nr}</td>
                <td className="e-objekt">
                  {c.objekt}
                  <span className="e-unter">{c.anbieter}</span>
                  {raus && <span className="e-vorschlag">Ausschluss vorgeschlagen</span>}
                </td>
                <td>{c.typ}</td>
                <td className="z">{c.zimmer}</td>
                <td className="z">{c.baujahr}</td>
                <td className="z">{de(c.wfl, 1)}</td>
                <td className="z e-haupt">{de(c.eurQm)}</td>
                <td className="z">{ganz(c.kalt)}</td>
                <td>{c.ebk ? "ja" : "–"}</td>
                <td className="z">{c.tage}</td>
                <td className="z">{c.anfragen}</td>
                <td className="z" title={c.anfragenMonat === null ? "unter 7 Tagen online" : undefined}>
                  {c.anfragenMonat === null ? "–" : de(c.anfragenMonat, 1)}
                </td>
                <td className="z" title={ENTF_LANG[c.entfArt]}>
                  {de(c.entfKm, 1)}
                  <span className="e-entf">{ENTF_KURZ[c.entfArt]}</span>
                </td>
                <td>
                  <EStern an={gemerkt.has(c.nr)} name={`Comp ${c.nr}`} onKlick={() => onStern(c.nr)} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ------------------------------------------------------------------ VALUE

/** VALUE-Statistik je Zimmerzahl (n, Ø m², Min, Ø, Median, P75, Max). Eingabe: keine (Beispieldaten). Ausgabe: Tabelle. */
export function ValueTabelle() {
  return (
    <table className="e-tabelle e-value">
      <thead>
        <tr>
          <th scope="col">Zi.</th>
          <th className="z" scope="col">n</th>
          <th className="z" scope="col">Ø m²</th>
          <th className="z" scope="col">Min</th>
          <th className="z" scope="col" title="flächengewichtet">Ø</th>
          <th className="z" scope="col">Median</th>
          <th className="z" scope="col">P75</th>
          <th className="z" scope="col">Max</th>
        </tr>
      </thead>
      <tbody>
        {valueTabelle.map((z) => (
          <tr key={z.zimmer}>
            <td>{z.zimmer.replace(" Zi.", "")}</td>
            <td className="z">{z.n}</td>
            <td className="z">{z.wfl}</td>
            <td className="z e-leise">{z.min}</td>
            <td className="z e-haupt">{z.mittel}</td>
            <td className="z">{z.median}</td>
            <td className="z">{z.p75}</td>
            <td className="z e-leise">{z.max}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ------------------------------------------------------------------ Freigabe (Interrupt)

export type Entscheidung = "offen" | "angenommen" | "geaendert" | "abgelehnt";

/**
 * Freigabe-Karte an einem Interrupt-Punkt des Agenten-Workflows: Vorschlag, Begründung, Belege, Entscheidung.
 * Ab M6 setzt die Entscheidung den pausierten LangGraph-Lauf fort; im Prototyp ändert sie nur die Anzeige.
 * Eingabe: optionaler Verweis (Link zur betroffenen Tabelle). Ausgabe: Karte mit Annehmen / Ändern / Ablehnen.
 */
export function FreigabeKarte({ verweis }: { verweis?: { href: string; text: string } }) {
  const [entscheidung, setEntscheidung] = useState<Entscheidung>("offen");
  const [aendern, setAendern] = useState(false);
  const [kommentar, setKommentar] = useState("");

  /** Hält die Entscheidung fest und schließt das Änderungsformular. Eingabe: Entscheidung. Ausgabe: keine. */
  function setze(e: Entscheidung) {
    setEntscheidung(e);
    setAendern(false);
  }

  if (entscheidung !== "offen") {
    const text = {
      angenommen: "Angenommen. Der Mietansatz-Agent arbeitet mit 11 Comps weiter.",
      geaendert: "Mit deinen Änderungen übernommen. Die Änderung ist als Nutzerkorrektur gespeichert.",
      abgelehnt: "Abgelehnt. Der Exposé-Agent prüft die Auswahl erneut mit deinem Kommentar.",
    }[entscheidung];
    return (
      <section className="e-freigabe e-freigabe-erledigt" aria-live="polite">
        <p className="e-freigabe-kopf">{freigabe.titel}</p>
        <p>{text}</p>
        <button type="button" className="e-link" onClick={() => setEntscheidung("offen")}>
          Rückgängig
        </button>
      </section>
    );
  }

  return (
    <section className="e-freigabe" aria-labelledby="freigabe-titel">
      <p className="e-freigabe-kopf">Freigabe erforderlich</p>
      <h3 id="freigabe-titel" className="e-freigabe-frage">
        {freigabe.frage}
      </h3>
      <dl className="e-freigabe-vorschlag">
        {freigabe.vorschlag.map((v) => (
          <div key={v.text}>
            <dt>{v.text}</dt>
            <dd>{v.wert}</dd>
          </div>
        ))}
      </dl>
      <p className="e-freigabe-grund">{freigabe.begruendung}</p>
      {verweis && (
        <p className="e-verweis">
          <a href={verweis.href}>{verweis.text}</a>
        </p>
      )}
      <ul className="e-belege" aria-label="Belege">
        {freigabe.belege.map((b) => (
          <li key={b.quelle}>
            <button type="button" className="e-beleg">
              {b.quelle}
            </button>{" "}
            <span className="e-leise">{b.fundstelle}</span>
          </li>
        ))}
      </ul>
      {aendern && (
        <div className="e-freigabe-aendern">
          <label>
            <input type="checkbox" defaultChecked={false} /> Comp 6 trotzdem übernehmen
          </label>
          <label className="e-freigabe-kommentar">
            Kommentar für den Agenten
            <textarea rows={2} value={kommentar} onChange={(e) => setKommentar(e.target.value)} />
          </label>
        </div>
      )}
      <div className="e-freigabe-aktionen">
        <button type="button" className="e-knopf e-knopf-primaer" onClick={() => setze(aendern ? "geaendert" : "angenommen")}>
          {aendern ? "Änderung übernehmen" : "Annehmen"}
        </button>
        <button type="button" className="e-knopf" onClick={() => setAendern((a) => !a)} aria-expanded={aendern}>
          {aendern ? "Abbrechen" : "Ändern"}
        </button>
        <button type="button" className="e-knopf e-knopf-still" onClick={() => setze("abgelehnt")}>
          Ablehnen
        </button>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ Herleitungskette

/**
 * Mietansatz als Kette Beleg → Annahme → Zahl; ein Klick auf einen Schritt zeigt Quelle und Rechenwerkzeug.
 * Eingabe: keine (Beispieldaten). Ausgabe: Liste mit Summenzeile.
 */
export function Herleitung() {
  const [offen, setOffen] = useState<string | null>(null);
  return (
    <div className="e-kette">
      <ol className="e-kette-liste">
        {herleitung.map((s) => {
          const zahl = s.glieder.find((g) => g.art === "zahl");
          const beleg = s.glieder.find((g) => g.art === "beleg");
          const annahme = s.glieder.find((g) => g.art === "annahme");
          return (
            <li key={s.schritt} className="e-kette-schritt">
              <button
                type="button"
                className="e-kette-zeile"
                aria-expanded={offen === s.schritt}
                onClick={() => setOffen(offen === s.schritt ? null : s.schritt)}
              >
                <span className="e-kette-name">{s.schritt}</span>
                <span className="e-kette-beleg">{beleg?.text}</span>
                <span className="e-kette-pfeil" aria-hidden="true">→</span>
                <span className="e-kette-annahme">{annahme?.text}</span>
                <span className="e-kette-pfeil" aria-hidden="true">→</span>
                <span className="e-kette-zahl">{zahl?.wert}</span>
              </button>
              {offen === s.schritt && (
                <div className="e-kette-quelle">
                  Quelle: <button type="button" className="e-beleg">{beleg?.quelle}</button>
                  {zahl?.quelle && (
                    <>
                      {" "}· Rechenwerkzeug <code>{zahl.quelle}</code>
                    </>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ol>
      <div className="e-kette-summe">
        <span>Saldo Zu-/Abschläge {mietansatzErgebnis.saldo}</span>
        <span>vor Rundung {mietansatzErgebnis.vorRundung}</span>
      </div>
      <p className="e-leise e-kette-status">
        {mietansatzErgebnis.status} · gerundet {mietansatzErgebnis.rundung} · jede Zahl aus einem Rechenwerkzeug
      </p>
    </div>
  );
}

// ------------------------------------------------------------------ Zustände

/** Leerzustand mit Erklärung und optionaler nächster Aktion. Eingabe: Titel, Text, Aktion. Ausgabe: Hinweisblock. */
export function LeerZustand({ titel, text, aktion }: { titel: string; text: string; aktion?: string }) {
  return (
    <div className="e-leer" role="status">
      <p className="e-leer-titel">{titel}</p>
      <p className="e-leise">{text}</p>
      {aktion && (
        <button type="button" className="e-knopf">
          {aktion}
        </button>
      )}
    </div>
  );
}

/** Fehlerzustand mit Ursache und Ausweg. Eingabe: Titel, Text, Aktion. Ausgabe: Hinweisblock (role=alert). */
export function FehlerZustand({ titel, text, aktion = "Erneut versuchen" }: { titel: string; text: string; aktion?: string }) {
  return (
    <div className="e-fehler" role="alert">
      <p className="e-fehler-titel">{titel}</p>
      <p>{text}</p>
      <button type="button" className="e-knopf">
        {aktion}
      </button>
    </div>
  );
}

/** Platzhalterzeilen während des Ladens. Eingabe: Anzahl Zeilen. Ausgabe: pulsierende Balken. */
export function LadeZeilen({ zeilen = 4 }: { zeilen?: number }) {
  return (
    <div className="e-laden" role="status" aria-label="Wird geladen">
      {Array.from({ length: zeilen }, (_, i) => (
        <span key={i} style={{ width: `${92 - i * 13}%` }} />
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ Hilfen

/** Agentenstatus als Text. Eingabe: Status. Ausgabe: z. B. „wartet auf dich“. */
export function statusText(s: AgentSchritt["status"]): string {
  return { fertig: "fertig", arbeitet: "arbeitet", rueckfrage: "wartet auf dich", wartet: "wartet", fehler: "Fehler" }[s];
}

/** Dauer als Text. Eingabe: Sekunden oder null. Ausgabe: „4,2 s“ bzw. leer. */
export function sekunden(s: number | null): string {
  return s === null ? "" : `${de(s, 1)} s`;
}

/** Kosten als Text. Eingabe: Euro. Ausgabe: „0,21 €“; Kleinstbeträge als „< 0,01 €“. */
export function euro(e: number): string {
  return e < 0.005 && e > 0 ? "< 0,01 €" : `${de(e, 2)} €`;
}
