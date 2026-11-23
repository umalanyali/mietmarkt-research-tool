// Responsive-Prüfung: Startseite, Analyse (erstes Demo-Projekt) und Zustände bei 375, 768, 1280 und 1440 px.
// Jede Seite darf nicht horizontal scrollen (scrollWidth ≤ clientWidth); Screenshots nach docs/screenshots/responsive/.
// Aufruf (App muss laufen): node skripte/responsive.mjs   – Exit-Code 1 bei Überlauf, mit den Elementen, die herausragen.
import { mkdir } from "node:fs/promises";
import { chromium } from "playwright-core";

const basis = process.env.APP_URL ?? "http://localhost:5173";
const ziel = new URL("../../docs/screenshots/responsive/", import.meta.url).pathname;
const BREITEN = [375, 768, 1280, 1440];

const projekte = await (await fetch(`${basis}/api/projekte`)).json();
const projekt = projekte.find((p) => p.demo) ?? projekte[0];
const SEITEN = { start: "/", analyse: `/analyse/${projekt.id}`, zustaende: "/zustaende" };

await mkdir(ziel, { recursive: true });
const browser = await chromium.launch({ channel: "chrome", args: ["--enable-unsafe-swiftshader"] });
const fehler = [];
for (const breite of BREITEN) {
  for (const [name, pfad] of Object.entries(SEITEN)) {
    const seite = await browser.newPage({ viewport: { width: breite, height: 900 } });
    // „load“ statt „networkidle“: die Karte lädt fortlaufend Kacheln nach
    await seite.goto(basis + pfad, { waitUntil: "load" });
    await seite.waitForTimeout(name === "analyse" ? 4000 : 1500);
    const r = await seite.evaluate(() => {
      const d = document.documentElement;
      // Verursacher: ragt über den Rand und wird von keinem Scroll-Rahmen abgeschnitten – oder ist absolut
      // positioniert (entkommt dem Rahmen, wenn dessen Bezugspunkt außerhalb liegt, z. B. Screenreader-Texte)
      const geclippt = (e) => { for (let a = e.parentElement; a && a !== document.body; a = a.parentElement) if (getComputedStyle(a).overflowX !== "visible") return true; return false; };
      const raus = [...document.querySelectorAll("body *")]
        .filter((e) => e.getBoundingClientRect().right > d.clientWidth + 1 && (!geclippt(e) || ["absolute", "fixed"].includes(getComputedStyle(e).position)))
        .slice(0, 5).map((e) => `${e.tagName.toLowerCase()}.${[...e.classList].join(".")}`);
      return { sw: d.scrollWidth, cw: d.clientWidth, raus };
    });
    await seite.screenshot({ path: `${ziel}${name}-${breite}.png`, fullPage: true });
    const ok = r.sw <= r.cw;
    console.log(`${ok ? "ok    " : "FEHLER"} ${name} ${breite}px: scrollWidth ${r.sw}, clientWidth ${r.cw}${ok ? "" : " – " + r.raus.join(", ")}`);
    if (!ok) fehler.push(`${name} ${breite}`);
    await seite.close();
  }
}
await browser.close();
if (fehler.length) {
  console.error(`Horizontaler Überlauf: ${fehler.join("; ")}`);
  process.exit(1);
}
