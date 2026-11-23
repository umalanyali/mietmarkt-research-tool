// Prüft die Farben gegen CLAUDE.md Regel 5 (kein Blau, Lila, Türkis oder Mint) und dass Farbwerte nur in
// stil/tokens.css stehen (Ausnahme: der Kartenstil, denn MapLibre zeichnet auf Canvas und kennt keine CSS-Variablen).
import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const lesen = (d: string) => readFileSync(resolve(__dirname, d), "utf8");

describe("Farben", () => {
  it("verwenden kein Blau, Lila oder Türkis in Design-Tokens und Kartenstil", () => {
    const css = ["../stil/tokens.css", "../komponenten/kartenstil.ts"].map(lesen).join("\n");
    const farben = [...css.matchAll(/#([0-9a-f]{6})\b/gi)].map((m) => m[1]);
    expect(farben.length).toBeGreaterThan(10);
    for (const hex of farben) {
      const [r, g, b] = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
      const max = Math.max(r, g, b);
      const min = Math.min(r, g, b);
      const d = max - min;
      const l = (max + min) / 2;
      const s = d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1));
      if (s < 0.12) continue; // Neutraltöne
      let h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
      h = (h * 60 + 360) % 360;
      // Türkis/Mint, Blau und Lila liegen etwa zwischen 160° und 320°
      expect(h > 160 && h < 320, `#${hex} Farbton ${Math.round(h)}°`).toBe(false);
    }
  });

  it("stehen nur in tokens.css", () => {
    const dateien = [
      ...["app.css", "basis.css"].map((d) => `../stil/${d}`),
      ...["komponenten", "seiten"].flatMap((o) => readdirSync(resolve(__dirname, `../${o}`)).map((d) => `../${o}/${d}`)),
    ].filter((d) => !d.endsWith("kartenstil.ts"));
    for (const d of dateien) expect(lesen(d), d).not.toMatch(/#[0-9a-f]{3,6}\b|rgba?\(|hsla?\(/i);
  });
});
