"""
Optical–SAR Fusion Specialist.

Handles multimodal Optical + Synthetic Aperture Radar (SAR) fusion queries for all-weather, cloud-penetrating,
and day/night satellite imagery analysis.

IMPORTANT DISCLAIMER:
    The current test benchmark dataset for this SAR pathway relies on synthetic placeholder arrays
    with fabricated Gaussian pixel statistics (generated via prepare_sar_samples.py). The pathway is
    validated ONLY against synthetic placeholder data pending real imagery integration (e.g. Sentinel-1 GRD
  from Copernicus Open Access Hub or BigEarthNet-S1), and is not presented as a validated real-world working capability.

Implementation & Engineering Note:
  This specialist implements a scoped multimodal fusion approach combining:
  1. Deep VLM Optical Scene Understanding via GeoChat-7B (analyzes optical spectral/contextual features).
  2. Classical SAR Backscatter Thresholding on Sentinel-1 VV radar imagery:
     - Low backscatter (<0.12 normalized intensity): Specular reflection off smooth surfaces (Water bodies).
     - High backscatter (>0.55 normalized intensity): Double-bounce / corner reflection off rough built-up structures.
  3. Decision-level Fusion Synthesis: Combines GeoChat optical descriptions with quantitative SAR backscatter metrics.
  This provides a reliable, explainable multimodal fusion mechanism given current model capabilities.
"""

import time
import logging
import numpy as np
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image

from geochat_engine import (
    run_geochat_inference,
    is_geochat_loaded,
)

logger = logging.getLogger(__name__)

# Standard Sentinel-1 VV backscatter normalized intensity thresholds
WATER_THRESHOLD_MAX = 0.12     # Smooth surface -> low backscatter (dark)
BUILTUP_THRESHOLD_MIN = 0.55   # Rough / double-bounce -> high backscatter (bright)


def _process_sar_backscatter(sar_img: Image.Image) -> Dict[str, Any]:
    """Applies classical SAR backscatter thresholding to compute water & built-up coverage percentages."""
    sar_gray = sar_img.convert("L")
    arr = np.array(sar_gray, dtype=np.float32) / 255.0  # Normalize to 0.0 .. 1.0

    total_pixels = arr.size
    if total_pixels == 0:
        return {"water_pct": 0.0, "builtup_pct": 0.0, "other_pct": 100.0}

    water_mask = arr < WATER_THRESHOLD_MAX
    builtup_mask = arr > BUILTUP_THRESHOLD_MIN

    water_count = int(np.sum(water_mask))
    builtup_count = int(np.sum(builtup_mask))

    water_pct = round((water_count / total_pixels) * 100.0, 2)
    builtup_pct = round((builtup_count / total_pixels) * 100.0, 2)
    other_pct = round(100.0 - (water_pct + builtup_pct), 2)

    return {
        "water_pct": water_pct,
        "builtup_pct": builtup_pct,
        "other_pct": max(0.0, other_pct),
        "total_pixels": total_pixels,
        "water_pixel_count": water_count,
        "builtup_pixel_count": builtup_count,
    }


def _load_image(item: Any) -> Optional[Image.Image]:
    """Helper to convert input image paths or objects into PIL RGB Image."""
    if isinstance(item, Image.Image):
        return item.convert("RGB")
    if isinstance(item, str):
        try:
            return Image.open(item).convert("RGB")
        except Exception:
            try:
                import rasterio
                with rasterio.open(item) as src:
                    arr = src.read()
                    if arr.ndim == 3:
                        rgb = arr[:3, :, :].transpose(1, 2, 0)
                    else:
                        rgb = np.stack([arr] * 3, axis=-1)
                    if rgb.dtype != np.uint8:
                        val_min, val_max = rgb.min(), rgb.max()
                        if val_max > val_min:
                            rgb = ((rgb - val_min) / (val_max - val_min) * 255.0).astype(np.uint8)
                        else:
                            rgb = (rgb * 255.0).clip(0, 255).astype(np.uint8)
                    return Image.fromarray(rgb, mode="RGB")
            except Exception as ex:
                logger.warning(f"Failed to load image path '{item}': {ex}")
                return None
    return None


