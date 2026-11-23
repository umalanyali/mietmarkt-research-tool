// Karte des Dashboards (MapLibre): Projektstandort, Umkreisringe, Comps mit Gruppen-Markern, Ebenen und Lade-/Fehlerzustand.
import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl, { type Map as MLMap, type Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Comp } from "../api";
import { KARTENSTIL } from "./kartenstil";

export type Ebene = "Comps" | "Projekte" | "ÖPNV" | "Nahversorgung" | "Wohnlage";
export const EBENEN: Ebene[] = ["Comps", "Projekte", "ÖPNV", "Nahversorgung", "Wohnlage"];

export interface Punkt {
  name: string;
  lat: number;
  lon: number;
}

export type KartenZustand = "bereit" | "laden" | "fehler";

interface Props {
  zentrum: { lat: number; lon: number; name: string };
  ringeKm: number[];
  comps: Comp[];
  weitere: { projekte: Punkt[]; oepnv: Punkt[]; nahversorgung: Punkt[] };
  aktiveEbenen: Set<Ebene>;
  ausgewaehlt: number | null;
  onAuswahl: (nr: number) => void;
  /** Erzwingt einen Zustand (für die Zustandsübersicht) */
  zustand?: KartenZustand;
  hoehe?: number | string;
  /** Projektname als Schild über dem Standort */
  beschriftung?: boolean;
}

/** Verschiebt eine Koordinate um Meter (Näherung für kleine Abstände). Eingabe: lat, lon, dx/dy in m. Ausgabe: [lon, lat]. */
function versatz(lat: number, lon: number, dx: number, dy: number): [number, number] {
  return [lon + dx / (111320 * Math.cos((lat * Math.PI) / 180)), lat + dy / 111320];
}

/** Kreis als Linienzug für einen Umkreisring. Eingabe: Mittelpunkt, Radius km, Stützpunkte. Ausgabe: Koordinatenliste. */
function kreis(lat: number, lon: number, km: number, punkte = 120): [number, number][] {
  return Array.from({ length: punkte + 1 }, (_, i) => {
    const w = (2 * Math.PI * i) / punkte;
    return versatz(lat, lon, Math.sin(w) * km * 1000, Math.cos(w) * km * 1000);
  });
}

/**
 * DOM-Element für einen Marker. Mit Klick-Handler ein <button> (Tastatur erreichbar), sonst ein Bild mit Beschriftung.
 * Eingabe: CSS-Klasse, Text, Screenreader-Label, optional Klick. Ausgabe: HTML-Element.
 */
function element(klasse: string, text: string, label: string, onClick?: () => void): HTMLElement {
  const el = document.createElement(onClick ? "button" : "div");
  el.className = `km ${klasse}`;
  el.textContent = text;
  el.setAttribute("aria-label", label);
  el.title = label;
  if (onClick) {
    (el as HTMLButtonElement).type = "button";
    el.addEventListener("click", onClick);
  } else {
    el.setAttribute("role", "img");
  }
  return el;
}

/**
 * Karte mit eigenem Stil, Umkreisringen, nummerierten Comps und Gruppen-Markern (mehrere Inserate am selben Haus).
 * Eingabe: Standort, Ringe, Comps, weitere Punkte, aktive Ebenen, Auswahl; optional erzwungener Zustand.
 * Ausgabe: Kartenfläche mit Zoom-Knöpfen bzw. Lade- oder Fehlerhinweis.
 */
