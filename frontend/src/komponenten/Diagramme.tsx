// Schlanke Diagramme mit visx: Zeitreihe (Linien mit Fadenkreuz) und Säulen. Farben kommen aus CSS-Variablen.
import { useEffect, useRef, useState } from "react";
import { scaleBand, scaleLinear, scalePoint } from "@visx/scale";
import { LinePath } from "@visx/shape";
import { de } from "../format";

/** Beobachtet die Breite des Elternelements, damit Diagramme im Raster mitwachsen. Eingabe: keine. Ausgabe: [Ref, Breite in px]. */
function useBreite<T extends HTMLElement>(): [React.RefObject<T>, number] {
  const ref = useRef<T>(null);
  const [breite, setBreite] = useState(320);
  useEffect(() => {
    if (!ref.current || typeof ResizeObserver === "undefined") return;
    const beobachter = new ResizeObserver(([e]) => setBreite(Math.floor(e.contentRect.width)));
    beobachter.observe(ref.current);
    return () => beobachter.disconnect();
  }, []);
  return [ref, breite];
}

// ------------------------------------------------------------------ Zeitreihe

export interface Reihe {
  schluessel: string;
  name: string;
  farbe: string; // CSS-Variable
  strich?: string; // Strichmuster als zweite Kodierung neben der Farbe
}

interface ZeitreiheProps {
  daten: Array<Record<string, number | string>>;
  x: string;
  reihen: Reihe[];
  einheit: string;
  hoehe?: number;
}

/**
 * Liniendiagramm mit Fadenkreuz und Tooltip; Legende plus Direktbeschriftung am Linienende.
 * Eingabe: Datenzeilen, Schlüssel der x-Achse, Reihen (Schlüssel, Name, Farbe, Strich), Einheit, Höhe.
 * Ausgabe: SVG mit Legende.
 */
