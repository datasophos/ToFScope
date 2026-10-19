import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  server: {
    port: 18763,
    strictPort: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:18764", changeOrigin: false },
      "/healthz": "http://127.0.0.1:18764",
    },
  },
  build: { chunkSizeWarningLimit: 1600 },
});
