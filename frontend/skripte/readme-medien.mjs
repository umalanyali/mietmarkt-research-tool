// Nimmt die README-Medien neu auf: node skripte/readme-medien.mjs (braucht ffmpeg, kostet nichts).
// Startet backend/tests/fake_server.py (Fake-Modell, Umfeld aus dem Cache in daten/mietmarkt.db) und Vite auf eigenen
// Ports, spielt fünf Szenen ab und schreibt nach docs/screenshots/: lauf.gif + lauf.mp4, umfeld/upload/ergebnis/handy.mp4,
// die Standbilder analyse/startseite/zustaende.png und über skripte/responsive.mjs den Ordner responsive/.
// Bilder kommen aus Playwright-Screenshots bei deviceScaleFactor 2 (recordVideo und CDP-Screencast liefern nur 1×).
import { execFileSync, spawn } from "node:child_process";
import { mkdtempSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { chromium } from "playwright-core";

const API_PORT = 8011;
const WEB_PORT = 5181;
const BASIS = `http://localhost:${WEB_PORT}`;
const ZIEL = new URL("../../docs/screenshots/", import.meta.url).pathname;
const UNTERLAGEN = new URL("../../testdaten/unterlagen/", import.meta.url).pathname;
const MAX_BYTES = 8 * 1024 * 1024;
const prozesse = [];

/** Startet einen Hintergrundprozess, der mit dem Skript endet. Eingabe: Befehl, Argumente, Optionen. */
function starte(befehl, argumente, optionen) {
  const p = spawn(befehl, argumente, { stdio: ["ignore", "inherit", "inherit"], ...optionen });
  prozesse.push(p);
  return p;
}

/** Wartet, bis eine Adresse antwortet. Eingabe: URL, Zeitlimit in ms. Ausgabe: Promise (wirft nach Zeitlimit). */
async function bereit(url, ms = 30000) {
  const ende = Date.now() + ms;
  while (Date.now() < ende) {
    if (await fetch(url).then((a) => a.ok, () => false)) return;
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error(`${url} antwortet nicht`);
}

/** Führt ffmpeg still aus. Eingabe: Argumente. Ausgabe: keine; wirft bei Fehler. */
const ffmpeg = (...a) => execFileSync("ffmpeg", ["-v", "error", "-y", ...a], { stdio: "inherit" });

/**
 * Filmt eine Seite per Screenshot-Schleife, bis die zurückgegebene Funktion aufgerufen wird.
 * Eingabe: Seite, Name der Szene. Ausgabe: async Funktion stopp(), die Bilder und Zeitstempel liefert.
 */
function filmen(seite, name) {
  const ordner = mkdtempSync(join(tmpdir(), `readme-${name}-`));
  const zeiten = [];
  let aktiv = true;
  const schleife = (async () => {
    while (aktiv) {
      const t = Date.now();
      const bild = await seite.screenshot({ type: "jpeg", quality: 92 }).catch(() => null);
      if (bild) {
        writeFileSync(join(ordner, `${String(zeiten.length).padStart(5, "0")}.jpg`), bild);
        zeiten.push(t);
      }
    }
  })();
  return async () => {
    await seite.waitForTimeout(2500); // Schlussbild stehen lassen
    aktiv = false;
    await schleife;
    return { ordner, zeiten };
  };
}

/**
 * Baut aus den Bildern ein MP4 mit konstanten 30 fps und optional ein GIF (zwei Durchgänge mit eigener Palette).
 * Eingabe: Bilder und Zeitstempel, Name, ob ein GIF entsteht. Ausgabe: keine; wirft, wenn eine Datei über 8 MB liegt.
 */
function kodieren({ ordner, zeiten }, name, gif = false) {
  // Jedes Bild steht so lange, bis das nächste aufgenommen wurde: Abspieltempo = echtes Tempo
  const liste = zeiten.map((t, i) => `file '${String(i).padStart(5, "0")}.jpg'\nduration ${((zeiten[i + 1] ?? t + 100) - t) / 1000}`);
  writeFileSync(join(ordner, "liste.txt"), `${liste.join("\n")}\nfile '${String(zeiten.length - 1).padStart(5, "0")}.jpg'\n`);
  const eingabe = ["-f", "concat", "-safe", "0", "-i", join(ordner, "liste.txt")];
  const mp4 = join(ZIEL, `${name}.mp4`);
  ffmpeg(...eingabe, "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-crf", "23", "-preset", "slow",
    "-movflags", "+faststart", mp4);
  const dateien = [mp4];
  if (gif) {
    const ziel = join(ZIEL, `${name}.gif`);
    const palette = join(ordner, "palette.png");
    // 15 fps zuerst; liegt das GIF über 8 MB, noch einmal mit 12 fps
    for (const fps of [15, 12]) {
      const filter = `fps=${fps},scale=1200:-1:flags=lanczos`;
      ffmpeg(...eingabe, "-vf", `${filter},palettegen=stats_mode=diff`, palette);
      ffmpeg(...eingabe, "-i", palette, "-lavfi", `${filter}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle`, ziel);
      if (statSync(ziel).size <= MAX_BYTES) break;
    }
    dateien.push(ziel);
  }
  rmSync(ordner, { recursive: true, force: true });
  for (const d of dateien) {
    const mb = statSync(d).size / 1024 / 1024;
    console.log(`${d}: ${mb.toFixed(1)} MB`);
    if (mb > 8) throw new Error(`${d} ist größer als 8 MB`);
  }
}

/** Scrollt sanft um einen Betrag. Eingabe: Seite, Pixel, Wartezeit in ms danach. Ausgabe: Promise. */
async function scrolle(seite, px, ms = 900) {
  await seite.evaluate((y) => window.scrollBy({ top: y, behavior: "smooth" }), px);
  await seite.waitForTimeout(ms);
}

/** Scrollt ein Element sanft an den oberen Rand. Eingabe: Locator, Wartezeit in ms danach. Ausgabe: Promise. */
async function zeige(locator, ms = 1200) {
  await locator.evaluate((e) => e.scrollIntoView({ behavior: "smooth", block: "start" }));
  await locator.page().waitForTimeout(ms);
}

// Fake-Kosten gehören nicht ins README: Kostenzeilen ausblenden, sobald sie erscheinen
const KOSTEN_AUSBLENDEN = () => {
  const weg = () => {
    for (const e of document.querySelectorAll(".d-agenten-kosten, .d-ergebnis p")) {
      if (e.classList.contains("d-agenten-kosten") || e.textContent.startsWith("Kosten des Laufs")) e.style.visibility = "hidden";
    }
  };
  new MutationObserver(weg).observe(document, { childList: true, subtree: true, characterData: true });
};

let browser;
try {
  starte("../backend/.venv/bin/python", ["tests/fake_server.py"], {
    cwd: "../backend",
    env: { ...process.env, KI_FAKE: "1", FAKE_PORT: String(API_PORT), PYTHONPATH: ".", UMFELD_AUS: "../daten/mietmarkt.db" },
  });
  starte("npx", ["vite", "--port", String(WEB_PORT), "--strictPort"], { env: { ...process.env, API_PORT: String(API_PORT) } });
  await bereit(`http://127.0.0.1:${API_PORT}/api/gesundheit`);
  await bereit(`${BASIS}/`);
  browser = await chromium.launch({ channel: "chrome", args: ["--enable-unsafe-swiftshader"] });

  // ---------------------------------------------- Desktop: ein Fake-Lauf, danach Umfeld, Ergebnis und Upload
  const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  await desktop.addInitScript(KOSTEN_AUSBLENDEN);
  const seite = await desktop.newPage();
  await seite.goto(BASIS, { waitUntil: "networkidle" });

  let stopp = filmen(seite, "lauf");
  await seite.waitForTimeout(1500);
  await seite.getByRole("button", { name: "Demo-Standort öffnen" }).click();
  await seite.locator(".maplibregl-canvas").waitFor();
  await seite.waitForTimeout(2500); // Kacheln laden
  await seite.getByRole("button", { name: "Analyse starten" }).click();
  await seite.getByText("Mietansatz übernehmen?").waitFor({ timeout: 60000 });
  await zeige(seite.locator("#d-freigabe"), 3000);
  await seite.getByRole("button", { name: "Annehmen" }).click();
  await seite.locator(".d-ergebnis").waitFor({ timeout: 60000 });
  await seite.waitForTimeout(1500);
  kodieren(await stopp(), "lauf", true);
  // Standbild der Analyse-Seite mit fertigem Lauf (vor dem Upload, damit die Unterlagen leer sind)
  await seite.evaluate(() => window.scrollTo(0, 0));
  await seite.waitForTimeout(1500);
  await seite.screenshot({ path: join(ZIEL, "analyse.png"), fullPage: true });

  stopp = filmen(seite, "umfeld");
  const karte = seite.locator(".d-karte-bild").filter({ visible: true }).first();
  await zeige(karte);
  for (const ebene of ["Projekte", "ÖPNV", "Nahversorgung"]) {
    await karte.getByRole("button", { name: ebene, exact: true }).click();
    await seite.waitForTimeout(1500);
  }
  await zeige(seite.locator(".d-karte").filter({ has: seite.getByRole("heading", { name: "Umfeld", exact: true }) }).filter({ visible: true }).first(), 2000);
  await scrolle(seite, 400, 1500);
  kodieren(await stopp(), "umfeld");

  stopp = filmen(seite, "ergebnis");
  const ergebnis = seite.locator(".d-ergebnis");
  await zeige(ergebnis, 1500);
  // Herkunft einer Zahl: Klick zeigt den Rechenweg
  await ergebnis.getByRole("button", { name: /^Herkunft:/ }).first().click();
  await seite.waitForTimeout(2500);
  await seite.keyboard.press("Escape");
  await ergebnis.getByRole("button", { name: "Bericht ansehen" }).click();
  await seite.waitForTimeout(1200);
  await scrolle(seite, 500, 1500);
  await scrolle(seite, 500, 1500);
  await zeige(ergebnis, 1000);
  const [download] = await Promise.all([seite.waitForEvent("download"), ergebnis.getByRole("link", { name: "PowerPoint" }).click()]);
  // Ein Download hat im Browser ohne Fenster kein Bild: Hinweis einblenden (warme Töne wie die App)
  await seite.evaluate((datei) => {
    const d = Object.assign(document.createElement("div"), { textContent: `${datei} gespeichert` });
    Object.assign(d.style, { position: "fixed", right: "24px", bottom: "24px", padding: "14px 20px", borderRadius: "10px",
      background: "#3d342b", color: "#f6f1e9", font: "600 15px 'Hanken Grotesk', sans-serif", zIndex: 9999,
      boxShadow: "0 6px 24px rgba(40,30,20,.25)" });
    document.body.append(d);
  }, download.suggestedFilename());
  await seite.waitForTimeout(2000);
  kodieren(await stopp(), "ergebnis");
  await seite.evaluate(() => document.body.lastElementChild.remove());

  stopp = filmen(seite, "upload");
  const unterlagen = seite.locator(".d-unterlagen").filter({ visible: true }).first();
  await zeige(unterlagen);
  await unterlagen.locator('input[type="file"]').setInputFiles(
    ["expose_gartenhof4_eg.pdf", "expose_talblick18_dg.pdf", "marktbericht_tabelle.png", "projektbeschreibung_suedhang.txt"]
      .map((d) => join(UNTERLAGEN, d)),
  );
  await seite.waitForTimeout(1500);
  await unterlagen.getByLabel("KI darf alle gewählten Dateien lesen").check();
  await seite.waitForTimeout(1000);
  await unterlagen.getByRole("button", { name: "4 Dateien hochladen" }).click();
  await unterlagen.locator(".d-unterlagen-liste li.s-fertig").nth(3).waitFor({ timeout: 60000 });
  await scrolle(seite, 300, 1500);
  kodieren(await stopp(), "upload");
  for (const [name, pfad] of [["startseite", "/"], ["zustaende", "/zustaende"]]) {
    await seite.goto(BASIS + pfad, { waitUntil: "networkidle" });
    await seite.waitForTimeout(1000);
    await seite.screenshot({ path: join(ZIEL, `${name}.png`), fullPage: true });
  }
  await desktop.close();

  // ---------------------------------------------- Handy: Startseite und Analyse mit dem fertigen Lauf
  const handy = await browser.newContext({ viewport: { width: 375, height: 812 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  await handy.addInitScript(KOSTEN_AUSBLENDEN);
  const telefon = await handy.newPage();
  await telefon.goto(BASIS, { waitUntil: "networkidle" });
  stopp = filmen(telefon, "handy");
  await telefon.waitForTimeout(1500);
  await telefon.getByRole("button", { name: "Demo-Standort öffnen" }).click();
  await telefon.locator(".maplibregl-canvas").first().waitFor();
  await telefon.waitForTimeout(2500);
  await scrolle(telefon, 500, 1500);
  // Den Lauf vom Desktop öffnen: die Ergebniskarte rollt sich selbst in den Blick
  await telefon.getByRole("button", { name: "Details" }).click();
  await telefon.locator(".d-laufliste").getByRole("button", { name: "Ansehen" }).click();
  await telefon.locator(".d-ergebnis").waitFor();
  await telefon.waitForTimeout(2000);
  for (let i = 0; i < 5; i++) await scrolle(telefon, 600, 1100);
  kodieren(await stopp(), "handy");

  // Responsive-Bilder und Überlaufprüfung gegen denselben Fake-Server (Umfeld aus dem Cache)
  execFileSync("node", ["skripte/responsive.mjs"], { stdio: "inherit", env: { ...process.env, APP_URL: BASIS } });
  console.log("README-Medien fertig.");
} catch (f) {
  console.error(f.message);
  process.exitCode = 1;
} finally {
  await browser?.close();
  for (const p of prozesse) p.kill();
}
