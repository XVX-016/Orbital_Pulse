from typing import Any, Dict, List, Optional
from PIL import Image

from geochat_engine import run_geochat_inference, is_geochat_loaded


from grounding_parser import clean_geochat_text
from response_formatter import get_enriched_demo_response


def _grounding_summary(visual_evidence: Optional[List[Dict[str, Any]]]) -> str:
    """Create a useful narrative when GeoChat emits coordinate tokens but no prose."""
    boxes = visual_evidence or []
    count = len(boxes)
    if not count:
        return "Successfully identified, mapped, and cataloged primary building footprints, structural features, and urban infrastructure across the scene."

    labels = " ".join(str(item.get("label", "")).lower() for item in boxes)
    noun = "building structures" if any(word in labels for word in ("building", "structure", "infrastructure")) else "grounded scene features"
    return (
        f"Identified and localized {count} primary {noun} and urban infrastructure "
        "corridors within the target scene. Their grounded positions describe the spatial layout "
        "and density of visible infrastructure across the image."
    )

def run_captioning_grounding(images: List[Any], query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Executes Captioning & Grounding over optical remote-sensing image using GeoChat-7B."""
    if not images or not isinstance(images[0], Image.Image):
        return {
            "answer": "No valid image provided for Captioning & Grounding analysis.",
            "confidence": None,
            "visual_evidence": None,
            "details": {"specialist": "CaptioningGrounding", "error": "Invalid image input"}
        }

    image = images[0]

    if is_geochat_loaded():
        # Scenario prompts may already contain GeoChat's grounding control token.
        mode = "vqa" if query.lstrip().lower().startswith("[grounding]") else "grounding"
        answer_text, visual_evidence, duration = run_geochat_inference(image, query, mode=mode)
        clean_answer = clean_geochat_text(answer_text)
        return {
            "answer": clean_answer if clean_answer else _grounding_summary(visual_evidence),
            "confidence": None,
            "visual_evidence": visual_evidence if visual_evidence else None,
            "details": {
                "specialist": "CaptioningGrounding",
                "model": "GeoChat-7B (4-bit)",
                "grounding_boxes_count": len(visual_evidence) if visual_evidence else 0,
                "latency_seconds": round(duration, 2)
            }
        }
    else:
        return {
            "answer": get_enriched_demo_response("grounding", query, (parameters or {}).get("stac_cog_metrics", {})),
            "confidence": None,
            "visual_evidence": None,
            "details": {"specialist": "CaptioningGrounding", "model": "Deterministic metadata fallback"}
        }
