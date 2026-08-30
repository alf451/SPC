import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// build in "dist/" (servito da FastAPI in produzione, vedi backend/app/main.py
// e docs/installazione.md) - base relativa cosi' funziona sia in dev (root "/")
// sia montato sotto la root del backend.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
  },
  build: {
    outDir: "dist",
  },
});
