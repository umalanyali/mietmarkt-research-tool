// Prüft die Adresssuche (Combobox-Logik), unabhängig von einer Seite.
import { act, renderHook } from "@testing-library/react";
import { useAdressSuche } from "../entwuerfe/gemeinsam/hooks";

describe("useAdressSuche", () => {
  it("lässt ein vorbelegtes Feld vollständig leeren", () => {
    const { result } = renderHook(() => useAdressSuche(() => {}, "Lindenallee 30, 12345 Musterstadt"));
    expect(result.current.feld.value).toBe("Lindenallee 30, 12345 Musterstadt");
    act(() => result.current.feld.onChange({ target: { value: "" } } as React.ChangeEvent<HTMLInputElement>));
    expect(result.current.feld.value).toBe("");
  });
});
