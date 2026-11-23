// Prüft die Stream-Verarbeitung mit Ereignissen, die einmal vom Backend mit Fake-Modell aufgezeichnet wurden
// (backend/tests/fake_server.py): Zeitleiste, tokenweiser Text, Freigabe, Endstand und das SSE-Format selbst.
import aufzeichnung from "./aufzeichnung.json";
import { LEER, sseLesen, verarbeite, type Ereignis, type LaufZustand } from "../lauf";

/** Spielt Ereignisse nacheinander ein, je Ereignis eine Sekunde später. Eingabe: Start, Ereignisse. Ausgabe: Zustand. */
function abspielen(start: LaufZustand, ereignisse: Ereignis[]): LaufZustand {
  return ereignisse.reduce((z, e, i) => verarbeite(z, e, i * 1000), start);
}

const bisFreigabe = aufzeichnung.bis_freigabe as Ereignis[];
const nachFreigabe = aufzeichnung.nach_freigabe as Ereignis[];

describe("Stream-Verarbeitung", () => {
  it("baut die Zeitleiste bis zur Freigabe auf", () => {
    const z = abspielen(LEER, bisFreigabe);
    expect(z.schritte.map((s) => [s.agent, s.status])).toEqual([
      ["standort", "fertig"],
      ["supervisor", "fertig"], // meldet sich erst mit seinen Kosten, nach dem ersten Agentenstart
      ["marktdaten", "fertig"],
      ["mietansatz", "fertig"],
      ["freigabe", "rueckfrage"],
    ]);
    const markt = z.schritte.find((s) => s.agent === "marktdaten")!;
    expect(markt.werkzeuge[0]).toMatchObject({ name: "kennzahlen", argumente: {} });
    expect(markt.werkzeuge[0].ergebnis).toHaveProperty("comps");
    expect(markt.tokens).toBe(300); // zwei Aufrufe à 100 + 50 Token
    expect(markt.dauerS).toBeGreaterThan(0);
    expect(z.offen?.art).toBe("mietansatz");
    if (z.offen?.art === "mietansatz") expect(z.offen.vorschlag.herleitungen.regel_eg?.schritte[1].name).toBe("Energiestandard");
    expect(z.kostenEur).toBeCloseTo(bisFreigabe.filter((e) => e.typ === "kosten").reduce((s, e) => s + e.eur.wert, 0));
    expect(z.ende).toBeNull();
  });

  it("zeigt laufenden Text Stück für Stück", () => {
    const erstesStueck = bisFreigabe.findIndex((e) => e.typ === "text");
    const z = abspielen(LEER, bisFreigabe.slice(0, erstesStueck + 2));
    const standort = z.schritte.find((s) => s.agent === "standort")!;
    expect(standort.status).toBe("arbeitet");
    expect(standort.text).toBe("Der Standort ");
  });

  it("läuft nach der Freigabe bis zum Bericht weiter", () => {
    const z = abspielen(abspielen(LEER, bisFreigabe), nachFreigabe);
    expect(z.offen).toBeNull();
    expect(z.ende).toBe("fertig");
    expect(z.schritte.find((s) => s.agent === "freigabe")).toMatchObject({ status: "fertig", text: "angenommen" });
    expect(z.schritte.find((s) => s.agent === "pruefung")?.text).toBe("hinweis: Befund hinweis.");
    expect(z.herleitungen?.regel_eg?.ergebnis.wert).toBeCloseTo(17.26, 2);
    expect(z.bericht).not.toBeNull();
    expect(z.kostenEur).toBe(nachFreigabe.at(-1)!.kosten_eur);
  });

  it("baut einen beendeten Lauf allein aus dem Endstand auf", () => {
    const z = verarbeite(LEER, nachFreigabe.at(-1)!, 0);
    expect(z.schritte.map((s) => s.agent)).toEqual(["standort", "marktdaten", "mietansatz", "pruefung"]);
    expect(z.schritte.every((s) => s.status === "fertig")).toBe(true);
    expect(z.herleitungen?.regel_eg).toBeDefined();
  });

  it("markiert arbeitende Agenten bei einem Fehler", () => {
    const z = abspielen(LEER, [bisFreigabe[0], { typ: "fehler", meldung: "Lauf unterbrochen" }]);
    expect(z.schritte.find((s) => s.agent === "standort")?.status).toBe("fehler");
    expect(z.meldung).toBe("Lauf unterbrochen");
  });

  it("liest SSE-Blöcke, auch wenn sie mitten im Block geteilt ankommen", async () => {
    const text = 'event: text\ndata: {"typ": "text", "agent": "standort", "text": "Hallo "}\n\nevent: fertig\ndata: {"typ": "fertig"}\n\n';
    const strom = new ReadableStream({
      start(c) {
        const bytes = new TextEncoder().encode(text);
        c.enqueue(bytes.slice(0, 30));
        c.enqueue(bytes.slice(30));
        c.close();
      },
    });
    const gelesen: Ereignis[] = [];
    for await (const e of sseLesen(new Response(strom))) gelesen.push(e);
    expect(gelesen.map((e) => e.typ)).toEqual(["text", "fertig"]);
    expect(gelesen[0].text).toBe("Hallo ");
  });
});
