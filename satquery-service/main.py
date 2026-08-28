import os
import time
import logging
from typing import List, Optional, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import torch
from PIL import Image

from controller import route_and_execute

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SatQuery AI Service (Remote-Sensing VQA & Agentic Analysis)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    query: str
    scenario: Optional[str] = None
    modality: Optional[str] = "optical"
    temporal: Optional[str] = "single"

@app.on_event("startup")
async def startup_event():
    # Load 4-bit GeoChat-7B model engine once at startup
    try:
        from geochat_engine import init_geochat_model
        init_geochat_model("MBZUAI/geochat-7B")
    except Exception as ge_err:
        logger.error(f"Failed to initialize GeoChat engine: {ge_err}")

    os.makedirs("data/deforestation", exist_ok=True)
    os.makedirs("data/disaster", exist_ok=True)
    os.makedirs("public/masks", exist_ok=True)
    os.makedirs("public/images", exist_ok=True)

    app.mount("/masks", StaticFiles(directory="public/masks"), name="masks")
    app.mount("/images", StaticFiles(directory="public/images"), name="images")

@app.get("/health")
def health_check():
    from geochat_engine import is_geochat_loaded
    peak_vram_gb = torch.cuda.max_memory_allocated() / 1024**3 if torch.cuda.is_available() else 0.0
    return {
        "status": "ok" if is_geochat_loaded() else "degraded",
        "service": "SatQuery AI Agentic Service",
        "model": "MBZUAI/geochat-7B (4-bit)",
        "geochat_loaded": is_geochat_loaded(),
        "peak_vram_gb": round(peak_vram_gb, 2),
    }

@app.post("/api/analyze")
async def analyze_query(request: Request):
    """Main Agentic VQA & Remote-Sensing Analysis Endpoint.

    Accepts JSON body (`{"query": "...", "scenario": "...", ...}`) or multipart form data.
    Routes execution to appropriate specialist via Controller and returns structured output
    with auditable execution trace.
    """
    content_type = request.headers.get("content-type", "")
    
    user_query = ""
    scenario = None
    modality = "optical"
    temporal = "single"
    images_payload = []

    if "application/json" in content_type:
        body = await request.json()
        user_query = body.get("query", "")
        scenario = body.get("scenario")
        modality = body.get("modality", "optical")
        temporal = body.get("temporal", "single")
    else:
        form = await request.form()
        user_query = form.get("query", "")
        scenario = form.get("scenario")
        modality = form.get("modality", "optical")
        temporal = form.get("temporal", "single")
        
        # Collect file uploads if present
        for key in form:
            val = form[key]
            if hasattr(val, "filename") and val.filename:
                contents = await val.read()
                import io
                try:
                    img = Image.open(io.BytesIO(contents)).convert("RGB")
                    images_payload.append(img)
                except Exception as img_err:
                    logger.warning(f"Could not parse uploaded file as PIL Image: {img_err}")

    if not user_query:
        raise HTTPException(status_code=400, detail="Query string is required.")

    # If scenario specified, load bi-temporal pair for change detection / change-VQA
    if scenario:
        before_path = f"data/{scenario}/before.tif"
        after_path = f"data/{scenario}/after.tif"
        if os.path.exists(before_path) and os.path.exists(after_path):
            try:
                images_payload = [Image.open(before_path).convert("RGB"), Image.open(after_path).convert("RGB")]
            except Exception:
                images_payload = [before_path, after_path]
            temporal = "bi-temporal"

    # Route through controller
    response = route_and_execute(
        images=images_payload,
        query=user_query,
        modality=modality or "optical",
        temporal=temporal or "single"
    )

    return response

