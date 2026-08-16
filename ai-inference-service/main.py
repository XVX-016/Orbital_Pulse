import os
import time
import math
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import torch
import numpy as np
from PIL import Image

try:
    import rasterio
except ImportError:
    rasterio = None

# We use transformers AutoModel
from transformers import AutoModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Inference Service (Prithvi-100M)")

# CORS — allow the frontend (running on a different port/origin) to load images and call APIs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to the frontend origin
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL_ID = "ibm-nasa-geospatial/Prithvi-EO-1.0-100M"
model = None
device = "cuda" if torch.cuda.is_available() else "cpu"

# Track whether real preprocessed data is available
_data_ready = False

EXPECTED_DATA_FILES = [
    "data/deforestation/before.tif",
    "data/deforestation/after.tif",
    "data/disaster/before.tif",
    "data/disaster/after.tif",
]

class ScenarioRequest(BaseModel):
    scenario: str

@app.on_event("startup")
async def startup_event():
    global model, _data_ready
    logger.info(f"Loading model {MODEL_ID} into memory on {device}...")
    try:
        # Load the model. trust_remote_code may be needed for custom architectures.
        model = AutoModel.from_pretrained(MODEL_ID, trust_remote_code=True)
        model.to(device)
        model.eval()
        logger.info("Model loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load model {MODEL_ID}: {e}")
        # We don't exit so the health check can report the failure or the endpoint can return 500
        model = None

    # Ensure output directories exist
    os.makedirs("data/deforestation", exist_ok=True)
    os.makedirs("data/disaster", exist_ok=True)
    os.makedirs("public/masks", exist_ok=True)
    os.makedirs("public/images", exist_ok=True)

    # ── Strict data validation (NO silent random-noise fallback) ──────────
    missing_files = [f for f in EXPECTED_DATA_FILES if not os.path.exists(f)]
    if missing_files:
        logger.critical("=" * 60)
        logger.critical("MISSING PREPROCESSED DATA FILES")
        logger.critical("=" * 60)
        for f in missing_files:
            logger.critical(f"  ✗ {f}")
        logger.critical("")
        logger.critical("The AI inference service requires real preprocessed GeoTIFF data.")
        logger.critical("Run the data preparation script first:")
        logger.critical("  python scripts/prepare_data.py --raw-dir raw_data/ --output-dir data/")
        logger.critical("")
        logger.critical("See README.md for instructions on sourcing Sentinel-2 / xBD imagery.")
        logger.critical("The /api/change-detection endpoint will return 503 until data is provided.")
        logger.critical("=" * 60)
        _data_ready = False
    else:
        # Validate that existing files are real GeoTIFFs, not zero-byte or corrupted
        all_valid = True
        for f in EXPECTED_DATA_FILES:
            file_size = os.path.getsize(f)
            if file_size < 1024:
                logger.warning(f"  ⚠ Suspiciously small data file ({file_size} bytes): {f}")
            if rasterio:
                try:
                    with rasterio.open(f) as src:
                        if src.count < 6:
                            logger.warning(f"  ⚠ {f} has {src.count} bands (expected 6). Model may produce unexpected results.")
                        if src.width != 224 or src.height != 224:
                            logger.warning(f"  ⚠ {f} is {src.width}×{src.height} (expected 224×224). Will be resized during inference.")
                except Exception as e:
                    logger.critical(f"  ✗ Cannot read {f}: {e}")
                    all_valid = False
        _data_ready = all_valid
        if all_valid:
            logger.info("✓ All preprocessed data files validated and ready.")
        else:
            logger.critical("Some data files are corrupted. Re-run prepare_data.py.")

    # Mount static file directories
    app.mount("/masks", StaticFiles(directory="public/masks"), name="masks")
    app.mount("/images", StaticFiles(directory="public/images"), name="images")

@app.get("/health")
def health_check():
    if model is None:
        return JSONResponse(status_code=503, content={"status": "error", "message": "Model not loaded"})
    return {
        "status": "ok",
        "model": MODEL_ID,
        "data_ready": _data_ready,
    }

def load_image_tensor(filepath: str) -> torch.Tensor:
    """Loads a preprocessed 6-band 224×224 GeoTIFF and returns a tensor for Prithvi.
       Prithvi expects shape (B, C, T, H, W) where C=6.
       
       Raises RuntimeError if rasterio is not installed or the file is unreadable.
    """
    if not rasterio:
        raise RuntimeError(
            "rasterio is not installed. Cannot load GeoTIFF data. "
            "Install with: pip install rasterio"
        )

    with rasterio.open(filepath) as src:
        # Shape: (C, H, W)
        data = src.read()
    
    # Convert to torch tensor, add Batch and Time dimensions -> (1, C, 1, H, W)
    tensor = torch.from_numpy(data).float().unsqueeze(0).unsqueeze(2).to(device)
    
    # Resize to 224x224 if the preprocessed data isn't already that size
    import torch.nn.functional as F
    tensor = tensor.squeeze(2) # (B, C, H, W)
    if tensor.shape[2] != 224 or tensor.shape[3] != 224:
        tensor = F.interpolate(tensor, size=(224, 224), mode='bilinear', align_corners=False)
    tensor = tensor.unsqueeze(2) # (B, C, 1, H, W)
    
    return tensor

