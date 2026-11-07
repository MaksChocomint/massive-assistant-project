import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === "build" ? "/static/ui/" : "/",
  build: {
    outDir: "../app/static/ui",
    emptyOutDir: true,
    assetsInlineLimit: 0,
  },
  server: {
    proxy: {
      "/api": "http://localhost:8010",
      "/static": "http://localhost:8010",
      "/presentation": "http://localhost:8010",
      "/docs": "http://localhost:8010",
      "/openapi.json": "http://localhost:8010",
    },
  },
}));
