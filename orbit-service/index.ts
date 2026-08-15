import express, { Request, Response } from "express";
import cors from "cors";

const app = express();
const PORT = process.env.PORT || 8081;
const FRONTEND_ORIGIN = process.env.FRONTEND_ORIGIN || "http://localhost:5173";

// Enable CORS for frontend origin
app.use(
  cors({
    origin: (origin, callback) => {
      // Allow requests with no origin (like mobile apps, curl, or same-origin) or matching origin
      if (!origin || origin === FRONTEND_ORIGIN || origin.startsWith("http://localhost:")) {
        callback(null, true);
      } else {
        callback(null, true); // Permissive for local dev & demo flexibility
      }
    },
  })
);

app.use(express.json());

interface CacheEntry {
  data: string;
  timestamp: number;
}

// In-memory cache for TLE groups
const tleCache: Record<string, CacheEntry> = {};
const CACHE_TTL_MS = 6 * 60 * 60 * 1000; // 6 hours

// GET /health
app.get("/health", (_req: Request, res: Response) => {
  res.json({ status: "ok" });
});

// GET /api/tle?group=active
app.get("/api/tle", async (req: Request, res: Response) => {
  const group = (req.query.group as string) || "active";
  const now = Date.now();
  const cached = tleCache[group];

  if (cached && now - cached.timestamp < CACHE_TTL_MS) {
    console.log(`[Cache HIT] Serving cached TLE data for group: ${group}`);
    res.setHeader("Content-Type", "text/plain");
    res.setHeader("X-Cache-Status", "HIT");
    res.send(cached.data);
    return;
  }

  console.log(`[Cache MISS / LIVE FETCH] Fetching TLE data from CelesTrak for group: ${group}...`);

  const celestrakUrl = `https://celestrak.org/NORAD/elements/gp.php?GROUP=${encodeURIComponent(group)}&FORMAT=tle`;

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000); // 15s timeout

    const response = await fetch(celestrakUrl, {
      signal: controller.signal,
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OrbitalPulse/1.0",
      },
    });
    clearTimeout(timeout);

    if (!response.ok) {
      throw new Error(`CelesTrak responded with HTTP status ${response.status}`);
    }

    const text = await response.text();

    if (!text || text.trim().length === 0) {
      throw new Error("CelesTrak returned empty response");
    }

    // Cache the raw TLE text in memory
    tleCache[group] = {
      data: text,
      timestamp: Date.now(),
    };

    console.log(`[Live Fetch SUCCESS] Successfully fetched and cached TLE data for group: ${group} (${text.length} bytes)`);

    res.setHeader("Content-Type", "text/plain");
    res.setHeader("X-Cache-Status", "MISS");
    res.send(text);
  } catch (err: any) {
    console.error(`[Live Fetch FAILED] Error fetching TLE data for group '${group}':`, err.message || err);

    // If fetch failed and no cache exists, return 503 quickly
    res.status(503).json({
      error: "Service Unavailable",
      message: `Failed to fetch TLE data for group '${group}' from CelesTrak and no cached data is available.`,
      details: err.message || String(err),
    });
  }
});

app.listen(PORT, () => {
  console.log(`[Orbit Service] Orbit service listening on port ${PORT}`);
  console.log(`[Orbit Service] CORS configured for frontend origin: ${FRONTEND_ORIGIN}`);
});
