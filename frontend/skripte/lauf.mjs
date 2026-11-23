// Kompletter Agenten-Lauf im Browser gegen das Backend mit Fake-Modell: node skripte/lauf.mjs [screenshot-ordner]
// Startet backend/tests/fake_server.py (KI_FAKE=1, nur hier gesetzt) und Vite auf eigenen Ports, klickt „Analyse
// starten“, nimmt die Freigabe an und wartet auf den freigegebenen Mietansatz. Exit-Code 1 bei einem Fehler.
import { spawn } from "node:child_process";
import { chromium } from "playwright-core";

const API_PORT = 8010;
const WEB_PORT = 5180;
const [ziel] = process.argv.slice(2);
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

/** Prüft eine Bedingung. Eingabe: Wert, Meldung. Ausgabe: keine; wirft bei falsch. */
function pruefe(wert, meldung) {
  if (!wert) throw new Error(`Prüfung fehlgeschlagen: ${meldung}`);
  console.log("ok:", meldung);
}

let browser;
try {
  starte("../backend/.venv/bin/python", ["tests/fake_server.py"], {
    cwd: "../backend",
    env: { ...process.env, KI_FAKE: "1", FAKE_PORT: String(API_PORT), PYTHONPATH: "." },
  });
  starte("npx", ["vite", "--port", String(WEB_PORT), "--strictPort"], { env: { ...process.env, API_PORT: String(API_PORT) } });
  await bereit(`http://127.0.0.1:${API_PORT}/api/gesundheit`);
  await bereit(`http://localhost:${WEB_PORT}/`);

  browser = await chromium.launch({ channel: "chrome", args: ["--enable-unsafe-swiftshader"] });
  const seite = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  // Kein Overpass-Abruf aus dem Test: das Umfeld meldet „nicht erreichbar“ (die Seite zeigt dafür einen Hinweis)
  await seite.route("**/api/projekte/*/umfeld", (r) => r.fulfill({ status: 503, body: "{}" }));
  await seite.goto(`http://localhost:${WEB_PORT}/analyse/1`);

  await seite.getByRole("button", { name: "Analyse starten" }).click();
  await seite.getByText("Mietansatz übernehmen?").waitFor();
  pruefe(await seite.getByRole("link", { name: "Freigabe wartet auf dich" }).isVisible(), "Hinweis auf die offene Freigabe");
  pruefe((await seite.locator(".d-schritt.s-fertig").count()) >= 3, "Standort, Marktdaten, Mietansatz fertig");
  pruefe((await seite.locator(".d-agenten-kosten").textContent()).includes("€"), "Token und Kosten angezeigt");

  // Herkunft einer Zahl in der Herleitung: Klick zeigt den Rechenweg
  await seite.locator("#d-freigabe").getByRole("button", { name: "Herkunft: ki" }).first().click();
  pruefe((await seite.getByRole("note").textContent()).includes("Effizienzhaus 40"), "Herkunft zeigt Begründung des Zuschlags");

  if (ziel) await seite.screenshot({ path: `${ziel}/lauf-freigabe.png`, fullPage: true });
  await seite.getByRole("button", { name: "Annehmen" }).click();
  await seite.getByText("freigegeben", { exact: true }).waitFor();
  pruefe((await seite.locator(".d-ansatz").textContent()).includes("17,26"), "Mietansatz 17,26 €/m² freigegeben");
  pruefe(await seite.getByText("Prüfung").first().isVisible(), "Prüfung in der Zeitleiste");

  await seite.getByRole("button", { name: "Details" }).click();
  await seite.locator(".d-laufliste").getByText("fertig").waitFor();
  pruefe(true, "Laufliste zeigt den Lauf als fertig");
  if (ziel) await seite.screenshot({ path: `${ziel}/lauf-fertig.png`, fullPage: true });
  console.log("Lauf komplett.");
} catch (f) {
  console.error(f.message);
  process.exitCode = 1;
} finally {
  await browser?.close();
  for (const p of prozesse) p.kill();
}
