/*
 * Synthetische Beispieldaten für die Agenten-Elemente des Dashboards:
 * Zeitleiste, Freigabe (Interrupt) und Herleitungskette des Mietansatzes.
 * Alle Zahlen sind Beispielwerte; ab M6 kommen sie aus dem LangGraph-Lauf.
 */

export type AgentStatus = "fertig" | "arbeitet" | "rueckfrage" | "wartet" | "fehler";

export interface Werkzeugaufruf {
  name: string;
}

export interface AgentSchritt {
  id: string;
  agent: string;
  status: AgentStatus;
  dauerS: number | null;
  zusammenfassung: string;
  werkzeuge: Werkzeugaufruf[];
  tokens: number;
  kostenEur: number;
}

export const lauf = {
  id: "A-014",
  tokens: 48210,
  kostenEur: 0.21,
};

export const zeitleiste: AgentSchritt[] = [
  {
    id: "standort",
    agent: "Standort",
    status: "fertig",
    dauerS: 4.2,
    zusammenfassung: "Adresse verortet, 2 Haltestellen und 2 Nahversorger im Umkreis, 12 Wegezeiten berechnet",
    werkzeuge: [
      { name: "geokodieren" },
      { name: "pois" },
      { name: "wegezeit" },
    ],
    tokens: 2140,
    kostenEur: 0.0,
  },
  {
    id: "expose",
    agent: "Exposé",
    status: "fertig",
    dauerS: 18.6,
    zusammenfassung: "12 Exposés gelesen; Parser füllte 94 % der Felder, Modell ergänzte 5 Felder (markiert)",
    werkzeuge: [
      { name: "is24_parser" },
      { name: "luecken_fuellen" },
      { name: "plausibilitaet" },
    ],
    tokens: 21400,
    kostenEur: 0.01,
  },
  {
    id: "screenshot",
    agent: "Screenshot",
    status: "fertig",
    dauerS: 11.3,
    zusammenfassung: "2 RIWIS-Bilder ausgelesen, 14 Werte, davon 6 aus Grafiken abgelesen",
    werkzeuge: [{ name: "bild_auslesen" }],
    tokens: 9870,
    kostenEur: 0.0,
  },
  {
    id: "marktdaten",
    agent: "Marktdaten",
    status: "fertig",
    dauerS: 3.1,
    zusammenfassung: "449 Zeilen, 37 Dubletten entfernt, Statistik je Zimmerzahl für 412 Inserate",
    werkzeuge: [
      { name: "value_einlesen" },
      { name: "dubletten_entfernen" },
      { name: "statistik_je_zimmer" },
    ],
    tokens: 3900,
    kostenEur: 0.0,
  },
  {
    id: "supervisor",
    agent: "Supervisor",
    status: "fertig",
    dauerS: 2.4,
    zusammenfassung: "Alle Eingänge vollständig. Nächster Schritt: Comps zur Freigabe vorlegen",
    werkzeuge: [],
    tokens: 10900,
    kostenEur: 0.2,
  },
  {
    id: "comps_freigabe",
    agent: "Comps-Freigabe",
    status: "rueckfrage",
    dauerS: null,
    zusammenfassung: "Wartet auf deine Entscheidung",
    werkzeuge: [],
    tokens: 0,
    kostenEur: 0,
  },
  { id: "mietansatz", agent: "Mietansatz", status: "wartet", dauerS: null, zusammenfassung: "", werkzeuge: [], tokens: 0, kostenEur: 0 },
  { id: "pruefung", agent: "Prüfung", status: "wartet", dauerS: null, zusammenfassung: "", werkzeuge: [], tokens: 0, kostenEur: 0 },
  { id: "bericht", agent: "Bericht", status: "wartet", dauerS: null, zusammenfassung: "", werkzeuge: [], tokens: 0, kostenEur: 0 },
];

export const freigabe = {
  titel: "Comps freigeben",
  frage: "11 von 12 Vergleichsangeboten in die Auswertung übernehmen?",
  vorschlag: [
    { text: "Comps 1–5 und 7–12 übernehmen", wert: "11 Inserate" },
    { text: "Comp 6 (Ulmenweg 7) ausschließen", wert: "5 Tage online" },
  ],
  begruendung:
    "Comp 6 ist erst 5 Tage online; Anfragen je Monat sind damit nicht belastbar. Alle übrigen liegen innerhalb der Plausibilitätsgrenzen (5–40 €/m², Abweichung vom Median unter 30 %).",
  belege: [
    { quelle: "Exposé Ulmenweg 7", fundstelle: "S. 1, „online seit 16.11.2026“" },
    { quelle: "Werkzeug plausibilitaet", fundstelle: "Lauf A-014, Aufruf 3" },
  ],
};

export interface KettenGlied {
  art: "beleg" | "annahme" | "zahl";
  text: string;
  wert?: string;
  quelle?: string;
}

/** Mietansatz-Herleitung: Beleg → Annahme → Zahl (Beispielwerte, rechnerisch stimmig). */
export const herleitung: { schritt: string; glieder: KettenGlied[] }[] = [
  {
    schritt: "Basis",
    glieder: [
      { art: "beleg", text: "9 Comps Regelgeschoss/EG", quelle: "Comps 1, 3, 4, 7, 9–12" },
      { art: "annahme", text: "Ø flächengewichtet als Basis" },
      { art: "zahl", text: "Basis", wert: "16,96 €/m²", quelle: "basis_berechnen" },
    ],
  },
  {
    schritt: "Energiestandard",
    glieder: [
      { art: "beleg", text: "Effizienzhaus 40, Wärmepumpe", quelle: "Baubeschreibung S. 4" },
      { art: "annahme", text: "Vorteil gegenüber Comps mit EH 55" },
      { art: "zahl", text: "Zuschlag", wert: "+0,30 €/m²" },
    ],
  },
  {
    schritt: "Ausstattung",
    glieder: [
      { art: "beleg", text: "Parkett, bodengleiche Duschen", quelle: "Baubeschreibung S. 7" },
      { art: "annahme", text: "leicht über Comps-Durchschnitt" },
      { art: "zahl", text: "Zuschlag", wert: "+0,20 €/m²" },
    ],
  },
  {
    schritt: "Verkehr / Lärm",
    glieder: [
      { art: "beleg", text: "Hauptstraße in 40 m", quelle: "Standort-Agent, wegezeit" },
      { art: "annahme", text: "Abschlag für straßenseitige Einheiten" },
      { art: "zahl", text: "Abschlag", wert: "−0,25 €/m²" },
    ],
  },
  {
    schritt: "Fortschreibung",
    glieder: [
      { art: "beleg", text: "Vermarktungsstart 01/2028", quelle: "Projektgedächtnis" },
      { art: "annahme", text: "g = 2,0 % p. a., 14 Monate" },
      { art: "zahl", text: "(1 + g)^(14/12)", wert: "× 1,0234", quelle: "fortschreiben" },
    ],
  },
];

export const mietansatzErgebnis = {
  saldo: "+0,25 €/m²",
  vorRundung: "17,61 €/m²",
  rundung: "auf 0,10 €/m²",
  status: "Vorschlag – noch nicht bestätigt",
};
