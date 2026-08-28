"""
VQA Answer Scoring Module for GeoChat Benchmark Evaluation.

Provides a robust `compute_answer_score()` function that handles the
realities of VQA output — GeoChat generates conversational prose with grounding tags,
while ground truths are often concise descriptions or keyword sets.

Scoring strategy by answer type:
  - Yes/No:       Leading-token / polarity check → 1.0 or 0.0
  - Numeric/Count: Extract numbers → exact match 1.0, partial 0.5, none 0.0
  - General:       Grounding tag stripping + Token-set overlap (Recall/Jaccard) → float in [0.0, 1.0]
"""

import re
from typing import Optional


def strip_grounding_markup(text: str) -> str:
    """Removes GeoChat grounding tags (<p>...</p>), coordinate tokens ({<...|...>}), and delimiters."""
    # Remove coordinate tokens like {<28><55><36><57>|<1>}
    text = re.sub(r"\{<\d+><\d+><\d+><\d+>\|[^}]*\}", "", text)
    # Remove <delim> tags
    text = re.sub(r"<delim>", "", text)
    # Strip <p> and </p> tags but preserve the inner label text
    text = re.sub(r"</?p>", "", text)
    # Clean up whitespace
    return re.sub(r"\s+", " ", text).strip()


def compute_answer_score(
    prediction: str,
    ground_truth: str,
    question_type: Optional[str] = None,
) -> float:
    """
    Computes a robust score between 0.0 and 1.0 for VQA answers.
    Strips grounding markup first, then performs polarity checks for Yes/No,
    numeric matching for Count, and token recall/containment for General questions.

    Args:
        prediction:    The model's raw text output (may contain grounding markup).
        ground_truth:  The expected answer / reference description.
        question_type: Optional hint — "yes_no", "count", or "general".

    Returns:
        A float score in [0.0, 1.0].
    """
    # 0. Strip visual grounding tokens
    clean_pred = strip_grounding_markup(str(prediction)).strip().lower()
    clean_gt = strip_grounding_markup(str(ground_truth)).strip().lower()

    if not clean_pred:
        return 0.0

    # 1. Exact match shortcut
    if clean_pred == clean_gt:
        return 1.0

    # Stopwords to ignore during token overlap scoring
    stopwords = {"a", "an", "the", "in", "on", "at", "of", "and", "or", "is", "are", "there", "this", "image", "aerial", "remote", "sensing", "view", "scene", "with"}

    # 2. Yes/No / Presence questions
    if clean_gt.startswith("yes") or clean_gt.startswith("no") or question_type == "yes_no":
        pred_words = re.findall(r"\b[a-z]+\b", clean_pred)
        first_word = pred_words[0] if pred_words else ""
        gt_polarity = "yes" if ("yes" in clean_gt or clean_gt.startswith("yes")) else "no"
        
        if first_word == gt_polarity or (gt_polarity in clean_pred[:15]):
            # Check content match after polarity
            gt_tokens = set(re.findall(r"\b[a-z]+\b", clean_gt)) - stopwords - {"yes", "no"}
            pred_tokens = set(re.findall(r"\b[a-z]+\b", clean_pred)) - stopwords - {"yes", "no"}
            if not gt_tokens or (gt_tokens & pred_tokens):
                return 1.0
            return 0.8  # Correct polarity, minor keyword variance

        if gt_polarity == "no" and first_word in ("no", "not", "none", "neither"):
            return 1.0

        return 0.0

    # 3. Numeric / Count questions
    if clean_gt.isdigit() or question_type == "count":
        pred_numbers = re.findall(r"\d+", clean_pred)
        if clean_gt in pred_numbers:
            return 1.0
        elif pred_numbers:
            return 0.5
        return 0.0

    # 4. General / Categorical text matching
    gt_tokens = set(re.findall(r"\b[a-z]+\b", clean_gt)) - stopwords
    pred_tokens = set(re.findall(r"\b[a-z]+\b", clean_pred)) - stopwords

    if not gt_tokens:
        return 1.0 if clean_pred else 0.0

    overlap = gt_tokens & pred_tokens
    recall = len(overlap) / len(gt_tokens)

    if recall >= 0.8:
        return 1.0
    elif recall >= 0.5:
        return 0.75
    elif recall >= 0.25:
        return 0.5
    elif len(overlap) >= 1:
        return 0.25

    return 0.0
