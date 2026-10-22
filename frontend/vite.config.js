import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => {
  const backendUrl = loadEnv(mode, process.cwd(), "VITE_").VITE_BACKEND_URL || "http://localhost:8000";
  return ({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: backendUrl,
        changeOrigin: true,
      },
      "/auth": {
        target: backendUrl,
        changeOrigin: true,
      },
      "/session/": {
        target: backendUrl,
        changeOrigin: true,
      },
      "/meta": {
        target: backendUrl,
        changeOrigin: true,
      },
      "/socket.io": {
        target: backendUrl,
        ws: true,
        changeOrigin: true,
      },
    },
  },
  });
});
