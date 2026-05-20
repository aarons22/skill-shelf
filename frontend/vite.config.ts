import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiProxyTarget =
  process.env.VITE_API_PROXY_TARGET ?? "http://localhost:3000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    watch: { usePolling: true },
    proxy: {
      "/api": apiProxyTarget,
      "/auth": apiProxyTarget,
      "/m/": apiProxyTarget,
    },
  },
});
