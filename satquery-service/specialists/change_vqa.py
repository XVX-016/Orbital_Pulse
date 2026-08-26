"""
Change-VQA & Bi-temporal Analysis Specialist.

Handles bi-temporal satellite imagery comparison, change quantification, and change-VQA answering.
Uses GeoChat-7B native multi-image prompting confirmed via test_two_image.py.
"""

import time
import logging
from typing import Any, Dict, List, Optional
from PIL import Image

from geochat_engine import (
    run_geochat_multi_image_inference,
    run_geochat_inference,
    is_geochat_loaded,
)

logger = logging.getLogger(__name__)


def run_change_vqa(images: List[Any], query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Exposes Change Detection & Change-VQA over bi-temporal imagery pairs using native GeoChat multi-image prompting.

    Architecture Note:
        Prompt 56 verification (test_two_image.py) confirmed that GeoChat natively supports multiple <image>
        tokens in a single prompt by batching image tensors (shape: [N, 3, 504, 504]).
        Therefore, this specialist passes both bi-temporal images into GeoChat in a single forward pass
        to enable direct visual comparison attention across time steps.

    Result schema:
      - answer: str
      - confidence: float | None
      - visual_evidence: dict | None (bboxes / grounding evidence list)
      - details: dict (metadata, specialist name, latency, model used)
    """
    if not images or len(images) == 0:
        return {
            "answer": "No valid imagery provided for bi-temporal change analysis.",
            "confidence": None,
            "visual_evidence": None,
            "details": {
                "specialist": "ChangeVQA",
                "error": "Empty images list",
            },
        }

    def _load_image(item: Any) -> Optional[Image.Image]:
        if isinstance(item, Image.Image):
            return item.convert("RGB")
        if isinstance(item, str):
            try:
                return Image.open(item).convert("RGB")
            except Exception:
                # Fallback for multi-band float GeoTIFF (.tif) satellite imagery via rasterio
                try:
                    import rasterio
                    import numpy as np
                    with rasterio.open(item) as src:
                        arr = src.read()
                        if arr.ndim == 3:
                            # Take first 3 bands for RGB (or top 3)
                            rgb = arr[:3, :, :].transpose(1, 2, 0)
                        else:
                            rgb = np.stack([arr] * 3, axis=-1)
                        # Normalize to 0..255 uint8 if float
                        if rgb.dtype != np.uint8:
                            val_min, val_max = rgb.min(), rgb.max()
                            if val_max > val_min:
                                rgb = ((rgb - val_min) / (val_max - val_min) * 255.0).astype(np.uint8)
                            else:
                                rgb = (rgb * 255.0).clip(0, 255).astype(np.uint8)
                        return Image.fromarray(rgb, mode="RGB")
                except Exception as ex:
                    logger.warning(f"Failed to load image from path '{item}': {ex}")
                    return None
        return None

    # Filter/convert inputs to PIL.Image
    pil_images: List[Image.Image] = []
    for item in images:
        loaded = _load_image(item)
        if loaded:
            pil_images.append(loaded)

    if len(pil_images) == 0:
        return {
            "answer": "Failed to decode input images for Change-VQA.",
            "confidence": None,
            "visual_evidence": None,
            "details": {
                "specialist": "ChangeVQA",
                "error": "No decodable PIL images",
            },
        }

    t0 = time.time()

    if is_geochat_loaded():
        try:
            if len(pil_images) >= 2:
                # Native multi-image forward pass across bi-temporal pair
                answer_text, visual_evidence, duration = run_geochat_multi_image_inference(
                    images=pil_images[:2],
                    query=query,
                )
                model_name = "GeoChat-7B (Native Multi-Image Bi-Temporal 4-bit)"
            else:
                # Fallback to single image VQA if only 1 image provided
                answer_text, visual_evidence, duration = run_geochat_inference(
                    image=pil_images[0],
                    query=query,
                )
                model_name = "GeoChat-7B (Single-Image VQA 4-bit)"

            return {
                "answer": answer_text,
                "confidence": None,  # Causal LM standard sampling; confidence unavailable
                "visual_evidence": {
                    "grounding_bboxes": visual_evidence if visual_evidence else [],
                    "image_count": len(pil_images),
                },
                "details": {
                    "specialist": "ChangeVQA",
                    "model": model_name,
                    "bi_temporal_mode": "native_multi_image" if len(pil_images) >= 2 else "single_image",
                    "latency_seconds": round(duration, 2),
                },
            }
        except Exception as e:
            logger.error(f"Error executing GeoChat inference in run_change_vqa: {e}", exc_info=True)
            return {
                "answer": f"Error during bi-temporal analysis: {str(e)}",
                "confidence": None,
                "visual_evidence": None,
                "details": {
                    "specialist": "ChangeVQA",
                    "error": str(e),
                },
            }
    else:
        # Engine uninitialized fallback
        return {
            "answer": f"[GeoChat Engine uninitialized] Bi-temporal query comparison for: '{query}'. Images analyzed: {len(pil_images)}.",
            "confidence": None,
            "visual_evidence": None,
            "details": {
                "specialist": "ChangeVQA",
                "model": "Fallback Stub",
                "image_count": len(pil_images),
            },
        }

