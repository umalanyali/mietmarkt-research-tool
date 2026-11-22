/*
 * Richtung D · nach dem Mockup
 * Aufbau, Spalten und Bausteine wie in docs/mockups/ (Startseite zentriert, Dashboard in drei Spalten
 * mit schwarzen Titelbalken, weißen Karten, Pills, Tabellenkopf in Akzentfarbe).
 * Ohne Logo und Firmenname; Akzent Oliv statt der Firmenfarbe (CLAUDE.md: warme Neutraltöne, kein Türkis).
 * Ergänzt um Agentenleiste und Freigabe-Karte aus dem freigegebenen Plan.
 */
import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import "@fontsource/hanken-grotesk/400.css";
import "@fontsource/hanken-grotesk/500.css";
import "@fontsource/hanken-grotesk/600.css";
import "@fontsource/hanken-grotesk/700.css";
import "../gemeinsam/basis.css";
import "./d.css";
import { comps, compsZusammenfassung as zf, datenstand, kartenPunkte, preisklassen, projekt, screenshots, soziodemografie, valueKennzahlen, weitereQuellen, zeitreihe, zuletzt } from "../../daten/beispiel";
import { de } from "../../format";
import { Merkliste } from "../../komponenten/Merkliste";
import { Saeulen, Zeitreihe } from "../../komponenten/Diagramme";
import { SucheSymbol } from "../../komponenten/Symbole";
import { EntwurfKarte, EBENEN, type Ebene } from "../gemeinsam/EntwurfKarte";
import { useAdressSuche, useMerkliste, passtZimmer, ZIMMER, type ZimmerFilter } from "../gemeinsam/hooks";
import { lauf, zeitleiste } from "../gemeinsam/agentenDaten";
import { CompsTabelle, EStern, euro, FehlerZustand, FreigabeKarte, Herleitung, LadeZeilen, LeerZustand, sekunden, statusText, ValueTabelle } from "../gemeinsam/Bausteine";

// Leere Kartenebenen für die Zustandsübersicht
const LEER = { projekte: [], oepnv: [], nahversorgung: [] };
// Quellenkürzel in der Merkliste
const KUERZEL: Record<string, string> = { RIWIS: "R", VALUE: "V", IS24: "IS" };

/** Ortsmarke für die Vorschlagsliste. Eingabe: keine. Ausgabe: SVG. */
function PinSymbol() {
  return (
    <svg width="12" height="16" viewBox="0 0 12 16" aria-hidden="true">
      <path d="M6 15s5-5.2 5-9A5 5 0 0 0 1 6c0 3.8 5 9 5 9z" fill="none" stroke="currentColor" strokeWidth="1.3" />
      <circle cx="6" cy="6" r="1.8" fill="currentColor" />
    </svg>
  );
}

/** Kopfzeile mit Wortmarke und Navigation. Eingabe: keine. Ausgabe: <header>. */
function Kopf() {
  return (
    <header className="d-kopf">
      <Link to="/entwurf/d" className="d-marke">
        Mietmarkt Research
      </Link>
      <nav aria-label="Hauptnavigation" className="d-nav">
        <NavLink end to="/entwurf/d">
          Neue Suche
        </NavLink>
        <NavLink end to="/entwurf/d/dashboard">
          Projekte
        </NavLink>
        <NavLink end to="/entwurf/d/zustaende">
          Zustände
        </NavLink>
      </nav>
    </header>
  );
}

