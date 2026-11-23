// Upload eigener Unterlagen (Exposé-PDF, Bild, Text) zu einem Projekt: mehrere Dateien oder ganze Ordner, je Datei ein
// Status und bei PDFs die Exposé-Felder aus dem Parser; dazu die Volltextsuche über alle Unterlagen. Ob die KI eine Datei lesen darf, gilt zunächst für die ganze Auswahl und lässt sich je Datei ändern; Standard
// ist nein, denn mit Haken geht das Dokument bei einem Lauf an Anthropic.
import { useState } from "react";
import { dokumentHochladen, unterlagenSuchen, type DokumentAus, type Treffer, type Wert } from "../api";
import { HerkunftMarke } from "./Herkunft";

type Status = { art: "bereit" } | { art: "laedt" } | { art: "fertig"; d: DokumentAus } | { art: "abgelehnt"; grund: string };
interface Eintrag {
  id: number;
  datei: File;
  ki: boolean;
  status: Status;
}

let naechsteId = 0;

/**
 * Sammelt Dateien aus Drag-&-Drop-Einträgen, Ordner rekursiv; versteckte Dateien (.DS_Store …) fallen weg.
 * Eingabe: Einträge aus DataTransferItem.webkitGetAsEntry(). Ausgabe: Dateien in Ordnerreihenfolge.
 */
export async function dateienAusEintraegen(eintraege: FileSystemEntry[]): Promise<File[]> {
  const dateien: File[] = [];
  for (const e of eintraege) {
    if (e.name.startsWith(".")) continue;
    if (e.isFile) {
      dateien.push(await new Promise<File>((ok, fehler) => (e as FileSystemFileEntry).file(ok, fehler)));
    } else if (e.isDirectory) {
      const leser = (e as FileSystemDirectoryEntry).createReader();
      // readEntries liefert Stapel (Chrome höchstens 100); erst eine leere Liste heißt: Ordner vollständig gelesen
      for (;;) {
        const stapel = await new Promise<FileSystemEntry[]>((ok, fehler) => leser.readEntries(ok, fehler));
        if (stapel.length === 0) break;
        dateien.push(...(await dateienAusEintraegen(stapel)));
      }
    }
  }
  return dateien;
}

/** Statuszeile einer Datei. Eingabe: Status. Ausgabe: Text. */
function statusText(s: Status): string {
  if (s.art === "bereit") return "bereit";
  if (s.art === "laedt") return "lädt …";
  if (s.art === "abgelehnt") return `abgelehnt: ${s.grund}`;
  const umfang = s.d.art === "png" || s.d.art === "jpg" ? "Bild" : `${s.d.seiten} ${s.d.seiten === 1 ? "Seite" : "Seiten"}`;
  return `fertig · ${umfang} · KI darf lesen: ${s.d.ki_freigabe ? "ja" : "nein"}`;
}

const FELDNAMEN = { wohnflaeche: "Wohnfläche", kaltmiete: "Kaltmiete", zimmer: "Zimmer", baujahr: "Baujahr" } as const;

/** Zahl eines Exposé-Felds wie in der Unterlage. Eingabe: Wert. Ausgabe: z. B. „72,5 m²“, „1.250 €“, „2025“. */
function feldText(w: Wert): string {
  const zahl = (w.wert ?? 0).toLocaleString("de-DE", { maximumFractionDigits: 2, useGrouping: w.einheit !== "Jahr" });
  return w.einheit === "Jahr" ? zahl : `${zahl} ${w.einheit}`;
}

/**
 * Ausschnitt um den ersten Treffer, damit nicht der ganze Abschnitt (rund 800 Zeichen) erscheint.
 * Eingabe: Text, Suchtext, Länge. Ausgabe: Ausschnitt mit „…“ an abgeschnittenen Enden.
 */
function umTreffer(text: string, frage: string, laenge = 220): string {
  const klein = text.toLowerCase();
  const stellen = (frage.toLowerCase().match(/[\p{L}\p{N}]{2,}/gu) ?? []).map((w) => klein.indexOf(w)).filter((i) => i >= 0);
  const start = Math.max(0, Math.min(...stellen, text.length) - 60);
  const ende = Math.min(text.length, start + laenge);
  return `${start > 0 ? "…" : ""}${text.slice(start, ende).trim()}${ende < text.length ? "…" : ""}`;
}

/**
 * Aufklappbare Auswertung einer hochgeladenen Datei. Eingabe: Ergebnis des Uploads.
 * Ausgabe: Exposé-Felder (PDF) bzw. Hinweis (Bild); nichts bei Texten. Leere Felder und Bilder liest nur ein
 * Lauf mit KI-Freigabe, deshalb steht „wird beim nächsten Lauf gelesen“ nur, wenn die Freigabe gesetzt ist.
 */
