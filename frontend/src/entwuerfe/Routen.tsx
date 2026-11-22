// Routen unter /entwurf: Startseite, Analyse-Dashboard und Zustandsübersicht von Design D.
import { Navigate, Route, Routes } from "react-router-dom";
import { DashboardD, StartD, ZustaendeD } from "./d/RichtungD";

/** Seiten von Design D. Eingabe: keine. Ausgabe: die Seite zum Unterpfad; /entwurf allein leitet auf die Startseite. */
export function EntwurfRouten() {
  return (
    <Routes>
      <Route index element={<Navigate to="d" replace />} />
      <Route path="d" element={<StartD />} />
      <Route path="d/dashboard" element={<DashboardD />} />
      <Route path="d/zustaende" element={<ZustaendeD />} />
    </Routes>
  );
}