export function Zeitreihe({ daten, x, reihen, einheit, hoehe = 190 }: ZeitreiheProps) {
  const [ref, breite] = useBreite<HTMLDivElement>();
  const [aktiv, setAktiv] = useState<number | null>(null);
  const rand = { oben: 10, rechts: 46, unten: 22, links: 30 };
  const innenB = Math.max(breite - rand.links - rand.rechts, 50);
  const innenH = hoehe - rand.oben - rand.unten;

  const werte = daten.flatMap((d) => reihen.map((r) => Number(d[r.schluessel])));
  const min = Math.floor(Math.min(...werte) - 1);
  const max = Math.ceil(Math.max(...werte) + 0.5);
  const xs = scalePoint({ domain: daten.map((d) => String(d[x])), range: [0, innenB] });
  const ys = scaleLinear({ domain: [min, max], range: [innenH, 0], nice: true });
  const ticksY = ys.ticks(4);
  const letzter = daten[daten.length - 1];

  // Endbeschriftungen ohne Überlappung: von oben nach unten mit Mindestabstand stapeln
  const endPos: Record<string, number> = {};
  const MINDEST = 12;
  [...reihen]
    .map((r) => ({ s: r.schluessel, y: ys(Number(letzter[r.schluessel])) }))
    .sort((a, b) => a.y - b.y)
    .reduce((vorher, e) => {
      const y = Math.max(e.y, vorher + MINDEST);
      endPos[e.s] = y;
      return y;
    }, -Infinity);

  /** Markiert den Datenpunkt, der der Mausposition am nächsten liegt. Eingabe: Zeigerereignis. Ausgabe: keine. */
  function beiBewegung(e: React.PointerEvent<SVGRectElement>) {
    const box = e.currentTarget.getBoundingClientRect();
    const pos = e.clientX - box.left;
    const schritt = innenB / (daten.length - 1);
    setAktiv(Math.max(0, Math.min(daten.length - 1, Math.round(pos / schritt))));
  }

  const aktivDaten = aktiv === null ? null : daten[aktiv];

  return (
    <div ref={ref} className="diagramm">
      <svg width={breite} height={hoehe} role="img" aria-label={`Zeitreihe ${reihen.map((r) => r.name).join(", ")}`}>
        <g transform={`translate(${rand.links},${rand.oben})`}>
          {ticksY.map((t) => (
            <g key={t}>
              <line x1={0} x2={innenB} y1={ys(t)} y2={ys(t)} stroke="var(--linie)" strokeWidth={1} />
              <text x={-8} y={ys(t)} dy="0.32em" textAnchor="end" className="achse">
                {de(t, 0)}
              </text>
            </g>
          ))}
          {daten.map((d, i) =>
            i % 2 === 0 ? (
              <text key={String(d[x])} x={xs(String(d[x]))} y={innenH + 16} textAnchor="middle" className="achse">
                {String(d[x])}
              </text>
            ) : null,
          )}
          {reihen.map((r) => (
            <LinePath
              key={r.schluessel}
              data={daten}
              x={(d) => xs(String(d[x])) ?? 0}
              y={(d) => ys(Number(d[r.schluessel]))}
              stroke={r.farbe}
              strokeWidth={2}
              strokeDasharray={r.strich}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ))}
          {/* Direktbeschriftung am Linienende */}
          {reihen.map((r) => (
            <text
              key={r.schluessel}
              x={innenB + 6}
              y={endPos[r.schluessel]}
              dy="0.32em"
              className="achse achse-wert"
            >
              {de(Number(letzter[r.schluessel]), 1)}
            </text>
          ))}
          {aktivDaten && (
            <g>
              <line
                x1={xs(String(aktivDaten[x]))}
                x2={xs(String(aktivDaten[x]))}
                y1={0}
                y2={innenH}
                stroke="var(--text-leise)"
                strokeWidth={1}
              />
              {reihen.map((r) => (
                <circle
                  key={r.schluessel}
                  cx={xs(String(aktivDaten[x]))}
                  cy={ys(Number(aktivDaten[r.schluessel]))}
                  r={4}
                  fill={r.farbe}
                  stroke="var(--flaeche)"
                  strokeWidth={2}
                />
              ))}
            </g>
          )}
          <rect
            width={innenB}
            height={innenH}
            fill="transparent"
            onPointerMove={beiBewegung}
            onPointerLeave={() => setAktiv(null)}
          />
        </g>
      </svg>
      {aktivDaten && (
        <div
          className="tooltip"
          style={{ left: Math.min(rand.links + (xs(String(aktivDaten[x])) ?? 0) + 10, breite - 150) }}
          role="status"
        >
          <div className="tooltip-titel">{String(aktivDaten[x])}</div>
          {reihen.map((r) => (
            <div key={r.schluessel} className="tooltip-zeile">
              <span>{r.name}</span>
              <span>
                {de(Number(aktivDaten[r.schluessel]), 2)} {einheit}
              </span>
            </div>
          ))}
        </div>
      )}
      <ul className="legende">
        {reihen.map((r) => (
          <li key={r.schluessel}>
            <svg width="18" height="8" aria-hidden="true">
              <line x1="1" x2="17" y1="4" y2="4" stroke={r.farbe} strokeWidth="2" strokeDasharray={r.strich} />
            </svg>
            {r.name}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ------------------------------------------------------------------ Säulen

interface SaeulenProps {
  daten: Array<{ klasse: string; n: number }>;
  einheit: string;
  hoehe?: number;
}

/**
 * Säulen je Preisklasse; die stärkste Klasse trägt den Akzent, die übrigen Steingrau.
 * Eingabe: Klassen mit Anzahl n, Einheit, Höhe. Ausgabe: SVG mit Tooltip beim Überfahren.
 */
export function Saeulen({ daten, einheit, hoehe = 130 }: SaeulenProps) {
  const [ref, breite] = useBreite<HTMLDivElement>();
  const [aktiv, setAktiv] = useState<number | null>(null);
  const rand = { oben: 14, rechts: 0, unten: 30, links: 0 };
  const innenB = Math.max(breite - rand.links - rand.rechts, 50);
  const innenH = hoehe - rand.oben - rand.unten;
  const xs = scaleBand({ domain: daten.map((d) => d.klasse), range: [0, innenB], padding: 0.18 });
  const ys = scaleLinear({ domain: [0, Math.max(...daten.map((d) => d.n))], range: [innenH, 0] });
  const maxIndex = daten.reduce((m, d, i) => (d.n > daten[m].n ? i : m), 0);
  const radius = 2;

  return (
    <div ref={ref} className="diagramm">
      <svg width={breite} height={hoehe} role="img" aria-label="Preisklassen, Anzahl Angebote je Klasse">
        <g transform={`translate(${rand.links},${rand.oben})`}>
          {daten.map((d, i) => {
            const x = xs(d.klasse) ?? 0;
            const y = ys(d.n);
            const b = xs.bandwidth();
            const h = innenH - y;
            const r = Math.min(radius, h);
            // Nur oben gerundet, unten auf der Grundlinie verankert
            const pfad = `M${x},${innenH} V${y + r} Q${x},${y} ${x + r},${y} H${x + b - r} Q${x + b},${y} ${x + b},${y + r} V${innenH} Z`;
            return (
              <g
                key={d.klasse}
                onPointerEnter={() => setAktiv(i)}
                onPointerLeave={() => setAktiv(null)}
              >
                <rect x={x - 2} y={0} width={b + 4} height={innenH} fill="transparent" />
                <path d={pfad} fill={i === maxIndex ? "var(--akzent)" : "var(--linie-stark)"} opacity={aktiv === null || aktiv === i ? 1 : 0.6} />
                {(i === maxIndex || aktiv === i) && (
                  <text x={x + b / 2} y={y - 4} textAnchor="middle" className="achse achse-wert">
                    {d.n}
                  </text>
                )}
              </g>
            );
          })}
          <line x1={0} x2={innenB} y1={innenH} y2={innenH} stroke="var(--text)" strokeWidth={1} />
          {daten.map((d, i) =>
            i % 2 === 0 ? (
              <text key={d.klasse} x={(xs(d.klasse) ?? 0) + xs.bandwidth() / 2} y={innenH + 14} textAnchor="middle" className="achse">
                {d.klasse}
              </text>
            ) : null,
          )}
          <text x={innenB} y={innenH + 27} textAnchor="end" className="achse">
            {einheit}
          </text>
        </g>
      </svg>
      {aktiv !== null && (
        <div className="tooltip" style={{ left: Math.min((xs(daten[aktiv].klasse) ?? 0) + 8, breite - 150) }} role="status">
          <div className="tooltip-titel">{daten[aktiv].klasse} {einheit}</div>
          <div className="tooltip-zeile">
            <span>Angebote</span>
            <span>{daten[aktiv].n}</span>
          </div>
        </div>
      )}
    </div>
  );
}
