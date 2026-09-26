# SatQuery AI — Agentic Remote-Sensing VQA & Multi-Modal Analysis Platform

SatQuery AI is an agentic vision-language platform for satellite and remote-sensing imagery, built for **ISRO PS-26167**. It combines fine-tuned 4-bit GeoChat-7B multimodal intelligence with an independent deterministic geospatial metrics engine, a live STAC catalog with on-demand global fallback, and a PostGIS-backed analysis history with interactive map exploration.

---

## 🏛️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            User / React SPA (Port 5173)                      │
│                                                                             │
│   ┌───────────────────────┐   ┌───────────────────┐   ┌───────────────────┐ │
│   │ 3D Satellite Tracking │   │ SatQuery Agentic  │   │ PostGIS Spatial   │ │
│   │ Constellation Globe   │   │ AI Interface      │   │ History & Map View│ │
│   └───────────────────────┘   └─────────┬─────────┘   └───────────────────┘ │
└─────────────────────────────────────────┼───────────────────────────────────┘
                                          │
                                   POST /api/analyze
                                          │
    ┌─────────────────────────────────────▼────────────────────────────────┐
    │                     SatQuery Agentic Controller                      │
    │  - Task Intent Routing (VQA, Grounding, Change, SAR Fusion, Metrics) │
    │  - Independent Deterministic Geospatial Metrics (NDVI, Land Cover)   │
    │  - Live STAC Catalog Integration (Earth Search / AWS Element84)      │
    │  - PostGIS Spatial Audit & History Logging (Port 5432)               │
    └─────────────────────────────────────┬────────────────────────────────┘
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    │                                           │
  ┌─────────────────▼─────────────────┐       ┌─────────────────▼─────────────────┐
  │ Local GPU Inference Engine        │       │ Deterministic Geospatial Metrics  │
  │ - GeoChat-7B 4-bit (BitsAndBytes) │       │ - Raw GeoTIFF Pixel Computation   │
  │ - QLoRA BigEarthNet Adapter       │       │ - NDVI, Land Cover, Change Area   │
  │ - Python 3.10 CUDA venv           │       │ - Cross-Check Validation Layer    │
  └───────────────────────────────────┘       └───────────────────────────────────┘
```

---

## 🚀 System Run Configuration

### The Two-Part Architecture (Why This Split Exists)

SatQuery AI operates as a coordinated hybrid stack:
1. **Containerized Core & Infrastructure (`docker compose`)**:
   - **PostGIS 3.4 (PostgreSQL 16)**: Spatial database storing analyzed bounding boxes, imagery footprints, and session history.
   - **SatQuery Service (FastAPI)**: Controller, task routing, deterministic pixel metrics engine, and STAC catalog daemon.
   - **React SPA**: Modern frontend interface on port `5173`.
2. **Local GPU Inference Process (`ml/geochat/venv`)**:
   - Runs GeoChat-7B 4-bit with BitsAndBytes quantization directly on host NVIDIA GPU hardware.
   - **Why this split exists**: Complete containerization of GeoChat-7B with CUDA 12.1 kernel compilation across Docker layers is brittle and highly hardware-dependent. Direct host execution in a Python 3.10 venv (`ml/geochat/venv/Scripts/python.exe` on Windows or `ml/geochat/venv/bin/python` on Linux) is the tested, verified, and high-performance execution path.

---

## ▶️ Setup & Execution Guide

### Step 1 — Start Infrastructure with Docker Compose
Start the spatial database and backend controller services:
```bash
docker compose up -d postgis satquery-service
```
Or start the complete containerized stack including the frontend:
```bash
docker compose up -d
```

### Step 2 — Start GeoChat-7B GPU Inference Process
In your host environment with NVIDIA GPU access, activate the prepared virtual environment (see [`ml/geochat/SETUP.md`](ml/geochat/SETUP.md) for first-time environment creation):

```powershell
# Windows (PowerShell):
.\ml\geochat\venv\Scripts\Activate.ps1