export function Karte({
  zentrum,
  ringeKm,
  comps,
  weitere,
  aktiveEbenen,
  ausgewaehlt,
  onAuswahl,
  zustand,
  hoehe = 440,
  beschriftung = false,
}: Props) {
  const behaelter = useRef<HTMLDivElement>(null);
  const karteRef = useRef<MLMap | null>(null);
  const markerRef = useRef<Record<string, Marker[]>>({});
  const [geladen, setGeladen] = useState<KartenZustand>("laden");
  const [versuch, setVersuch] = useState(0);
  const anzeige: KartenZustand = zustand ?? geladen;

  // Comps an derselben Adresse zu einem Gruppen-Marker „3–5“ zusammenfassen
  const gruppen = useMemo(() => {
    const m = new Map<string, Comp[]>();
    // Comps ohne Koordinaten können nicht auf die Karte
    for (const c of comps) if (c.lat !== null && c.lon !== null) m.set(c.objekt, [...(m.get(c.objekt) ?? []), c]);
    return [...m.values()];
  }, [comps]);

  useEffect(() => {
    if (zustand || !behaelter.current) return;
    setGeladen("laden");
    // Ausschnitt: größter Ring plus 10 % Rand
    const r = Math.max(...ringeKm) * 1.1 * 1000;
    const [w, s] = versatz(zentrum.lat, zentrum.lon, -r, -r);
    const [o, n] = versatz(zentrum.lat, zentrum.lon, r, r);
    let karte: MLMap;
    try {
      karte = new maplibregl.Map({
        container: behaelter.current,
        style: KARTENSTIL,
        bounds: [w, s, o, n],
        attributionControl: { compact: true },
      });
    } catch {
      setGeladen("fehler");
      return;
    }
    karteRef.current = karte;
    const zeitlimit = window.setTimeout(() => !karte.loaded() && setGeladen("fehler"), 15000);

    karte.on("error", (e) => {
      // Einzelne fehlende Kacheln sind kein Totalausfall; nur ohne geladenen Stil gilt die Karte als gestört
      if (!karte.isStyleLoaded()) setGeladen("fehler");
      console.warn("Karte:", e.error?.message);
    });

    // Marker und Ringe erst nach dem Laden des Stils hinzufügen, sonst lehnt MapLibre neue Quellen ab
    karte.on("load", () => {
      window.clearTimeout(zeitlimit);
      setGeladen("bereit");
      const stil = getComputedStyle(behaelter.current!);
      // Ringfarbe aus dem CSS-Token lesen, damit die Karte der Palette folgt
      const ring = stil.getPropertyValue("--karte-ring").trim(); // in tokens.css auf :root, also immer gesetzt
      karte.addSource("ringe", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: ringeKm.map((km) => ({
            type: "Feature",
            properties: {},
            geometry: { type: "LineString", coordinates: kreis(zentrum.lat, zentrum.lon, km) },
          })),
        },
      });
      karte.addLayer({
        id: "ringe",
        type: "line",
        source: "ringe",
        paint: { "line-color": ring, "line-width": 1, "line-dasharray": [2, 3] },
      });

      const setze = (ebene: string, liste: Marker[]) => {
        markerRef.current[ebene] = liste;
        liste.forEach((m) => m.addTo(karte));
      };
      setze(
        "Ringe",
        ringeKm.map((km) =>
          new maplibregl.Marker({ element: element("km-ring", `${km} km`, `Umkreis ${km} km`) }).setLngLat(
            versatz(zentrum.lat, zentrum.lon, 0, km * 1000),
          ),
        ),
      );
      setze("Standort", [
        new maplibregl.Marker({ element: element("km-standort", "", `Projektstandort ${zentrum.name}`) }).setLngLat([
          zentrum.lon,
          zentrum.lat,
        ]),
        ...(beschriftung && zentrum.name
          ? [
              new maplibregl.Marker({ element: element("km-name", zentrum.name, zentrum.name), anchor: "bottom", offset: [0, -16] }).setLngLat([
                zentrum.lon,
                zentrum.lat,
              ]),
            ]
          : []),
      ]);
      setze(
        "Comps",
        gruppen.map((g) => {
          const nr = g.map((c) => c.nr);
          const text = nr.length > 1 ? `${nr[0]}–${nr[nr.length - 1]}` : String(nr[0]);
          const label =
            nr.length > 1 ? `${g[0].objekt}: Comps ${text}, ${nr.length} Inserate` : `Comp ${text}: ${g[0].objekt}`;
          const el = element(nr.length > 1 ? "km-comp km-gruppe" : "km-comp", text, label, () => onAuswahl(nr[0]));
          el.dataset.von = String(nr[0]);
          el.dataset.bis = String(nr[nr.length - 1]);
          return new maplibregl.Marker({ element: el }).setLngLat([g[0].lon!, g[0].lat!]);
        }),
      );
      sichtbarkeit();
    });

    return () => {
      window.clearTimeout(zeitlimit);
      karte.remove();
      karteRef.current = null;
      markerRef.current = {};
    };
    // Karte nur bei neuem Versuch neu aufbauen
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [versuch, zustand]);

  /** Blendet Marker je nach aktiven Ebenen ein oder aus. Eingabe: keine. Ausgabe: keine. */
  function sichtbarkeit() {
    for (const [ebene, liste] of Object.entries(markerRef.current)) {
      if (ebene === "Standort" || ebene === "Ringe") continue;
      const sichtbar = aktiveEbenen.has(ebene as Ebene);
      liste.forEach((m) => (m.getElement().style.display = sichtbar ? "" : "none"));
    }
  }

  // Punkte-Ebenen (Bauprojekte, ÖPNV, Nahversorgung) kommen teils später aus der API; bei jeder Änderung neu setzen
  useEffect(() => {
    const karte = karteRef.current;
    if (!karte || geladen !== "bereit") return;
    const punkte = (liste: Punkt[], klasse: string, zeichen: string) =>
      liste.map((p) => new maplibregl.Marker({ element: element(klasse, zeichen, p.name) }).setLngLat([p.lon, p.lat]).addTo(karte));
    const neu = {
      Projekte: punkte(weitere.projekte, "km-projekt", "P"),
      ÖPNV: punkte(weitere.oepnv, "km-poi", "H"),
      Nahversorgung: punkte(weitere.nahversorgung, "km-poi", "N"),
    };
    Object.assign(markerRef.current, neu);
    sichtbarkeit();
    return () => Object.values(neu).flat().forEach((m) => m.remove());
    // sichtbarkeit liest aktiveEbenen selbst; neu setzen nur bei neuen Punkten oder nach dem Laden
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [weitere, geladen]);

  useEffect(sichtbarkeit);

  useEffect(() => {
    (markerRef.current["Comps"] ?? []).forEach((m) => {
      const el = m.getElement();
      const von = Number(el.dataset.von);
      const bis = Number(el.dataset.bis);
      el.classList.toggle("km-aktiv", ausgewaehlt !== null && ausgewaehlt >= von && ausgewaehlt <= bis);
    });
  }, [ausgewaehlt]);

  return (
    <div className="ek" style={{ height: hoehe }}>
      <div ref={behaelter} className="ek-flaeche" aria-label="Karte: Projektstandort, Umkreisringe, Vergleichsangebote" />
      {anzeige === "bereit" && (
        <div className="ek-zoom" role="group" aria-label="Kartenmaßstab">
          <button type="button" aria-label="Hineinzoomen" onClick={() => karteRef.current?.zoomIn()}>
            +
          </button>
          <button type="button" aria-label="Herauszoomen" onClick={() => karteRef.current?.zoomOut()}>
            −
          </button>
        </div>
      )}
      {anzeige === "laden" && (
        <div className="ek-zustand" role="status">
          <span className="ek-ladebalken" aria-hidden="true" />
          Karte wird geladen
        </div>
      )}
      {anzeige === "fehler" && (
        <div className="ek-zustand ek-fehler" role="alert">
          <strong>Kartenkacheln nicht erreichbar.</strong>
          <span>Comps und Entfernungen bleiben nutzbar; die Lage fehlt nur als Bild.</span>
          {!zustand && (
            <button type="button" onClick={() => setVersuch((v) => v + 1)}>
              Erneut versuchen
            </button>
          )}
        </div>
      )}
    </div>
  );
}
