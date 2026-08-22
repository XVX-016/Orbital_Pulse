# SatQuery AI

A full-stack remote-sensing VQA and change-analysis platform featuring natural-language querying of multi-temporal optical & SAR satellite imagery, orchestrated by an agentic multimodal controller and backed by PostGIS.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         Browser (User)                          │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │  /           │  │  /analyze    │  │  /about               │  │
│  │  Landing     │  │  SatQuery AI │  │  Architecture &       │  │
│  │  Hero & EONET│  │  Query Agent │  │  Edge Roadmap         │  │
│  └──────────────┘  └──────┬───────┘  └───────────────────────┘  │
└───────────────────────────┼──────────────────────────────────────┘
                            │
                   POST /api/analyze
                   GET /health
                            │
                 ┌──────────▼──────────────┐
                 │  satquery-service       │
                 │  FastAPI (8082)         │
                 │  - Controller           │
                 │  - Task Router          │
                 │  - Specialists (VQA,    │
                 │    Change, SAR, Ground) │
                 │  - Prithvi-EO / GeoChat │
                 └──────────┬──────────────┘
                            │
                 ┌──────────▼──────────────┐
                 │  PostGIS (5432)         │
                 │  postgis/postgis:16-3.4 │
                 └─────────────────────────┘
```

## Services

| Service | Port | Description |
|---|---|---|
| **Frontend** | `5173` | React SPA served via Nginx (Docker) or Vite dev server (local) |
| **Orbit Service** | `8081` | Express proxy for CelesTrak TLE data with 6-hour in-memory cache |
| **AI Inference Service** | `8082` | FastAPI + Prithvi-EO-1.0-100M for satellite image change detection |
| **PostGIS** | `5432` | PostgreSQL 16 + PostGIS 3.4 geospatial database |

## Prerequisites

- **Docker** ≥ 24.0 and **Docker Compose** ≥ 2.20 (for containerized stack)
- **Node.js** ≥ 20 and **pnpm** ≥ 10 (for local development)
- **Python** ≥ 3.11 (for running `prepare_data.py` locally)
- A **Cesium Ion token** from [ion.cesium.com/tokens](https://ion.cesium.com/tokens)

---

## Environment Setup

1. Copy the example env file:
   ```bash
   cp .env.example .env
   ```

2. Fill in the required values:
   ```env
   # Required — 3D globe won't render without this
   VITE_CESIUM_ION_TOKEN=your_cesium_ion_token_here

   # These default to localhost and are correct for both local dev and Docker
   VITE_ORBIT_SERVICE_URL=http://localhost:8081
   VITE_AI_SERVICE_URL=http://localhost:8082

   # PostGIS credentials (used by docker-compose)
   POSTGRES_USER=orbital_user
   POSTGRES_PASSWORD=orbital_password
   POSTGRES_DB=orbital_db
   ```

---

## Data Preparation (AI Inference Service)

The AI inference service requires **real GeoTIFF satellite imagery** — it does NOT fall back to random noise. You must provide source data and run the preprocessing script before the `/api/change-detection` endpoint will work.

### Step 1: Source the Data

Place raw GeoTIFF files in `ai-inference-service/raw_data/`:

```
ai-inference-service/raw_data/
├── deforestation/
│   ├── before.tif    ← Sentinel-2 L2A, Rondônia region, ~2019
│   └── after.tif     ← Sentinel-2 L2A, Rondônia region, ~2023
└── disaster/
    ├── before.tif    ← Pre-disaster imagery (Sentinel-2 or xBD)
    └── after.tif     ← Post-disaster imagery
```

#### Where to get data

| Source | Type | Bands | Resolution | URL |
|---|---|---|---|---|
| **Copernicus Open Access Hub** | Sentinel-2 L2A | 13 bands | 10–60m | [scihub.copernicus.eu](https://scihub.copernicus.eu/) |
| **Copernicus Browser** | Sentinel-2 (easy download) | 13 bands | 10–60m | [browser.dataspace.copernicus.eu](https://browser.dataspace.copernicus.eu/) |
| **xBD Dataset** | Maxar/DigitalGlobe | 3 bands (RGB) | ~0.3m | [xview2.org](https://xview2.org/) |
| **USGS Earth Explorer** | Landsat / Sentinel | varies | 10–30m | [earthexplorer.usgs.gov](https://earthexplorer.usgs.gov/) |

#### Band compatibility

| Source | Band Count | Prithvi Compatibility |
|---|---|---|
| Sentinel-2 L2A (13-band) | 13 | ✅ Full — script selects B2, B3, B4, B8A, B11, B12 |
| Sentinel-2 subset (6-band) | 6 | ✅ Full — used as-is (assumed HLS order) |
| xBD / RGB imagery | 3 | ⚠️ Padded to 6 bands — model output less meaningful |

### Step 2: Run the Preprocessing Script

```bash
cd ai-inference-service
python scripts/prepare_data.py \
  --raw-dir raw_data/ \
  --output-dir data/ \
  --preview-dir public/images/
