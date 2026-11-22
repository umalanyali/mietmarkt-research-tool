// Wiederkehrende Seitenteile: Kopfzeile mit Navigation, Pill-Auswahl und Liste der Adressvorschläge.
import { Link, NavLink, useLocation } from "react-router-dom";
import { PinSymbol } from "./Symbole";
import type { useAdressSuche } from "../hooks";

/** Kopfzeile mit Wortmarke und Navigation. Eingabe: keine. Ausgabe: <header>. */
export function Kopf() {
  // „Projekte“ gilt auf jeder Analyseseite als aktiv, daher von Hand statt über NavLink
  const aufAnalyse = useLocation().pathname.startsWith("/analyse");
  return (
    <header className="d-kopf">
      <Link to="/" className="d-marke">
        Mietmarkt Research
      </Link>
      <nav aria-label="Hauptnavigation" className="d-nav">
        <NavLink end to="/">
          Neue Suche
        </NavLink>
        <Link to="/#zuletzt" aria-current={aufAnalyse ? "page" : undefined}>
          Projekte
        </Link>
        <NavLink end to="/zustaende">
          Zustände
        </NavLink>
      </nav>
    </header>
  );
}

/** Pill-Auswahl wie im Mockup, technisch eine Radiogruppe. Eingabe: Name, Optionen, Wert, Handler. Ausgabe: Knopfgruppe. */
export function Pills<T extends string>({ name, optionen, wert, onWahl }: { name: string; optionen: readonly T[]; wert: T; onWahl: (w: T) => void }) {
  return (
    <div className="d-pills" role="radiogroup" aria-label={name}>
      {optionen.map((o) => (
        <button key={o} type="button" role="radio" aria-checked={o === wert} className={o === wert ? "an" : ""} onClick={() => onWahl(o)}>
          {o}
        </button>
      ))}
    </div>
  );
}

/**
 * Adressvorschläge unter einem Suchfeld samt Zustandshinweisen (sucht, kein Treffer, Dienst nicht erreichbar).
 * Eingabe: Ergebnis von useAdressSuche. Ausgabe: Liste mit Quellenhinweis, ein Hinweis oder nichts.
 */
export function Vorschlagsliste({ suche }: { suche: ReturnType<typeof useAdressSuche> }) {
  if (suche.status === "nicht-erreichbar") {
    return <p className="d-hinweis" role="alert">Adressdienst nicht erreichbar. Bitte gleich noch einmal versuchen.</p>;
  }
  if (suche.status === "fehler") return <p className="d-hinweis" role="alert">Die Suche ist fehlgeschlagen.</p>;
  if (suche.keinTreffer) return <p className="d-hinweis">Keine Adresse in Deutschland gefunden. Schreibweise prüfen oder Ort ergänzen.</p>;
  if (!suche.zeigeListe) return suche.status === "laden" ? <p className="d-hinweis" role="status">Suche …</p> : null;
  return (
    <div className="d-vorschlaege">
      <ul id={suche.listenId} role="listbox" aria-label="Adressvorschläge">
        {suche.vorschlaege.map((v, i) => (
          <li key={`${v.label}-${v.lat}-${v.lon}`} {...suche.option(i)}>
            <span className="d-pin">
              <PinSymbol />
            </span>
            <span className="d-vorschlag-text">
              <strong>{v.strasse || v.ort}</strong>
              {v.strasse && `, ${v.plz} ${v.ort}`}
            </span>
            <span className="d-vorschlag-ort">{v.ortsteil}</span>
          </li>
        ))}
      </ul>
      <p className="d-vorschlag-quelle">{suche.attribution}</p>
    </div>
  );
}
