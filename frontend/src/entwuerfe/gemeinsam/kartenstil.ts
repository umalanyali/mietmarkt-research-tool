/*
 * Eigener MapLibre-Stil auf Basis der OpenFreeMap-Vektorkacheln (OpenMapTiles-Schema).
 * Kein Standard-OSM-Stil: nur die Ebenen, die für eine Standortanalyse zählen, in warmen Neutraltönen.
 */
import type { FilterSpecification, StyleSpecification } from "maplibre-gl";

/** Kartenfarben: helles, warmes Grau, Straßen weiß, Gebäude leicht abgesetzt. */
const F = {
  land: "#ebe8e1",
  gruen: "#e2e2d2",
  wasser: "#d6d2c9",
  gebaeude: "#dfdad0",
  strasse: "#f8f6f1",
  strasseHaupt: "#ffffff",
  strasseKontur: "#d7d2c7",
  bahn: "#b4aea2",
  schrift: "#8a847a",
};

/** Filter: Feld „class“ ist einer der Werte. */
const klasse = (...werte: string[]) => ["in", ["get", "class"], ["literal", werte]] as unknown as FilterSpecification;

/** Linienbreite, die mit dem Zoom wächst (basis = Breite bei Zoom 14). */
const breite = (basis: number) =>
  ["interpolate", ["exponential", 1.6], ["zoom"], 11, basis * 0.4, 14, basis, 17, basis * 4] as unknown as number;

const HAUPTSTRASSEN = klasse("primary", "secondary", "tertiary", "trunk", "motorway");

export const KARTENSTIL: StyleSpecification = {
  version: 8,
  glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
  sources: { omt: { type: "vector", url: "https://tiles.openfreemap.org/planet" } },
  layers: [
    { id: "land", type: "background", paint: { "background-color": F.land } },
    {
      id: "gruen",
      type: "fill",
      source: "omt",
      "source-layer": "landuse",
      filter: klasse("park", "cemetery", "grass", "recreation_ground"),
      paint: { "fill-color": F.gruen },
    },
    { id: "gruen-park", type: "fill", source: "omt", "source-layer": "park", paint: { "fill-color": F.gruen } },
    { id: "wasser", type: "fill", source: "omt", "source-layer": "water", paint: { "fill-color": F.wasser } },
    { id: "wasserlauf", type: "line", source: "omt", "source-layer": "waterway", paint: { "line-color": F.wasser, "line-width": 1.2 } },
    { id: "gebaeude", type: "fill", source: "omt", "source-layer": "building", minzoom: 12, paint: { "fill-color": F.gebaeude } },
    {
      // Kontur unter den Hauptstraßen, damit weiße Straßen auf hellem Grund sichtbar bleiben
      id: "strasse-kontur",
      type: "line",
      source: "omt",
      "source-layer": "transportation",
      filter: HAUPTSTRASSEN,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": F.strasseKontur, "line-width": breite(3.6) },
    },
    {
      id: "strasse-neben",
      type: "line",
      source: "omt",
      "source-layer": "transportation",
      filter: klasse("minor", "service", "track", "path"),
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": F.strasse, "line-width": breite(1.2) },
    },
    {
      id: "strasse-haupt",
      type: "line",
      source: "omt",
      "source-layer": "transportation",
      filter: HAUPTSTRASSEN,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": F.strasseHaupt, "line-width": breite(2.4) },
    },
    {
      id: "bahn",
      type: "line",
      source: "omt",
      "source-layer": "transportation",
      filter: klasse("rail", "transit"),
      paint: { "line-color": F.bahn, "line-width": 1, "line-dasharray": [4, 3] },
    },
    {
      id: "strassennamen",
      type: "symbol",
      source: "omt",
      "source-layer": "transportation_name",
      minzoom: 14,
      layout: {
        "symbol-placement": "line",
        "text-field": ["get", "name"],
        "text-font": ["Noto Sans Regular"],
        "text-size": 10.5,
        "text-letter-spacing": 0.04,
      },
      paint: { "text-color": F.schrift, "text-halo-color": F.land, "text-halo-width": 1.4 },
    },
  ],
};