```

This will:
1. **Validate** each source file is a readable GeoTIFF
2. **Select/map bands** to produce 6-band HLS-ordered data
3. **Resize** to 224×224 (Prithvi's expected input size)
4. **Write** preprocessed GeoTIFFs to `data/`
5. **Generate JPEG previews** to `public/images/` (displayed in the frontend slider)

The script **fails loudly** with a clear error and exit code 1 if any file is missing or malformed.

### Output

```
ai-inference-service/
├── data/                           ← Preprocessed (6-band, 224×224, float32)
│   ├── deforestation/
│   │   ├── before.tif
│   │   └── after.tif
│   └── disaster/
│       ├── before.tif
│       └── after.tif
└── public/images/                  ← JPEG previews for frontend
    ├── deforestation-before.jpg
    ├── deforestation-after.jpg
    ├── disaster-before.jpg
    └── disaster-after.jpg
```

---

## Edge Deployment Quantization Benchmarking

To benchmark the Prithvi model for the **Edge Deployment Roadmap** (comparing FP32 full precision vs. dynamic INT8 quantization on CPU hardware), run:

```bash
cd ai-inference-service
python scripts/benchmark_quantization.py --iterations 5
```

### Benchmarking Outputs
- **Console Summary**: Displays model memory size before/after, CPU latency before/after, speedup factor, and mask Cosine Similarity / MSE metrics.
- **`benchmark_results.json`**: Structured JSON report for automated validation and slide metrics.
- **`benchmark_results.csv`**: Tabular CSV summary formatted for presentation charts.


---

## Docker Compose (Full Stack)

> **Prerequisites**: Docker ≥ 24.0 and Docker Compose ≥ 2.20 must be installed and the Docker daemon must be running before any of the commands below.

### Step 0: Environment Setup (Required)

Before running Docker, ensure your `.env` is configured:

```bash
cp .env.example .env
# Edit .env and set VITE_CESIUM_ION_TOKEN — the globe will not render without it
```

The `VITE_CESIUM_ION_TOKEN` is passed as a **Docker build arg** to the frontend service (baked into the Nginx bundle at image-build time). If it is missing, the CesiumJS globe will fail to initialize silently — there is no runtime injection.

### Step 1: Place Raw GeoTIFF Data (Required for Change Detection)

The AI inference service requires real satellite imagery. Place source files **on the host** at:

```
ai-inference-service/raw_data/
├── deforestation/
│   ├── before.tif    ← Sentinel-2 L2A, Rondônia region, ~2019
│   └── after.tif     ← Sentinel-2 L2A, Rondônia region, ~2023
└── disaster/
    ├── before.tif    ← Pre-disaster imagery
    └── after.tif     ← Post-disaster imagery
```

The `raw_data/` directory is bind-mounted read-only into the container. **The container will automatically run `prepare_data.py` at startup** to preprocess these files into the `ai-data` named volume. If files are missing, the service will still start and pass its healthcheck, but `/api/change-detection` will return HTTP 503 with an actionable error message.

### Step 2: Clean Slate

Remove all containers, named volumes (including cached model weights and preprocessed data), and orphaned services:

```bash
docker compose down -v --remove-orphans
```

> ⚠️ **`-v` wipes named volumes** — this includes `huggingface-cache` (model weights) and `ai-data` / `ai-previews` (preprocessed data). On the next `up --build`, the model will be re-downloaded and `prepare_data.py` will re-process raw data from the host bind mount. Omit `-v` to preserve cached weights across restarts.

### Step 3: Build and Start

```bash
docker compose up --build
```

This builds and starts all 4 services. **Startup is ordered by healthcheck dependencies**:

```
postgis ──healthcheck──► (no dependents at startup)
orbit-service ──healthcheck──► frontend waits here
ai-inference-service ──healthcheck──► frontend waits here
                   └─ runs prepare_data.py, then uvicorn
