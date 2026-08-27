"""
VQA Answer Scoring Module for GeoChat Benchmark Evaluation.

Provides a robust `compute_answer_score()` function that handles the
realities of VQA output — GeoChat generates conversational prose while
ground truths are often terse (e.g., "yes", "403", "forest").

Scoring strategy by answer type:
  - Yes/No:       Leading-token polarity check → 1.0 or 0.0
  - Numeric/Count: Extract digits from prose → exact match 1.0, near-miss 0.5, none 0.0
  - Categorical:   Token-set containment / Jaccard similarity → 1.0, 0.75, or 0.0
"""

import re
from typing import Optional


def compute_answer_score(
    prediction: str,
    ground_truth: str,
    question_type: Optional[str] = None,
) -> float:
    """
    Computes a robust score between 0.0 and 1.0 for VQA answers,
    handling prose-to-number extraction and clean yes/no polarity checks.

    Args:
        prediction:    The model's raw text output (may be conversational prose).
        ground_truth:  The expected terse answer from the dataset.
        question_type: Optional hint — "yes_no", "count", or "general".
                       If None, the function auto-detects from the ground truth.

    Returns:
        A float score in [0.0, 1.0].
    """
    pred_cleaned = str(prediction).strip().lower()
    gt_cleaned = str(ground_truth).strip().lower()

    # ── 1. Exact match shortcut ──────────────────────────────────────────
    if pred_cleaned == gt_cleaned:
        return 1.0

    # ── 2. Yes/No / Presence questions ───────────────────────────────────
    # Auto-detect or use explicit hint
    if gt_cleaned in ("yes", "no") or question_type == "yes_no":
        # Extract the first alphabetic word from the prediction
        tokens = re.findall(r"\b[a-z]+\b", pred_cleaned)
        first_word = tokens[0] if tokens else ""
        if first_word == gt_cleaned:
            return 1.0
        # Also check for strong negation cues when gt is "no"
        if gt_cleaned == "no" and first_word in ("no", "not", "none", "neither"):
            return 1.0
        return 0.0  # Clear polarity mismatch for binary questions

    # ── 3. Numeric / Count questions ─────────────────────────────────────
    if gt_cleaned.isdigit() or question_type == "count":
        # Find all integer sequences in the prediction text
        pred_numbers = re.findall(r"\d+", pred_cleaned)
        if gt_cleaned in pred_numbers:
            return 1.0
        elif pred_numbers:
            # Partial credit: the model produced a number, but not the right one
            return 0.5
        else:
            return 0.0

    # ── 4. General / Categorical text matching ───────────────────────────
    gt_tokens = set(re.findall(r"\b[a-z]+\b", gt_cleaned))
    pred_tokens = set(re.findall(r"\b[a-z]+\b", pred_cleaned))

    if not gt_tokens:
        # Edge case: ground truth has no alphabetic tokens (unlikely)
        return 0.0

    # Full containment: every GT token appears in the prediction
    if gt_tokens.issubset(pred_tokens):
        return 1.0

    # Jaccard similarity fallback for partial matches
    intersection = gt_tokens & pred_tokens
    union = gt_tokens | pred_tokens
    if union and (len(intersection) / len(union)) > 0.5:
        return 0.75

    return 0.0
