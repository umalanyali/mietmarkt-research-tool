// Prüft den Upload eigener Unterlagen: mehrere Dateien, Status je Datei, KI-Häkchen für alle und je Datei, Ordner per Drag & Drop.
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { Unterlagen, dateienAusEintraegen } from "../komponenten/Unterlagen";

/** Datei für Tests. Eingabe: Name. Ausgabe: File mit kurzem Inhalt. */
const datei = (name: string) => new File(["x"], name);

const WOHNFLAECHE = { wert: 72.5, einheit: "m²", herkunft: "import", quelle_id: 9, rechenweg_text: "a.pdf, S. 1: „Wohnfläche 72,5 m²“", fundstelle: "S. 1" };
const TREFFER = [{ datei: "a.pdf", seite: 3, ausschnitt: "Lange Einleitung ohne Bezug. ".repeat(20) + "Jede Wohnung hat eine Wallbox in der Tiefgarage." }];

/** Antwort des Backends auf einen Upload. Eingabe: Dateiname, KI-Freigabe. Ausgabe: DokumentAus (PDF mit Exposé-Feldern). */
function antwort(name: string, ki: boolean) {
  const bild = name.endsWith(".png");
  const expose = bild || name.endsWith(".txt") ? null : {
    felder: { wohnflaeche: WOHNFLAECHE, kaltmiete: null, zimmer: null, baujahr: null },
    ausstattung: [{ merkmal: "Balkon", fundstelle: "S. 2", herkunft: "import" }],
  };
  return { id: 1, dateiname: name, art: bild ? "png" : "pdf", seiten: bild ? 0 : 2, abschnitte: 3, ki_freigabe: ki, expose };
}

/** Gesendete Uploads: Dateiname und KI-Freigabe je POST. */
function gesendet() {
  return vi.mocked(fetch).mock.calls.filter(([, init]) => init).map(([, init]) => {
    const f = init!.body as FormData;
    return [(f.get("datei") as File).name, f.get("ki_freigabe")];
  });
}

beforeEach(() => {
  // „kaputt.pdf“ lehnt das Backend mit Grund ab, alle anderen nimmt es an
  vi.stubGlobal(
    "fetch",
    vi.fn((pfad: string, init?: RequestInit) => {
      if (!init) return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(pfad.includes("q=Wallbox") ? TREFFER : []) });
      const f = init.body as FormData;
      const name = (f.get("datei") as File).name;
      const ok = name !== "kaputt.pdf";
      return Promise.resolve({
        ok,
        status: ok ? 201 : 422,
        json: () => Promise.resolve(ok ? antwort(name, f.get("ki_freigabe") === "true") : { detail: "PDF ist nicht lesbar" }),
      });
    }),
  );
});

afterEach(() => vi.unstubAllGlobals());