/** Pill-Auswahl wie im Mockup, technisch eine Radiogruppe. Eingabe: Name, Optionen, Wert, Handler. Ausgabe: Knopfgruppe. */
function Pills<T extends string>({ name, optionen, wert, onWahl }: { name: string; optionen: readonly T[]; wert: T; onWahl: (w: T) => void }) {
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

// ======================================================================= Startseite

/** Startseite: Adresssuche, Filter, Datenstand je Quelle, zuletzt analysierte Projekte. Eingabe: keine. Ausgabe: Seite. */
export function StartD() {
  const navigate = useNavigate();
  const suche = useAdressSuche(() => navigate("/entwurf/d/dashboard"));
  const [nutzung, setNutzung] = useState<"Wohnen" | "Gewerbe">("Wohnen");
  const [alter, setAlter] = useState<"Neubau" | "Bestand">("Neubau");
  const [umkreis, setUmkreis] = useState<"Umkreis 1 km" | "Umkreis 2 km" | "Umkreis 5 km">("Umkreis 2 km");
  const [art, setArt] = useState<"Miete" | "Kauf">("Miete");

  return (
    <div className="rd">
      <Kopf />
      <main className="d-start">
        <h1 className="d-start-titel">Mietmarkt Research</h1>
        <p className="d-start-unter">Eine Adresse – alle importierten Marktdaten aus RIWIS, VALUE, ImmoScout24 und amtlichen Quellen</p>

        <form
          className="d-suche"
          role="search"
          onSubmit={(e) => {
            e.preventDefault();
            navigate("/entwurf/d/dashboard");
          }}
        >
          <span className="d-suche-symbol">
            <SucheSymbol />
          </span>
          <label htmlFor="d-adresse" className="e-sr">
            Adresse
          </label>
          <input id="d-adresse" placeholder="Adresse eingeben, z. B. Lindenallee 30, Musterstadt" {...suche.feld} />
          <button type="submit" className="d-knopf-gross">
            Analyse starten
          </button>
          {suche.zeigeListe && (
            <ul id={suche.listenId} role="listbox" className="d-vorschlaege" aria-label="Adressvorschläge">
              {suche.vorschlaege.map((v, i) => (
                <li key={v.strasse + v.plz} {...suche.option(i)}>
                  <span className="d-pin">
                    <PinSymbol />
                  </span>
                  <span className="d-vorschlag-text">
                    <strong>{v.strasse}</strong>, {v.plz} {v.ort}
                  </span>
                  <span className="d-vorschlag-ort">{v.ortsteil}</span>
                </li>
              ))}
            </ul>
          )}
          {suche.keinTreffer && <p className="d-hinweis">Keine Adresse gefunden. Ort oder Postleitzahl ergänzen.</p>}
        </form>

        <div className="d-start-filter">
          <Pills name="Nutzung" optionen={["Wohnen", "Gewerbe"] as const} wert={nutzung} onWahl={setNutzung} />
          <Pills name="Baualter" optionen={["Neubau", "Bestand"] as const} wert={alter} onWahl={setAlter} />
          <Pills name="Umkreis" optionen={["Umkreis 1 km", "Umkreis 2 km", "Umkreis 5 km"] as const} wert={umkreis} onWahl={setUmkreis} />
          <Pills name="Vermarktung" optionen={["Miete", "Kauf"] as const} wert={art} onWahl={setArt} />
        </div>

        <div className="d-quellen">
          <span className="d-quellen-label">Datenstand Musterstadt-Nordstadt:</span>
          {datenstand.map((d) => (
            <span key={d.quelle} className="d-quelle">
              <span className="d-punkt" aria-hidden="true" />
              {d.quelle} <span className="d-leise">{d.stand}</span>
            </span>
          ))}
          <span className="d-quelle d-quelle-fehlt">
            <span className="d-punkt aus" aria-hidden="true" />
            Wohnlagenkarte <span className="d-leise">fehlt</span>
          </span>
        </div>

        <section className="d-zuletzt" aria-labelledby="d-zuletzt-titel">
          <h2 id="d-zuletzt-titel" className="d-ueber">
            Zuletzt analysiert
          </h2>
          <div className="d-zuletzt-karten">
            {zuletzt.map((p, i) => (
              <Link key={p.id} to="/entwurf/d/dashboard" className="d-karte d-projekt">
                <span className="d-projekt-titel">
                  <strong>{p.name}</strong>, {p.adresse}
                </span>
                <span className="d-leise">
                  {p.ort} · {p.datum} · {i === 0 ? <span className="d-akzent">Freigabe offen</span> : p.exporte > 0 ? `${p.exporte} Exporte` : `Merkliste (${p.merkliste})`}
                </span>
              </Link>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

// ======================================================================= Agentenleiste

/**
 * Agentenleiste: Schritte des Analyse-Laufs mit Status, Hinweis auf offene Freigabe, Tokens und Kosten;
 * „Details“ klappt eine Tabelle je Agent auf. Eingabe: keine (Beispieldaten). Ausgabe: Abschnitt.
 */
function Agentenleiste() {
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

// ======================================================================= Dashboard

/**
 * Analyse-Dashboard in drei Spalten: RIWIS links, Lage und Comps in der Mitte, VALUE, Mietansatz, Quellen und Merkliste rechts.
 * Eingabe: keine (Beispieldaten). Ausgabe: Seite.
 */
export function DashboardD() {
  const navigate = useNavigate();
  const m = useMerkliste();
  const suche = useAdressSuche(() => navigate("/entwurf/d/dashboard"), `${projekt.adresse}, ${projekt.plz} ${projekt.ort}`);
  const [zimmer, setZimmer] = useState<ZimmerFilter>("Alle");
  const [ebenen, setEbenen] = useState<Set<Ebene>>(new Set(["Comps", "Projekte"]));
  const [auswahl, setAuswahl] = useState<number | null>(null);
  const [mietansatzOffen, setMietansatzOffen] = useState(false);
  const sichtbar = comps.filter((c) => passtZimmer(c.zimmer, zimmer));
  // Stern-Zustand und Umschalter für einen Merklisten-Baustein
  const merk = (id: string, titel: string, quelle: string, art: string, folie: string) => ({
    an: m.istGemerkt(id),
    klick: () => m.umschalten({ id, titel, quelle, art, folie }),
  });
  const kennzahlenStern = merk("m2", "Einwohner, Haushalte, Kaufkraft", "RIWIS", "Kennzahlen", "Standort");
  const zeitreiheStern = merk("m1", "Angebotsmieten Neubau, Zeitreihe", "RIWIS", "Diagramm", "Mietmarkt");
  const preisStern = merk("preisklassen", "Preisklassen Neubau", "RIWIS", "Diagramm", "Mietmarkt");
  const screenStern = merk("m5", "Wohnlagenkarte", "RIWIS", "Bild", "Standort");
  const valueStern = merk("m3", "Angebotsmiete Neubau 17,40 €/m²", "VALUE", "Kennzahl", "Marktdaten");
  const quellenStern = merk("quellen", "Weitere Quellen", "Amtlich", "Liste", "Standort");

  return (
    <div className="rd">
      <Kopf />

      {/* ------------------------------------------- Suchleiste mit Filtern und Datenstand */}
      <div className="d-leiste">
        <form
          className="d-leiste-suche"
          role="search"
          onSubmit={(e) => {
            e.preventDefault();
          }}
        >
          <span className="d-suche-symbol">
            <SucheSymbol />
          </span>
          <label htmlFor="d-adresse-2" className="e-sr">
            Adresse
          </label>
          <input id="d-adresse-2" {...suche.feld} />
          {suche.zeigeListe && (
            <ul id={suche.listenId} role="listbox" className="d-vorschlaege" aria-label="Adressvorschläge">
              {suche.vorschlaege.map((v, i) => (
                <li key={v.strasse + v.plz} {...suche.option(i)}>
                  <span className="d-pin">
                    <PinSymbol />
                  </span>
                  <span className="d-vorschlag-text">
                    <strong>{v.strasse}</strong>, {v.plz} {v.ort}
                  </span>
                  <span className="d-vorschlag-ort">{v.ortsteil}</span>
                </li>
              ))}
            </ul>
          )}
        </form>
        <span className="d-chip an">Wohnen · Neubau</span>
        <span className="d-chip">
          PLZ {projekt.plz} · {projekt.ortsteil}
        </span>
        <span className="d-chip">Umkreis 2 km</span>
        <span className="d-chip">Miete</span>
        <span className="d-leiste-stand">
          Stichtag {projekt.stichtag} · RIWIS 11/2026 · VALUE Q3/2026 · IS24 04.11.2026
        </span>
      </div>

      <Agentenleiste />

      <main className="d-spalten">
        {/* =========================================== links: RIWIS */}
        <section className="d-spalte" aria-labelledby="d-riwis">
          <h2 id="d-riwis" className="d-balken">
            <span>RIWIS</span>
            <span className="d-balken-info">
              Soziodemografie · PLZ {projekt.plz}
            </span>
          </h2>

          <div className="d-karte">
            <div className="d-karte-stern">
              <EStern an={kennzahlenStern.an} name="Kennzahlen Soziodemografie" onKlick={kennzahlenStern.klick} />
            </div>
            <dl className="d-kpis">
              {soziodemografie.map((k) => (
                <div key={k.bezeichnung}>
                  <dt>{k.bezeichnung}</dt>
                  <dd className="d-kpi-zahl">
                    {k.herkunft === "abgelesen" && <span className="d-rd">rd. </span>}
                    {k.wert}
                    {k.einheit && <small>{k.einheit}</small>}
                  </dd>
                  <dd className="d-kpi-vergleich">
                    {k.vergleich}
                    {k.herkunft === "abgelesen" && <span className="d-abgelesen">abgelesen</span>}
                  </dd>
                </div>
              ))}
            </dl>
          </div>

          <div className={`d-karte${zeitreiheStern.an ? " d-karte-markiert" : ""}`}>
            <div className="d-karte-kopf">
              <h3>Neubau-Angebotsmieten</h3>
              <EStern an={zeitreiheStern.an} name="Angebotsmieten-Zeitreihe" onKlick={zeitreiheStern.klick} />
            </div>
            <Zeitreihe
              daten={zeitreihe}
              x="q"
              einheit="€/m²"
              hoehe={170}
              reihen={[
                { schluessel: "plz", name: `Ø PLZ ${projekt.plz}`, farbe: "var(--akzent)" },
                { schluessel: "stadt", name: "Ø Musterstadt", farbe: "var(--reihe-2)", strich: "5 3" },
                { schluessel: "quantil", name: "95-%-Quantil", farbe: "var(--reihe-3)", strich: "1 3" },
              ]}
            />
            <button type="button" className="d-link d-mehr">
              Alle RIWIS-Daten öffnen →
            </button>
          </div>

          <div className="d-karte">
            <div className="d-karte-kopf">
              <h3>
                Preisklassen Neubau (n = {preisklassen.reduce((s, p) => s + p.n, 0)})
              </h3>
              <EStern an={preisStern.an} name="Preisklassen" onKlick={preisStern.klick} />
            </div>
            <Saeulen daten={preisklassen} einheit="€/m²" hoehe={110} />
            <p className="d-fuss">36 % zwischen 16,50 und 18,00 €/m²</p>
          </div>

          <div className="d-karte">
            <div className="d-karte-kopf">
              <h3>Screenshot RIWIS-Marktmonitor</h3>
              <EStern an={screenStern.an} name="Screenshot Wohnlagenkarte" onKlick={screenStern.klick} />
            </div>
            <button type="button" className="d-ablage">
              <span>{screenshots[0].titel} · {screenshots[0].datum}</span>
              <span className="d-leise">Bild hierher ziehen oder auswählen</span>
            </button>
          </div>
        </section>

        {/* =========================================== Mitte: Lage & Comps */}
        <section className="d-spalte" aria-labelledby="d-lage">
          <h2 id="d-lage" className="d-balken">
            <span>Lage &amp; ImmoScout24-Comps</span>
            <span className="d-balken-info">
              {comps.length} Exposés · 2 Projekte · Stichtag {projekt.stichtag}
            </span>
          </h2>

          <div className="d-karte d-karte-bild">
            <div className="d-ebenen" role="group" aria-label="Kartenebenen">
              {EBENEN.map((e) => (
                <button
                  key={e}
                  type="button"
                  aria-pressed={ebenen.has(e)}
                  onClick={() =>
                    setEbenen((a) => {
                      const n = new Set(a);
                      if (n.has(e)) n.delete(e);
                      else n.add(e);
                      return n;
                    })
                  }
                >
                  {e === "Wohnlage" ? "Wohnlagen" : e}
                </button>
              ))}
            </div>
            <EntwurfKarte
              zentrum={{ lat: projekt.lat, lon: projekt.lon, name: projekt.name }}
              ringeKm={[1, 2]}
              comps={comps}
              weitere={kartenPunkte}
              aktiveEbenen={ebenen}
              ausgewaehlt={auswahl}
              onAuswahl={setAuswahl}
              hoehe={440}
              beschriftung
            />
          </div>

          <div id="d-freigabe">
            <FreigabeKarte verweis={{ href: "#d-comps", text: "Zur Tabelle" }} />
          </div>

          <div className="d-karte" id="d-comps">
            <div className="d-karte-kopf">
              <h3>Vergleichsangebote Neubau</h3>
              <Pills name="Zimmer" optionen={ZIMMER.map((z) => (z === "Alle" ? z : `${z} Zi.`)) as unknown as readonly string[]} wert={zimmer === "Alle" ? "Alle" : `${zimmer} Zi.`} onWahl={(w) => setZimmer((w === "Alle" ? "Alle" : w.replace(" Zi.", "")) as ZimmerFilter)} />
            </div>
            {sichtbar.length === 0 ? (
              <LeerZustand titel="Keine Comps mit dieser Zimmerzahl" text="Filter auf „Alle“ stellen oder weitere Exposés importieren." aktion="Exposés importieren" />
            ) : (
              <CompsTabelle comps={sichtbar} gemerkt={m.compsGemerkt} onStern={m.compUmschalten} ausgewaehlt={auswahl} onAuswahl={setAuswahl} ausgeschlossen={new Set([6])} />
            )}
            <div className="d-tabellen-fuss">
              <span>
                Über alle Zimmerzahlen: Ø Regelgeschoss/EG <strong>{de(zf.regelEg.eurQm)} €/m²</strong> (n = {zf.regelEg.n}) · Ø DG <strong>{de(zf.dg.eurQm)} €/m²</strong> (n = {zf.dg.n}) ·{" "}
                {de(zf.anfragenMonat, 1)} Anfragen je Monat und Inserat
              </span>
              <span className="d-leise">km: F zu Fuß · R Rad · L Luftlinie</span>
            </div>
          </div>
        </section>

        {/* =========================================== rechts: VALUE, Quellen, Merkliste */}
        <section className="d-spalte" aria-labelledby="d-value">
          <h2 id="d-value" className="d-balken">
            <span>VALUE Marktdaten</span>
            <span className="d-balken-info">Q3/2026 · Umkreis 2 km</span>
          </h2>

          <div className="d-karte">
            <div className="d-karte-stern">
              <EStern an={valueStern.an} name="Angebotsmiete Neubau" onKlick={valueStern.klick} />
            </div>
            <dl className="d-kpis d-kpis-2">
              {valueKennzahlen.map((k) => (
                <div key={k.bezeichnung}>
                  <dt>{k.bezeichnung}</dt>
                  <dd className={`d-kpi-zahl${k.wert.startsWith("+") ? " d-akzent" : ""}`}>
                    {k.wert}
                    {k.einheit && <small>{k.einheit}</small>}
                  </dd>
                </div>
              ))}
            </dl>
            <ValueTabelle />
          </div>

          <div className="d-karte">
            <div className="d-karte-kopf">
              <h3>Mietansatz</h3>
              <span className="d-akzent d-klein">Vorschlag, unbestätigt</span>
            </div>
            <p className="d-ansatz">
              17,60 <small>€/m²</small>
            </p>
            <button type="button" className="d-link" aria-expanded={mietansatzOffen} onClick={() => setMietansatzOffen((o) => !o)}>
              {mietansatzOffen ? "Herleitung schließen" : "Herleitung: Beleg → Annahme → Zahl"}
            </button>
            {mietansatzOffen && <Herleitung />}
          </div>

          <div className="d-karte">
            <div className="d-karte-kopf">
              <h3>Weitere Quellen</h3>
              <EStern an={quellenStern.an} name="Weitere Quellen" onKlick={quellenStern.klick} />
            </div>
            <ul className="d-quellenliste">
              {weitereQuellen.map((q) => (
                <li key={q.text}>
                  <span>
                    {q.text}: <strong>{q.wert}</strong>
                  </span>
                  <span className="d-leise">
                    {q.quelle} · {q.datum}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div className="d-merkliste">
            <h2 className="d-merkliste-kopf">
              Merkliste „{projekt.name}“ <span className="d-zaehler">{m.bausteine.length}</span>
            </h2>
            <Merkliste bausteine={m.bausteine} onAenderung={m.setBausteine} kuerzel={(b) => KUERZEL[b.quelle] ?? b.quelle.slice(0, 2)} />
          </div>
        </section>
      </main>
    </div>
  );
}

// ======================================================================= Zustände

/** Übersicht der Lade-, Leer-, Fehler- und Teildaten-Zustände. Eingabe: keine. Ausgabe: Seite. */
export function ZustaendeD() {
  return (
    <div className="rd">
      <Kopf />
      <main className="d-zustaende">
        <h1 className="d-start-titel d-klein-titel">Zustände</h1>
        <div className="d-zustand-raster">
          {[
            ["Karte lädt", <EntwurfKarte key="l" zentrum={{ lat: projekt.lat, lon: projekt.lon, name: "" }} ringeKm={[2]} comps={[]} weitere={LEER} aktiveEbenen={new Set()} ausgewaehlt={null} onAuswahl={() => {}} zustand="laden" hoehe={200} />],
            ["Karte nicht erreichbar", <EntwurfKarte key="f" zentrum={{ lat: projekt.lat, lon: projekt.lon, name: "" }} ringeKm={[2]} comps={[]} weitere={LEER} aktiveEbenen={new Set()} ausgewaehlt={null} onAuswahl={() => {}} zustand="fehler" hoehe={200} />],
            ["Noch keine Exposés", <LeerZustand key="e" titel="Noch keine Vergleichsangebote" text="IS24-Exposés als PDF ablegen. Der Exposé-Agent liest sie und legt die Comps zur Freigabe vor." aktion="Exposés importieren" />],
            ["Kennzahlen werden berechnet", <LadeZeilen key="z" zeilen={5} />],
            ["Teildaten", <LeerZustand key="t" titel="RIWIS fehlt für PLZ 12345" text="VALUE und Comps sind vollständig. Die linke Spalte bleibt leer, bis ein Screenshot importiert ist." aktion="Screenshot ablegen" />],
            ["Agent gestoppt", <FehlerZustand key="a" titel="Screenshot-Agent: Anfragelimit erreicht" text="Die Anthropic-API meldet zu viele Anfragen. Der Lauf ist gesichert und setzt an dieser Stelle fort." aktion="In 30 s fortsetzen" />],
          ].map(([titel, inhalt]) => (
            <figure key={titel as string} className="d-karte">
              <figcaption className="d-karte-kopf">
                <h3>{titel}</h3>
              </figcaption>
              {inhalt}
            </figure>
          ))}
        </div>
      </main>
    </div>
  );
}
