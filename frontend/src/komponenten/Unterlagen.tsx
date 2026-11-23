// Upload eigener Unterlagen (Exposé-PDF, Bild, Text) zu einem Projekt. Ob die KI ein Dokument lesen darf, entscheidet
// der Nutzer je Datei; Standard ist nein, denn mit Haken geht das Dokument bei einem Lauf an Anthropic.
import { useState } from "react";
import { dokumentHochladen, type DokumentAus } from "../api";

/**
 * Formular mit Dateiwahl und Häkchen „KI darf lesen“. Eingabe: Projekt-ID. Ausgabe: Karte mit Ergebnis bzw. Fehler.
 */
export function Unterlagen({ projektId }: { projektId: number }) {
  const [datei, setDatei] = useState<File | null>(null);
  const [kiFreigabe, setKiFreigabe] = useState(false);
  const [zustand, setZustand] = useState<{ art: "ruhig" | "laden" } | { art: "fertig"; d: DokumentAus } | { art: "fehler"; text: string }>({ art: "ruhig" });

  return (
    <form
      className="d-karte d-unterlagen"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!datei) return;
        setZustand({ art: "laden" });
        try {
          setZustand({ art: "fertig", d: await dokumentHochladen(projektId, datei, kiFreigabe) });
        } catch (f) {
          setZustand({ art: "fehler", text: (f as Error).message });
        }
      }}
    >
      <h3>Eigene Unterlagen</h3>
      <label>
        Datei (PDF, PNG, JPG oder Text, höchstens 10 MB)
        <input type="file" accept=".pdf,.png,.jpg,.jpeg,.txt,application/pdf,image/png,image/jpeg,text/plain" onChange={(e) => setDatei(e.target.files?.[0] ?? null)} />
      </label>
      <label className="d-unterlagen-ki">
        <input type="checkbox" checked={kiFreigabe} onChange={(e) => setKiFreigabe(e.target.checked)} aria-describedby="d-ki-hinweis" />
        KI darf dieses Dokument lesen
      </label>
      <p id="d-ki-hinweis" className="d-leise d-klein">
        Mit Haken geht das Dokument bei einem Analyse-Lauf an Anthropic (Claude). Ohne Haken bleibt es auf diesem Rechner und wird nur lokal durchsucht.
      </p>
      <button type="submit" className="e-knopf" disabled={!datei || zustand.art === "laden"}>
        {zustand.art === "laden" ? "Lädt hoch …" : "Hochladen"}
      </button>
      {zustand.art === "fertig" && (
        <p role="status" className="d-klein">
          {zustand.d.dateiname} hochgeladen · {zustand.d.seiten} {zustand.d.seiten === 1 ? "Seite" : "Seiten"} · KI darf lesen: {zustand.d.ki_freigabe ? "ja" : "nein"}
        </p>
      )}
      {zustand.art === "fehler" && (
        <p role="alert" className="d-klein d-akzent">
          {zustand.text}
        </p>
      )}
    </form>
  );
}
