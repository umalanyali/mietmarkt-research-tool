// Prüft die synthetischen Beispieldaten und die Design-Tokens gegen die Regeln aus CLAUDE.md.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { comps } from "../daten/beispiel";

describe("Beispieldaten", () => {
  // Regel: Anfragen je Monat erst ab 7 Tagen online, sonst ist der Wert nicht belastbar
  it("enthalten keine Anfragen je Monat unter 7 Tagen online", () => {
    for (const c of comps) if (c.tage < 7) expect(c.anfragenMonat).toBeNull();
  });

  // Regel 5: kein Blau, Lila, Türkis oder Mint – geprüft über den Farbton gesättigter Farben
  it("verwenden kein Blau, Lila oder Türkis in den Design-Tokens", () => {
    const css = readFileSync(resolve(__dirname, "../entwuerfe/d/d.css"), "utf8");
    const farben = [...css.matchAll(/#([0-9a-f]{6})\b/gi)].map((m) => m[1]);
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
});
