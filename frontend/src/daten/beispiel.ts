/*
 * Synthetische Beispieldaten für den Prototyp, bis Importe und Datenbank stehen.
 * Fiktive Stadt „Musterstadt“, fiktive Anbieter und Adressen. Keine echten Marktdaten.
 * Die Werte der Comps-Zusammenfassung wurden einmalig per Skript berechnet; ab Meilenstein 2
 * liefert das Python-Fachpaket alle Kennzahlen, das Frontend rechnet nie selbst.
 */

export type Herkunft = "import" | "manuell" | "ki" | "abgelesen";

export interface Kennzahl {
  bezeichnung: string;
  wert: string;
  einheit?: string;
  vergleich?: string;
  herkunft: Herkunft;
}

export interface Comp {
  nr: number;
  objekt: string;
  anbieter: string;
  typ: "Regel" | "EG" | "DG";
  zimmer: number;
  baujahr: number;
  wfl: number;
  kalt: number;
  eurQm: number;
  ebk: boolean;
  tage: number;
  anfragen: number;
  anfragenMonat: number | null;
  entfKm: number;
  entfArt: "Fuß" | "Rad" | "Luftlinie";
  lat: number;
  lon: number;
  gemerkt: boolean;
}

export interface Zusammenfassung {
  regelEg: { n: number; eurQm: number };
  dg: { n: number; eurQm: number };
  alle: { n: number; eurQm: number };
  anfragenMonat: number;
  nAnfragen: number;
}

export const projekt = {
  id: "lindenquartier",
  name: "Lindenquartier",
  adresse: "Lindenallee 30",
  plz: "12345",
  ort: "Musterstadt",
  ortsteil: "Nordstadt",
  lat: 51.3127,
  lon: 9.4797,
  stichtag: "04.11.2026",
  filter: ["Wohnen", "Neubau", "Umkreis 2 km", "Miete"],
};

export const datenstand = [
  { quelle: "RIWIS", stand: "11/2026", umfang: "Soziodemografie, Angebotsmieten", datum: "11.11.2026" },
  { quelle: "VALUE", stand: "Q3/2026", umfang: "412 Inserate, Umkreis 2 km", datum: "08.11.2026" },
  { quelle: "IS24-Exposés", stand: "04.11.2026", umfang: "12 Exposés", datum: "04.11.2026" },
  { quelle: "Amtliche Daten", stand: "2025", umfang: "3 Werte, manuell erfasst", datum: "02.11.2026" },
];

export const soziodemografie: Kennzahl[] = [
  { bezeichnung: "Einwohner", wert: "18.460", vergleich: "Stadt 204.300", herkunft: "import" },
  { bezeichnung: "Haushalte", wert: "9.870", vergleich: "Stadt 108.900", herkunft: "import" },
  { bezeichnung: "Ø Personen je HH", wert: "1,87", vergleich: "Stadt 1,88", herkunft: "import" },
  { bezeichnung: "Kaufkraft je Einw.", wert: "26.900", einheit: "€", vergleich: "Stadt 25.100 €", herkunft: "abgelesen" },
  { bezeichnung: "Arbeitslosenquote", wert: "5,4", einheit: "%", vergleich: "Stadt 6,9 %", herkunft: "import" },
];

/** Angebotsmieten Neubau, €/m² nettokalt, Quartale */
export const zeitreihe = [
  { q: "Q4/24", plz: 15.1, stadt: 14.2, quantil: 18.6 },
  { q: "Q1/25", plz: 14.8, stadt: 14.4, quantil: 18.9 },
  { q: "Q2/25", plz: 15.4, stadt: 14.6, quantil: 19.0 },
  { q: "Q3/25", plz: 15.9, stadt: 14.9, quantil: 19.4 },
  { q: "Q4/25", plz: 16.3, stadt: 15.1, quantil: 20.6 },
  { q: "Q1/26", plz: 16.2, stadt: 15.3, quantil: 21.2 },
  { q: "Q2/26", plz: 16.6, stadt: 15.6, quantil: 21.3 },
  { q: "Q3/26", plz: 16.1, stadt: 15.8, quantil: 21.4 },
];

