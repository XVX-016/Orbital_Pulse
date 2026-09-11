import { defineConfig, Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { viteStaticCopy } from "vite-plugin-static-copy";
import path from "node:path";
import fs from "node:fs";
import https from "node:https";

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
  worker: {
    format: "es",
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
    proxyApiPlugin(),
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

function proxyApiPlugin(): Plugin {
  const tleCache: Record<string, string> = {};

  const getConstellationTLE = (group: string): string | null => {
    if (tleCache[group]) return tleCache[group];
    try {
      const content = fs.readFileSync(path.resolve(import.meta.dirname, './client/lib/mock-tles.ts'), 'utf8');
      const marker = `${group}: \``;
      const s = content.indexOf(marker);
      if (s !== -1) {
        const ds = s + marker.length;
        const e = content.indexOf('`', ds);
        if (e !== -1) {
          const tle = content.slice(ds, e);
          tleCache[group] = tle;
          return tle;
        }
      }
      // If group not explicitly matched (e.g. active), return starlink cache (~11k satellites)
      if (group !== 'starlink') {
        return getConstellationTLE('starlink');
      }
      return null;
    } catch (err) {
      console.warn("Failed to load local TLE cache:", err);
      return null;
    }
  };

  return {
    name: "proxy-api",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (req.url && req.url.startsWith("/api/satellites/")) {
          const rawConstellation = req.url.split("/").pop();
          const constellation = rawConstellation?.split('?')[0].toLowerCase() || "active";
          
          const mirrorMap: Record<string, string> = {
            "starlink": "starlink.tle",
            "active": "active.tle",
            "stations": "stations.tle",
            "gps": "gps-ops.tle",
            "weather": "weather.tle",
            "resource": "resource.tle",
            "science": "science.tle",
            "cubesat": "cubesat.tle",
          };

          const mirrorFile = mirrorMap[constellation] || "active.tle";

          const fallback = () => {
            if (res.headersSent) return;
            const tle = getConstellationTLE(constellation) || getConstellationTLE('active') || getConstellationTLE('starlink');
            if (tle) {
              res.writeHead(200, { 
                'Content-Type': 'text/plain',
                'Cache-Control': 'public, max-age=3600'
              });
              res.end(tle);
            } else {
              res.statusCode = 500;
              res.end("Failed to load satellite data");
            }
          };

          const options = {
            headers: { 'User-Agent': 'OrbitalPulse-Dev/1.0 (Mozilla/5.0 Windows)' }
          };

          // Fetch from high-speed CelesTrak GitHub CDN mirror (avoids residential/ISP port blocks)
          let finished = false;
          const mirrorUrl = `https://raw.githubusercontent.com/satvisorcom/satvisor-data/master/celestrak/tle/${mirrorFile}`;

          const timeoutId = setTimeout(() => {
            if (finished) return;
            finished = true;
            mirrorReq.destroy();
            fallback();
          }, 8000);

          const mirrorReq = https.get(mirrorUrl, options, (mirrorRes) => {
            if (finished || res.headersSent) return;
            if (mirrorRes.statusCode && mirrorRes.statusCode >= 200 && mirrorRes.statusCode < 300) {
              clearTimeout(timeoutId);
              finished = true;
              res.writeHead(mirrorRes.statusCode, {
                'Content-Type': 'text/plain',
                'Cache-Control': 'public, max-age=300'
              });
              mirrorRes.pipe(res);
            } else {
              clearTimeout(timeoutId);
              finished = true;
              fallback();
            }
          });

          mirrorReq.on('error', () => {
            if (finished) return;
            clearTimeout(timeoutId);
            finished = true;
            fallback();
          });
          return;
        }

        if (req.url && req.url.startsWith("/api/ai/satellite-info") && req.method === "POST") {
          let body = "";
          req.on("data", chunk => { body += chunk.toString(); });
          req.on("end", async () => {
            try {
              const { name, type } = JSON.parse(body);
              let apiKey = process.env.OPENAI_API_KEY;
              if (!apiKey) {
                try {
                  const envFile = fs.readFileSync('.env', 'utf-8');
                  const match = envFile.match(/OPENAI_API_KEY=(.*)/);
                  if (match && match[1]) apiKey = match[1].trim();
                } catch(e) {}
              }
              
              if (!apiKey) {
                res.statusCode = 500;
                res.end(JSON.stringify({ error: "OpenAI API Key not configured." }));
                return;
              }

              const prompt = `Provide a very brief 2-3 sentence explanation of the satellite '${name}' (Type: ${type}). What is its primary purpose and origin?`;

              const openaiReq = https.request("https://api.openai.com/v1/chat/completions", {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  "Authorization": `Bearer ${apiKey}`
                }
              }, (openaiRes) => {
                let aiData = "";
                openaiRes.on("data", chunk => { aiData += chunk; });
                openaiRes.on("end", () => {
                  if (openaiRes.statusCode === 200) {
                    const responseJson = JSON.parse(aiData);
                    const text = responseJson.choices?.[0]?.message?.content || "No information available.";
                    res.writeHead(200, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ info: text }));
                  } else {
                    res.statusCode = openaiRes.statusCode || 500;
                    res.end(JSON.stringify({ error: "Failed to fetch from OpenAI", details: aiData }));
                  }
                });
              });
              
              openaiReq.on('error', (e) => {
                res.statusCode = 500;
                res.end(JSON.stringify({ error: e.message }));
              });
              
              openaiReq.write(JSON.stringify({
                model: "gpt-4o-mini",
                messages: [{ role: "user", content: prompt }]
              }));
              openaiReq.end();
              
            } catch (err) {
              res.statusCode = 400;
              res.end(JSON.stringify({ error: "Invalid request body" }));
            }
          });
          return;
        }

        next();
      });
    }
  };
}
