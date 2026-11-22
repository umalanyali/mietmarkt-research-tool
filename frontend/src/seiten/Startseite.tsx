// Startseite: Adresssuche, Filter, Datenstand je Quelle und zuletzt analysierte Projekte.
import { useState } from "react";
import { Link } from "react-router-dom";
import { datum, useApi, type Projekt, type ProjektDetail } from "../api";
import { FehlerZustand, LadeZeilen } from "../komponenten/Bausteine";
import { SucheSymbol } from "../komponenten/Symbole";
import { Kopf, Pills, Vorschlagsliste } from "../komponenten/Gestell";
import { useAdressSuche, useProjektAnlage } from "../hooks";

/** Startseite: Adresssuche, Filter, Datenstand je Quelle, zuletzt analysierte Projekte. Eingabe: keine. Ausgabe: Seite. */
export function Startseite() {
  const [liste, nochmal] = useApi<Projekt[]>("/api/projekte");
  const projekte = liste.status === "bereit" ? liste.daten : [];
  // Datenstand zeigt das zuletzt analysierte Projekt (die API liefert die neuesten zuerst)
  const [detail] = useApi<ProjektDetail>(projekte[0] ? `/api/projekte/${projekte[0].id}` : null);
  const anlage = useProjektAnlage();
  const suche = useAdressSuche(anlage.anlegen);
  const [nutzung, setNutzung] = useState<"Wohnen" | "Gewerbe">("Wohnen");
  const [alter, setAlter] = useState<"Neubau" | "Bestand">("Neubau");
  const [umkreis, setUmkreis] = useState<"Umkreis 1 km" | "Umkreis 2 km" | "Umkreis 5 km">("Umkreis 2 km");
  const [art, setArt] = useState<"Miete" | "Kauf">("Miete");

  return (
    <div className="app">
      <Kopf />
      <main className="d-start">
        <h1 className="d-start-titel">Mietmarkt Research</h1>
        <p className="d-start-unter">Eine Adresse – alle importierten Marktdaten aus RIWIS, VALUE, ImmoScout24 und amtlichen Quellen</p>

        <form
          className="d-suche"
          role="search"
          onSubmit={(e) => {
            e.preventDefault();
            // „Analyse starten“ ohne Auswahl nimmt den ersten Vorschlag
            if (suche.vorschlaege[0]) suche.waehlen(suche.vorschlaege[0]);
          }}
        >
          <span className="d-suche-symbol">
            <SucheSymbol />
          </span>
          <label htmlFor="d-adresse" className="e-sr">
            Adresse
          </label>
          <input id="d-adresse" placeholder="Adresse eingeben, z. B. Lindenallee 30, Musterstadt" {...suche.feld} />
          <button type="submit" className="d-knopf-gross" disabled={anlage.status === "laden"}>
            {anlage.status === "laden" ? "Wird angelegt …" : "Analyse starten"}
          </button>
          <Vorschlagsliste suche={suche} />
        </form>

        <div className="d-start-filter">
          <Pills name="Nutzung" optionen={["Wohnen", "Gewerbe"] as const} wert={nutzung} onWahl={setNutzung} />
          <Pills name="Baualter" optionen={["Neubau", "Bestand"] as const} wert={alter} onWahl={setAlter} />
          <Pills name="Umkreis" optionen={["Umkreis 1 km", "Umkreis 2 km", "Umkreis 5 km"] as const} wert={umkreis} onWahl={setUmkreis} />
          <Pills name="Vermarktung" optionen={["Miete", "Kauf"] as const} wert={art} onWahl={setArt} />
        </div>

        {anlage.status === "nicht-erreichbar" && (
          <FehlerZustand titel="Geokodierung nicht erreichbar" text="Nominatim antwortet gerade nicht; das Projekt wurde nicht angelegt." aktion="Erneut versuchen" onAktion={() => suche.vorschlaege[0] && suche.waehlen(suche.vorschlaege[0])} />
        )}
        {anlage.status === "fehler" && <FehlerZustand titel="Projekt konnte nicht angelegt werden" text="Der Server hat die Anfrage abgelehnt." />}
        {liste.status === "fehler" && (
          <FehlerZustand titel="Backend nicht erreichbar" text={`${liste.meldung}. Läuft der Server auf Port 8000?`} onAktion={nochmal} />
        )}
        <div className="d-quellen">
          {detail.status === "bereit" && (
            <>
              <span className="d-quellen-label">
                Datenstand {detail.daten.ort}-{detail.daten.ortsteil}:
              </span>
              {detail.daten.quellen.length === 0 && <span className="d-leise">noch keine Daten importiert</span>}
              {detail.daten.quellen.map((q) => (
                <span key={q.id} className="d-quelle" title={`${q.datei ?? q.art} · abgerufen ${datum(q.abgerufen_am)}`}>
                  <span className="d-punkt" aria-hidden="true" />
                  {q.name} <span className="d-leise">{q.stand}</span>
                </span>
              ))}
            </>
          )}
          <span className="d-quelle d-quelle-fehlt">
            <span className="d-punkt aus" aria-hidden="true" />
            Wohnlagenkarte <span className="d-leise">fehlt</span>
          </span>
        </div>

        <section id="zuletzt" className="d-zuletzt" aria-labelledby="d-zuletzt-titel">
          <h2 id="d-zuletzt-titel" className="d-ueber">
            Zuletzt analysiert
          </h2>
          <div className="d-zuletzt-karten">
            {liste.status === "laden" && <LadeZeilen zeilen={3} />}
            {projekte.map((p) => (
              <Link key={p.id} to={`/analyse/${p.id}`} className="d-karte d-projekt">
                <span className="d-projekt-titel">
                  <strong>{p.name}</strong>, {p.adresse}
                </span>
                <span className="d-leise">
                  {p.ort}-{p.ortsteil} · {datum(p.analysiert_am)}
                </span>
              </Link>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