def run_sar_fusion(images: List[Any], query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Exposes Optical-SAR Multimodal Fusion over paired Sentinel-1 SAR and Sentinel-2 Optical imagery.

    Inputs:
      - images: List of images [optical_image, sar_image] (or dict with 'optical' and 'sar' keys).
      - query: Question or analysis request.

    Result schema:
      - answer: str (synthesized Optical + SAR analysis)
      - confidence: float | None
      - visual_evidence: dict (SAR threshold metrics & coverage breakdown)
      - details: dict (metadata, specialist name, latency)
    """
    if not images or len(images) == 0:
        return {
            "answer": "No imagery provided for Optical-SAR fusion analysis.",
            "confidence": None,
            "visual_evidence": None,
            "details": {
                "specialist": "SARFusion",
                "error": "Empty images list",
            },
        }

    # Extract optical and SAR images
    optical_img: Optional[Image.Image] = None
    sar_img: Optional[Image.Image] = None

    if isinstance(images, dict):
        optical_img = _load_image(images.get("optical"))
        sar_img = _load_image(images.get("sar"))
    elif isinstance(images, list):
        if len(images) >= 2:
            optical_img = _load_image(images[0])
            sar_img = _load_image(images[1])
        elif len(images) == 1:
            optical_img = _load_image(images[0])

    if optical_img is None:
        return {
            "answer": "Failed to decode valid optical imagery for Optical-SAR fusion.",
            "confidence": None,
            "visual_evidence": None,
            "details": {
                "specialist": "SARFusion",
                "error": "Invalid optical image",
            },
        }

    t0 = time.time()

    # 1. Classical SAR Backscatter Thresholding Analysis
    sar_metrics: Optional[Dict[str, Any]] = None
    sar_summary_str = ""
    if sar_img is not None:
        sar_metrics = _process_sar_backscatter(sar_img)
        sar_summary_str = (
            f"SAR backscatter analysis (Sentinel-1 VV) indicates: "
            f"Water coverage ~{sar_metrics['water_pct']}%, "
            f"Built-up/urban coverage ~{sar_metrics['builtup_pct']}%."
        )
    else:
        sar_summary_str = "SAR image not provided; running optical-only scene analysis."

    # 2. GeoChat-7B Optical Scene Description
    optical_description = ""
    duration = 0.0
    if is_geochat_loaded():
        optical_description, visual_evidence, duration = run_geochat_inference(
            image=optical_img,
            query=query,
        )
        model_name = "GeoChat-7B Optical VLM + Classical SAR Backscatter Thresholding"
    else:
        optical_description = f"[GeoChat engine uninitialized] Optical scene description for query: '{query}'."
        model_name = "Fallback Stub (SAR Thresholding Active)"
        duration = time.time() - t0

    # 3. Decision-Level Multimodal Fusion Synthesis
    combined_answer = (
        f"Optical imagery analysis (GeoChat): {optical_description}\n\n"
        f"Synthetic Aperture Radar (SAR) Analysis: {sar_summary_str}"
    )

    return {
        "answer": combined_answer,
        "confidence": None,
        "visual_evidence": {
            "fusion_type": "Optical_SAR_Multimodal",
            "optical_analyzed": True,
            "sar_analyzed": sar_metrics is not None,
            "sar_metrics": sar_metrics,
            "sar_thresholds": {
                "water_max_intensity": WATER_THRESHOLD_MAX,
                "builtup_min_intensity": BUILTUP_THRESHOLD_MIN,
            },
        },
        "details": {
            "specialist": "SARFusion",
            "model": model_name,
            "fusion_technique": "Optical VLM Scene Description + Classical SAR Backscatter Thresholding",
            "latency_seconds": round(duration, 2),
        },
    }

