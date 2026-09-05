"""SatQuery AI Agent Controller.

Orchestrates task classification, specialist selection, parameter extraction, and execution tracing for remote-sensing VQA and change analysis requests.
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from specialists.vqa import run_vqa
from specialists.captioning_grounding import run_captioning_grounding
from specialists.change_vqa import run_change_vqa
from specialists.sar_fusion import run_sar_fusion

from geospatial_metrics import (
    compute_ndvi_coverage,
    compute_change_area,
    compute_area_from_bbox,
    compute_landcover_breakdown,
)

logger = logging.getLogger(__name__)


def classify_task(
    query: str,
    image_count: int,
    modality: str = "optical",
    temporal: str = "single"
) -> str:
    """Rule-based classifier determining the primary specialist task.

    Task types:
    - 'sar_fusion': SAR imagery involved (modality == 'sar' or 'both', or query mentions SAR/radar)
    - 'change_vqa': Bi-temporal comparison (image_count >= 2, temporal == 'bi-temporal', or change keywords)
    - 'grounding': Query requests object detection/location (where, find, locate, bounding box, highlight)
    - 'vqa': General visual question answering over single optical image
    """
    q_lower = query.lower()
    
    # Rule 1: SAR modality or SAR keywords -> Optical-SAR Fusion
    if modality in ["sar", "both"] or any(kw in q_lower for kw in ["sar", "radar", "sentinel-1", "cloud-penetrating", "night"]):
        return "sar_fusion"
    
    # Rule 2: Multiple images, bi-temporal flag, or change/compare keywords -> Change-VQA
    change_keywords = ["change", "compare", "deforestation", "disaster", "before", "after", "difference", "altered", "modified"]
    if image_count >= 2 or temporal == "bi-temporal" or any(kw in q_lower for kw in change_keywords):
        return "change_vqa"
    
    # Rule 3: Grounding / spatial localization keywords -> Grounding / Captioning
    grounding_keywords = ["where", "locate", "find", "highlight", "bounding box", "detect", "ground", "point out", "segment", "identify", "infrastructure", "object"]
    if any(kw in q_lower for kw in grounding_keywords):
        return "grounding"
        
    # Rule 4: Default -> Visual Question Answering
    return "vqa"


def _load_bands_from_path(path: str) -> Optional[np.ndarray]:
    """Load a GeoTIFF as a (C, H, W) float32 numpy array. Returns None on failure."""
    try:
        import rasterio
        with rasterio.open(path) as src:
            return src.read().astype(np.float32)
    except Exception as e:
        logger.debug(f"_load_bands_from_path failed for '{path}': {e}")
        return None


def _load_geotransform_from_path(path: str):
    """Load rasterio Affine transform from a GeoTIFF path. Returns None on failure."""
    try:
        import rasterio
        with rasterio.open(path) as src:
            return src.transform if src.crs else None
    except Exception:
        return None


def _compute_change_vqa_metrics(
    images: List[Any],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compute deterministic geospatial metrics for a change_vqa task.

    Runs alongside (not inside) GeoChat: loads raw band arrays from GeoTIFF paths
    when available, computes NDVI + landcover for before/after, and spectral change area.
    Returns a structured dict for the top-level 'computed_metrics' field.
    Returns None when no GeoTIFF band data is available (e.g., JPEG upload with no georef).
    """
    metrics: Dict[str, Any] = {}

    # Recover GeoTIFF paths from params if the scenario route populated them
    before_path: Optional[str] = params.get("before_tif_path")
    after_path: Optional[str] = params.get("after_tif_path")

    before_bands: Optional[np.ndarray] = None
    after_bands: Optional[np.ndarray] = None
    geotransform = None

    if before_path:
        before_bands = _load_bands_from_path(before_path)
        geotransform = _load_geotransform_from_path(before_path)

    if after_path:
        after_bands = _load_bands_from_path(after_path)

    if before_bands is None and after_bands is None:
        return {}

    # --- Per-date NDVI coverage
    if before_bands is not None:
        try:
            metrics["before_ndvi"] = compute_ndvi_coverage(before_bands)
        except Exception as e:
            logger.warning(f"compute_ndvi_coverage(before) failed: {e}")

    if after_bands is not None:
        try:
            metrics["after_ndvi"] = compute_ndvi_coverage(after_bands)
        except Exception as e:
            logger.warning(f"compute_ndvi_coverage(after) failed: {e}")

    # --- Per-date landcover breakdown
    if before_bands is not None:
        try:
            metrics["before_landcover"] = compute_landcover_breakdown(before_bands)
        except Exception as e:
            logger.warning(f"compute_landcover_breakdown(before) failed: {e}")

    if after_bands is not None:
        try:
            metrics["after_landcover"] = compute_landcover_breakdown(after_bands)
        except Exception as e:
            logger.warning(f"compute_landcover_breakdown(after) failed: {e}")

    # --- Bi-temporal change area (only when we have both dates)
    if before_bands is not None and after_bands is not None:
        try:
            metrics["spectral_change"] = compute_change_area(
                before_bands=before_bands,
                after_bands=after_bands,
                geotransform=geotransform,
                threshold=0.15,
            )
        except Exception as e:
            logger.warning(f"compute_change_area failed: {e}")

    if not metrics:
        return {}

    return {
        "task": "change_vqa",
        "georeferenced": geotransform is not None,
        **metrics,
    }


