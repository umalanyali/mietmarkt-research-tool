// Analyse-Dashboard in drei Spalten (Aufbau nach Mockup): Marktbericht links, Lage und Comps in der Mitte, Angebotsstatistik, Mietansatz,
// weitere Quellen und Merkliste rechts. Ohne Logo und Firmenname; Akzent Oliv (CLAUDE.md Regel 5).
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { datum, useApi, type Comp, type Kennzahlen, type LaufInfo, type Marktkennzahl, type Projekt, type ProjektDetail, type Umfeld } from "../api";
import { bauprojekte, screenshots } from "../daten/platzhalter";
import { de } from "../format";
import { Merkliste } from "../komponenten/Merkliste";
import { Saeulen, Zeitreihe } from "../komponenten/Diagramme";
import { SucheSymbol } from "../komponenten/Symbole";
import { Karte, EBENEN, type Ebene } from "../komponenten/Karte";
import { Agentenleiste } from "../komponenten/Agentenleiste";
import { UmfeldKarte } from "../komponenten/UmfeldKarte";
import { Kopf, Pills, Vorschlagsliste } from "../komponenten/Gestell";
import { CompsTabelle, EStern, FehlerZustand, FreigabeKarte, Herleitung, LadeZeilen, LeerZustand, AngebotTabelle } from "../komponenten/Bausteine";
import { HerkunftMarke } from "../komponenten/Herkunft";
import { Unterlagen } from "../komponenten/Unterlagen";
import { useLauf } from "../lauf";
import { useAdressSuche, useMerkliste, useProjektAnlage, passtZimmer, ZIMMER, type ZimmerFilter } from "../hooks";

// Quellenkürzel in der Merkliste
const KUERZEL: Record<string, string> = { Marktbericht: "M", Angebotsstatistik: "A", Portal: "P" };

// Farben und Strichmuster der Zeitreihen in Reihenfolge der Reihen (zweite Kodierung neben der Farbe)
const REIHEN_STIL = [
  { farbe: "var(--akzent)" },
  { farbe: "var(--reihe-2)", strich: "5 3" },
  { farbe: "var(--reihe-3)", strich: "1 3" },
];

/** Zahl einer Kennzahl mit ihren Nachkommastellen. Eingabe: Kennzahl. Ausgabe: Text, „–“ ohne Wert. */
function zahl(k: Marktkennzahl | undefined): string {
  return de(k?.wert, k?.stellen ?? 0);
}

/** Kennzahlen einer Gruppe. Eingabe: alle Kennzahlen, Gruppe. Ausgabe: gefilterte Liste in Original-Reihenfolge. */
function gruppe(alle: Marktkennzahl[], name: Marktkennzahl["gruppe"]): Marktkennzahl[] {
  return alle.filter((k) => k.gruppe === name);
}

/**
 * Analyse-Seite: lädt Projekt, Comps und Kennzahlen über die API und zeigt Lade- bzw. Fehlerzustand.
 * Eingabe: Projekt-ID aus der Adresse (/analyse/:id). Ausgabe: Seite.
 */
export function Analyse() {
  const { id } = useParams();
  const [projekt, p1] = useApi<ProjektDetail>(`/api/projekte/${id}`);
  const [comps, p2] = useApi<Comp[]>(`/api/projekte/${id}/comps`);
  const [kennzahlen, p3] = useApi<Kennzahlen>(`/api/projekte/${id}/kennzahlen`);
  const zustaende = [projekt, comps, kennzahlen];
  const fehler = zustaende.find((z) => z.status === "fehler");
  if (projekt.status === "bereit" && comps.status === "bereit" && kennzahlen.status === "bereit") {
    // key: bei Projektwechsel den Seitenzustand (Merkliste, Auswahl, Filter) neu aufsetzen
    return <AnalyseInhalt key={id} projekt={projekt.daten} comps={comps.daten} kennzahlen={kennzahlen.daten} />;
  }
  return (
    <div className="app">
      <Kopf />
      <main className="d-zustaende">
        {fehler?.status === "fehler" && fehler.meldung === "Nicht gefunden" ? (
          <LeerZustand titel={`Projekt ${id} gibt es nicht`} text="Auf der Startseite ein vorhandenes Projekt wählen oder eine neue Adresse suchen." />
        ) : fehler?.status === "fehler" ? (
          <FehlerZustand
            titel="Analyse konnte nicht geladen werden"
            text={`${fehler.meldung}. Läuft der Server auf Port 8000, und ist der Demo-Datensatz geladen?`}
            onAktion={() => [p1, p2, p3].forEach((f) => f())}
          />
        ) : (
          <LadeZeilen zeilen={6} />
        )}
      </main>
    </div>
  );
}

