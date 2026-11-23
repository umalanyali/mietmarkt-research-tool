// Zugriff auf die Backend-API (/api, im Dev-Server an Port 8000 weitergeleitet) und die Typen ihrer Antworten.
// Alle Zahlen kommen fertig berechnet aus Python; das Frontend formatiert nur (CLAUDE.md Regel 1).
import { useCallback, useEffect, useState } from "react";

export type Herkunft = "import" | "manuell" | "ki" | "abgelesen" | "berechnet";

/** Eine Zahl mit Einheit, Herkunft und Rechenweg, wie sie das Fachpaket liefert. */
export interface Wert {
  wert: number | null;
  einheit: string;
  herkunft: Herkunft;
  quelle_id: number | null;
  rechenweg_text: string;
  fundstelle?: string; // Stelle in einer Unterlage, z. B. „S. 2“
  ausschnitt?: number[] | null; // bei Werten aus Bildern: [x, y, Breite, Höhe] in Pixeln
}

export interface Projekt {
  id: number;
  name: string;
  adresse: string;
  plz: string;
  ort: string;
  ortsteil: string;
  lat: number;
  lon: number;
  stichtag: string;
  analysiert_am: string;
  segment: string;
  umkreis_km: number;
  vermarktung: string;
  demo: boolean;
}

export interface Quelle {
  id: number;
  name: string;
  art: string;
  datei: string | null;
  stand: string;
  abgerufen_am: string;
  seite: string | null;
}

export interface ProjektDetail extends Projekt {
  quellen: Quelle[];
}

export interface Comp {
  id: number;
  nr: number;
  objekt: string;
  anbieter: string;
  typ: "Regel" | "EG" | "DG";
  zimmer: number;
  baujahr: number | null;
  wohnflaeche: number;
  kaltmiete: number;
  ebk: boolean;
  anfragen: number | null;
  lat: number | null;
  lon: number | null;
  gemerkt: boolean;
  herkunft: Herkunft;
  quelle_id: number | null;
  fundstelle: string;
  eur_qm: Wert;
  tage_online: Wert;
  anfragen_monat: Wert;
  entfernung_km: Wert | null;
}

export interface Marktkennzahl {
  id: number;
  gruppe: "soziodemografie" | "zeitreihe" | "preisklassen" | "value" | "value_tabelle" | "weitere";
  bezeichnung: string;
  kategorie: string;
  gebiet: string;
  wert: number | null;
  einheit: string;
  stellen: number;
  herkunft: Herkunft;
  quelle_id: number | null;
  rechenweg_text: string;
}

export interface Kennzahlen {
  kennzahlen: Marktkennzahl[];
  quellen: Quelle[];
  comps: Record<"regel_eg" | "regel_eg_n" | "dg" | "dg_n" | "anfragen_monat" | "anzahl" | "median" | "q1" | "q3" | "mittel_flaechengewichtet", Wert>;
  preisklassen: { summe: Wert; staerkste: string | null; anteil: Wert };
}

export interface Vorschlag {
  label: string;
  strasse: string;
  plz: string;
  ort: string;
  ortsteil: string;
  lat: number;
  lon: number;
}

export interface UmfeldPoi {
  kategorie: string;
  name: string;
  lat: number;
  lon: number;
  luftlinie: Wert;
  zu_fuss: Wert | null;
  rad: Wert | null;
  methode_fuss: "Route" | "Luftlinie";
  methode_rad: "Route" | "Luftlinie";
}

export interface Umfeld {
  pois: UmfeldPoi[];
  radius_m: number;
  attribution: string;
}

/** Ein Agenten-Lauf in der Laufliste; „offen“ = pausiert oder unterbrochen, lässt sich fortsetzen. */
export interface LaufInfo {
  id: string;
  gestartet_am: string;
  status: "fertig" | "abgebrochen" | "offen";
}

export interface DokumentAus {
  id: number;
  dateiname: string;
  art: string;
  seiten: number;
  abschnitte: number;
  ki_freigabe: boolean;
}

