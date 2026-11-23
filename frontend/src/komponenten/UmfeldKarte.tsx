// Umfeld-Karte im Dashboard: nächste Haltestellen, Supermärkte, Schulen, Kitas und Ärzte mit Wegezeiten aus OSM.
import type { Ladezustand, Umfeld, UmfeldPoi, Wert } from "../api";
import { de } from "../format";
import { FehlerZustand, herkunftText, LadeZeilen, LeerZustand } from "./Bausteine";

/** Wegezeit oder Luftlinien-Hinweis. Eingabe: Wert und Methode. Ausgabe: Zelle mit Rechenweg als Tooltip. */
function Zeit({ wert, methode, luftlinie }: { wert: Wert | null; methode: UmfeldPoi["methode_fuss"]; luftlinie: Wert }) {
  // Ohne Routing keine erfundene Minutenangabe, sondern die gerechnete Luftlinie mit Kennzeichnung
  if (methode === "Luftlinie" || !wert) {
    return <td className="z d-leise" title={`Routing nicht erreichbar · ${luftlinie.rechenweg_text}`}>Luftlinie</td>;
  }
  return (
    <td className="z" title={herkunftText(wert)}>
      {de(wert.wert, 0)} min
    </td>
  );
}

/**
 * Umfeld-Tabelle mit Lade-, Leer- und Fehlerzustand.
 * Eingabe: Ladezustand der Umfeld-Abfrage, Funktion zum erneuten Laden. Ausgabe: Karte.
 */
export function UmfeldKarte({ umfeld, nochmal }: { umfeld: Ladezustand<Umfeld>; nochmal: () => void }) {
  return (
    <div className="d-karte" id="d-umfeld">
      <div className="d-karte-kopf">
        <h3>Umfeld</h3>
        <span className="d-leise d-klein">{umfeld.status === "bereit" ? `Umkreis ${de(umfeld.daten.radius_m, 0)} m` : ""}</span>
      </div>
      {umfeld.status === "laden" && <LadeZeilen zeilen={4} />}
      {umfeld.status === "fehler" && (
        <FehlerZustand
          titel={umfeld.http === 503 ? "Dienst nicht erreichbar" : "Umfeld konnte nicht geladen werden"}
          text={umfeld.http === 503 ? "Overpass (OpenStreetMap) antwortet gerade nicht. Die übrigen Daten bleiben nutzbar." : umfeld.meldung}
          onAktion={nochmal}
        />
      )}
      {umfeld.status === "bereit" && umfeld.daten.pois.length === 0 && (
        <LeerZustand titel="Nichts im Umkreis gefunden" text="Im Umkreis von 1 km sind in OpenStreetMap keine Haltestellen, Supermärkte, Schulen, Kitas oder Ärzte eingetragen." />
      )}
      {umfeld.status === "bereit" && umfeld.daten.pois.length > 0 && (
        <>
          <div className="e-tabelle-scroll"><table className="e-tabelle e-umfeld">
            <thead>
              <tr>
                <th scope="col">Kategorie</th>
                <th scope="col">Name</th>
                <th className="z" scope="col">Luftlinie</th>
                <th className="z" scope="col">zu Fuß</th>
                <th className="z" scope="col">Rad</th>
              </tr>
            </thead>
            <tbody>
              {umfeld.daten.pois.map((p) => (
                <tr key={`${p.kategorie}-${p.name}-${p.lat}`}>
                  <td>{p.kategorie}</td>
                  <td className="d-umbruch">{p.name}</td>
                  <td className="z" title={herkunftText(p.luftlinie)}>
                    {de((p.luftlinie.wert ?? 0) * 1000, 0)} m
                  </td>
                  <Zeit wert={p.zu_fuss} methode={p.methode_fuss} luftlinie={p.luftlinie} />
                  <Zeit wert={p.rad} methode={p.methode_rad} luftlinie={p.luftlinie} />
                </tr>
              ))}
            </tbody>
          </table></div>
          <p className="d-fuss">Daten {umfeld.daten.attribution} · Wegezeiten: OSRM (routing.openstreetmap.de)</p>
        </>
      )}
    </div>
  );
}
