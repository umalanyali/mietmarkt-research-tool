// Prüft die Adresssuche (Combobox-Logik): Debounce, Mindestlänge, Abbruch alter Anfragen, Dienstausfall.
import { act, renderHook } from "@testing-library/react";
import { useAdressSuche } from "../hooks";

const VORSCHLAG = { label: "Lindenallee 30, 12345 Musterstadt", strasse: "Lindenallee 30", plz: "12345", ort: "Musterstadt", ortsteil: "Nordstadt", lat: 51.3, lon: 9.4 };

/** Simuliert Tippen. Eingabe: Hook-Ergebnis, Text. Ausgabe: keine. */
function tippe(result: { current: ReturnType<typeof useAdressSuche> }, text: string) {
  act(() => result.current.feld.onChange({ target: { value: text } } as React.ChangeEvent<HTMLInputElement>));
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("useAdressSuche", () => {
  it("lässt ein vorbelegtes Feld vollständig leeren, ohne zu suchen", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useAdressSuche(() => {}, "Lindenallee 30, 12345 Musterstadt"));
    expect(result.current.feld.value).toBe("Lindenallee 30, 12345 Musterstadt");
    tippe(result, "");
    expect(result.current.feld.value).toBe("");
    act(() => vi.advanceTimersByTime(500));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("fragt erst ab 3 Zeichen und nur einmal nach 300 ms Tipppause", async () => {
    const fetchMock = vi.fn((_pfad: string) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ vorschlaege: [VORSCHLAG], attribution: "© OpenStreetMap-Mitwirkende" }) }));
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useAdressSuche(() => {}));
    tippe(result, "Li");
    act(() => vi.advanceTimersByTime(500));
    expect(fetchMock).not.toHaveBeenCalled();
    for (const t of ["Lin", "Lind", "Linde"]) {
      tippe(result, t);
      act(() => vi.advanceTimersByTime(100));
    }
    await act(async () => vi.advanceTimersByTimeAsync(300));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/adressen/vorschlaege?q=Linde");
    expect(result.current.vorschlaege[0].ortsteil).toBe("Nordstadt");
    expect(result.current.attribution).toBe("© OpenStreetMap-Mitwirkende");
  });

  it("bricht eine laufende Anfrage ab, wenn weitergetippt wird", async () => {
    const signale: AbortSignal[] = [];
    vi.stubGlobal("fetch", vi.fn((_: string, init: RequestInit) => {
      signale.push(init.signal!);
      return new Promise(() => {}); // antwortet nie
    }));
    const { result } = renderHook(() => useAdressSuche(() => {}));
    tippe(result, "Linden");
    await act(async () => vi.advanceTimersByTimeAsync(300));
    tippe(result, "Lindenallee");
    expect(signale[0].aborted).toBe(true);
  });

  it("meldet einen nicht erreichbaren Dienst (503) als eigenen Zustand", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, status: 503, json: () => Promise.resolve({}) })));
    const { result } = renderHook(() => useAdressSuche(() => {}));
    tippe(result, "Linden");
    await act(async () => vi.advanceTimersByTimeAsync(300));
    expect(result.current.status).toBe("nicht-erreichbar");
  });
});
