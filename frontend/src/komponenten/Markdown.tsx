// Markdown aus Agententexten (fett, Listen, Tabellen) als HTML. Rohes HTML im Text wird nicht ausgeführt.
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Tabellen in einem eigenen Scroll-Container, damit breite Tabellen nicht die ganze Seite verbreitern. */
const TEILE = { table: (p: JSX.IntrinsicElements["table"]) => <div className="e-tabelle-scroll"><table className="e-tabelle" {...p} /></div> };

/**
 * Rendert Markdown (GitHub-Variante mit Tabellen). Eingabe: Text, optionale CSS-Klasse des Rahmens.
 * Ausgabe: div mit Absätzen, Listen und Tabellen; react-markdown lässt HTML im Text standardmäßig weg.
 */
export function Markdown({ text, className }: { text: string; className?: string }) {
  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={TEILE}>
        {text}
      </ReactMarkdown>
    </div>
  );
}
