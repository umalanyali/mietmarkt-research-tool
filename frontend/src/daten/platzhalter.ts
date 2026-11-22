// Platzhalter für Funktionen späterer Meilensteine, bis die echte Quelle steht. Keine Marktdaten:
// die Merkliste kommt ab M3 aus der Datenbank, Screenshots ab M5 aus dem Import, Bauprojekte aus einer späteren Quelle.
// Synthetisch, fiktive Musterstadt.

export const screenshots = [
  { titel: "Wohnlagenkarte", quelle: "RIWIS", datum: "11.11.2026", status: "geprüft" },
];

export const merklisteStart = [
  { id: "m1", titel: "Angebotsmieten Neubau, Zeitreihe", quelle: "RIWIS", art: "Diagramm", folie: "Mietmarkt" },
  { id: "m2", titel: "Einwohner, Haushalte, Kaufkraft", quelle: "RIWIS", art: "Kennzahlen", folie: "Standort" },
  { id: "m3", titel: "Angebotsmiete Neubau 17,40 €/m²", quelle: "VALUE", art: "Kennzahl", folie: "Marktdaten" },
  { id: "m4", titel: "Comps 1, 3, 9 mit Karte", quelle: "IS24", art: "Tabelle + Karte", folie: "Comps" },
  { id: "m5", titel: "Wohnlagenkarte", quelle: "RIWIS", art: "Bild", folie: "Standort" },
];

/** Bauprojekte im Umfeld des Demo-Standorts (Kartenebene „Projekte“), bis eine echte Quelle angebunden ist */
export const bauprojekte = [
  { name: "Wohnpark Ost (im Bau)", lat: 51.3185, lon: 9.4998 },
  { name: "Quartier Mühlgraben (geplant)", lat: 51.3208, lon: 9.4668 },
];
