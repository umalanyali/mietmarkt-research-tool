// Oberste Routing-Ebene: Alles läuft über Design D; unbekannte Adressen landen auf dessen Startseite.
import { Navigate, Route, Routes } from "react-router-dom";
import { EntwurfRouten } from "./entwuerfe/Routen";

/** App-Wurzel. Eingabe: keine. Ausgabe: die passende Seite zur aktuellen Adresse. */
export function App() {
  return (
    <Routes>
      <Route path="/entwurf/*" element={<EntwurfRouten />} />
      <Route path="*" element={<Navigate to="/entwurf/d" replace />} />
    </Routes>
  );
}
