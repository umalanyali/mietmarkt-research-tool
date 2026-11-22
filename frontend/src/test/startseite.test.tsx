// Prüft die Startseite: Suche mit Vorschlägen per Tastatur, Datenstand, zuletzt analysierte Projekte, Filter.
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { Startseite } from "../seiten/Startseite";


// Antworten der API wie aus dem Demo-Datensatz (gekürzt)
const PROJEKT = { id: 1, name: "Lindenquartier", adresse: "Lindenallee 30", plz: "12345", ort: "Musterstadt", ortsteil: "Nordstadt",
  lat: 51.3, lon: 9.4, stichtag: "2026-11-04", analysiert_am: "2026-11-11", segment: "Wohnen · Neubau", umkreis_km: 2, vermarktung: "Miete" };
const VORSCHLAEGE = [
  { label: "Lindenallee 30, 12345 Musterstadt", strasse: "Lindenallee 30", plz: "12345", ort: "Musterstadt", ortsteil: "Nordstadt", lat: 51.3, lon: 9.4 },
  { label: "Lindenallee 42, 12345 Musterstadt", strasse: "Lindenallee 42", plz: "12345", ort: "Musterstadt", ortsteil: "Nordstadt", lat: 51.3, lon: 9.4 },
];
const ANTWORTEN: Record<string, unknown> = {
  "/api/adressen/vorschlaege?q=Linden": { vorschlaege: VORSCHLAEGE, attribution: "© OpenStreetMap-Mitwirkende" },
  "/api/projekte": [PROJEKT],
  "/api/projekte/1": { ...PROJEKT, quellen: [{ id: 1, name: "RIWIS", art: "datei", datei: "x.png", stand: "11/2026", abgerufen_am: "2026-11-11", seite: null }] },
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((pfad: string, init?: RequestInit) =>
      Promise.resolve({ ok: true, status: init?.method === "POST" ? 201 : 200, json: () => Promise.resolve(init?.method === "POST" ? { ...PROJEKT, id: 7 } : ANTWORTEN[pfad]) }),
    ),
  );
});

afterEach(() => vi.unstubAllGlobals());

/** Rendert die Startseite in einem Test-Router. Eingabe: keine. Ausgabe: Render-Ergebnis von Testing Library. */
function zeige() {
  return render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<Startseite />} />
        <Route path="/analyse/:id" element={<p>Analyse geöffnet</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Startseite", () => {
  it("zeigt Suche, Datenstand und zuletzt analysierte Projekte aus der API", async () => {
    zeige();
    expect(screen.getByRole("combobox", { name: "Adresse" })).toBeInTheDocument();
    expect(await screen.findByText(/Datenstand Musterstadt-Nordstadt/)).toBeInTheDocument();
    expect(screen.getByText("Lindenquartier")).toBeInTheDocument();
    expect(screen.getByText("11/2026")).toBeInTheDocument();
  });

  it("meldet einen nicht erreichbaren Server mit Ausweg", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("Failed to fetch"))));
    zeige();
    expect(await screen.findByText("Backend nicht erreichbar")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Erneut versuchen" })).toBeInTheDocument();
  });

  it("Vorschlag per Tastatur wählen legt das Projekt an und öffnet die Analyse", async () => {
    zeige();
    const feld = screen.getByRole("combobox", { name: "Adresse" });
    fireEvent.change(feld, { target: { value: "Linden" } });
    const optionen = await screen.findAllByRole("option");
    expect(optionen[0]).toHaveTextContent("Nordstadt");
    expect(screen.getByText("© OpenStreetMap-Mitwirkende")).toBeInTheDocument();
    fireEvent.keyDown(feld, { key: "ArrowDown" });
    expect(optionen[1]).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(feld, { key: "Enter" });
    expect(await screen.findByText("Analyse geöffnet")).toBeInTheDocument();
    const post = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === "POST")!;
    expect(JSON.parse(post[1]!.body as string).label).toBe("Lindenallee 42, 12345 Musterstadt");
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