/** Preisklassen Neubau-Angebote, Anzahl je Klasse (Summe = n) */
export const preisklassen = [
  { klasse: "< 12", n: 4 },
  { klasse: "12–13,50", n: 6 },
  { klasse: "13,50–15", n: 14 },
  { klasse: "15–16,50", n: 21 },
  { klasse: "16,50–18", n: 38 },
  { klasse: "18–19,50", n: 13 },
  { klasse: "19,50–21", n: 6 },
  { klasse: "> 21", n: 3 },
];

export const screenshots = [
  { titel: "Wohnlagenkarte", quelle: "RIWIS", datum: "11.11.2026", status: "geprüft" },
  { titel: "Angebotsmieten nach Baujahr", quelle: "RIWIS", datum: "11.11.2026", status: "zu prüfen" },
];

export const valueKennzahlen: Kennzahl[] = [
  { bezeichnung: "Angebotsmiete Neubau", wert: "17,40", einheit: "€/m²", herkunft: "import" },
  { bezeichnung: "Veränderung 12 Monate", wert: "+3,8", einheit: "%", herkunft: "import" },
  { bezeichnung: "Vermarktungsdauer", wert: "36", einheit: "Tage", herkunft: "import" },
  { bezeichnung: "Angebote (12 M.)", wert: "412", herkunft: "import" },
];

export const valueTabelle = [
  { zimmer: "1 Zi.", n: 48, wfl: "37", min: "13,90", mittel: "19,20", median: "19,05", p75: "20,40", max: "24,80" },
  { zimmer: "2 Zi.", n: 156, wfl: "57", min: "12,80", mittel: "17,60", median: "17,45", p75: "18,70", max: "22,10" },
  { zimmer: "3 Zi.", n: 131, wfl: "79", min: "12,20", mittel: "16,90", median: "16,80", p75: "18,10", max: "21,30" },
  { zimmer: "4 Zi.", n: 58, wfl: "98", min: "11,90", mittel: "16,40", median: "16,25", p75: "17,60", max: "20,50" },
  { zimmer: "5+ Zi.", n: 19, wfl: "128", min: "12,40", mittel: "16,10", median: "15,90", p75: "17,20", max: "19,80" },
];

export const weitereQuellen = [
  { text: "Einwohner Ortsteil Nordstadt", wert: "18.460", quelle: "Statistikamt Musterstadt", datum: "31.12.2025" },
  { text: "Baufertigstellungen Wohnungen", wert: "1.240", quelle: "Statistisches Landesamt", datum: "2025" },
  { text: "Mietspiegel Ø Nettokaltmiete", wert: "9,85 €/m²", quelle: "Mietspiegel Musterstadt", datum: "2026" },
];

export const merklisteStart = [
  { id: "m1", titel: "Angebotsmieten Neubau, Zeitreihe", quelle: "RIWIS", art: "Diagramm", folie: "Mietmarkt" },
  { id: "m2", titel: "Einwohner, Haushalte, Kaufkraft", quelle: "RIWIS", art: "Kennzahlen", folie: "Standort" },
  { id: "m3", titel: "Angebotsmiete Neubau 17,40 €/m²", quelle: "VALUE", art: "Kennzahl", folie: "Marktdaten" },
  { id: "m4", titel: "Comps 1, 3, 9 mit Karte", quelle: "IS24", art: "Tabelle + Karte", folie: "Comps" },
  { id: "m5", titel: "Wohnlagenkarte", quelle: "RIWIS", art: "Bild", folie: "Standort" },
];

export const zuletzt = [
  { id: "lindenquartier", name: "Lindenquartier", adresse: "Lindenallee 30", ort: "Musterstadt-Nordstadt", datum: "11.11.2026", merkliste: 5, exporte: 1 },
  { id: "hafenblock", name: "Hafenblock", adresse: "Kaistraße 8", ort: "Musterstadt-Hafen", datum: "07.11.2026", merkliste: 12, exporte: 0 },
  { id: "am-park", name: "Am Stadtpark", adresse: "Parkring 61", ort: "Beispielheim", datum: "29.10.2026", merkliste: 3, exporte: 2 },
];