function Auswertung({ d }: { d: DokumentAus }) {
  const spaeter = d.ki_freigabe ? "wird beim nächsten Lauf gelesen" : "nicht gefunden (ohne KI-Freigabe liest es kein Lauf)";
  if (d.art === "png" || d.art === "jpg") {
    return (
      <details className="d-auswertung">
        <summary>Inhalt</summary>
        <p className="d-leise">{d.ki_freigabe ? "wird beim nächsten Lauf gelesen" : "Bilder liest nur die KI; ohne Freigabe bleibt dieses Bild ungelesen."}</p>
      </details>
    );
  }
  if (!d.expose) return null;
  return (
    <details className="d-auswertung">
      <summary>Exposé-Felder</summary>
      <dl>
        {(Object.keys(FELDNAMEN) as (keyof typeof FELDNAMEN)[]).map((f) => {
          const w = d.expose!.felder[f];
          return (
            <div key={f}>
              <dt>{FELDNAMEN[f]}</dt>
              <dd>
                {w ? (
                  <>
                    {feldText(w)} <span className="d-leise">{w.fundstelle}</span> <HerkunftMarke wert={w} />
                  </>
                ) : (
                  <span className="d-leise">{spaeter}</span>
                )}
              </dd>
            </div>
          );
        })}
        <div>
          <dt>Ausstattung</dt>
          <dd>
            {d.expose.ausstattung.length === 0 && <span className="d-leise">{spaeter}</span>}
            {d.expose.ausstattung.map((a) => (
              <span key={a.merkmal} className="d-merkmal">{`${a.merkmal} · ${a.fundstelle} · ${a.herkunft}`}</span>
            ))}
          </dd>
        </div>
      </dl>
    </details>
  );
}

/**
 * Suchfeld über alle Unterlagen des Projekts (dieselbe Volltextsuche wie das Agenten-Werkzeug dokumente_suchen,
 * hier lokal und ohne KI). Eingabe: Projekt-ID. Ausgabe: Formular mit Trefferliste.
 */