/** Fehler einer API-Antwort mit HTTP-Status (503 = externer Dienst nicht erreichbar). */
export class ApiFehler extends Error {
  constructor(
    meldung: string,
    readonly status: number,
  ) {
    super(meldung);
  }
}

/** Liest eine Antwort als JSON oder wirft ApiFehler. Eingabe: fetch-Antwort. Ausgabe: Daten. */
async function json<T>(antwort: Response): Promise<T> {
  if (!antwort.ok) {
    const text = antwort.status === 404 ? "Nicht gefunden" : antwort.status === 503 ? "Dienst nicht erreichbar" : `Server antwortet mit ${antwort.status}`;
    throw new ApiFehler(text, antwort.status);
  }
  return (await antwort.json()) as T;
}

/** Legt ein Projekt aus einem gewählten Vorschlag an. Eingabe: Vorschlag. Ausgabe: Projekt (oder ApiFehler). */
export async function projektAnlegen(v: Vorschlag): Promise<Projekt> {
  return json<Projekt>(await fetch("/api/projekte", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(v) }));
}

/**
 * Lädt eine eigene Unterlage hoch. Eingabe: Projekt-ID, Datei, ob die KI sie lesen darf. Ausgabe: Dokument
 * (oder ApiFehler mit dem Grund aus dem Backend, z. B. zu groß oder falscher Dateityp).
 */
export async function dokumentHochladen(projektId: number, datei: File, kiFreigabe: boolean): Promise<DokumentAus> {
  const form = new FormData();
  form.append("datei", datei);
  form.append("ki_freigabe", String(kiFreigabe));
  const antwort = await fetch(`/api/projekte/${projektId}/dokumente`, { method: "POST", body: form });
  if (!antwort.ok) {
    const detail = await antwort.json().then((j) => j.detail).catch(() => null);
    throw new ApiFehler(typeof detail === "string" ? detail : `Server antwortet mit ${antwort.status}`, antwort.status);
  }
  return (await antwort.json()) as DokumentAus;
}

/** Adressvorschläge. Eingabe: Suchtext, Abbruchsignal. Ausgabe: Vorschläge mit Quellenhinweis (oder ApiFehler). */
export async function adressVorschlaege(q: string, signal: AbortSignal): Promise<{ vorschlaege: Vorschlag[]; attribution: string }> {
  return json(await fetch(`/api/adressen/vorschlaege?q=${encodeURIComponent(q)}`, { signal }));
}

export type Ladezustand<T> =
  | { status: "laden" }
  | { status: "fehler"; meldung: string; http?: number }
  | { status: "bereit"; daten: T };

/**
 * Lädt JSON von der API und hält den Zustand (laden, fehler, bereit).
 * Eingabe: Pfad wie „/api/projekte“ (null = nichts laden). Ausgabe: [Zustand, neu laden].
 */
export function useApi<T>(pfad: string | null): [Ladezustand<T>, () => void] {
  const [zustand, setZustand] = useState<Ladezustand<T>>({ status: "laden" });
  const [versuch, setVersuch] = useState(0);
  useEffect(() => {
    if (pfad === null) return;
    // Antworten veralteter Anfragen verwerfen, falls sich der Pfad inzwischen geändert hat
    let gueltig = true;
    setZustand({ status: "laden" });
    fetch(pfad)
      .then((antwort) => json<T>(antwort))
      .then((daten) => gueltig && setZustand({ status: "bereit", daten }))
      .catch((e: Error) => gueltig && setZustand({ status: "fehler", meldung: e.message, http: e instanceof ApiFehler ? e.status : undefined }));
    return () => {
      gueltig = false;
    };
  }, [pfad, versuch]);
  return [zustand, useCallback(() => setVersuch((v) => v + 1), [])];
}

/** ISO-Datum als TT.MM.JJJJ. Eingabe: „2026-11-04“. Ausgabe: „04.11.2026“. */
export function datum(iso: string): string {
  const [j, m, t] = iso.split("-");
  return `${t}.${m}.${j}`;
}
