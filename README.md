# Orbital Pulse

A full-stack satellite tracking and Earth observation platform featuring a 3D globe with live satellite positions, AI-powered change detection using NASA/IBM's Prithvi foundation model, and a PostGIS-backed geospatial database.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         Browser (User)                          │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │  /           │  │  /globe      │  │  /change-detection    │  │
│  │  Landing     │  │  CesiumJS    │  │  Before/After Slider  │  │
│  │  Page        │  │  3D Globe    │  │  + AI Inference       │  │
│  └──────────────┘  └──────┬───────┘  └───────────┬───────────┘  │
└──────────────────────────────────────────────────────────────────┘
                            │                      │
                   Live TLE data           POST /api/change-detection
                   GET /api/tle            GET /images/*.jpg (previews)
                            │                      │
                 ┌──────────▼───────┐   ┌──────────▼──────────────┐
                 │  orbit-service   │   │  ai-inference-service   │
                 │  Express (8081)  │   │  FastAPI (8082)         │
                 │                  │   │  Prithvi-EO-1.0-100M    │
                 │  Fetches from    │   │  GeoTIFF processing     │
                 │  CelesTrak API   │   │  Change detection masks │
                 └──────────────────┘   └─────────────────────────┘
                                                   │
                                        ┌──────────▼──────────────┐
                                        │  PostGIS (5432)         │
                                        │  postgis/postgis:16-3.4 │
                                        │  Geospatial database    │
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

### Clean Start

Remove any existing containers, volumes, and orphaned services:

```bash
docker compose down -v --remove-orphans
```

### Build and Start

```bash
docker compose up --build
```

This starts all 4 services:
- **Frontend** → `http://localhost:5173`
- **Orbit Service** → `http://localhost:8081`
- **AI Inference Service** → `http://localhost:8082`
- **PostGIS** → `localhost:5432`

> **Note**: The AI inference service takes ~60s to start (model loading). The health check has a `start_period: 60s` to accommodate this.

### Volume Mounts

| Volume | Purpose |
|---|---|
| `huggingface-cache` | Caches the Prithvi model weights between restarts |
| `ai-data` | Preprocessed GeoTIFFs persist across container restarts |
| `ai-previews` | JPEG preview images for frontend |
| `pgdata` | PostGIS database files |
| `./ai-inference-service/raw_data` → `/app/raw_data` (bind mount, read-only) | Raw source GeoTIFFs from host |

### Using Data with Docker

If you want to preprocess data **inside** the container:

```bash
# Start just the AI service
docker compose up -d ai-inference-service

# Run the preprocessing script inside the container
docker compose exec ai-inference-service python scripts/prepare_data.py

# Restart to pick up the validated data
docker compose restart ai-inference-service
```

Or preprocess **locally** before building:

```bash
cd ai-inference-service
python scripts/prepare_data.py
cd ..
docker compose up --build
```

---

## Verification Checklist

After running `docker compose up --build`, verify each service:

### 1. Frontend (`http://localhost:5173`)

- [ ] Landing page loads at `http://localhost:5173`
- [ ] Navigation works (Globe, Change Detection, About links)
- [ ] No console errors related to missing assets

### 2. Globe Page — Live TLE Data (`http://localhost:5173/globe`)

- [ ] 3D CesiumJS globe renders
- [ ] **The status pill shows "X satellites loaded (Orbit Service)"** — NOT "Offline Catalog"
- [ ] If the pill says "Offline Catalog", the orbit-service is not reachable from the frontend
- [ ] Satellites appear as points on the globe
- [ ] Search and Inspector panel work

**Troubleshooting "Offline Catalog"**:
- Check orbit-service logs: `docker compose logs orbit-service`
- The frontend fetches from `VITE_ORBIT_SERVICE_URL` (baked in at build time)
- In Docker, this is set to `http://localhost:8081` in `docker-compose.yml` build args
- CelesTrak may rate-limit or block requests — check for 429/503 errors in orbit-service logs

### 3. Change Detection (`http://localhost:5173/change-detection`)

- [ ] Before/after image slider shows real satellite imagery previews (not blank/placeholder)
- [ ] Clicking "Run Detection" returns a result (not an error)
- [ ] Result shows `change_percentage` and a mask URL
- [ ] If `used_fallback_mask: true`, the model's output format doesn't match the expected embedding shape (non-critical)

**Troubleshooting**:
- If images are blank: check that `prepare_data.py` was run and JPEG previews exist in `public/images/`
- If "AI inference service is unreachable": check `docker compose logs ai-inference-service`
- If "Preprocessed data is not available": run `prepare_data.py` first
- If "Model not loaded": the Prithvi model failed to download — check HuggingFace connectivity

### 4. PostGIS (`localhost:5432`)

- [ ] Database is reachable:
  ```bash
  psql -h localhost -p 5432 -U orbital_user -d orbital_db -c "SELECT PostGIS_Version();"
  ```
  (Password: `orbital_password`)

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
