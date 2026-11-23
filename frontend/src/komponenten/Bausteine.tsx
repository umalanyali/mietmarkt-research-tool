/*
 * Wiederverwendbare Bausteine des Dashboards: Comps- und Angebotstabelle, Freigabe-Karte, Herleitungskette, Zustände.
 * Struktur und Verhalten stehen hier, das Aussehen in stil/app.css (Klassen mit Präfix „e-“).
 */
import { useState } from "react";
import { de, ganz } from "../format";
import type { Comp, Marktkennzahl, Wert } from "../api";
import { SternSymbol } from "./Symbole";
import type { AgentStatus, Freigabe, Herleitungen } from "../lauf";
import { HerkunftMarke } from "./Herkunft";

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
}

/**
 * Tabelle der Vergleichsangebote. Eingabe: Comps, gemerkte Nummern, Auswahl-Handler.
 * Ausgabe: Tabelle; Klick oder Enter auf eine Zeile wählt den Comp (hebt ihn auf der Karte hervor).
 */
export function CompsTabelle({ comps, gemerkt, onStern, ausgewaehlt, onAuswahl }: CompsProps) {
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
            return (
              <tr
                key={c.nr}
                className={[ausgewaehlt === c.nr ? "aktiv" : "", gemerkt.has(c.nr) ? "gemerkt" : ""].join(" ")}
                onClick={() => onAuswahl(c.nr)}
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && onAuswahl(c.nr)}
                aria-selected={ausgewaehlt === c.nr}
              >
                <td className="z e-nr">{c.nr}</td>
                <td className="e-objekt">
                  {c.objekt}
                  <span className="e-unter">{c.anbieter}</span>
                </td>
                <td>{c.typ}</td>
                <td className="z">{c.zimmer}</td>
                <td className="z">{c.baujahr}</td>
                <td className="z">{de(c.wohnflaeche, 1)}</td>
                <td className="z e-haupt" title={c.eur_qm.rechenweg_text}>{de(c.eur_qm.wert)}</td>
                <td className="z">{ganz(c.kaltmiete)}</td>
                <td>{c.ebk ? "ja" : "–"}</td>
                <td className="z" title={c.tage_online.rechenweg_text}>{de(c.tage_online.wert, 0)}</td>
                <td className="z">{c.anfragen ?? "–"}</td>
                <td className="z" title={c.anfragen_monat.rechenweg_text}>
                  {de(c.anfragen_monat.wert, 1)}
                </td>
                <td className="z" title={c.entfernung_km?.rechenweg_text}>
                  {de(c.entfernung_km?.wert, 1)}
                  {/* Bis zum Routing (M4) ist jede Entfernung Luftlinie */}
                  <span className="e-entf">L</span>
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

// ------------------------------------------------------------------ Angebotsstatistik

const VALUE_SPALTEN = ["n", "Ø m²", "Min", "Ø", "Median", "P75", "Max"];

/**
 * Angebotsstatistik je Zimmerzahl. Eingabe: Kennzahlen der Gruppe „angebot_tabelle“ (Zeile = Kategorie, Spalte = Bezeichnung).
 * Ausgabe: Tabelle; jede Zelle zeigt beim Überfahren Herkunft und Rechenweg.
 */
export function AngebotTabelle({ werte }: { werte: Marktkennzahl[] }) {
  const zeilen = [...new Set(werte.map((w) => w.kategorie))];
  const zelle = (zeile: string, spalte: string) => werte.find((w) => w.kategorie === zeile && w.bezeichnung === spalte);
  return (
    <table className="e-tabelle e-angebot">
      <thead>
        <tr>
          <th scope="col">Zi.</th>
          {VALUE_SPALTEN.map((s) => (
            <th key={s} className="z" scope="col">
              {s}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {zeilen.map((z) => (
          <tr key={z}>
            <td>{z.replace(" Zi.", "")}</td>
            {VALUE_SPALTEN.map((s) => {
              const w = zelle(z, s);
              const klasse = s === "Ø" ? "z e-haupt" : s === "Min" || s === "Max" ? "z e-leise" : "z";
              return (
                <td key={s} className={klasse} title={w ? herkunftText(w) : undefined}>
                  {de(w?.wert, w?.stellen ?? 0)}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Herkunft einer Zahl als Hinweistext. Eingabe: Wert oder Kennzahl. Ausgabe: z. B. „import · Σ … = …“. */
export function herkunftText(w: Pick<Wert, "herkunft" | "rechenweg_text">): string {
  return [w.herkunft, w.rechenweg_text].filter(Boolean).join(" · ");
}

// ------------------------------------------------------------------ Freigabe (Interrupt)

const BASIS_TEXT = { regel_eg: "Regelgeschoss/EG", dg: "Dachgeschoss" } as const;

/** Betrag mit Vorzeichen. Eingabe: Zahl. Ausgabe: z. B. „+0,30“. */
const mitVorzeichen = (w: number | null) => `${w !== null && w > 0 ? "+" : ""}${de(w)}`;

/**
 * Freigabe-Karte am Interrupt des Laufs: Vorschlag je Basis, Begründung, Herleitungskette, Annehmen / Ändern /
 * Ablehnen mit Kommentar. Eingabe: Vorschlag aus „wartet_auf_freigabe“, Absenden-Handler, ob gerade gesendet wird.
 * Ausgabe: Karte. Ablehnen braucht einen Kommentar (das Backend verlangt ihn, damit der Agent weiß, was anders soll).
 */
export function FreigabeKarte({ vorschlag, onSenden, sendet }: { vorschlag: { herleitungen: Herleitungen; begruendung: string }; onSenden: (f: Freigabe) => void; sendet: boolean }) {
  const basen = Object.keys(vorschlag.herleitungen) as (keyof Herleitungen)[];
  const [aendern, setAendern] = useState(false);
  const [kommentar, setKommentar] = useState("");
  // Eingaben je Basis: Basiswert und Beträge der vorgeschlagenen Zu-/Abschläge, als Text (Komma erlaubt)
  const [eingaben, setEingaben] = useState(() =>
    Object.fromEntries(basen.map((b) => {
      const schritte = vorschlag.herleitungen[b]!.schritte;
      return [b, schritte.filter((x) => x.art === "basis" || x.art === "anpassung").map((x) => de(x.wert.wert))];
    })) as Record<string, string[]>,
  );
  const text = kommentar.trim() || undefined;

  /** Baut die Änderungen: nur Basen, an denen sich etwas geändert hat. Ausgabe: aenderungen oder undefined. */
  function aenderungen(): Freigabe["aenderungen"] {
    const aus: NonNullable<Freigabe["aenderungen"]> = {};
    for (const b of basen) {
      const h = vorschlag.herleitungen[b]!;
      const [basis, ...betraege] = eingaben[b].map((t) => Number(t.replace(/\./g, "").replace(",", ".")));
      const anp = h.schritte.filter((x) => x.art === "anpassung");
      const e: { basiswert?: number; anpassungen?: { name: string; betrag: number; begruendung: string }[] } = {};
      if (eingaben[b][0] !== de(h.schritte[0].wert.wert)) e.basiswert = basis;
      if (anp.some((x, i) => eingaben[b][i + 1] !== de(x.wert.wert))) {
        e.anpassungen = anp.map((x, i) => ({ name: x.name, betrag: betraege[i], begruendung: x.begruendung }));
      }
      if (Object.keys(e).length) aus[b] = e;
    }
    return Object.keys(aus).length ? aus : undefined;
  }
  const geaendert = aendern ? aenderungen() : undefined;

  return (
    <section className="e-freigabe" aria-labelledby="freigabe-titel">
      <p className="e-freigabe-kopf">Freigabe erforderlich</p>
      <h3 id="freigabe-titel" className="e-freigabe-frage">
        Mietansatz übernehmen?
      </h3>
      <dl className="e-freigabe-vorschlag">
        {basen.map((b) => {
          const h = vorschlag.herleitungen[b]!;
          return (
            <div key={b}>
              <dt>{BASIS_TEXT[b]}</dt>
              <dd>
                {de(h.ergebnis.wert)} €/m² <HerkunftMarke wert={h.ergebnis} />
                {h.fortgeschrieben && <> · bei Vermarktung {de(h.fortgeschrieben.wert)} €/m² <HerkunftMarke wert={h.fortgeschrieben} /></>}
              </dd>
            </div>
          );
        })}
      </dl>
      <p className="e-freigabe-grund">{vorschlag.begruendung}</p>
      <Herleitung herleitungen={vorschlag.herleitungen} />
      {aendern && (
        <div className="e-freigabe-aendern">
          {basen.map((b) => {
            const glieder = vorschlag.herleitungen[b]!.schritte.filter((x) => x.art === "basis" || x.art === "anpassung");
            return (
              <fieldset key={b}>
                <legend>{BASIS_TEXT[b]} (€/m²)</legend>
                {glieder.map((g, i) => (
                  <label key={i}>
                    {g.art === "basis" ? "Basiswert" : g.name}
                    <input
                      inputMode="decimal"
                      value={eingaben[b][i]}
                      onChange={(e) => setEingaben((alt) => ({ ...alt, [b]: alt[b].map((t, j) => (j === i ? e.target.value : t)) }))}
                    />
                  </label>
                ))}
              </fieldset>
            );
          })}
        </div>
      )}
      <label className="e-freigabe-kommentar">
        Kommentar für den Agenten {!aendern && <span className="e-leise">(nötig zum Ablehnen)</span>}
        <textarea rows={2} maxLength={2000} value={kommentar} onChange={(e) => setKommentar(e.target.value)} />
      </label>
      <div className="e-freigabe-aktionen">
        {aendern ? (
          <button type="button" className="e-knopf e-knopf-primaer" disabled={sendet || !geaendert} onClick={() => onSenden({ aktion: "aendern", aenderungen: geaendert, kommentar: text })}>
            Änderung übernehmen
          </button>
        ) : (
          <button type="button" className="e-knopf e-knopf-primaer" disabled={sendet} onClick={() => onSenden({ aktion: "annehmen", kommentar: text })}>
            Annehmen
          </button>
        )}
        <button type="button" className="e-knopf" disabled={sendet} onClick={() => setAendern((a) => !a)} aria-expanded={aendern}>
          {aendern ? "Abbrechen" : "Ändern"}
        </button>
        <button type="button" className="e-knopf e-knopf-still" disabled={sendet || !text} onClick={() => onSenden({ aktion: "ablehnen", kommentar: text })}>
          Ablehnen
        </button>
      </div>
    </section>
  );
}

// ------------------------------------------------------------------ Herleitungskette

/**
 * Mietansatz als Kette Basis → Zu-/Abschläge → Ergebnis (→ Fortschreibung), je Basis; jede Zahl mit Herkunft.
 * Eingabe: Herleitungen aus dem Lauf. Ausgabe: Listen je Basis.
 */
export function Herleitung({ herleitungen }: { herleitungen: Herleitungen }) {
  return (
    <div className="e-kette">
      {(Object.keys(herleitungen) as (keyof Herleitungen)[]).map((b) => (
        <ol key={b} className="e-kette-liste" aria-label={`Herleitung ${BASIS_TEXT[b]}`}>
          {herleitungen[b]!.schritte.map((s, i) => (
            <li key={i} className={`e-kette-schritt k-${s.art}`}>
              <span className="e-kette-name">
                {s.art === "basis" ? `Basis ${BASIS_TEXT[b]}` : s.name}
                {s.begruendung && <span className="e-kette-beleg">{s.begruendung}</span>}
              </span>
              <span className="e-kette-zahl">
                {s.art === "anpassung" ? mitVorzeichen(s.wert.wert) : de(s.wert.wert)} €/m² <HerkunftMarke wert={s.wert} />
              </span>
            </li>
          ))}
        </ol>
      ))}
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

/** Fehlerzustand mit Ursache und Ausweg. Eingabe: Titel, Text, Aktionstext und -Handler. Ausgabe: Hinweisblock (role=alert). */
export function FehlerZustand({ titel, text, aktion = "Erneut versuchen", onAktion }: { titel: string; text: string; aktion?: string; onAktion?: () => void }) {
  return (
    <div className="e-fehler" role="alert">
      <p className="e-fehler-titel">{titel}</p>
      <p>{text}</p>
      <button type="button" className="e-knopf" onClick={onAktion}>
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
export function statusText(s: AgentStatus): string {
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
