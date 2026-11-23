// Prüft, dass useApi bei einem Dienstausfall (503) den genauen Grund aus dem Backend weitergibt.
import { renderHook, waitFor } from "@testing-library/react";
import { useApi } from "../api";

afterEach(() => vi.unstubAllGlobals());

describe("useApi", () => {
  it("übernimmt bei 503 die Meldung des Backends samt Statuscode des Dienstes", async () => {
    const detail = "Overpass nicht erreichbar: overpass-api.de: HTTP 406 Not Acceptable";
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, status: 503, json: () => Promise.resolve({ detail }) })));
    const { result } = renderHook(() => useApi<unknown>("/api/projekte/1/umfeld"));
    await waitFor(() => expect(result.current[0]).toEqual({ status: "fehler", meldung: detail, http: 503 }));
  });
});
