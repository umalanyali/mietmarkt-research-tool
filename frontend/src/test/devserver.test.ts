// @vitest-environment node
// Sicherheitsregeln für den Dev-Server (Befund S1): aktuelles Vite und kein CORS, damit fremde Websites die API nicht lesen.
import viteKonfig from "../../vite.config";
import vitePaket from "vite/package.json";

describe("Dev-Server", () => {
  it("nutzt Vite ab 5.4.21 (behebt CVE-2025-30208 und prüft den Host)", () => {
    const [haupt, neben, patch] = vitePaket.version.split(".").map(Number);
    expect(haupt > 5 || (haupt === 5 && (neben > 4 || patch >= 21))).toBe(true);
  });

  it("schaltet CORS aus; der /api-Proxy braucht es nicht", () => {
    expect(viteKonfig.server?.cors).toBe(false);
  });
});
