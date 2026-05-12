import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

function fileUrlToFsPath(relativePath: string): string {
  const fileUrl = new URL(relativePath, import.meta.url);
  const pathname = decodeURI(fileUrl.pathname);
  return pathname.replace(/^\/([A-Za-z]:\/)/, "$1");
}

const bundleDirectory = fileUrlToFsPath("../bundle");
const frontendDirectory = fileUrlToFsPath(".");

export default defineConfig({
  plugins: [react()],
  server: {
    fs: {
      allow: [frontendDirectory, bundleDirectory],
    },
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
