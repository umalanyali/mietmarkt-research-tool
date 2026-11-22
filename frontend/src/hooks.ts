// React-Hooks für Startseite und Dashboard: Adresssuche (Combobox) und Merkliste, dazu kleine Filterhilfen.
import { useId, useMemo, useState } from "react";
import { adressVorschlaege, comps, merklisteStart } from "../../daten/beispiel";
import type { Baustein } from "../../komponenten/Merkliste";

type Vorschlag = (typeof adressVorschlaege)[number];

/**
 * Adresssuche als barrierefreie Combobox: Vorschläge ab 2 Zeichen, Pfeiltasten, Enter, Escape.
 * Eingabe: onStart (wird bei Enter nach gewählter Adresse aufgerufen), startwert (Vorbelegung des Felds).
 * Ausgabe: Props für das Eingabefeld (feld) und je Vorschlag (option), dazu Listenzustand.
 */
export function useAdressSuche(onStart: () => void, startwert = "") {
  const listenId = useId();
  const [eingabe, setEingabe] = useState(startwert);
  const [offen, setOffen] = useState(false);
  const [markiert, setMarkiert] = useState(0);
  const [gewaehlt, setGewaehlt] = useState<Vorschlag | null>(null);

  // Prototyp: Vorschläge aus Beispieldaten; ab M4 kommen sie gedrosselt und gecacht aus dem Backend
  const vorschlaege = useMemo(() => {
    const s = eingabe.trim().toLowerCase();
    if (s.length < 2) return [];
    return adressVorschlaege
      .filter((v) => `${v.strasse} ${v.plz} ${v.ort} ${v.ortsteil}`.toLowerCase().includes(s))
      .slice(0, 5);
  }, [eingabe]);

  const zeigeListe = offen && vorschlaege.length > 0;
  const keinTreffer = offen && eingabe.trim().length >= 2 && vorschlaege.length === 0 && !gewaehlt;

  /** Übernimmt einen Vorschlag ins Feld und schließt die Liste. Eingabe: Vorschlag. Ausgabe: keine. */
  function waehlen(v: Vorschlag) {
    setGewaehlt(v);
    setEingabe(`${v.strasse}, ${v.plz} ${v.ort}`);
    setOffen(false);
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
      setGewaehlt(null);
      setOffen(true);
      setMarkiert(0);
    },
    onFocus: () => setOffen(true),
    // Verzögert schließen, damit ein Klick auf einen Vorschlag noch ankommt
    onBlur: () => window.setTimeout(() => setOffen(false), 120),
    onKeyDown: (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (!zeigeListe) {
        if (e.key === "Enter" && gewaehlt) onStart();
        return;
      }
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

  return { feld, option, listenId, vorschlaege, zeigeListe, keinTreffer };
}

/**
 * Merkliste und gemerkte Comps (Prototyp: nur im Speicher, ab M3 in der Datenbank).
 * Eingabe: keine. Ausgabe: Bausteine mit Setter, Abfrage/Umschalten je Baustein, gemerkte Comp-Nummern.
 */
export function useMerkliste() {
  const [bausteine, setBausteine] = useState<Baustein[]>(merklisteStart);
  const [compsGemerkt, setCompsGemerkt] = useState<Set<number>>(
    () => new Set(comps.filter((c) => c.gemerkt).map((c) => c.nr)),
  );
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

/** Kürzel und Langform der Entfernungsart (Route zu Fuß/Rad oder Luftlinie als Rückfall). */
export const ENTF_KURZ = { Fuß: "F", Rad: "R", Luftlinie: "L" } as const;
export const ENTF_LANG = { Fuß: "Route zu Fuß", Rad: "Route mit dem Rad", Luftlinie: "Luftlinie" } as const;
