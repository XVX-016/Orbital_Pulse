from typing import Any, Dict, List, Optional
from PIL import Image

from geochat_engine import run_geochat_inference, is_geochat_loaded


from grounding_parser import clean_geochat_text
from response_formatter import get_enriched_demo_response

def run_vqa(images: List[Any], query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Executes VQA over optical remote-sensing image using GeoChat-7B."""
    if not images or not isinstance(images[0], Image.Image):
        return {
            "answer": "No valid image provided for Visual Question Answering.",
            "confidence": None,
            "visual_evidence": None,
            "details": {"specialist": "VQA", "error": "Invalid image input"}
        }

    image = images[0]

    if is_geochat_loaded():
        answer_text, visual_evidence, duration = run_geochat_inference(image, query)
        clean_answer = clean_geochat_text(answer_text)
        return {
            "answer": clean_answer if clean_answer else answer_text,
            "confidence": None,  # Model logits unavailable in standard generation
            "visual_evidence": visual_evidence if visual_evidence else None,
            "details": {
                "specialist": "VQA",
                "model": "GeoChat-7B (4-bit)",
                "latency_seconds": round(duration, 2)
            }
        }
    else:
        return {
            "answer": get_enriched_demo_response("vqa", query, (parameters or {}).get("stac_cog_metrics", {})),
            "confidence": None,
            "visual_evidence": None,
            "details": {"specialist": "VQA", "model": "Deterministic metadata fallback"}
        }
