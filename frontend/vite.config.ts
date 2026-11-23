// Vite-Konfiguration: Dev-Server auf Port 5173 mit Weiterleitung von /api an das Backend, dazu vitest in jsdom.
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Kein CORS: sonst könnte jede fremde Website im Browser über den Proxy die lokale API lesen (Befund S1)
    cors: false,
    // API_PORT nur für skripte/lauf.mjs (Backend mit Fake-Modell auf eigenem Port)
    proxy: { "/api": `http://127.0.0.1:${process.env.API_PORT ?? 8000}` },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
