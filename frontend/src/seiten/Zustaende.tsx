// Zustandsübersicht: zeigt, wie Karte, Tabellen und Agenten bei Laden, Leere, Fehler und Teildaten aussehen,
// dazu Freigabe- und Ergebniskarte aus einem aufgezeichneten Fake-Lauf (für Responsive-Prüfung und Screenshots).
import { useEffect, useState } from "react";
import { Karte } from "../komponenten/Karte";
import { FehlerZustand, FreigabeKarte, LadeZeilen, LeerZustand } from "../komponenten/Bausteine";
import { Ergebniskarte } from "../komponenten/Ergebniskarte";
import { Kopf } from "../komponenten/Gestell";
import { LEER as LAUF_LEER, verarbeite, type Ereignis, type LaufZustand } from "../lauf";

// Begründung, wie der Mietansatz-Agent sie oft schreibt: fett und mit Tabelle (Markdown)
const BEGRUENDUNG = "**Vorschlag:** Basis aus den Regelgeschoss-Comps, Zuschlag für den besseren Energiestandard.\n\n" +
  "| Basis | Comps | Median €/m² | Zu-/Abschlag | Ansatz €/m² | Fortgeschrieben €/m² |\n|---|---|---|---|---|---|\n" +
  "| Regelgeschoss/EG | 12 | 16,96 | +0,30 | 17,26 | 17,55 |\n| Dachgeschoss | 4 | 17,80 | 0,00 | 17,80 | 18,10 |";

// Leere Kartenebenen für die Zustandsübersicht; die Karte selbst wird bei erzwungenem Zustand nicht geladen
const LEER = { projekte: [], oepnv: [], nahversorgung: [] };
const ORT = { lat: 0, lon: 0, name: "" };

/** Übersicht der Lade-, Leer-, Fehler- und Teildaten-Zustände. Eingabe: keine. Ausgabe: Seite. */
export function Zustaende() {
  // Aufzeichnung erst bei Bedarf laden: 60 KB, die das Haupt-Bundle nicht braucht
  const [lauf, setLauf] = useState<{ vorschlag: Ereignis["vorschlag"]; ende: LaufZustand } | null>(null);
  useEffect(() => {
    import("../test/aufzeichnung.json").then(({ default: a }) => {
      const bis = a.bis_freigabe as Ereignis[];
      setLauf({ vorschlag: { ...bis.at(-1)!.vorschlag, begruendung: BEGRUENDUNG },
                ende: [...bis, ...(a.nach_freigabe as Ereignis[])].reduce((z, e) => verarbeite(z, e, 0), LAUF_LEER) });
    });
  }, []);
  return (
    <div className="app">
      <Kopf />
      <main className="d-zustaende">
        <h1 className="d-start-titel d-klein-titel">Zustände</h1>
        <div className="d-zustand-raster">
          {[
            ["Karte lädt", <Karte key="l" zentrum={ORT} ringeKm={[2]} comps={[]} weitere={LEER} aktiveEbenen={new Set()} ausgewaehlt={null} onAuswahl={() => {}} zustand="laden" hoehe={200} />],
            ["Karte nicht erreichbar", <Karte key="f" zentrum={ORT} ringeKm={[2]} comps={[]} weitere={LEER} aktiveEbenen={new Set()} ausgewaehlt={null} onAuswahl={() => {}} zustand="fehler" hoehe={200} />],
            ["Noch keine Exposés", <LeerZustand key="e" titel="Noch keine Vergleichsangebote" text="Portal-Exposés als PDF ablegen. Der Exposé-Agent liest sie und legt die Comps zur Freigabe vor." aktion="Exposés importieren" />],
            ["Kennzahlen werden berechnet", <LadeZeilen key="z" zeilen={5} />],
            ["Teildaten", <LeerZustand key="t" titel="Marktbericht fehlt für PLZ 12345" text="Angebotsstatistik und Comps sind vollständig. Die linke Spalte bleibt leer, bis ein Screenshot importiert ist." aktion="Screenshot ablegen" />],
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
        {lauf && (
          <div className="d-zustand-lauf">
            <FreigabeKarte vorschlag={lauf.vorschlag} onSenden={() => {}} sendet={false} />
            <Ergebniskarte laufId="beispiel" zustand={lauf.ende} />
          </div>
        )}
      </main>
    </div>
  );
}
