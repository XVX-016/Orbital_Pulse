# SatQuery AI — Agentic Remote-Sensing VQA & Multi-Modal Analysis Platform

SatQuery AI is a production-ready, agentic remote-sensing application featuring natural-language VQA, spatial object grounding, bi-temporal change analysis, and synthetic SAR-optical fusion over satellite imagery.

---

## 🏛️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            User / React SPA (Port 5173)                      │
│                                                                             │
│   ┌───────────────────────┐   ┌───────────────────┐   ┌───────────────────┐ │
│   │ 3D Cesium Satellite   │   │ SatQuery Agentic  │   │ Bi-Temporal       │ │
│   │ Tracking Globe        │   │ AI Interface      │   │ Change Visualizer │ │
│   └───────────────────────┘   └─────────┬─────────┘   └───────────────────┘ │
└─────────────────────────────────────────┼───────────────────────────────────┘
                                          │
                                   POST /api/analyze
                                          │
    ┌─────────────────────────────────────▼────────────────────────────────┐
    │                     SatQuery Agentic Controller                      │
    │  - Rule-Based Task Classifier (Task Intent, Modality & Temporality)  │
    │  - Audit Execution Trace Logger                                      │
    └──────────────┬──────────────────┬───────────────────┬────────────────┘
                   │                  │                   │
  ┌────────────────▼───┐    ┌─────────▼─────────┐   ┌─────▼───────────────┐
  │ Optical VQA        │    │ Change-VQA        │   │ SAR-Optical Fusion  │
  │ Specialist         │    │ Specialist        │   │ Specialist          │
  │ (GeoChat-7B 4-bit) │    │ (Bi-temporal VQA) │   │ (Radar/Optical)     │
  └────────────────────┘    └───────────────────┘   └─────────────────────┘
```

---

## 🚀 Quick Start & Installation

### Prerequisites
- **Node.js** ≥ 20 & **npm** ≥ 10
- **Python** ≥ 3.10 with PyTorch CUDA support
- **NVIDIA GPU** with ≥ 8GB VRAM (for 4-bit GeoChat-7B local LLM execution)

### Environment Configuration
Copy `.env.example` to `.env` and set your Cesium ION token:
```bash
cp .env.example .env
# Edit .env and set VITE_CESIUM_ION_TOKEN
```

---

## ▶️ Primary Run Method — Local venv (Verified & Recommended)

This is the tested, working run path used for all demos and evaluations.

### Step 1 — Frontend & Orbit Service
```bash
# From repo root
npm install
npm run dev
# → React SPA + Express orbit proxy on http://localhost:8080
```

### Step 2 — SatQuery AI Service (Python venv)
```bash
cd satquery-service
pip install -r requirements.txt   # first time only

# Start FastAPI agentic service on port 8082
uvicorn main:app --host 0.0.0.0 --port 8082
```

Once you see `INFO: Application startup complete.` the `/api/analyze` endpoint is live and the React UI will connect automatically.

> 📖 **GeoChat-7B Model Setup**: For complete details on downloading and initializing the 4-bit GeoChat-7B LLM engine, see [`ml/geochat/SETUP.md`](ml/geochat/SETUP.md).

---

## 🐳 Docker Compose (Fully Verified)

All infrastructure services build and start cleanly, and the complete multi-container stack has been fully verified:

```bash
docker compose up --build
```

**Services:**
- **frontend**: React SPA served via Nginx on port `5173`
- **satquery-service**: FastAPI agentic service on port `8082`
- **postgis**: PostgreSQL 16 + PostGIS 3.4 database on port `5432`

Import verification test inside the container:
```bash
docker build -t satquery-service-test ./satquery-service
docker run --rm satquery-service-test python -c \
  "from grounding_parser import parse_geochat_grounding; print('OK')"
# → OK: grounding_parser imported successfully
```

> **Note:** When running in Docker, the Hugging Face cache is mounted inside the container. If weights/packages (such as the large GeoChat package tree) are not loaded, the SatQuery AI service starts in a degraded fallback mode but maintains active health checks. For a fully live local execution, see the verified venv instructions above.

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
| **SAR-Optical Fusion** | **Synthetic Demonstration** | Tested & verified using synthetic SAR backscatter arrays (`ml/geochat/test_sar_fusion.py`). Real Sentinel-1 IW GRD radar ingestion is scoped out. |
| **Bi-Temporal Change VQA** | **Categorical "What" Only** | Multi-image VQA classifies *what* changed between before/after scenes. Spatial mask pixel-level *where* localization is not yet integrated into the VQA pipeline. |
| **Benchmark Scoring** | **Manual Eyeball Reviewed** | Evaluated via a 10-sample manual eyeball review (`satquery-service/eval/manual_review.md`) due to missing full real dataset image downloads. |

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
```
