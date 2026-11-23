// Sicherheitsbefund M1: Modelltext darf über Markdown keine Bilder nachladen und keine klickbaren Links setzen.
import { render } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { Markdown } from "../komponenten/Markdown";

describe("Markdown aus Modelltext", () => {
  it("rendert keine Bilder, auch nicht von fremder Adresse", () => {
    const { container } = render(<Markdown text={"Begründung ![x](https://fremd.example/p?d=1) Ende"} />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("Ende");
  });

  it("zeigt Links nur als Text: Daten in der URL sollen nicht per Klick abfließen", () => {
    const { container } = render(<Markdown text={"Siehe [Quelle](https://fremd.example/x?miete=1) Ende"} />);
    expect(container.querySelector("a")).toBeNull();
    expect(container.textContent).toContain("Siehe Quelle Ende");
  });

  it("index.html hat eine strenge CSP für Bilder und Verbindungen", () => {
    const html = readFileSync("index.html", "utf8");
    const csp = html.match(/http-equiv="Content-Security-Policy" content="([^"]+)"/)?.[1] ?? "";
    expect(csp).toMatch(/img-src 'self'[^;]*;/);
    expect(csp).toMatch(/connect-src 'self'[^;]*;/);
    expect(csp).not.toMatch(/(img|connect)-src[^;]*(\*|https:(?!\/\/))/); // keine Platzhalter für beliebige Hosts
  });
});