frontend ◄── starts only after orbit-service AND ai-inference-service are both healthy
```

Expected startup timeline:
- `postgis`: healthy in ~15s
- `orbit-service`: healthy in ~20–30s (fetches CelesTrak TLE data on first request)
- `ai-inference-service`: healthy in **90–120s** (GDAL + model download/load from cache; `start_period: 120s`)
- `frontend`: starts after both services are healthy

Once up, confirm all four services are healthy:

```bash
docker compose ps
# Expected output (all STATUS fields showing "healthy"):
# NAME                                   STATUS
# orbital_pulse-ai-inference-service-1   Up N minutes (healthy)
# orbital_pulse-frontend-1               Up N minutes (healthy)
# orbital_pulse-orbit-service-1          Up N minutes (healthy)
# orbital_pulse-postgis-1                Up N minutes (healthy)
```

### Step 4: Verify Each Service

#### 4a. Frontend — `http://localhost:5173`

- Landing page loads with the 3D Earth hero and "Launch Globe" CTA
- Navigation bar links to `/globe`, `/change-detection`, `/about` all work
- No console errors about missing assets

#### 4b. Globe / Orbit Service — `http://localhost:5173/globe`

- 3D CesiumJS globe renders with photorealistic Earth imagery
- **Status pill must show `"X satellites loaded (Orbit Service)"` — NOT `"Offline Catalog"`**
- Satellite markers (blue dots) are visible orbiting the Earth
- If it shows Offline Catalog, the orbit-service is not reachable. Diagnose:
  ```bash
  docker compose logs orbit-service          # check for fetch errors
  docker compose ps                           # verify service is healthy
  curl http://localhost:8081/health           # confirm it responds
  curl http://localhost:8081/api/tle | head   # confirm TLE data is returned (text/plain format)
  ```
  The `VITE_ORBIT_SERVICE_URL` is baked in at build time as `http://localhost:8081`. The browser fetches it from the host machine — this works as long as port 8081 is published (it is).

#### 4c. Change Detection — `http://localhost:5173/change-detection`

- Before/after image slider shows real satellite imagery (not blank)
- Clicking **Run Detection** returns a `change_percentage` value (not a 503 or network error)

**Verify data is mounted correctly inside the container:**
```bash
# Check that prepare_data.py output landed in the named volume
docker compose exec ai-inference-service ls -la data/deforestation/ data/disaster/

# Check that JPEG previews are in the named volume
docker compose exec ai-inference-service ls -la public/images/

# Confirm the service reports data_ready: true
curl http://localhost:8082/health
# Expected: {"status":"ok","model":"ibm-nasa-geospatial/Prithvi-EO-1.0-100M","data_ready":true}
```

If `data_ready: false`:
```bash
# Re-run prepare_data.py inside the running container
docker compose exec ai-inference-service python scripts/prepare_data.py

# Restart to re-validate on startup (optional — the exec above is sufficient)
docker compose restart ai-inference-service
```

#### 4d. PostGIS — `localhost:5432`

```bash
# Requires psql installed locally, or use the container:
docker compose exec postgis psql -U orbital_user -d orbital_db -c "SELECT PostGIS_Version();"
```

Expected output: a PostGIS version string like `3.4 USE_GEOS=1 USE_PROJ=1 USE_STATS=1`.

### Verify Healthcheck-Based Startup Ordering

To confirm the `depends_on: condition: service_healthy` ordering actually held during startup (not just that everything eventually came up), check container creation timestamps:

```bash
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.CreatedAt}}"
```

The `frontend` container's `CreatedAt` timestamp must be **later** than both `orbit-service` and `ai-inference-service` — it cannot start until both report healthy. You can also inspect the ordering in the startup log stream: `frontend` will not appear until after `orbit-service ... healthy` and `ai-inference-service ... healthy` are both logged.

### Volume Mounts Reference

| Volume | Type | Purpose |
|---|---|---|
| `pgdata` | Named | PostGIS database files |
| `huggingface-cache` | Named | Prithvi model weights (avoid re-downloading) |
| `ai-data` | Named | Preprocessed 6-band 224×224 GeoTIFFs (output of `prepare_data.py`) |
| `ai-previews` | Named | JPEG previews for the frontend slider |
| `./ai-inference-service/raw_data` | Bind (ro) | Raw source GeoTIFFs from host — **must exist before `up`** |

