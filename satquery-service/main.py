import os
import time
import logging
from typing import List, Optional, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import base64
import io
import torch
from PIL import Image

from controller import route_and_execute
from geochat_engine import load_image_robust

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
        preview_base64_list = []
        for key in form:
            val = form[key]
            if hasattr(val, "filename") and val.filename:
                contents = await val.read()
                img = load_image_robust(contents)
                if img is not None:
                    images_payload.append(img)
                    try:
                        buf = io.BytesIO()
                        img.save(buf, format="JPEG", quality=85)
                        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
                        preview_base64_list.append(f"data:image/jpeg;base64,{b64_str}")
                    except Exception as e:
                        logger.warning(f"Could not generate base64 preview: {e}")
                else:
                    logger.warning(f"Could not decode uploaded file '{val.filename}' via PIL or rasterio — skipping.")

    if not user_query:
        raise HTTPException(status_code=400, detail="Query string is required.")

    # If scenario specified, load bi-temporal pair for change detection / change-VQA
    if scenario:
        before_path = f"data/{scenario}/before.tif"
        after_path = f"data/{scenario}/after.tif"
        if os.path.exists(before_path) and os.path.exists(after_path):
            before_img = load_image_robust(before_path)
            after_img = load_image_robust(after_path)
            if before_img and after_img:
                images_payload = [before_img, after_img]
                temporal = "bi-temporal"
                # Encode both scenario images to base64 for frontend slider preview
                scenario_previews = []
                for s_img in [before_img, after_img]:
                    try:
                        buf = io.BytesIO()
                        s_img.save(buf, format="JPEG", quality=85)
                        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
                        scenario_previews.append(f"data:image/jpeg;base64,{b64_str}")
                    except Exception as e:
                        logger.warning(f"Could not generate scenario base64 preview: {e}")
                if len(scenario_previews) == 2:
                    preview_base64_list = scenario_previews

    # Route through controller
    response = route_and_execute(
        images=images_payload,
        query=user_query,
        modality=modality or "optical",
        temporal=temporal or "single"
    )

    if isinstance(response, dict):
        if 'preview_base64_list' in locals() and preview_base64_list:
            response["preview_images_base64"] = preview_base64_list
            response["preview_image_base64"] = preview_base64_list[0]

    return response

