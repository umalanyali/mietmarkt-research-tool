// Zustandsübersicht: zeigt, wie Karte, Tabellen und Agenten bei Laden, Leere, Fehler und Teildaten aussehen.
import { Karte } from "../komponenten/Karte";
import { FehlerZustand, LadeZeilen, LeerZustand } from "../komponenten/Bausteine";
import { Kopf } from "../komponenten/Gestell";

// Leere Kartenebenen für die Zustandsübersicht; die Karte selbst wird bei erzwungenem Zustand nicht geladen
const LEER = { projekte: [], oepnv: [], nahversorgung: [] };
const ORT = { lat: 0, lon: 0, name: "" };

/** Übersicht der Lade-, Leer-, Fehler- und Teildaten-Zustände. Eingabe: keine. Ausgabe: Seite. */
export function Zustaende() {
  return (
    <div className="app">
      <Kopf />
      <main className="d-zustaende">
        <h1 className="d-start-titel d-klein-titel">Zustände</h1>
        <div className="d-zustand-raster">
          {[
            ["Karte lädt", <Karte key="l" zentrum={ORT} ringeKm={[2]} comps={[]} weitere={LEER} aktiveEbenen={new Set()} ausgewaehlt={null} onAuswahl={() => {}} zustand="laden" hoehe={200} />],
            ["Karte nicht erreichbar", <Karte key="f" zentrum={ORT} ringeKm={[2]} comps={[]} weitere={LEER} aktiveEbenen={new Set()} ausgewaehlt={null} onAuswahl={() => {}} zustand="fehler" hoehe={200} />],
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