---

## Verification Checklist

After `docker compose up --build`, confirm:

- [ ] `http://localhost:5173` — landing page loads
- [ ] `http://localhost:5173/globe` — globe renders, pill shows **Orbit Service** (not Offline Catalog)
- [ ] `http://localhost:5173/change-detection` — slider shows real imagery; Run Detection returns a result
- [ ] `http://localhost:5173/about` — About page with roadmap timeline loads
- [ ] `curl http://localhost:8081/health` → `{"status":"ok"}`
- [ ] `curl http://localhost:8082/health` → `{"status":"ok","data_ready":true}`
- [ ] `docker compose exec postgis psql -U orbital_user -d orbital_db -c "SELECT PostGIS_Version();"` — returns version string
- [ ] `docker compose ps` — all 4 services show `healthy` status



---

## Local Development (without Docker)

### Frontend + Orbit Service

```bash
# Install dependencies
pnpm install

# Start the Vite dev server (frontend on port 8080)
pnpm dev

# In a separate terminal, start the orbit service
pnpm run orbit-service
```

### AI Inference Service

```bash
cd ai-inference-service

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Preprocess data (after placing raw TIFFs in raw_data/)
python scripts/prepare_data.py

# Start the service
uvicorn main:app --host 0.0.0.0 --port 8082
```

---

## Project Structure

```
orbital-pulse/
├── client/                         # React SPA frontend
│   ├── pages/                      # Route components
│   │   ├── Index.tsx               # Landing page
│   │   ├── Globe.tsx               # 3D satellite globe (CesiumJS)
│   │   ├── ChangeDetection.tsx     # AI change detection with image slider
│   │   ├── About.tsx               # About page
│   │   └── NotFound.tsx            # 404 page
│   ├── components/                 # Reusable UI components
│   │   ├── globe/                  # Globe-specific components
│   │   ├── layout/                 # App layout (navbar, etc.)
│   │   └── ui/                     # Radix UI component library
│   ├── lib/                        # Utilities and services
│   │   ├── globe-context.tsx       # Globe state management
│   │   ├── satellite-service.ts    # TLE parsing + orbit propagation
│   │   └── utils.ts                # cn() helper
│   ├── App.tsx                     # Entry point + routing
│   ├── global.css                  # TailwindCSS theme
│   ├── Dockerfile                  # Multi-stage: build + Nginx
│   └── nginx.conf                  # SPA routing config
│
├── orbit-service/                  # TLE proxy service
│   ├── index.ts                    # Express server + CelesTrak fetch
│   └── Dockerfile                  # Node.js runtime
│
├── ai-inference-service/           # AI change detection service
│   ├── main.py                     # FastAPI app + Prithvi inference
│   ├── scripts/
│   │   └── prepare_data.py         # GeoTIFF validation + preprocessing
│   ├── raw_data/                   # User-provided source GeoTIFFs
│   ├── data/                       # Preprocessed 6-band 224×224 TIFFs
│   ├── public/
│   │   ├── images/                 # JPEG previews for frontend
│   │   └── masks/                  # Inference output masks
│   ├── requirements.txt            # Python dependencies
│   └── Dockerfile                  # Python runtime + GDAL
│
├── shared/                         # Shared TypeScript types
│   └── api.ts                      # API interfaces
│
├── docker-compose.yml              # Full stack orchestration
├── .env.example                    # Environment variable template
├── package.json                    # Node.js dependencies + scripts
├── vite.config.ts                  # Vite + Cesium config
├── tailwind.config.ts              # TailwindCSS theme
└── tsconfig.json                   # TypeScript config
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, TailwindCSS 3, CesiumJS, React Router 6 |
| Globe | CesiumJS + Resium, satellite.js for orbit propagation |
| Orbit Service | Express 5, Node.js 20 |
| AI Service | FastAPI, PyTorch, HuggingFace Transformers, rasterio/GDAL |
| AI Model | [Prithvi-EO-1.0-100M](https://huggingface.co/ibm-nasa-geospatial/Prithvi-EO-1.0-100M) (IBM/NASA) |
| Database | PostgreSQL 16 + PostGIS 3.4 |
| Build | Vite 8, pnpm |
| Deploy | Docker Compose, Nginx |
