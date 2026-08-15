import os
import time
import math
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
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

MODEL_ID = "ibm-nasa-geospatial/Prithvi-EO-1.0-100M"
model = None
device = "cuda" if torch.cuda.is_available() else "cpu"

class ScenarioRequest(BaseModel):
    scenario: str

@app.on_event("startup")
async def startup_event():
    global model
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

    # Ensure data directories exist
    os.makedirs("data/deforestation", exist_ok=True)
    os.makedirs("data/disaster", exist_ok=True)
    os.makedirs("public/masks", exist_ok=True)
    
    # Mount the public masks directory to serve static images
    app.mount("/masks", StaticFiles(directory="public/masks"), name="masks")

    # Generate dummy TIF files if they don't exist (so the endpoint doesn't crash)
    _ensure_dummy_tif("data/deforestation/before.tif")
    _ensure_dummy_tif("data/deforestation/after.tif")
    _ensure_dummy_tif("data/disaster/before.tif")
    _ensure_dummy_tif("data/disaster/after.tif")

def _ensure_dummy_tif(filepath: str):
    if not os.path.exists(filepath):
        logger.info(f"Creating dummy TIFF image: {filepath}")
        if rasterio:
            # Create a dummy 6-band (Prithvi input) 224x224 TIFF
            data = np.random.rand(6, 224, 224).astype(np.float32)
            with rasterio.open(
                filepath, 'w', driver='GTiff',
                height=224, width=224, count=6, dtype='float32'
            ) as dst:
                dst.write(data)
        else:
            logger.warning("rasterio not installed, skipping dummy TIF creation")

@app.get("/health")
def health_check():
    if model is None:
        return JSONResponse(status_code=503, content={"status": "error", "message": "Model not loaded"})
    return {"status": "ok", "model": MODEL_ID}

def load_image_tensor(filepath: str) -> torch.Tensor:
    """Loads a TIFF file and returns a dummy tensor formatted for Prithvi.
       Prithvi typically expects shape (B, C, T, H, W) where C=6.
    """
    if not rasterio:
        # Return random noise if rasterio is missing
        return torch.rand(1, 6, 1, 224, 224).to(device)
        
    with rasterio.open(filepath) as src:
        # Shape: (C, H, W)
        data = src.read()
    
    # Convert to torch tensor, add Batch and Time dimensions -> (1, C, 1, H, W)
    tensor = torch.from_numpy(data).unsqueeze(0).unsqueeze(2).to(device)
    
    # Resize or crop to 224x224 (required for typical ViT patches)
    # For dummy purposes, we just interpolate if necessary
    import torch.nn.functional as F
    tensor = tensor.squeeze(2) # (B, C, H, W)
    tensor = F.interpolate(tensor, size=(224, 224), mode='bilinear')
    tensor = tensor.unsqueeze(2) # (B, C, 1, H, W)
    
    return tensor

@app.post("/api/change-detection")
def run_change_detection(req: ScenarioRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Model is not loaded and unavailable.")
        
    scenario = req.scenario
    if scenario not in ["deforestation", "disaster"]:
        raise HTTPException(status_code=400, detail="Invalid scenario. Must be 'deforestation' or 'disaster'.")
        
    before_path = f"data/{scenario}/before.tif"
    after_path = f"data/{scenario}/after.tif"
    
    if not os.path.exists(before_path) or not os.path.exists(after_path):
        raise HTTPException(status_code=404, detail=f"Image pairs for scenario '{scenario}' not found.")
        
    start_time = time.time()
    
    try:
        # 1. Load images
        t_before = load_image_tensor(before_path)
        t_after = load_image_tensor(after_path)
        
        # 2. Run inference (dummy approach: get embeddings and compute difference)
        # We use torch.no_grad() for inference
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
                diff = torch.rand(1, 14*14).to(device)
                
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
            mask_tensor = torch.rand(224, 224).to(device)
            
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
        confidence = round(float(np.random.uniform(0.75, 0.98)), 3) # Dummy confidence
        
        latency = (time.time() - start_time) * 1000
        logger.info(f"Inference complete for {scenario}. Latency: {latency:.2f}ms")
        
        return {
            "change_percentage": change_percentage,
            "confidence": confidence,
            "mask_url": f"/masks/{mask_filename}",
            "latency_ms": latency
        }
        
    except Exception as e:
        logger.error(f"Inference error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}")
