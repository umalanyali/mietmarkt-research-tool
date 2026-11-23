// React-Hooks für Startseite und Dashboard: Adresssuche (Combobox gegen die API) und Merkliste, dazu Filterhilfen.
import { useEffect, useId, useState } from "react";
import { useNavigate } from "react-router-dom";
import { adressVorschlaege, ApiFehler, projektAnlegen, type Vorschlag } from "./api";
import { merklisteStart } from "./daten/platzhalter";
import type { Baustein } from "./komponenten/Merkliste";

const MIN_ZEICHEN = 3;
const DEBOUNCE_MS = 300;

export type SuchStatus = "ruhig" | "laden" | "fehler" | "nicht-erreichbar";

/**
 * Adresssuche als barrierefreie Combobox. Vorschläge kommen von /api/adressen/vorschlaege (Photon),
 * ab 3 Zeichen, 300 ms nach dem letzten Tastendruck; ältere Anfragen werden abgebrochen.
 * Eingabe: onWahl (gewählter Vorschlag), startwert (Vorbelegung des Felds, löst keine Suche aus).
 * Ausgabe: Props für Eingabefeld (feld) und Vorschläge (option), Listen- und Ladezustand, Quellenhinweis.
 */
export function useAdressSuche(onWahl: (v: Vorschlag) => void, startwert = "") {
  const listenId = useId();
  const [eingabe, setEingabe] = useState(startwert);
  const [getippt, setGetippt] = useState(false);
  const [offen, setOffen] = useState(false);
  const [markiert, setMarkiert] = useState(0);
  const [vorschlaege, setVorschlaege] = useState<Vorschlag[]>([]);
  const [status, setStatus] = useState<SuchStatus>("ruhig");
  const [attribution, setAttribution] = useState("");

  useEffect(() => {
    const text = eingabe.trim();
    if (!getippt || text.length < MIN_ZEICHEN) {
      setVorschlaege([]);
      setStatus("ruhig");
      return;
    }
    const abbruch = new AbortController();
    // Erst nach einer Tipppause fragen; jede neue Eingabe verwirft Timer und laufende Anfrage
    const timer = window.setTimeout(() => {
      setStatus("laden");
      adressVorschlaege(text, abbruch.signal)
        .then((a) => {
          setVorschlaege(a.vorschlaege);
          setAttribution(a.attribution);
          setMarkiert(0);
          setStatus("ruhig");
        })
        .catch((e: Error) => {
          if (e.name === "AbortError") return;
          setVorschlaege([]);
          setStatus(e instanceof ApiFehler && e.status === 503 ? "nicht-erreichbar" : "fehler");
        });
    }, DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timer);
      abbruch.abort();
    };
  }, [eingabe, getippt]);

  const zeigeListe = offen && vorschlaege.length > 0;
  const keinTreffer = offen && getippt && status === "ruhig" && eingabe.trim().length >= MIN_ZEICHEN && vorschlaege.length === 0;

  /** Übernimmt einen Vorschlag ins Feld, schließt die Liste und meldet ihn. Eingabe: Vorschlag. Ausgabe: keine. */
  function waehlen(v: Vorschlag) {
    setEingabe(v.label);
    setGetippt(false);
    setOffen(false);
    onWahl(v);
  }

  const feld = {
    value: eingabe,
    role: "combobox" as const,
    autoComplete: "off",
    "aria-expanded": zeigeListe,
    "aria-controls": listenId,
    // Screenreader lesen so den markierten Vorschlag vor, obwohl der Fokus im Eingabefeld bleibt
    "aria-activedescendant": zeigeListe ? `${listenId}-${markiert}` : undefined,
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
      setEingabe(e.target.value);
      setGetippt(true);
      setOffen(true);
    },
    onFocus: () => setOffen(true),
    // Verzögert schließen, damit ein Klick auf einen Vorschlag noch ankommt
    onBlur: () => window.setTimeout(() => setOffen(false), 120),
    onKeyDown: (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (!zeigeListe) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setMarkiert((m) => (m + 1) % vorschlaege.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setMarkiert((m) => (m - 1 + vorschlaege.length) % vorschlaege.length);
      } else if (e.key === "Enter") {
        e.preventDefault();
        waehlen(vorschlaege[markiert]);
      } else if (e.key === "Escape") {
        setOffen(false);
      }
    },
  };

  /** Props für den Vorschlag an Position i. Eingabe: Index. Ausgabe: id, Rolle und Maus-Handler. */
  const option = (i: number) => ({
    id: `${listenId}-${i}`,
    role: "option" as const,
    "aria-selected": i === markiert,
    // mousedown statt click: feuert vor dem blur des Eingabefelds
    onMouseDown: (e: React.MouseEvent) => {
      e.preventDefault();
      waehlen(vorschlaege[i]);
    },
    onMouseEnter: () => setMarkiert(i),
  });

  return { feld, option, listenId, vorschlaege, zeigeListe, keinTreffer, status, attribution, waehlen };
}

/**
 * Legt aus einem gewählten Vorschlag ein Projekt an und öffnet dessen Analyse.
 * Eingabe: keine. Ausgabe: anlegen(v) und Zustand (ruhig, laden, fehler, nicht-erreichbar).
 */
export function useProjektAnlage() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<SuchStatus>("ruhig");
  function anlegen(v: Vorschlag) {
    setStatus("laden");
    projektAnlegen(v)
      .then((p) => navigate(`/analyse/${p.id}`))
      .catch((e: Error) => setStatus(e instanceof ApiFehler && e.status === 503 ? "nicht-erreichbar" : "fehler"));
  }
  return { anlegen, status };
}

/**
 * Merkliste und gemerkte Comps (Merkliste nur im Speicher des Browsers, nicht in der Datenbank).
 * Eingabe: Nummern der Comps, die laut Datenbank gemerkt sind; ob die Beispiel-Bausteine erscheinen. Ausgabe: Bausteine mit Setter,
 * Abfrage/Umschalten je Baustein, gemerkte Comp-Nummern mit Umschalter.
 */
export function useMerkliste(gemerktStart: number[], mitBeispielen: boolean) {
  const [bausteine, setBausteine] = useState<Baustein[]>(mitBeispielen ? merklisteStart : []);
  const [compsGemerkt, setCompsGemerkt] = useState<Set<number>>(() => new Set(gemerktStart));
  return {
    bausteine,
    setBausteine,
    istGemerkt: (id: string) => bausteine.some((b) => b.id === id),
    umschalten: (b: Baustein) =>
      setBausteine((m) => (m.some((x) => x.id === b.id) ? m.filter((x) => x.id !== b.id) : [...m, b])),
    compsGemerkt,
    compUmschalten: (nr: number) =>
      setCompsGemerkt((alt) => {
        const neu = new Set(alt);
        if (neu.has(nr)) neu.delete(nr);
        else neu.add(nr);
        return neu;
      }),
  };
}

export const ZIMMER = ["Alle", "1", "2", "3", "4+"] as const;
export type ZimmerFilter = (typeof ZIMMER)[number];

/** Passt die Zimmerzahl zum Filter? Eingabe: Zimmerzahl, Filter. Ausgabe: true/false („4+“ = ab 4 Zimmern). */
export function passtZimmer(z: number, f: ZimmerFilter) {
  if (f === "Alle") return true;
  if (f === "4+") return z >= 4;
  return z === Number(f);
}