# Linux / macOS:
source ml/geochat/venv/bin/activate
```

Launch the inference worker or run the standalone verification:
```bash
# Verify local GPU inference
python ml/geochat/test_inference.py
```

### Step 3 — Verify Stack Connection (`GET /health`)
Before assuming the system is operational, verify that the controller has successfully connected to the GeoChat model:

```bash
curl http://localhost:8082/health
```

**Expected Response:**
```json
{
  "status": "ok",
  "service": "SatQuery AI Agentic Service",
  "model": "MBZUAI/geochat-7B (4-bit)",
  "geochat_loaded": true,
  "geochat_error": null,
  "peak_vram_gb": 4.44
}
```

> ⚠️ **CRITICAL**: If `geochat_loaded` is `false`, the controller is in degraded mode. Check `geochat_error` in the JSON response to diagnose local inference initialization before testing VQA or Grounding queries.

### Step 4 — Run the Frontend
If not running the frontend inside Docker:
```bash
npm install
npm run dev
# → Vite dev server running on http://localhost:5173
```

---

## 🌟 Core Features

- **Agentic Multi-Specialist Controller**:
  - **Visual Question Answering (VQA)**: Zero-shot natural language QA over high-resolution optical satellite imagery.
  - **Spatial Object Grounding**: Localizes buildings, airfields, and infrastructure with normalized bounding boxes `[ymin, xmin, ymax, xmax]`.
  - **Bi-Temporal Change-VQA**: Pair-wise image comparison quantifying deforestation, flood inundation, and disaster impact.
  - **SAR-Optical Fusion**: Ingests synthetic aperture radar (SAR) channels for cloud-penetrating and night-time analysis.
- **Deterministic Geospatial Metrics Engine**: Computes NDVI, land cover distribution, and spectral change area directly from GeoTIFF pixel data, verifying the model's qualitative answer.
- **Live STAC Catalog**: Ingests imagery from AWS Element84 / Earth Search covering curated regions with on-demand fallback for global coordinates.
- **PostGIS Spatial History**: Persists analysis metadata, bounding boxes, and image footprints with interactive Leaflet map exploration.
- **Proactive Monitoring (reactive → proactive pivot)**: the ingestion daemon runs pluggable alert checks every cycle and writes land-change and severe-weather alerts to one PostGIS table, served as GeoJSON at `GET /api/alerts`.
  - **Track A, Land monitoring** (`/land-monitoring`): mining expansion at Jharia Coalfield and Joda iron-ore belt from real Sentinel-2 time series (`mining_monitor.py`). Boundaries are approximate, and the UI says so next to every number.
  - **Track B, Severe weather** (`/weather-monitoring`): elevated convective development risk from INSAT-3DR TIR-1 cloud-top cooling (`insat_ingest.py` + `storm_risk.py`), for Mayurbhanj, Ranchi and Dhanbad.
- **Live 3D Satellite Tracking**: High-performance CesiumJS globe tracking 16,000+ active satellites and constellations in real-time.

---

## ⛈️ Track B setup: INSAT-3DR via MOSDAC

Track B uses real INSAT-3DR thermal-IR data from MOSDAC (SAC-ISRO). Nothing is simulated: without an account the daemon idles and the dashboard says the feed is not connected.

1. Register at https://www.mosdac.gov.in/ and add to `.env` next to `docker-compose.yml`:
   ```
   MOSDAC_USERNAME=...
   MOSDAC_PASSWORD=...
   ```
   Three wrong passwords in a row lock a MOSDAC account for an hour, so the service stops after the first rejection.
2. Restart the stack, then pull the first frames and print their provenance:
   ```bash
   docker compose exec satquery-service python insat_ingest.py search          # archive listing, no login needed
   docker compose exec satquery-service python insat_ingest.py ingest
   docker compose exec satquery-service python insat_ingest.py verify          # raw counts, BT, exact API calls, timestamps
   ```
3. **Verification gate.** Find the printed identifier in MOSDAC's own archive browser and check that the acquisition time matches. Then open the gate:
   ```bash
   docker compose exec satquery-service python insat_ingest.py confirm <frame_id> --note "matched on MOSDAC catalog"
   ```
   `storm_risk.py` produces nothing until this is done.

Default product: `3RIMG_L1C_ASIA_MER` (INSAT-3DR L1C Mercator Asia sector, ~24 MB per half-hourly frame). Override it with `INSAT_DATASET_ID`.

---

## 🤖 Finetuned ML Model & Weights

The repository includes a domain-adapted QLoRA adapter trained on BigEarthNet remote-sensing multi-label land cover annotations:
- **Location:** `ml/geochat/finetune/checkpoints/geochat_qlora_bigearthnet/`
- **Artifacts:**
  - `adapter_model.bin` (42.5 MB QLoRA adapter weights)
  - `adapter_config.json`
  - `tokenizer_config.json` / `tokenizer.model`

To reproduce QLoRA finetuning or evaluate base vs. finetuned comparisons:
```bash
# Run QLoRA training
python ml/geochat/finetune/train_qlora.py

