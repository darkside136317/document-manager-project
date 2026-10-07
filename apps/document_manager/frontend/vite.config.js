import { fileURLToPath } from "node:url";
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

// The SPA is served by Frappe (www/dashboard): the build lands in the app's public folder, where
// nginx exposes it under /assets/document_manager/staff/, and dashboard.py reads its manifest.
const outDir = fileURLToPath(new URL("../document_manager/public/staff", import.meta.url));

// Windows/Docker bind mounts do not deliver file-system events: poll when asked to.
const polling = process.env.DM_WATCH_POLL === "1";

export default defineConfig({
  base: "/assets/document_manager/staff/",
  plugins: [vue()],
  build: {
    outDir,
    emptyOutDir: true,
    manifest: true,
    sourcemap: false,
    rollupOptions: { input: "src/main.js" },
    watch: process.argv.includes("--watch")
      ? { chokidar: polling ? { usePolling: true, interval: 500 } : {} }
      : null,
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["tests/**/*.test.js"],
  },
});
