// Agenten-Lauf im Browser: liest den Ereignisstrom des Backends (Server-Sent Events) und baut daraus die Zeitleiste,
// die offene Freigabe bzw. Rückfrage und den Endstand. Zahlen (Token, €) kommen fertig aus Python; hier wird nur summiert.
import { useCallback, useState } from "react";
import type { Wert } from "./api";

export type AgentStatus = "fertig" | "arbeitet" | "rueckfrage" | "wartet" | "fehler";

export interface Werkzeugaufruf {
  name: string;
  argumente?: unknown;
  ergebnis?: unknown;
}

export interface AgentSchritt {
  agent: string;
  status: AgentStatus;
  text: string;
  werkzeuge: Werkzeugaufruf[];
  start: number | null; // Browser-Uhr in ms; das Backend sendet keine Zeitstempel
  dauerS: number | null;
  tokens: number;
  kostenEur: number;
}

export interface HerleitungsSchritt {
  art: "basis" | "anpassung" | "ergebnis" | "fortschreibung";
  name: string;
  wert: Wert;
  begruendung: string;
}

export interface Herleitung {
  basis: "regel_eg" | "dg";
  schritte: HerleitungsSchritt[];
  ergebnis: Wert;
  fortgeschrieben: Wert | null;
}

export type Herleitungen = Partial<Record<"regel_eg" | "dg", Herleitung>>;

export type Offen =
  | { art: "mietansatz"; vorschlag: { herleitungen: Herleitungen; begruendung: string } }
  | { art: "rueckfrage"; frage: string };

export interface LaufZustand {
  schritte: AgentSchritt[];
  offen: Offen | null;
  herleitungen: Herleitungen | null; // freigegebener Mietansatz
  bericht: Record<string, unknown> | null;
  ende: "fertig" | "abgebrochen" | null;
  meldung: string | null; // Abbruchgrund oder Fehler
  kostenEur: number;
  berichtNeu: boolean; // abgebrochen im Bericht: POST /bericht kann ihn ohne neue Agentenläufe erzeugen
}

export const LEER: LaufZustand = { schritte: [], offen: null, herleitungen: null, bericht: null, ende: null, meldung: null, kostenEur: 0, berichtNeu: false };

// Ein Ereignis, wie es api/main.py sendet; Felder je nach „typ“ (siehe mietmarkt/agenten/ereignisse.py)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Ereignis = { typ: string } & Record<string, any>;

/**
 * Arbeitet ein Ereignis in den Zustand ein (reine Funktion, deshalb ohne React testbar).
 * Eingabe: bisheriger Zustand, Ereignis, aktuelle Zeit in ms. Ausgabe: neuer Zustand.
 */
export function verarbeite(z: LaufZustand, e: Ereignis, jetzt: number): LaufZustand {
  const schritte = z.schritte.map((s) => ({ ...s, werkzeuge: [...s.werkzeuge] }));
  // Schritt des Agenten holen oder anlegen; Prüfung, Bericht und Supervisor melden sich ohne „agent_gestartet“
  const schritt = (agent: string, status: AgentStatus = "arbeitet") => {
    let s = schritte.find((x) => x.agent === agent);
    if (!s) {
      s = { agent, status, text: "", werkzeuge: [], start: jetzt, dauerS: null, tokens: 0, kostenEur: 0 };
      schritte.push(s);
    }
    return s;
  };
  const beenden = (s: AgentSchritt, status: AgentStatus = "fertig") => {
    s.status = status;
    if (s.start !== null) s.dauerS = (jetzt - s.start) / 1000;
  };
  const n = { ...z, schritte };
  switch (e.typ) {
    case "agent_gestartet": {
      // Ein Agent kann im selben Lauf erneut drankommen (z. B. nach abgelehnter Freigabe): dann neu beginnen
      Object.assign(schritt(e.agent), { status: "arbeitet", text: "", start: jetzt, dauerS: null });
      break;
    }
    case "text":
      schritt(e.agent).text += e.text;
      break;
    case "werkzeugaufruf":
      schritt(e.agent).werkzeuge.push({ name: e.werkzeug, argumente: e.argumente });
      break;
    case "werkzeugergebnis": {
      const s = schritt(e.agent);
      const offen = s.werkzeuge.find((w) => w.name === e.werkzeug && w.ergebnis === undefined);
      if (offen) offen.ergebnis = e.ergebnis;
      else s.werkzeuge.push({ name: e.werkzeug, ergebnis: e.ergebnis });
      break;
    }
    case "agent_fertig": {
      const s = schritt(e.agent);
      s.text = e.text;
      beenden(s);
      break;
    }
    case "kosten": {
      const s = schritt(e.agent, "fertig");
      s.tokens += e.eingabe_tokens + e.ausgabe_tokens;
      s.kostenEur += e.eur.wert;
      n.kostenEur = z.kostenEur + e.eur.wert;
      break;
    }
    case "wartet_auf_freigabe":
      n.offen = { art: "mietansatz", vorschlag: e.vorschlag };
      schritt("freigabe", "rueckfrage").status = "rueckfrage";
      break;
    case "wartet_auf_antwort":
      n.offen = { art: "rueckfrage", frage: e.frage };
      schritt("rueckfrage", "rueckfrage").status = "rueckfrage";
      break;
    case "freigabe": {
      n.offen = null;
      n.herleitungen = e.herleitungen;
      const s = schritt("freigabe");
      s.text = { annehmen: "angenommen", aendern: "geändert übernommen", ablehnen: "abgelehnt" }[e.aktion as string] ?? e.aktion;
      beenden(s);
      break;
    }
    case "antwort": {
      n.offen = null;
      const s = schritt("rueckfrage");
      s.text = e.antwort;
      beenden(s);
      break;
    }
    case "pruefung": {
      const s = schritt("pruefung");
      s.text = e.befunde.map((b: { schweregrad: string; text: string }) => `${b.schweregrad}: ${b.text}`).join(" · ") || "keine Befunde";
      beenden(s);
      break;
    }
    case "bericht":
      n.bericht = e;
      beenden(schritt("bericht"));
      break;
    case "abbruch":
      n.meldung = e.grund;
      break;
    case "fehler":
      n.meldung = e.meldung;
      schritte.filter((s) => s.status === "arbeitet").forEach((s) => beenden(s, "fehler"));
      break;
    case "fertig": {
      // Ein beendeter Lauf liefert beim erneuten Abruf nur diesen Endstand: dann die Schritte daraus aufbauen
      for (const [agent, r] of Object.entries(e.ergebnisse as Record<string, { text: string }>)) {
        const s = schritt(agent, "fertig");
        if (s.status === "arbeitet") beenden(s);
        s.text ||= r.text;
      }
      n.ende = e.status;
      n.meldung = e.abbruch ?? z.meldung;
      n.kostenEur = e.kosten_eur;
      n.herleitungen = e.freigabe?.herleitungen ?? z.herleitungen;
      n.bericht = e.bericht ?? z.bericht;
      n.offen = null;
      n.berichtNeu = !!e.bericht_wiederholbar;
      break;
    }
  }
  return n;
}

