// Platzhalter, bis eine echte Quelle angebunden ist: Start-Bausteine der Merkliste, Screenshot-Liste und Bauprojekte.
// Keine Marktdaten.
// Synthetisch, fiktive Musterstadt.

export const screenshots = [
  { titel: "Wohnlagenkarte", quelle: "Marktbericht", datum: "11.11.2026", status: "geprüft" },
];

export const merklisteStart = [
  { id: "m1", titel: "Angebotsmieten Neubau, Zeitreihe", quelle: "Marktbericht", art: "Diagramm", folie: "Mietmarkt" },
  { id: "m2", titel: "Einwohner, Haushalte, Kaufkraft", quelle: "Marktbericht", art: "Kennzahlen", folie: "Standort" },
  { id: "m3", titel: "Angebotsmiete Neubau 17,40 €/m²", quelle: "Angebotsstatistik", art: "Kennzahl", folie: "Marktdaten" },
  { id: "m4", titel: "Comps 1, 3, 9 mit Karte", quelle: "Portal", art: "Tabelle + Karte", folie: "Comps" },
  { id: "m5", titel: "Wohnlagenkarte", quelle: "Marktbericht", art: "Bild", folie: "Standort" },
];

/** Bauprojekte im Umfeld des Demo-Standorts (Kartenebene „Projekte“), bis eine echte Quelle angebunden ist */
export const bauprojekte = [
  { name: "Wohnpark Ost (im Bau)", lat: 51.3185, lon: 9.4998 },
  { name: "Quartier Mühlgraben (geplant)", lat: 51.3208, lon: 9.4668 },
];
