"""SatQuery AI Agent Controller.

Orchestrates task classification, specialist selection, parameter extraction, and execution tracing for remote-sensing VQA and change analysis requests.
"""

import logging
from typing import Any, Dict, List, Optional

from specialists.vqa import run_vqa
from specialists.captioning_grounding import run_captioning_grounding
from specialists.change_vqa import run_change_vqa
from specialists.sar_fusion import run_sar_fusion

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
    grounding_keywords = ["where", "locate", "find", "highlight", "bounding box", "detect", "point out", "segment"]
    if any(kw in q_lower for kw in grounding_keywords):
        return "grounding"
        
    # Rule 4: Default -> Visual Question Answering
    return "vqa"


def route_and_execute(
    images: List[Any],
    query: str,
    modality: str = "optical",
    temporal: str = "single",
    custom_parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Routes request to specialist and returns structured answer with execution trace.

    Returns:
    - answer: str
    - confidence: float | None
    - visual_evidence: dict | None
    - execution_trace: dict (task, specialist_used, parameters)
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
    elif task == "change_vqa":
        specialist_name = "change_vqa.run_change_vqa"
        res = run_change_vqa(images, query, parameters=params)
    elif task == "grounding":
        specialist_name = "captioning_grounding.run_captioning_grounding"
        res = run_captioning_grounding(images, query, parameters=params)
    else:
        specialist_name = "vqa.run_vqa"
        res = run_vqa(images, query, parameters=params)

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
        "execution_trace": execution_trace
    }