/**
 * Dashboard in drei Spalten: Marktbericht links, Lage und Comps in der Mitte, Angebotsstatistik, Mietansatz, Quellen und Merkliste rechts.
 * Eingabe: geladene API-Daten. Ausgabe: Seite.
 */
function AnalyseInhalt({ projekt, comps, kennzahlen }: { projekt: ProjektDetail; comps: Comp[]; kennzahlen: Kennzahlen }) {
  // Merkliste, Screenshot und Bauprojekte sind noch Platzhalter mit Lindenquartier-Beispielen;
  // bei einem Projekt ohne Comps wären sie irreführend und bleiben weg
  const mitPlatzhaltern = comps.length > 0;
  const m = useMerkliste(comps.filter((c) => c.gemerkt).map((c) => c.nr), mitPlatzhaltern);
  const anlage = useProjektAnlage();
  const suche = useAdressSuche(anlage.anlegen, `${projekt.adresse}, ${projekt.plz} ${projekt.ort}`);
  const [umfeld, umfeldNochmal] = useApi<Umfeld>(`/api/projekte/${projekt.id}/umfeld`);
  // Ohne Comps und Kennzahlen gibt es hier keine Marktdaten; dann nur der echte Standortteil plus ehrlicher Hinweis
  const keineMarktdaten = comps.length === 0 && kennzahlen.kennzahlen.length === 0;
  const [alleProjekte] = useApi<Projekt[]>(keineMarktdaten ? "/api/projekte" : null);
  const demo = alleProjekte.status === "bereit" ? alleProjekte.daten.find((p) => p.demo && p.id !== projekt.id) : undefined;
  // Stabile Referenz, damit die Karte ihre Punkt-Ebenen nur bei neuen Daten neu setzt
  const weitere = useMemo(() => {
    const pois = umfeld.status === "bereit" ? umfeld.daten.pois : [];
    const punkte = (kategorie: string) => pois.filter((p) => p.kategorie === kategorie).map(({ name, lat, lon }) => ({ name, lat, lon }));
    return { projekte: mitPlatzhaltern ? bauprojekte : [], oepnv: punkte("ÖPNV"), nahversorgung: punkte("Supermarkt") };
  }, [umfeld, mitPlatzhaltern]);
  const zf = kennzahlen.comps;
  const k = kennzahlen.kennzahlen;
  const quelle = (id: number | null) => kennzahlen.quellen.find((q) => q.id === id);
  const dateiQuellen = projekt.quellen.filter((q) => q.art === "datei");
  const angebotQuelle = projekt.quellen.find((q) => q.name === "Angebotsstatistik");
  // Soziodemografie: Wert im Ortsteil, darunter der Vergleichswert der Stadt
  const sozio = gruppe(k, "soziodemografie").filter((x) => x.gebiet !== "Stadt");
  const stadt = (bez: string) => gruppe(k, "soziodemografie").find((x) => x.gebiet === "Stadt" && x.bezeichnung === bez);
  // Zeitreihe: aus einer Zeile je (Reihe, Quartal) eine Zeile je Quartal mit einer Spalte je Reihe
  const reihenNamen = [...new Set(gruppe(k, "zeitreihe").map((x) => x.bezeichnung))];
  const quartale = [...new Set(gruppe(k, "zeitreihe").map((x) => x.kategorie))];
  const zeitreihe = quartale.map((q) => ({
    q,
    ...Object.fromEntries(reihenNamen.map((r, i) => [`r${i}`, gruppe(k, "zeitreihe").find((x) => x.kategorie === q && x.bezeichnung === r)?.wert ?? 0])),
  }));
  const preisklassen = gruppe(k, "preisklassen").map((x) => ({ klasse: x.kategorie, n: x.wert ?? 0 }));
  const pk = kennzahlen.preisklassen;
  const [zimmer, setZimmer] = useState<ZimmerFilter>("Alle");
  // Echte Adressen zeigen gleich das OSM-Umfeld; Demo-Projekte die (Platzhalter-)Bauprojekte
  const [ebenen, setEbenen] = useState<Set<Ebene>>(
    new Set(projekt.demo ? ["Comps", "Projekte"] : ["Comps", "ÖPNV", "Nahversorgung"]),
  );
  const [auswahl, setAuswahl] = useState<number | null>(null);
  const [mietansatzOffen, setMietansatzOffen] = useState(false);
  const [laeufe, laeufeNeu] = useApi<LaufInfo[]>(`/api/projekte/${projekt.id}/laeufe`);
  const [gesundheit] = useApi<{ ki: boolean }>("/api/gesundheit");
  const lauf = useLauf(projekt.id, laeufeNeu);
  const offen = lauf.zustand.offen;
  // Mietansatz: freigegeben aus dem Lauf, sonst der offene Vorschlag (unbestätigt)
  const ansatz = lauf.zustand.herleitungen ?? (offen?.art === "mietansatz" ? offen.vorschlag.herleitungen : null);
  const haupt = ansatz?.regel_eg;
  const sichtbar = comps.filter((c) => passtZimmer(c.zimmer, zimmer));
  // Stern-Zustand und Umschalter für einen Merklisten-Baustein
  const merk = (id: string, titel: string, quelle: string, art: string, folie: string) => ({
    an: m.istGemerkt(id),
    klick: () => m.umschalten({ id, titel, quelle, art, folie }),
  });
  const kennzahlenStern = merk("m2", "Einwohner, Haushalte, Kaufkraft", "Marktbericht", "Kennzahlen", "Standort");
  const zeitreiheStern = merk("m1", "Angebotsmieten Neubau, Zeitreihe", "Marktbericht", "Diagramm", "Mietmarkt");
  const preisStern = merk("preisklassen", "Preisklassen Neubau", "Marktbericht", "Diagramm", "Mietmarkt");
  const screenStern = merk("m5", "Wohnlagenkarte", "Marktbericht", "Bild", "Standort");
  const angebotStern = merk("m3", "Angebotsmiete Neubau 17,40 €/m²", "Angebotsstatistik", "Kennzahl", "Marktdaten");
  const quellenStern = merk("quellen", "Weitere Quellen", "Amtlich", "Liste", "Standort");

  const kartenblock = (
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
      <Karte
        zentrum={{ lat: projekt.lat, lon: projekt.lon, name: projekt.name }}
        ringeKm={[1, 2]}
        comps={comps}
        weitere={weitere}
        aktiveEbenen={ebenen}
        ausgewaehlt={auswahl}
        onAuswahl={setAuswahl}
        hoehe={440}
        beschriftung
      />
    </div>
  );

  return (
    <div className="app">
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
          <Vorschlagsliste suche={suche} />
        </form>
        <span className="d-chip an">Wohnen · Neubau</span>
        <span className="d-chip">
          PLZ {projekt.plz} · {projekt.ortsteil}
        </span>
        <span className="d-chip">Umkreis 2 km</span>
        <span className="d-chip">Miete</span>
        <span className="d-leiste-stand">
          Stichtag {datum(projekt.stichtag)}
          {dateiQuellen.map((q) => ` · ${q.name} ${q.stand}`).join("")}
        </span>
      </div>

      <Agentenleiste lauf={lauf} laeufe={laeufe} ki={gesundheit.status === "bereit" ? gesundheit.daten.ki : null} />

      {anlage.status !== "ruhig" && anlage.status !== "laden" && (
        <div className="d-hinweis-leiste" role="alert">
          {anlage.status === "nicht-erreichbar" ? "Geokodierung (Nominatim) nicht erreichbar – Projekt nicht angelegt." : "Projekt konnte nicht angelegt werden."}
        </div>
      )}

      {keineMarktdaten ? (
        <main className="d-ohne-daten">
          <section className="d-karte d-banner" aria-labelledby="d-keine-daten">
            <h2 id="d-keine-daten">Für diesen Standort sind keine Marktdaten importiert.</h2>
            <p className="d-leise">
              Lage und Umfeld kommen live aus OpenStreetMap. Comps, Marktbericht- und Angebotswerte erscheinen, sobald Daten im Umkreis von{" "}
              {de(projekt.umkreis_km, 0)} km importiert sind.
            </p>
            <p className="d-banner-aktionen">
              <button type="button" className="e-knopf" disabled title="Der Import-Dialog folgt im nächsten Schritt">
                Daten importieren
              </button>
              {demo && (
                <Link to={`/analyse/${demo.id}`} className="d-link">
                  Demo-Standort öffnen
                </Link>
              )}
            </p>
          </section>
          <section className="d-spalte" aria-label="Lage">
            {kartenblock}
          </section>
          <section className="d-spalte" aria-label="Umfeld">
            <UmfeldKarte umfeld={umfeld} nochmal={umfeldNochmal} />
            <Unterlagen projektId={projekt.id} />
          </section>
        </main>
      ) : (
        <main className="d-spalten">
          {/* =========================================== links: Marktbericht */}
          <section className="d-spalte" aria-labelledby="d-markt">
            <h2 id="d-markt" className="d-balken">
              <span>Marktbericht</span>
              <span className="d-balken-info">
                Soziodemografie · PLZ {projekt.plz}
              </span>
            </h2>

            <div className="d-karte">
              <div className="d-karte-stern">
                <EStern an={kennzahlenStern.an} name="Kennzahlen Soziodemografie" onKlick={kennzahlenStern.klick} />
              </div>
              {sozio.length === 0 && <LeerZustand titel="Keine Soziodemografie" text="Marktbericht-Screenshot importieren, um Einwohner, Haushalte und Kaufkraft zu sehen." />}
              <dl className="d-kpis">
                {sozio.map((x) => (
                  <div key={x.id}>
                    <dt>{x.bezeichnung}</dt>
                    <dd className="d-kpi-zahl">
                      {x.herkunft === "abgelesen" && <span className="d-rd">rd. </span>}
                      {zahl(x)}
                      {x.einheit && <small>{x.einheit}</small>} <HerkunftMarke wert={x} quelle={quelle(x.quelle_id)} />
                    </dd>
                    <dd className="d-kpi-vergleich">
                      Stadt {zahl(stadt(x.bezeichnung))}
                      {x.einheit && ` ${x.einheit}`}
                      {x.herkunft === "abgelesen" && <span className="d-abgelesen">abgelesen</span>}
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
              {zeitreihe.length === 0 ? (
                <LeerZustand titel="Keine Zeitreihe" text="Angebotsmieten erscheinen nach dem Import des Marktberichts." />
              ) : (
                <Zeitreihe
                  daten={zeitreihe}
                  x="q"
                  einheit="€/m²"
                  hoehe={170}
                  reihen={reihenNamen.map((name, i) => ({ schluessel: `r${i}`, name, ...REIHEN_STIL[i % REIHEN_STIL.length] }))}
                />
              )}
              <button type="button" className="d-link d-mehr">
                Alle Marktbericht-Daten öffnen →
              </button>
            </div>

            <div className="d-karte">
              <div className="d-karte-kopf">
                <h3>
                  Preisklassen Neubau (n = {de(pk.summe.wert, 0)})
                </h3>
                <EStern an={preisStern.an} name="Preisklassen" onKlick={preisStern.klick} />
              </div>
              {preisklassen.length === 0 ? (
                <LeerZustand titel="Keine Preisklassen" text="Die Verteilung erscheint nach dem Import des Marktberichts." />
              ) : (
                <Saeulen daten={preisklassen} einheit="€/m²" hoehe={110} />
              )}
              {pk.staerkste && (
                <p className="d-fuss">
                  {de(pk.anteil.wert, 0)} % zwischen {pk.staerkste.replace("–", " und ")} €/m² <HerkunftMarke wert={pk.anteil} />
                </p>
              )}
            </div>

            <div className="d-karte">
              <div className="d-karte-kopf">
                <h3>Screenshot Marktbericht</h3>
                <EStern an={screenStern.an} name="Screenshot Wohnlagenkarte" onKlick={screenStern.klick} />
              </div>
              <button type="button" className="d-ablage">
                {mitPlatzhaltern && (
                  <span>
                    {screenshots[0].titel} · {screenshots[0].datum}
                  </span>
                )}
                <span className="d-leise">Bild hierher ziehen oder auswählen</span>
              </button>
            </div>
          </section>

          {/* =========================================== Mitte: Lage & Comps */}
          <section className="d-spalte" aria-labelledby="d-lage">
            <h2 id="d-lage" className="d-balken">
              <span>Lage &amp; Comps</span>
              <span className="d-balken-info">
                {comps.length} Exposés · {weitere.projekte.length} Projekte · Stichtag {datum(projekt.stichtag)}
              </span>
            </h2>

            {kartenblock}
            <UmfeldKarte umfeld={umfeld} nochmal={umfeldNochmal} />

            {offen?.art === "mietansatz" && (
              <div id="d-freigabe">
                <FreigabeKarte key={lauf.laufId} vorschlag={offen.vorschlag} onSenden={lauf.freigeben} sendet={lauf.aktiv} />
              </div>
            )}

            <div className="d-karte" id="d-comps">
              <div className="d-karte-kopf">
                <h3>Vergleichsangebote Neubau</h3>
                <Pills name="Zimmer" optionen={ZIMMER.map((z) => (z === "Alle" ? z : `${z} Zi.`)) as unknown as readonly string[]} wert={zimmer === "Alle" ? "Alle" : `${zimmer} Zi.`} onWahl={(w) => setZimmer((w === "Alle" ? "Alle" : w.replace(" Zi.", "")) as ZimmerFilter)} />
              </div>
              {comps.length === 0 ? (
                <LeerZustand titel="Noch keine Vergleichsangebote" text="Portal-Exposés oder eine Comps-Datei (CSV/XLSX) importieren." aktion="Comps importieren" />
              ) : sichtbar.length === 0 ? (
                <LeerZustand titel="Keine Comps mit dieser Zimmerzahl" text="Filter auf „Alle“ stellen oder weitere Exposés importieren." aktion="Exposés importieren" />
              ) : (
                <CompsTabelle comps={sichtbar} gemerkt={m.compsGemerkt} onStern={m.compUmschalten} ausgewaehlt={auswahl} onAuswahl={setAuswahl} />
              )}
              {comps.length > 0 && (
                <div className="d-tabellen-fuss">
                  <span>
                    Über alle Zimmerzahlen: Ø Regelgeschoss/EG{" "}
                    <strong>{de(zf.regel_eg.wert)} €/m²</strong> <HerkunftMarke wert={zf.regel_eg} /> (n = {de(zf.regel_eg_n.wert, 0)}) · Ø DG{" "}
                    <strong>{de(zf.dg.wert)} €/m²</strong> <HerkunftMarke wert={zf.dg} /> (n = {de(zf.dg_n.wert, 0)}) ·{" "}
                    {de(zf.anfragen_monat.wert, 1)} <HerkunftMarke wert={zf.anfragen_monat} /> Anfragen je Monat und Inserat
                  </span>
                  <span className="d-leise">km: L = Luftlinie (Wegezeiten folgen mit M4)</span>
                </div>
              )}
            </div>
          </section>

          {/* =========================================== rechts: Angebotsstatistik, Quellen, Merkliste */}
          <section className="d-spalte" aria-labelledby="d-angebot">
            <h2 id="d-angebot" className="d-balken">
              <span>Angebotsstatistik</span>
              <span className="d-balken-info">
                {angebotQuelle ? angebotQuelle.stand : "kein Import"} · Umkreis {de(projekt.umkreis_km, 0)} km
              </span>
            </h2>

            <div className="d-karte">
              <div className="d-karte-stern">
                <EStern an={angebotStern.an} name="Angebotsmiete Neubau" onKlick={angebotStern.klick} />
              </div>
              {gruppe(k, "angebot").length === 0 && <LeerZustand titel="Keine Angebotsdaten" text="Angebotsstatistik-Export (CSV/XLSX) importieren." />}
              <dl className="d-kpis d-kpis-2">
                {gruppe(k, "angebot").map((x) => {
                  // Veränderungen in % mit Vorzeichen und Akzent, damit die Richtung sofort lesbar ist
                  const veraenderung = x.einheit === "%" && (x.wert ?? 0) > 0;
                  return (
                    <div key={x.id}>
                      <dt>{x.bezeichnung}</dt>
                      <dd className={`d-kpi-zahl${veraenderung ? " d-akzent" : ""}`}>
                        {veraenderung && "+"}
                        {zahl(x)}
                        {x.einheit && <small>{x.einheit}</small>} <HerkunftMarke wert={x} quelle={quelle(x.quelle_id)} />
                      </dd>
                    </div>
                  );
                })}
              </dl>
              {gruppe(k, "angebot_tabelle").length > 0 && <AngebotTabelle werte={gruppe(k, "angebot_tabelle")} />}
            </div>

            <div className="d-karte">
              <div className="d-karte-kopf">
                <h3>Mietansatz</h3>
                {haupt && <span className="d-akzent d-klein">{lauf.zustand.herleitungen ? "freigegeben" : "Vorschlag, unbestätigt"}</span>}
              </div>
              {!ansatz || !haupt ? (
                <LeerZustand titel="Noch kein Mietansatz" text="Analyse starten: der Mietansatz-Agent leitet ihn aus den Comps her und legt ihn dir zur Freigabe vor." />
              ) : (
                <>
                  <p className="d-ansatz">
                    {de(haupt.ergebnis.wert)} <small>€/m²</small> <HerkunftMarke wert={haupt.ergebnis} />
                  </p>
                  {haupt.fortgeschrieben && (
                    <p className="d-leise d-klein">
                      bei Vermarktungsstart {de(haupt.fortgeschrieben.wert)} €/m² <HerkunftMarke wert={haupt.fortgeschrieben} />
                    </p>
                  )}
                  <button type="button" className="d-link" aria-expanded={mietansatzOffen} onClick={() => setMietansatzOffen((o) => !o)}>
                    {mietansatzOffen ? "Herleitung schließen" : "Herleitung: Basis → Zu-/Abschläge → Ergebnis"}
                  </button>
                  {mietansatzOffen && <Herleitung herleitungen={ansatz} />}
                </>
              )}
            </div>

            <Unterlagen projektId={projekt.id} />

            <div className="d-karte">
              <div className="d-karte-kopf">
                <h3>Weitere Quellen</h3>
                <EStern an={quellenStern.an} name="Weitere Quellen" onKlick={quellenStern.klick} />
              </div>
              {gruppe(k, "weitere").length === 0 && <p className="d-leise">Noch keine amtlichen Werte erfasst.</p>}
              <ul className="d-quellenliste">
                {gruppe(k, "weitere").map((x) => (
                  <li key={x.id}>
                    <span>
                      {x.bezeichnung}: <strong>{zahl(x)}{x.einheit && ` ${x.einheit}`}</strong> <HerkunftMarke wert={x} quelle={quelle(x.quelle_id)} />
                    </span>
                    <span className="d-leise">
                      {quelle(x.quelle_id)?.name} · {quelle(x.quelle_id)?.stand}
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
      )}
    </div>
  );
}

