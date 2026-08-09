import { defineConfig, Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { viteStaticCopy } from "vite-plugin-static-copy";
import path from "node:path";
import fs from "node:fs";

const cesiumBaseUrl = "cesiumStatic";
const cesiumSource = "node_modules/cesium/Build/Cesium";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  define: {
    CESIUM_BASE_URL: JSON.stringify(`/${cesiumBaseUrl}/`),
  },
  server: {
    host: "::",
    port: 8080,
    fs: {
      allow: ["./client", "./shared", "index.html", "node_modules/cesium"],
      deny: [".env", ".env.*", "*.{crt,pem}", "**/.git/**"],
    },
  },
  build: {
    outDir: "dist/spa",
  },
  plugins: [
    react(),
    viteStaticCopy({
      targets: [
        { src: `${cesiumSource}/Assets`, dest: cesiumBaseUrl },
        { src: `${cesiumSource}/ThirdParty`, dest: cesiumBaseUrl },
        { src: `${cesiumSource}/Widgets`, dest: cesiumBaseUrl },
        { src: `${cesiumSource}/Workers`, dest: cesiumBaseUrl },
      ],
    }),
    serveCesiumDevPlugin(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./client"),
      "@shared": path.resolve(import.meta.dirname, "./shared"),
    },
  },
}));

function serveCesiumDevPlugin(): Plugin {
  return {
    name: "serve-cesium-dev",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (req.url && req.url.startsWith(`/${cesiumBaseUrl}/`)) {
          const cleanUrl = req.url.split("?")[0];
          const relativePath = cleanUrl.replace(new RegExp(`^/${cesiumBaseUrl}/`), "");
          const filePath = path.resolve(import.meta.dirname, cesiumSource, relativePath);
          if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
            const ext = path.extname(filePath).toLowerCase();
            const mimeTypes: Record<string, string> = {
              ".json": "application/json",
              ".js": "application/javascript",
              ".png": "image/png",
              ".jpg": "image/jpeg",
              ".jpeg": "image/jpeg",
              ".css": "text/css",
              ".wasm": "application/wasm",
              ".gltf": "model/gltf+json",
              ".bgltf": "model/gltf-binary",
              ".glb": "model/gltf-binary",
            };
            res.setHeader("Content-Type", mimeTypes[ext] || "application/octet-stream");
            return fs.createReadStream(filePath).pipe(res);
          }
        }
        next();
      });
    },
  };
}