# Evaluate comparison metrics (BLEU, Exact Match, Soft Match)
python ml/geochat/finetune/eval_comparison.py
```

---

## 🎯 Implemented Scope vs. Stated Limitations

| Feature Component | Implementation Status | Technical Limitation / Scope Boundary |
|---|---|---|
| **Optical VQA & Grounding** | **Fully Implemented** | Powered by 4-bit quantized GeoChat-7B with custom `answer_scoring.py` keyword-recall and grounding markup stripping (`<p>...</p>`). |
| **Deterministic Metrics** | **Fully Implemented** | NDVI, land cover, and change-area computed from pixel arrays — independent of and cross-checked against the model's output. |
| **SAR-Optical Fusion** | **Synthetic Demonstration** | Validated on synthetic backscatter data for regions without real Sentinel-1 coverage yet (`satquery-service/test_sar_fusion.py`). |
| **Live STAC Fallback** | **Global Coverage** | Curated STAC imagery is cached; live STAC fallback trades network latency for global coverage outside pre-cataloged regions. |
| **Mining Expansion (Track A)** | **Implemented, real Sentinel-2** | Boundaries are approximations, not lease files. The "new bare ground inside boundary" figure is a triage signal: seasonal vegetation change inside the boundary can still register. |
| **Convective Risk (Track B)** | **Implemented; live once a MOSDAC account is configured** | Regional risk flag, never a strike or location forecast. Criteria: Roberts & Rutledge (2003), Mecikalski & Bedka (2006). Rates beyond −10 K/15 min are capped at info and flagged for re-verification. |
| **Benchmark Scoring** | **Manual Eyeball Reviewed** | Evaluated via a 10-sample manual review against real VRSBench/RSVQA-LR items (`satquery-service/eval/manual_review.md`). |

---

## 🛠️ Verification & Test Harnesses

```bash
# 1. Answer Scoring Regression Tests
python ml/geochat/eyeball_check.py

# 2. SatQuery Controller Evaluation
python satquery-service/eval/eyeball_check_satquery.py

# 3. SAR Fusion Specialist Verification
python satquery-service/test_sar_fusion.py

# 4. Change-VQA Specialist Verification
python satquery-service/test_change_vqa.py

# 5. Deterministic Geospatial Metrics Verification
python satquery-service/test_geospatial_metrics.py

# 6. Mining expansion eyeball harness (real Jharia / Joda imagery)
docker compose exec satquery-service python test_mining_monitor.py

# 7. Output composer: two real pairs must give different numbers
docker compose exec satquery-service python test_narrative_composer.py

# 8. Convective-risk math + INSAT HDF5 parsing
docker compose exec satquery-service python test_storm_risk.py
```