function Suche({ projektId }: { projektId: number }) {
  const [frage, setFrage] = useState("");
  const [ergebnis, setErgebnis] = useState<{ frage: string; treffer: Treffer[] } | { fehler: string } | null>(null);
  return (
    <form
      role="search"
      className="d-unterlagen-suche"
      onSubmit={async (e) => {
        e.preventDefault();
        const q = frage.trim();
        if (q.length < 2) return;
        try {
          setErgebnis({ frage: q, treffer: await unterlagenSuchen(projektId, q) });
        } catch (f) {
          setErgebnis({ fehler: (f as Error).message });
        }
      }}
    >
      <label htmlFor={`d-suche-${projektId}`}>In Unterlagen suchen</label>
      <span className="d-unterlagen-suchzeile">
        <input id={`d-suche-${projektId}`} type="search" value={frage} minLength={2} maxLength={200} placeholder="z. B. Wallbox, Nebenkosten" onChange={(e) => setFrage(e.target.value)} />
        <button type="submit" className="e-knopf">Suchen</button>
      </span>
      {ergebnis && "fehler" in ergebnis && <p role="alert" className="d-klein">{ergebnis.fehler}</p>}
      {ergebnis && "treffer" in ergebnis && ergebnis.treffer.length === 0 && <p className="d-leise d-klein">Keine Treffer.</p>}
      {ergebnis && "treffer" in ergebnis && ergebnis.treffer.length > 0 && (
        <ul className="d-treffer">
          {ergebnis.treffer.map((t) => (
            <li key={`${t.datei}-${t.seite}`}>
              <strong>{`${t.datei} · S. ${t.seite}`}</strong>
              <span>{umTreffer(t.ausschnitt, ergebnis.frage)}</span>
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}

/**
 * Ablagefläche mit Dateiwahl, Liste mit Status und KI-Häkchen je Datei. Eingabe: Projekt-ID. Ausgabe: Karte.
 */
export function Unterlagen({ projektId }: { projektId: number }) {
  const [eintraege, setEintraege] = useState<Eintrag[]>([]);
  const [kiAlle, setKiAlle] = useState(false);
  const [ziehen, setZiehen] = useState(false);
  const offen = eintraege.filter((e) => e.status.art === "bereit");
  const laedt = eintraege.some((e) => e.status.art === "laedt");

  /** Hängt Dateien an die Liste an; sie übernehmen das Häkchen „alle“. Eingabe: Dateien. */
  function hinzufuegen(dateien: File[]) {
    setEintraege((alt) => [...alt, ...dateien.map((datei) => ({ id: naechsteId++, datei, ki: kiAlle, status: { art: "bereit" } as Status }))]);
  }

  /** Ändert einen Eintrag. Eingabe: ID, Änderung. */
  function setze(id: number, aenderung: Partial<Eintrag>) {
    setEintraege((alt) => alt.map((e) => (e.id === id ? { ...e, ...aenderung } : e)));
  }

  /** Lädt alle offenen Dateien nacheinander hoch; jede Datei bekommt ihr eigenes Ergebnis. */
  async function hochladen() {
    for (const e of offen) {
      setze(e.id, { status: { art: "laedt" } });
      try {
        setze(e.id, { status: { art: "fertig", d: await dokumentHochladen(projektId, e.datei, e.ki) } });
      } catch (f) {
        setze(e.id, { status: { art: "abgelehnt", grund: (f as Error).message } });
      }
    }
  }

  return (
    <section className="d-karte d-unterlagen" aria-labelledby="d-unterlagen-titel">
      <h3 id="d-unterlagen-titel">Eigene Unterlagen</h3>
      <div
        className={`d-ablage${ziehen ? " d-ablage-aktiv" : ""}`}
        onDragOver={(e) => {
          e.preventDefault(); // sonst öffnet der Browser die Datei selbst
          setZiehen(true);
        }}
        onDragLeave={() => setZiehen(false)}
        onDrop={async (e) => {
          e.preventDefault();
          setZiehen(false);
          // Einträge sofort holen: DataTransfer ist nach dem ersten await nicht mehr lesbar
          const eintraege = Array.from(e.dataTransfer.items ?? [])
            .map((i) => i.webkitGetAsEntry?.())
            .filter((x): x is FileSystemEntry => !!x);
          hinzufuegen(eintraege.length ? await dateienAusEintraegen(eintraege) : Array.from(e.dataTransfer.files));
        }}
      >
        <p>Dateien oder Ordner hierher ziehen</p>
        <label className="e-knopf">
          Dateien wählen
          <input
            type="file"
            multiple
            className="e-sr"
            accept=".pdf,.png,.jpg,.jpeg,.txt,application/pdf,image/png,image/jpeg,text/plain"
            onChange={(e) => {
              hinzufuegen(Array.from(e.target.files ?? []));
              e.target.value = ""; // dieselbe Datei lässt sich erneut wählen
            }}
          />
        </label>
        <p className="d-leise d-klein">PDF, PNG, JPG oder Text, je Datei höchstens 10 MB (Bilder 5 MB)</p>
      </div>
      <label className="d-unterlagen-ki">
        <input
          type="checkbox"
          checked={kiAlle}
          aria-describedby="d-ki-hinweis"
          onChange={(e) => {
            setKiAlle(e.target.checked);
            setEintraege((alt) => alt.map((x) => (x.status.art === "bereit" ? { ...x, ki: e.target.checked } : x)));
          }}
        />
        KI darf alle gewählten Dateien lesen
      </label>
      <p id="d-ki-hinweis" className="d-leise d-klein">
        Mit Haken geht ein Dokument bei einem Analyse-Lauf an Anthropic (Claude). Ohne Haken bleibt es auf diesem Rechner und wird nur lokal durchsucht.
      </p>
      {eintraege.length > 0 && (
        <ul className="d-unterlagen-liste">
          {eintraege.map((e) => (
            <li key={e.id} className={`s-${e.status.art}`}>
              <span className="d-unterlagen-name">{e.datei.name}</span>
              <label className="d-klein">
                <input type="checkbox" checked={e.ki} disabled={e.status.art !== "bereit"} aria-label={`KI darf ${e.datei.name} lesen`} onChange={(x) => setze(e.id, { ki: x.target.checked })} />
                KI
              </label>
              <span className="d-klein d-unterlagen-status" role={e.status.art === "abgelehnt" ? "alert" : undefined}>
                {statusText(e.status)}
              </span>
              {e.status.art === "fertig" && <Auswertung d={e.status.d} />}
            </li>
          ))}
        </ul>
      )}
      <button type="button" className="e-knopf e-knopf-primaer" disabled={offen.length === 0 || laedt} onClick={hochladen}>
        {laedt ? "Lädt hoch …" : `${offen.length} ${offen.length === 1 ? "Datei" : "Dateien"} hochladen`}
      </button>
      <Suche projektId={projektId} />
    </section>
  );
}
