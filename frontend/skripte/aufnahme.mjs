// Screenshots beliebiger Seiten: node skripte/aufnahme.mjs <zielordner> <name=pfad> [<name=pfad> …]
// Wartet auf Netzwerkruhe und Kartenmarker. Umgebung: BREITE (Standard 1440), HOEHE (900), VOLL=0 nur sichtbarer Bereich.
import { chromium } from "playwright-core";

const [ziel, ...paare] = process.argv.slice(2);
const basis = process.env.APP_URL ?? "http://localhost:5173";
const breite = Number(process.env.BREITE ?? 1440);
const browser = await chromium.launch({ channel: "chrome", args: ["--enable-unsafe-swiftshader"] });
const seite = await browser.newPage({ viewport: { width: breite, height: Number(process.env.HOEHE ?? 900) }, deviceScaleFactor: 2 });
for (const paar of paare) {
  const [name, pfad] = paar.split("=");
  await seite.goto(`${basis}${pfad}`, { waitUntil: "networkidle" });
  if (await seite.$(".maplibregl-map")) {
    await seite.waitForSelector(".marker, .km-comp", { timeout: 20000 }).catch(() => console.warn(`${name}: keine Marker`));
    await seite.waitForTimeout(2500);
  }
  await seite.screenshot({ path: `${ziel}/${name}.png`, fullPage: process.env.VOLL !== "0" });
  console.log("gespeichert:", `${ziel}/${name}.png`);
}
await browser.close();
