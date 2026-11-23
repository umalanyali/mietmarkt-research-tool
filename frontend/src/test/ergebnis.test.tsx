// Prüft die Ergebniskarte nach einem fertigen Lauf (aufgezeichneter Fake-Lauf): Mietansatz je Basis, Befunde,
// Unterlagen, Kosten und die Export-Links, die vorher fehlten (PowerPoint-Export war im Browser nicht erreichbar).
import { fireEvent, render, screen, within } from "@testing-library/react";
import aufzeichnung from "./aufzeichnung.json";
import { Ergebniskarte } from "../komponenten/Ergebniskarte";
import { LEER, verarbeite, type Ereignis, type LaufZustand } from "../lauf";

/** Endstand des aufgezeichneten Laufs. Ausgabe: Zustand wie nach „fertig“ im Browser. */
function endstand(): LaufZustand {
  return [...aufzeichnung.bis_freigabe, ...aufzeichnung.nach_freigabe].reduce((z, e) => verarbeite(z, e as Ereignis, 0), LEER);
}

describe("Ergebniskarte", () => {
  it("verlinkt Markdown und PowerPoint des Laufs als Download", () => {
    render(<Ergebniskarte laufId="abc123" zustand={endstand()} />);
    const pptx = screen.getByRole("link", { name: "PowerPoint" });
    expect(pptx).toHaveAttribute("href", "/api/laeufe/abc123/bericht.pptx");
    expect(pptx).toHaveAttribute("download");
    expect(screen.getByRole("link", { name: "Markdown" })).toHaveAttribute("href", "/api/laeufe/abc123/bericht.md");
  });

  it("zeigt den freigegebenen Mietansatz je Basis mit Fortschreibung, Befunde und Kosten", () => {
    const z = endstand();
    render(<Ergebniskarte laufId="abc123" zustand={z} />);
    const tabelle = screen.getByRole("table", { name: "Freigegebener Mietansatz" });
    const zeilen = within(tabelle).getAllByRole("row");
    expect(zeilen.map((r) => r.textContent)).toEqual([
      expect.stringContaining("fortgeschrieben"),
      expect.stringMatching(/Regelgeschoss\/EG.*€\/m²/),
      expect.stringMatching(/Dachgeschoss.*€\/m²/),
    ]);
    const befunde = (z.bericht as { befunde: unknown[] }).befunde;
    expect(screen.getByRole("heading", { name: `Befunde der Prüfung (${befunde.length})` })).toBeInTheDocument();
    expect(screen.getByText(/Kosten des Laufs/)).toHaveTextContent(/\d+,\d{2} €/);
    expect(screen.getByText(/Keine Unterlagen ausgewertet/)).toBeInTheDocument();
  });

  it("nennt, was aus den Unterlagen übernommen wurde", () => {
    const z = endstand();
    z.schritte = [...z.schritte, { agent: "expose", status: "fertig", text: "talblick.pdf: baujahr 2025 Jahr [Quelle: talblick.pdf, S. 1]; Balkon [Quelle: talblick.pdf, S. 2]", werkzeuge: [], start: null, dauerS: null, tokens: 0, kostenEur: 0 }];
    render(<Ergebniskarte laufId="abc123" zustand={z} />);
    // Quellenangaben kurz als Fundstelle, der Dateiname steht einmal vorn
    const zeile = screen.getByText("talblick.pdf").closest("li")!;
    expect(zeile).toHaveTextContent("talblick.pdf baujahr 2025 Jahr (S. 1); Balkon (S. 2)");
  });

  it("„Bericht ansehen“ klappt den Bericht mit Abschnitten und Fußnoten auf", () => {
    render(<Ergebniskarte laufId="abc123" zustand={endstand()} />);
    const knopf = screen.getByRole("button", { name: "Bericht ansehen" });
    expect(knopf).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(knopf);
    expect(knopf).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("heading", { name: "Mietansatz" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Herkunft der Zahlen" })).toBeInTheDocument();
  });

  it("zeigt bei Abbruch den Grund statt der Export-Links", () => {
    render(<Ergebniskarte laufId="abc123" zustand={{ ...LEER, ende: "abgebrochen", meldung: "Budget erreicht", kostenEur: 0.5 }} />);
    expect(screen.getByText(/Budget erreicht/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "PowerPoint" })).toBeNull();
  });

  it("übersteht scrollIntoView, das ein Promise liefert (Chrome mit „smooth“), auch beim Entfernen", () => {
    const vorher = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = vi.fn(() => Promise.resolve()) as unknown as typeof vorher;
    try {
      const { unmount } = render(<Ergebniskarte laufId="abc123" zustand={endstand()} />);
      expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
      expect(() => unmount()).not.toThrow();
    } finally {
      Element.prototype.scrollIntoView = vorher;
    }
  });
});