/**
 * Liest einen SSE-Strom aus einer fetch-Antwort (EventSource kann kein POST, Freigaben senden aber per POST).
 * Eingabe: Antwort. Ausgabe: Ereignisse der Reihe nach, sobald ein Block vollständig ist.
 */
export async function* sseLesen(antwort: Response): AsyncGenerator<Ereignis> {
  const leser = antwort.body!.pipeThrough(new TextDecoderStream()).getReader();
  let puffer = "";
  for (;;) {
    const { value, done } = await leser.read();
    if (done) return;
    puffer += value;
    const bloecke = puffer.split("\n\n");
    puffer = bloecke.pop()!; // der letzte Block kann noch unvollständig sein
    for (const b of bloecke) {
      const daten = b.split("\n").find((z) => z.startsWith("data: "));
      if (daten) yield JSON.parse(daten.slice(6)) as Ereignis;
    }
  }
}

export interface Freigabe {
  aktion: "annehmen" | "aendern" | "ablehnen";
  aenderungen?: Partial<Record<"regel_eg" | "dg", { basiswert?: number; anpassungen?: { name: string; betrag: number; begruendung: string }[] }>>;
  kommentar?: string;
}

/**
 * Hält einen Lauf im Browser: starten, fortsetzen (pausierter Lauf aus der Laufliste), freigeben, antworten,
 * Bericht neu erzeugen.
 * Eingabe: Projekt-ID, Rückruf nach Stromende (z. B. Laufliste neu laden). Ausgabe: Zustand, Lauf-ID, ob gerade
 * gestreamt wird, und die Aktionen.
 */
export function useLauf(projektId: number, nachEnde: () => void) {
  const [zustand, setZustand] = useState<LaufZustand>(LEER);
  const [laufId, setLaufId] = useState<string | null>(null);
  const [aktiv, setAktiv] = useState(false);

  const streamen = useCallback(
    async (anfrage: Promise<Response>) => {
      setAktiv(true);
      try {
        const antwort = await anfrage;
        if (!antwort.ok) {
          const detail = await antwort.json().then((j) => j.detail).catch(() => null);
          setZustand((z) => verarbeite(z, { typ: "fehler", meldung: typeof detail === "string" ? detail : `Server antwortet mit ${antwort.status}` }, Date.now()));
          return;
        }
        for await (const e of sseLesen(antwort)) setZustand((z) => verarbeite(z, e, Date.now()));
      } catch {
        setZustand((z) => verarbeite(z, { typ: "fehler", meldung: "Verbindung zum Server abgerissen. Fortsetzen setzt den Lauf am letzten Schritt fort." }, Date.now()));
      } finally {
        setAktiv(false);
        nachEnde();
      }
    },
    [nachEnde],
  );

  const oeffnen = useCallback(
    (id: string) => {
      setLaufId(id);
      setZustand(LEER);
      return streamen(fetch(`/api/laeufe/${id}/ereignisse`));
    },
    [streamen],
  );

  const starten = useCallback(async () => {
    const antwort = await fetch(`/api/projekte/${projektId}/laeufe`, { method: "POST" });
    if (!antwort.ok) {
      setZustand(verarbeite(LEER, { typ: "fehler", meldung: antwort.status === 503 ? "KI nicht konfiguriert" : `Server antwortet mit ${antwort.status}` }, Date.now()));
      return;
    }
    return oeffnen((await antwort.json()).lauf_id);
  }, [projektId, oeffnen]);

  /** Sendet Freigabe oder Antwort und streamt die Fortsetzung. Eingabe: Pfadende, Inhalt. Ausgabe: Promise. */
  const senden = (ziel: "freigabe" | "antwort", inhalt: object) =>
    streamen(fetch(`/api/laeufe/${laufId}/${ziel}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(inhalt) }));

  return {
    zustand,
    laufId,
    aktiv,
    starten,
    oeffnen,
    freigeben: (f: Freigabe) => senden("freigabe", f),
    antworten: (antwort: string) => senden("antwort", { antwort }),
    berichtNeu: () => streamen(fetch(`/api/laeufe/${laufId}/bericht`, { method: "POST" })),
  };
}
