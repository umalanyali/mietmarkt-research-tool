// Merkliste: gesammelte Bausteine (Kennzahlen, Diagramme, Comps) für den PowerPoint-Export, per Drag & Drop sortierbar.
import { DndContext, KeyboardSensor, PointerSensor, closestCenter, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GriffSymbol } from "./Symbole";

export interface Baustein {
  id: string;
  titel: string;
  quelle: string;
  art: string;
  folie: string;
}

/** Eine sortierbare Zeile. Eingabe: Baustein, Quellenkürzel, Entfernen-Handler. Ausgabe: Listeneintrag. */
function Zeile({ b, kuerzel, onEntfernen }: { b: Baustein; kuerzel: string; onEntfernen: () => void }) {
  // dnd-kit liefert Verschiebung und Griff-Ereignisse; nur der Griff startet das Ziehen
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: b.id });
  return (
    <li
      ref={setNodeRef}
      className={`merkliste-zeile${isDragging ? " zieht" : ""}`}
      style={{ transform: CSS.Transform.toString(transform), transition }}
    >
      <button type="button" className="griff" aria-label={`${b.titel} verschieben`} {...attributes} {...listeners}>
        <GriffSymbol />
      </button>
      <span className="merkliste-kuerzel" title={b.quelle}>
        {kuerzel}
      </span>
      <div className="merkliste-text">
        <div>{b.titel}</div>
        <div className="etikett">
          {b.quelle} · {b.art} → Folie „{b.folie}“
        </div>
      </div>
      <button type="button" className="entfernen" aria-label={`${b.titel} entfernen`} onClick={onEntfernen}>
        ×
      </button>
    </li>
  );
}

interface Props {
  bausteine: Baustein[];
  onAenderung: (neu: Baustein[]) => void;
  /** Quellenkürzel je Baustein, z. B. „M“ für Marktbericht */
  kuerzel: (b: Baustein) => string;
}

/**
 * Merkliste mit Export-Knopf. Reihenfolge per Maus oder Tastatur (Griff fokussieren, Leertaste, Pfeiltasten).
 * Eingabe: Bausteine, Änderungs-Handler, Kürzel-Funktion. Ausgabe: Liste, Knopf und Folienzahl.
 */
export function Merkliste({ bausteine, onAenderung, kuerzel }: Props) {
  const sensoren = useSensors(
    // 4 px Mindestweg, damit ein normaler Klick auf den Griff kein Ziehen auslöst
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  /** Nach dem Ablegen: Baustein an die neue Position verschieben. Eingabe: Drag-Ereignis. Ausgabe: keine. */
  function beiEnde(e: DragEndEvent) {
    if (!e.over || e.active.id === e.over.id) return;
    const von = bausteine.findIndex((b) => b.id === e.active.id);
    const nach = bausteine.findIndex((b) => b.id === e.over!.id);
    onAenderung(arrayMove(bausteine, von, nach));
  }

  const folien = new Set(bausteine.map((b) => b.folie)).size;

  return (
    <div className="merkliste">
      {bausteine.length === 0 ? (
        <p className="merkliste-leer">Noch nichts gemerkt. Über den Stern an Kennzahlen, Diagrammen und Comps hinzufügen.</p>
      ) : (
        <DndContext sensors={sensoren} collisionDetection={closestCenter} onDragEnd={beiEnde}>
          <SortableContext items={bausteine.map((b) => b.id)} strategy={verticalListSortingStrategy}>
            <ol className="merkliste-liste">
              {bausteine.map((b) => (
                <Zeile key={b.id} b={b} kuerzel={kuerzel(b)} onEntfernen={() => onAenderung(bausteine.filter((x) => x.id !== b.id))} />
              ))}
            </ol>
          </SortableContext>
        </DndContext>
      )}
      <button type="button" className="merkliste-export" disabled={bausteine.length === 0}>
        PowerPoint erstellen
      </button>
      <p className="etikett merkliste-fuss">
        {folien} Folien · Deck-Prüfung und Quellenzeile vor dem Export
      </p>
    </div>
  );
}
