// Markdown aus Agententexten (fett, Listen, Tabellen) als HTML. Rohes HTML im Text wird nicht ausgeführt, Bilder und
// Links werden nicht gerendert (Sicherheitsbefund M1: Modelltext kann aus präparierten Unterlagen stammen).
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Tabellen in einem eigenen Scroll-Container, damit breite Tabellen nicht die ganze Seite verbreitern. */
const TEILE = { table: (p: JSX.IntrinsicElements["table"]) => <div className="e-tabelle-scroll"><table className="e-tabelle" {...p} /></div> };
// Ein Bild lädt der Browser sofort beim Anzeigen, ein Link nach einem Klick; eine präparierte Unterlage könnte so
// Projektdaten in die URL schreiben. Links bleiben als Text stehen (unwrapDisallowed), Bilder fallen weg.
const VERBOTEN = ["img", "a"];

/**
 * Rendert Markdown (GitHub-Variante mit Tabellen). Eingabe: Text, optionale CSS-Klasse des Rahmens.
 * Ausgabe: div mit Absätzen, Listen und Tabellen; react-markdown lässt HTML im Text standardmäßig weg.
 */
export function Markdown({ text, className }: { text: string; className?: string }) {
  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={TEILE} disallowedElements={VERBOTEN} unwrapDisallowed>
        {text}
      </ReactMarkdown>
    </div>
  );
}