describe("Unterlagen", () => {
  it("lädt mehrere Dateien einzeln hoch; ein Fehler stoppt die anderen nicht", async () => {
    render(<Unterlagen projektId={1} />);
    const wahl = screen.getByLabelText(/Dateien wählen/);
    expect(wahl).toHaveAttribute("multiple");
    fireEvent.change(wahl, { target: { files: [datei("a.pdf"), datei("kaputt.pdf"), datei("c.txt")] } });
    fireEvent.click(screen.getByRole("button", { name: "3 Dateien hochladen" }));

    const zeilen = await screen.findAllByRole("listitem");
    await waitFor(() => expect(within(zeilen[2]).getByText(/fertig/)).toBeInTheDocument());
    expect(within(zeilen[0]).getByText(/fertig · 2 Seiten/)).toBeInTheDocument();
    expect(within(zeilen[1]).getByText("abgelehnt: PDF ist nicht lesbar")).toBeInTheDocument();
    expect(within(zeilen[2]).getByText(/fertig · 2 Seiten/)).toBeInTheDocument();
    expect(gesendet().map(([n]) => n)).toEqual(["a.pdf", "kaputt.pdf", "c.txt"]);
  });

  it("KI-Häkchen gilt für die ganze Auswahl und lässt sich je Datei ändern", async () => {
    render(<Unterlagen projektId={1} />);
    fireEvent.click(screen.getByLabelText(/KI darf alle gewählten Dateien lesen/));
    fireEvent.change(screen.getByLabelText(/Dateien wählen/), { target: { files: [datei("a.pdf"), datei("b.png")] } });
    fireEvent.click(screen.getByLabelText("KI darf b.png lesen"));
    fireEvent.click(screen.getByRole("button", { name: "2 Dateien hochladen" }));
    await waitFor(() => expect(gesendet()).toEqual([["a.pdf", "true"], ["b.png", "false"]]));
    // Nach dem Hochladen ist die Freigabe der Datei festgelegt
    await waitFor(() => expect(screen.getByLabelText("KI darf a.pdf lesen")).toBeDisabled());
  });

  it("nimmt Dateien per Drag & Drop an", async () => {
    render(<Unterlagen projektId={1} />);
    const flaeche = screen.getByText(/hierher ziehen/).closest("div")!;
    await act(async () => {
      fireEvent.drop(flaeche, { dataTransfer: { items: [], files: [datei("a.pdf"), datei("b.txt")] } });
    });
    expect(screen.getAllByRole("listitem").map((z) => z.textContent)).toEqual([expect.stringContaining("a.pdf"), expect.stringContaining("b.txt")]);
  });

  it("liest Ordner rekursiv und überspringt versteckte Dateien", async () => {
    /** Datei-Eintrag wie von webkitGetAsEntry. */
    const eintrag = (name: string) => ({ isFile: true, isDirectory: false, name, file: (ok: (f: File) => void) => ok(datei(name)) });
    /** Ordner-Eintrag; readEntries liefert erst alles, dann eine leere Liste (wie im Browser in Stapeln). */
    const ordner = (name: string, inhalt: unknown[]) => ({
      isFile: false, isDirectory: true, name,
      createReader: () => {
        let gelesen = false;
        return { readEntries: (ok: (e: unknown[]) => void) => { ok(gelesen ? [] : inhalt); gelesen = true; } };
      },
    });
    const baum = ordner("unterlagen", [eintrag("a.pdf"), eintrag(".DS_Store"), ordner("bilder", [eintrag("b.png")])]);
    const dateien = await dateienAusEintraegen([baum as unknown as FileSystemEntry]);
    expect(dateien.map((f) => f.name)).toEqual(["a.pdf", "b.png"]);
  });

  it("zeigt die Exposé-Felder aus dem Parser sofort; Leeres und Bilder liest erst ein Lauf mit KI", async () => {
    render(<Unterlagen projektId={1} />);
    fireEvent.change(screen.getByLabelText(/Dateien wählen/), { target: { files: [datei("a.pdf"), datei("b.png")] } });
    fireEvent.click(screen.getByLabelText("KI darf a.pdf lesen"));
    fireEvent.click(screen.getByRole("button", { name: "2 Dateien hochladen" }));
    const [pdfZeile, bildZeile] = await screen.findAllByRole("listitem");
    fireEvent.click(await within(pdfZeile).findByText("Exposé-Felder"));
    expect(within(pdfZeile).getByText("72,5 m²")).toBeInTheDocument();
    fireEvent.click(within(pdfZeile).getByRole("button", { name: "Herkunft: import" }));
    expect(within(pdfZeile).getByRole("note")).toHaveTextContent("Fundstelle: S. 1");
    expect(within(pdfZeile).getAllByText("wird beim nächsten Lauf gelesen")).toHaveLength(3);
    expect(within(pdfZeile).getByText("Balkon · S. 2 · import")).toBeInTheDocument();
    // Bild ohne KI-Freigabe: der Lauf liest es nicht, also kein Versprechen
    expect(await within(bildZeile).findByText(/Bilder liest nur die KI/)).toBeInTheDocument();
  });

  it("sucht in den Unterlagen und zeigt Datei, Seite und den Ausschnitt um den Treffer", async () => {
    render(<Unterlagen projektId={1} />);
    fireEvent.change(screen.getByRole("searchbox", { name: "In Unterlagen suchen" }), { target: { value: "Wallbox" } });
    fireEvent.submit(screen.getByRole("search"));
    const treffer = await screen.findByText(/a\.pdf · S\. 3/);
    const text = treffer.closest("li")!.textContent!;
    expect(text).toContain("Wallbox in der Tiefgarage");
    expect(text.length).toBeLessThan(300);
    expect(vi.mocked(fetch)).toHaveBeenCalledWith("/api/projekte/1/dokumente/suche?q=Wallbox");
    fireEvent.change(screen.getByRole("searchbox", { name: "In Unterlagen suchen" }), { target: { value: "Sauna" } });
    fireEvent.submit(screen.getByRole("search"));
    expect(await screen.findByText("Keine Treffer.")).toBeInTheDocument();
  });
});
