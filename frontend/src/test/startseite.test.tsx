// Prüft die Startseite: Suche mit Vorschlägen per Tastatur, Datenstand, zuletzt analysierte Projekte, Filter.
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { StartD } from "../entwuerfe/d/RichtungD";

// MapLibre braucht WebGL und Browser-APIs, die jsdom nicht hat; die Startseite zeigt ohnehin keine Karte.
vi.mock("maplibre-gl", () => ({ default: {} }));

/** Rendert die Startseite in einem Test-Router. Eingabe: keine. Ausgabe: Render-Ergebnis von Testing Library. */
function zeige() {
  return render(
    <MemoryRouter>
      <StartD />
    </MemoryRouter>,
  );
}

describe("Startseite", () => {
  it("zeigt Suche, Datenstand und zuletzt analysierte Projekte", () => {
    zeige();
    expect(screen.getByRole("combobox", { name: "Adresse" })).toBeInTheDocument();
    expect(screen.getByText(/Datenstand Musterstadt-Nordstadt/)).toBeInTheDocument();
    expect(screen.getByText("Lindenquartier")).toBeInTheDocument();
  });

  it("Vorschläge lassen sich per Tastatur wählen und zeigen den Ortsteil", () => {
    zeige();
    const feld = screen.getByRole("combobox", { name: "Adresse" });
    fireEvent.change(feld, { target: { value: "Linden" } });
    const optionen = screen.getAllByRole("option");
    expect(optionen.length).toBeGreaterThan(1);
    expect(optionen[0]).toHaveTextContent("Nordstadt");
    fireEvent.keyDown(feld, { key: "ArrowDown" });
    expect(optionen[1]).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(feld, { key: "Enter" });
    expect(feld).toHaveValue("Lindenallee 42, 12345 Musterstadt");
  });

  it("Filter haben genau eine Auswahl je Gruppe", () => {
    zeige();
    const umkreis = screen.getByRole("radiogroup", { name: "Umkreis" });
    const fuenf = screen.getByRole("radio", { name: "Umkreis 5 km" });
    fireEvent.click(fuenf);
    expect(fuenf).toHaveAttribute("aria-checked", "true");
    expect(umkreis.querySelectorAll('[aria-checked="true"]')).toHaveLength(1);
  });
});
