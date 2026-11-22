// Routing der App: Startseite, Analyse-Dashboard je Projekt und Zustandsübersicht.
import { Navigate, Route, Routes } from "react-router-dom";
import { Startseite } from "./seiten/Startseite";
import { Analyse } from "./seiten/Analyse";
import { Zustaende } from "./seiten/Zustaende";

/** App-Wurzel. Eingabe: keine. Ausgabe: die Seite zur aktuellen Adresse; Unbekanntes leitet auf die Startseite. */
export function App() {
  return (
    <Routes>
      <Route path="/" element={<Startseite />} />
      <Route path="/analyse/:id" element={<Analyse />} />
      <Route path="/zustaende" element={<Zustaende />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
