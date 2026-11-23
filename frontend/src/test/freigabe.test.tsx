// Prüft die Freigabe-Karte (mit dem aufgezeichneten Vorschlag eines Fake-Laufs) und das Herkunfts-Kennzeichen.
import { fireEvent, render, screen } from "@testing-library/react";
import aufzeichnung from "./aufzeichnung.json";
import { FreigabeKarte } from "../komponenten/Bausteine";
import { HerkunftMarke } from "../komponenten/Herkunft";
import type { Ereignis } from "../lauf";

const vorschlag = (aufzeichnung.bis_freigabe as Ereignis[]).at(-1)!.vorschlag;

/** Rendert die Karte mit einem Mock als Absende-Handler. Ausgabe: Mock. */
function karte() {
  const senden = vi.fn();
  render(<FreigabeKarte vorschlag={vorschlag} onSenden={senden} sendet={false} />);
  return senden;
}

describe("Freigabe-Karte", () => {
  it("zeigt Vorschlag, Begründung und Herleitungskette", () => {
    karte();
    expect(screen.getByText("Mietansatz übernehmen?")).toBeInTheDocument();
    expect(screen.getByText(/17,26 €\/m²/, { selector: "dd" })).toBeInTheDocument();
    expect(screen.getByText(vorschlag.begruendung)).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Herleitung Regelgeschoss/EG" })).toHaveTextContent("Energiestandard");
    expect(screen.getByText("+0,30 €/m²", { exact: false })).toBeInTheDocument();
  });

  it("nimmt an, mit optionalem Kommentar", () => {
    const senden = karte();
    fireEvent.click(screen.getByRole("button", { name: "Annehmen" }));
    expect(senden).toHaveBeenCalledWith({ aktion: "annehmen", kommentar: undefined });
  });

  it("lehnt nur mit Kommentar ab", () => {
    const senden = karte();
    const ablehnen = screen.getByRole("button", { name: "Ablehnen" });
    expect(ablehnen).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Kommentar für den Agenten/), { target: { value: "Zuschlag zu hoch" } });
    fireEvent.click(ablehnen);
    expect(senden).toHaveBeenCalledWith({ aktion: "ablehnen", kommentar: "Zuschlag zu hoch" });
  });

  it("schickt beim Ändern nur geänderte Teile", () => {
    const senden = karte();
    fireEvent.click(screen.getByRole("button", { name: "Ändern" }));
    const uebernehmen = screen.getByRole("button", { name: "Änderung übernehmen" });
    expect(uebernehmen).toBeDisabled(); // noch nichts geändert
    fireEvent.change(screen.getAllByLabelText("Energiestandard")[0], { target: { value: "0,15" } });
    fireEvent.click(uebernehmen);
    expect(senden).toHaveBeenCalledWith({
      aktion: "aendern",
      aenderungen: { regel_eg: { anpassungen: [{ name: "Energiestandard", betrag: 0.15, begruendung: "Effizienzhaus 40 statt 55 bei den Comps" }] } },
      kommentar: undefined,
    });
  });
});

describe("Herkunfts-Kennzeichen", () => {
  const quelle = { id: 3, name: "RIWIS", art: "datei", datei: "riwis.png", stand: "11/2026", abgerufen_am: "2026-11-11", seite: null };

  it("zeigt beim Klick Quelle und Rechenweg, Escape schließt", () => {
    render(<HerkunftMarke wert={{ herkunft: "berechnet", rechenweg_text: "9.940 € / 586 m² = 16,96 €/m²" }} quelle={quelle} />);
    const knopf = screen.getByRole("button", { name: "Herkunft: berechnet" });
    expect(knopf).toHaveTextContent("Ber");
    expect(screen.queryByRole("note")).toBeNull();
    fireEvent.click(knopf);
    expect(screen.getByRole("note")).toHaveTextContent("Quelle: RIWIS · Stand 11/2026");
    expect(screen.getByRole("note")).toHaveTextContent("Rechenweg: 9.940 € / 586 m² = 16,96 €/m²");
    fireEvent.keyDown(knopf, { key: "Escape" });
    expect(screen.queryByRole("note")).toBeNull();
  });

  it("zeigt bei abgelesenen Werten Fundstelle und Bildausschnitt", () => {
    render(<HerkunftMarke wert={{ herkunft: "abgelesen", rechenweg_text: "", fundstelle: "S. 2", ausschnitt: [10, 20, 30, 40] }} />);
    fireEvent.click(screen.getByRole("button", { name: "Herkunft: abgelesen" }));
    expect(screen.getByRole("note")).toHaveTextContent("Fundstelle: S. 2");
    expect(screen.getByRole("note")).toHaveTextContent("10 × 20 × 30 × 40 px");
  });
});