@app.post("/api/change-detection")
def run_change_detection(req: ScenarioRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Model is not loaded and unavailable.")

    if not _data_ready:
        raise HTTPException(
            status_code=503,
            detail=(
                "Preprocessed data is not available. "
                "Run 'python scripts/prepare_data.py' to prepare real GeoTIFF imagery before using this endpoint. "
                "See README.md for data sourcing instructions."
            ),
        )

    scenario = req.scenario
    if scenario not in ["deforestation", "disaster"]:
        raise HTTPException(status_code=400, detail="Invalid scenario. Must be 'deforestation' or 'disaster'.")
        
    before_path = f"data/{scenario}/before.tif"
    after_path = f"data/{scenario}/after.tif"
    
    if not os.path.exists(before_path) or not os.path.exists(after_path):
        raise HTTPException(
            status_code=404,
            detail=f"Image pairs for scenario '{scenario}' not found at {before_path} and {after_path}.",
        )
        
    start_time = time.time()
    
    try:
        # 1. Load images
        t_before = load_image_tensor(before_path)
        t_after = load_image_tensor(after_path)
        
        # 2. Run inference (dummy approach: get embeddings and compute difference)
        # We use torch.no_grad() for inference
        used_fallback_mask = False
        with torch.no_grad():
            # For AutoModel, the output might vary, but typically it returns a BaseModelOutput
            out_before = model(t_before)
            out_after = model(t_after)
            
            # Usually out.last_hidden_state has shape (B, N, D)
            # We compute a basic L2 distance between the embeddings
            if hasattr(out_before, "last_hidden_state"):
                embed_b = out_before.last_hidden_state
                embed_a = out_after.last_hidden_state
                diff = torch.norm(embed_b - embed_a, dim=-1) # (B, N)
            else:
                # Fallback if the custom model output is different
                logger.warning("Model output missing last_hidden_state. Using random fallback mask.")
                diff = torch.rand(1, 14*14).to(device)
                used_fallback_mask = True
                
        # 3. Create a pseudo-mask image
        # Assuming 224x224 images and 16x16 patches, N is usually 14x14 = 196
        # Reshape to (14, 14) and upscale to (224, 224)
        num_patches = diff.shape[1]
        grid_size = int(math.sqrt(num_patches))
        if grid_size * grid_size == num_patches:
            diff_grid = diff.view(1, 1, grid_size, grid_size)
            import torch.nn.functional as F
            mask_tensor = F.interpolate(diff_grid, size=(224, 224), mode='nearest').squeeze()
        else:
            # Fallback random mask if shapes don't align cleanly
            logger.warning(f"Embedding patch count ({num_patches}) is not a perfect square grid. Using random fallback mask.")
            mask_tensor = torch.rand(224, 224).to(device)
            used_fallback_mask = True
            
        # Normalize to 0-255
        mask_min = mask_tensor.min()
        mask_max = mask_tensor.max()
        mask_norm = ((mask_tensor - mask_min) / (mask_max - mask_min + 1e-6) * 255).cpu().numpy().astype(np.uint8)
        
        # Save as PNG
        mask_filename = f"mask_{scenario}_{int(time.time())}.png"
        mask_filepath = os.path.join("public", "masks", mask_filename)
        im = Image.fromarray(mask_norm, mode='L')
        # Apply a simple colormap logic (optional, we can just save it as grayscale)
        im.save(mask_filepath)
        
        # 4. Compute metrics
        change_percentage = round(float((mask_norm > 128).mean() * 100), 2)
        # Prithvi raw embeddings do not provide classification logits or softmax entropy for confidence score
        confidence = None
        
        latency = (time.time() - start_time) * 1000
        logger.info(f"Inference complete for {scenario}. Latency: {latency:.2f}ms. Fallback mask used: {used_fallback_mask}")
        
        return {
            "change_percentage": change_percentage,
            "confidence": confidence,
            "used_fallback_mask": used_fallback_mask,
            "mask_url": f"/masks/{mask_filename}",
            "latency_ms": latency
        }
        
    except Exception as e:
        logger.error(f"Inference error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}")
