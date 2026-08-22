"""Change-VQA & Bi-temporal Analysis Specialist.

Handles bi-temporal imagery comparison, change quantification, and change-VQA query answering.
"""

from typing import Any, Dict, List, Optional


def run_change_vqa(images: List[Any], query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Exposes Change Detection & Change-VQA over bi-temporal imagery pairs.

    Result schema:
    - answer: str
    - confidence: float | None
    - visual_evidence: dict | None (mask_url, change_percentage)
    """
    # TODO: Integrate Prithvi-EO / Change-VQA bi-temporal model inference here
    
    return {
        "answer": f"Change VQA analysis for query: '{query}'. Bi-temporal comparison complete.",
        "confidence": None,
        "visual_evidence": {
            "mask_url": None,
            "change_percentage": None
        },
        "details": {
            "specialist": "ChangeVQA",
            "image_count": len(images),
            "model_target": "Prithvi-EO-100M / Change-VQA"
        }
    }