export const adressVorschlaege = [
  { strasse: "Lindenallee 30", plz: "12345", ort: "Musterstadt", ortsteil: "Nordstadt" },
  { strasse: "Lindenallee 42", plz: "12345", ort: "Musterstadt", ortsteil: "Nordstadt" },
  { strasse: "Lindenallee", plz: "12347", ort: "Musterstadt", ortsteil: "Am Anger" },
  { strasse: "Lindenhof 4", plz: "12345", ort: "Musterstadt", ortsteil: "Nordstadt" },
  { strasse: "Kaistraße 8", plz: "12349", ort: "Musterstadt", ortsteil: "Hafen" },
  { strasse: "Parkring 61", plz: "23456", ort: "Beispielheim", ortsteil: "Zentrum" },
];

/** Weitere Kartenebenen (Projekte, ÖPNV, Nahversorgung) – Positionen als Versatz in Metern zum Standort */
export const kartenPunkte = {
  projekte: [
    { name: "Wohnpark Ost (im Bau)", dx: 1400, dy: 650 },
    { name: "Quartier Mühlgraben (geplant)", dx: -900, dy: 900 },
  ],
  oepnv: [
    { name: "Haltestelle Lindenplatz", dx: 180, dy: 120 },
    { name: "Bahnhof Nordstadt", dx: -700, dy: -420 },
  ],
  nahversorgung: [
    { name: "Supermarkt", dx: 260, dy: -180 },
    { name: "Drogerie", dx: -320, dy: 260 },
  ],
};
export const comps: Comp[] = [
  {
    "nr": 1,
    "objekt": "Lindenhof 4",
    "anbieter": "Beispiel Wohnbau",
    "typ": "Regel",
    "zimmer": 2,
    "baujahr": 2025,
    "wfl": 58.4,
    "kalt": 1012,
    "eurQm": 17.33,
    "ebk": true,
    "tage": 34,
    "anfragen": 41,
    "anfragenMonat": 36.2,
    "entfKm": 0.7,
    "entfArt": "Fuß",
    "lat": 51.309915,
    "lon": 9.485736,
    "gemerkt": true
  },
  {
    "nr": 2,
    "objekt": "Am Mühlgraben 12",
    "anbieter": "Muster Immobilien",
    "typ": "DG",
    "zimmer": 3,
    "baujahr": 2025,
    "wfl": 86.0,
    "kalt": 1720,
    "eurQm": 20.0,
    "ebk": true,
    "tage": 12,
    "anfragen": 9,
    "anfragenMonat": 22.5,
    "entfKm": 0.8,
    "entfArt": "Fuß",
    "lat": 51.314317,
    "lon": 9.470502,
    "gemerkt": false
  },
  {
    "nr": 3,
    "objekt": "Kastanienallee 21",
    "anbieter": "Projekt Nord GmbH",
    "typ": "EG",
    "zimmer": 2,
    "baujahr": 2026,
    "wfl": 61.2,
    "kalt": 1028,
    "eurQm": 16.8,
    "ebk": true,
    "tage": 21,
    "anfragen": 27,
    "anfragenMonat": 38.6,
    "entfKm": 1.3,
    "entfArt": "Fuß",
    "lat": 51.317371,
    "lon": 9.492347,
    "gemerkt": true
  },
  {
    "nr": 4,
    "objekt": "Kastanienallee 21",
    "anbieter": "Projekt Nord GmbH",
    "typ": "Regel",
    "zimmer": 3,
    "baujahr": 2026,
    "wfl": 78.5,
    "kalt": 1295,
    "eurQm": 16.5,
    "ebk": true,
    "tage": 21,
    "anfragen": 19,
    "anfragenMonat": 27.1,
    "entfKm": 1.3,
    "entfArt": "Fuß",
    "lat": 51.317371,
    "lon": 9.492347,
    "gemerkt": false
  },
  {
    "nr": 5,
    "objekt": "Kastanienallee 21",
    "anbieter": "Projekt Nord GmbH",
    "typ": "DG",
    "zimmer": 4,
    "baujahr": 2026,
    "wfl": 104.3,
    "kalt": 1930,
    "eurQm": 18.5,
    "ebk": true,
    "tage": 21,
    "anfragen": 6,
    "anfragenMonat": 8.6,
    "entfKm": 1.3,
    "entfArt": "Fuß",
    "lat": 51.317371,
    "lon": 9.492347,
    "gemerkt": false
  },
  {
    "nr": 6,
    "objekt": "Ulmenweg 7",
    "anbieter": "Privat",
    "typ": "Regel",
    "zimmer": 1,
    "baujahr": 2024,
    "wfl": 38.9,
    "kalt": 742,
    "eurQm": 19.07,
    "ebk": false,
    "tage": 5,
    "anfragen": 14,
    "anfragenMonat": null,
    "entfKm": 1.5,
    "entfArt": "Rad",
    "lat": 51.306861,
    "lon": 9.463891,
    "gemerkt": false
  },
  {
    "nr": 7,
    "objekt": "Brunnenstraße 33",
    "anbieter": "Beispiel Wohnbau",
    "typ": "Regel",
    "zimmer": 2,
    "baujahr": 2025,
    "wfl": 55.0,
    "kalt": 935,
    "eurQm": 17.0,
    "ebk": true,
    "tage": 48,
    "anfragen": 52,
    "anfragenMonat": 32.5,
    "entfKm": 1.9,
    "entfArt": "Rad",
    "lat": 51.304615,
    "lon": 9.498383,
    "gemerkt": false
  },
  {
    "nr": 8,
    "objekt": "Brunnenstraße 33",
    "anbieter": "Beispiel Wohnbau",
    "typ": "DG",
    "zimmer": 3,
    "baujahr": 2025,
    "wfl": 91.7,
    "kalt": 1752,
    "eurQm": 19.11,
    "ebk": true,
    "tage": 48,
    "anfragen": 11,
    "anfragenMonat": 6.9,
    "entfKm": 1.9,
    "entfArt": "Rad",
    "lat": 51.304615,
    "lon": 9.498383,
    "gemerkt": false
  },
  {
    "nr": 9,
    "objekt": "Hafenkante 2",
    "anbieter": "Musterstadt Living",
    "typ": "Regel",
    "zimmer": 2,
    "baujahr": 2026,
    "wfl": 63.8,
    "kalt": 1148,
    "eurQm": 17.99,
    "ebk": true,
    "tage": 9,
    "anfragen": 8,
    "anfragenMonat": 26.7,
    "entfKm": 1.9,
    "entfArt": "Luftlinie",
    "lat": 51.322581,
    "lon": 9.458143,
    "gemerkt": true
  },
  {
    "nr": 10,
    "objekt": "Schulgasse 15",
    "anbieter": "Privat",
    "typ": "EG",
    "zimmer": 3,
    "baujahr": 2023,
    "wfl": 82.1,
    "kalt": 1260,
    "eurQm": 15.35,
    "ebk": false,
    "tage": 63,
    "anfragen": 30,
    "anfragenMonat": 14.3,
    "entfKm": 2.1,
    "entfArt": "Rad",
    "lat": 51.327073,
    "lon": 9.488323,
    "gemerkt": false
  },
  {
    "nr": 11,
    "objekt": "Feldrain 9",
    "anbieter": "Muster Immobilien",
    "typ": "Regel",
    "zimmer": 4,
    "baujahr": 2025,
    "wfl": 98.6,
    "kalt": 1625,
    "eurQm": 16.48,
    "ebk": true,
    "tage": 27,
    "anfragen": 7,
    "anfragenMonat": 7.8,
    "entfKm": 2.1,
    "entfArt": "Rad",
    "lat": 51.29698,
    "lon": 9.475389,
    "gemerkt": false
  },
  {
    "nr": 12,
    "objekt": "Gartenstraße 40",
    "anbieter": "Musterstadt Living",
    "typ": "Regel",
    "zimmer": 2,
    "baujahr": 2026,
    "wfl": 49.5,
    "kalt": 895,
    "eurQm": 18.08,
    "ebk": true,
    "tage": 15,
    "anfragen": 22,
    "anfragenMonat": 44.0,
    "entfKm": 1.8,
    "entfArt": "Luftlinie",
    "lat": 51.315395,
    "lon": 9.50485,
    "gemerkt": false
  }
];

export const compsZusammenfassung: Zusammenfassung = {
  "regelEg": {
    "n": 9,
    "eurQm": 16.96
  },
  "dg": {
    "n": 3,
    "eurQm": 19.16
  },
  "alle": {
    "n": 12,
    "eurQm": 17.68
  },
  "anfragenMonat": 24.1,
  "nAnfragen": 11
};