def _compute_grounding_metrics(
    images: List[Any],
    visual_evidence: Any,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compute bounding-box real-world areas for each detected object in a grounding task.

    For GeoTIFF inputs with a valid geotransform, each grounding box gets an estimated
    area in km². For plain JPEG/PNG uploads, box_area_km2 is None (no fabricated scale).
    """
    if not visual_evidence or not isinstance(visual_evidence, list):
        return {}

    # Recover image dimensions from first PIL Image if present
    img_w, img_h = None, None
    for img in images:
        try:
            from PIL.Image import Image as PILImage
            if isinstance(img, PILImage):
                img_w, img_h = img.size  # (width, height)
                break
        except Exception:
            pass

    if img_w is None or img_h is None:
        return {}

    # Attempt to recover geotransform from path param
    geotransform = None
    tif_path = params.get("before_tif_path") or params.get("tif_path")
    if tif_path:
        geotransform = _load_geotransform_from_path(tif_path)

    box_areas = []
    for item in visual_evidence:
        box = item.get("box_normalized")
        if not box or len(box) != 4:
            continue
        area_result = compute_area_from_bbox(
            box_normalized=box,
            geotransform=geotransform,
            image_width=img_w,
            image_height=img_h,
        )
        box_areas.append({
            "label": item.get("label", "object"),
            "box_normalized": box,
            "area_km2": area_result["area_km2"] if area_result else None,
            "area_m2": area_result["area_m2"] if area_result else None,
            "georeferenced": geotransform is not None,
        })

    if not box_areas:
        return {}

    return {
        "task": "grounding",
        "georeferenced": geotransform is not None,
        "object_areas": box_areas,
    }


def _compute_single_image_metrics(
    images: List[Any],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compute landcover breakdown + NDVI for single-image VQA tasks when a GeoTIFF path is available.
    """
    tif_path = params.get("before_tif_path") or params.get("tif_path")
    if not tif_path:
        return {}

    bands = _load_bands_from_path(tif_path)
    if bands is None:
        return {}

    metrics: Dict[str, Any] = {"task": "vqa"}
    try:
        metrics["ndvi"] = compute_ndvi_coverage(bands)
    except Exception as e:
        logger.warning(f"compute_ndvi_coverage(single) failed: {e}")
    try:
        metrics["landcover"] = compute_landcover_breakdown(bands)
    except Exception as e:
        logger.warning(f"compute_landcover_breakdown(single) failed: {e}")

    return metrics if len(metrics) > 1 else {}


def route_and_execute(
    images: List[Any],
    query: str,
    modality: str = "optical",
    temporal: str = "single",
    custom_parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Routes request to specialist and returns structured answer with execution trace.

    Returns:
    - answer: str                  — qualitative VLM output (GeoChat)
    - confidence: float | None
    - visual_evidence: dict | None — bboxes / SAR metrics from VLM
    - computed_metrics: dict | None — deterministic geospatial measurements (geospatial_metrics.py)
    - execution_trace: dict        — task, specialist_used, parameters
    """
    image_count = len(images)
    task = classify_task(query, image_count, modality=modality, temporal=temporal)
    params = custom_parameters or {}
    params.update({
        "image_count": image_count,
        "modality": modality,
        "temporal": temporal
    })
    
    logger.info(f"Controller routed query '{query}' (images={image_count}, modality={modality}) to task='{task}'")
    
    if task == "sar_fusion":
        specialist_name = "sar_fusion.run_sar_fusion"
        res = run_sar_fusion(images, query, parameters=params)
        computed_metrics = None  # SAR thresholding metrics already in visual_evidence.sar_metrics

    elif task == "change_vqa":
        specialist_name = "change_vqa.run_change_vqa"
        res = run_change_vqa(images, query, parameters=params)
        try:
            raw = _compute_change_vqa_metrics(images, params)
            computed_metrics = raw if raw else None
        except Exception as e:
            logger.warning(f"Geospatial metrics for change_vqa failed: {e}")
            computed_metrics = None

    elif task == "grounding":
        specialist_name = "captioning_grounding.run_captioning_grounding"
        res = run_captioning_grounding(images, query, parameters=params)
        try:
            raw = _compute_grounding_metrics(images, res.get("visual_evidence"), params)
            computed_metrics = raw if raw else None
        except Exception as e:
            logger.warning(f"Geospatial metrics for grounding failed: {e}")
            computed_metrics = None

    else:
        specialist_name = "vqa.run_vqa"
        res = run_vqa(images, query, parameters=params)
        try:
            raw = _compute_single_image_metrics(images, params)
            computed_metrics = raw if raw else None
        except Exception as e:
            logger.warning(f"Geospatial metrics for vqa failed: {e}")
            computed_metrics = None

    # Auditable execution trace
    execution_trace = {
        "task": task,
        "specialist_used": specialist_name,
        "parameters": params
    }
    
    return {
        "answer": res.get("answer", ""),
        "confidence": res.get("confidence", None),
        "visual_evidence": res.get("visual_evidence", None),
        "computed_metrics": computed_metrics,
        "execution_trace": execution_trace
    }
