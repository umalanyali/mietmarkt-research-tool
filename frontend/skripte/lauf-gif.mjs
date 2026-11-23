// Nimmt einen echten Agenten-Lauf auf dem Demo-Standort als GIF auf: node skripte/lauf-gif.mjs <ziel.gif>
// Kostet einen echten Lauf (Cent-Bereich, Anthropic-Schlüssel nötig). App muss laufen (APP_URL, Standard :5173).
// Ablauf: Startseite → „Demo-Standort öffnen“ → „Analyse starten“ → Freigabe annehmen → Lauf fertig.
// Bilder macht Playwright, das GIF baut Pillow aus dem Backend-venv (kein ffmpeg nötig).
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { chromium } from "playwright-core";

const [ziel] = process.argv.slice(2);
const basis = process.env.APP_URL ?? "http://localhost:5173";
const ordner = mkdtempSync(join(tmpdir(), "lauf-gif-"));
const browser = await chromium.launch({ channel: "chrome", args: ["--enable-unsafe-swiftshader"] });
const seite = await browser.newPage({ viewport: { width: 1440, height: 900 } });
let nr = 0;
let aktiv = true;

/** Macht alle 1,5 s ein Bild, bis „aktiv“ falsch wird. Ausgabe: Promise. */
async function filmen() {
  while (aktiv) {
    await seite.screenshot({ path: join(ordner, `${String(nr++).padStart(4, "0")}.png`) }).catch(() => {});
    await seite.waitForTimeout(1500);
  }
}

await seite.goto(basis, { waitUntil: "networkidle" });
const film = filmen();
await seite.waitForTimeout(1500);
await seite.getByRole("button", { name: "Demo-Standort öffnen" }).click();
await seite.waitForSelector(".marker, .km-comp", { timeout: 20000 }).catch(() => {});
await seite.waitForTimeout(2000);
await seite.getByRole("button", { name: "Analyse starten" }).click();
await seite.getByText("Mietansatz übernehmen?").waitFor({ timeout: 300000 });
await seite.locator("#d-freigabe").scrollIntoViewIfNeeded();
await seite.waitForTimeout(3000);
await seite.getByRole("button", { name: "Annehmen" }).click();
await seite.getByText("freigegeben", { exact: true }).waitFor({ timeout: 300000 });
await seite.getByRole("button", { name: "Details" }).click();
await seite.locator(".d-laufliste").getByText("fertig").waitFor({ timeout: 300000 });
await seite.waitForTimeout(3000);
console.log("Kosten laut Oberfläche:", (await seite.locator(".d-agenten-kosten").textContent())?.trim());
aktiv = false;
await film;
await browser.close();

// Gleiche Bilder hintereinander fallen weg; 960 px breit, 0,7 s je Bild, letztes Bild 4 s
execFileSync("../backend/.venv/bin/python", ["-I", "-c", `
import sys, pathlib
from PIL import Image, ImageChops
bilder, vorher = [], None
for p in sorted(pathlib.Path(sys.argv[1]).glob("*.png")):
    b = Image.open(p).convert("RGB").resize((960, 600), Image.LANCZOS)
    if vorher is None or ImageChops.difference(b, vorher).getbbox():
        bilder.append(b)
    vorher = b
dauer = [700] * (len(bilder) - 1) + [4000]
bilder[0].save(sys.argv[2], save_all=True, append_images=bilder[1:], duration=dauer, loop=0, optimize=True)
print(len(bilder), "Bilder ->", sys.argv[2])
`, ordner, ziel], { stdio: "inherit" });
