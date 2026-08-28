"""
VQA Answer Scoring Module for GeoChat Benchmark Evaluation.

Provides a robust `compute_answer_score()` function that handles the
realities of VQA output — GeoChat generates conversational prose with grounding tags,
while ground truths are often concise descriptions or keyword sets.

Scoring strategy by answer type:
  - Yes/No:       Polarity check (full prediction, not just first token) → 1.0/0.8/0.0
                  If GT is rich description starting "yes/no,", polarity + keyword-recall
                  are blended so paraphrases without leading "Yes" still score fairly.
  - Numeric/Count: Extract numbers → exact match 1.0, partial 0.5, none 0.0
  - General:       Grounding tag stripping + Token-set overlap (Recall/Jaccard) → float in [0.0, 1.0]

Bug-fix notes (2026-08-28):
  - Previously, yes_no predictions that expressed the correct answer as prose
    without a leading polarity word (e.g. "The image clearly shows green agricultural
    fields…") received 0.0 because the old code only checked the first token and the
    first 15 characters.  Now polarity is checked anywhere in the prediction and a
    keyword-recall fallback is used when the first-token heuristic doesn't trigger.
  - The content-keyword check now produces a blended score
    (1.0 for polarity + overlap, 0.8 for polarity alone) instead of the former
    binary 1.0/0.0 that could hide genuine model errors.
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


# Stopwords to ignore during token overlap scoring
_STOPWORDS = {
    "a", "an", "the", "in", "on", "at", "of", "and", "or", "is", "are",
    "there", "this", "image", "aerial", "remote", "sensing", "view",
    "scene", "with", "that", "it", "its", "be", "been", "was", "were",
    "has", "have", "had", "but", "by", "from", "into", "can", "visible",
}


def _keyword_recall(pred_tokens: set, gt_tokens: set) -> float:
    """Fraction of GT content-keywords found in the prediction (0.0–1.0)."""
    if not gt_tokens:
        return 1.0
    return len(gt_tokens & pred_tokens) / len(gt_tokens)


def _polarity_in_pred(clean_pred: str) -> Optional[str]:
    """
    Detects yes/no polarity anywhere in the prediction, with priority to leading
    cues.  Returns 'yes', 'no', or None.
    """
    pred_words = re.findall(r"\b[a-z]+\b", clean_pred)
    if not pred_words:
        return None

    # Leading token heuristics (highest priority)
    first = pred_words[0]
    if first in ("yes", "yeah", "yep", "certainly", "indeed", "absolutely", "definitely"):
        return "yes"
    if first in ("no", "not", "none", "neither", "never", "absent"):
        return "no"

    # Window over first few words for common negative openers
    first_chunk = " ".join(pred_words[:6])
    if re.search(r"\b(no|not|there is no|there are no|none of|cannot|can't)\b", first_chunk):
        return "no"
    if re.search(r"\b(yes|there (is|are))\b", first_chunk):
        return "yes"

    # Broader scan — only use if explicit affirmation/negation phrase found
    if re.search(r"\b(is present|are present|can be seen|are visible|clearly shows|does contain)\b", clean_pred):
        return "yes"
    if re.search(r"\b(is not present|are not present|not visible|not found|no .{0,20} present)\b", clean_pred):
        return "no"

    return None


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

    # Shared token sets (stopwords removed)
    gt_tokens = set(re.findall(r"\b[a-z]+\b", clean_gt)) - _STOPWORDS
    pred_tokens = set(re.findall(r"\b[a-z]+\b", clean_pred)) - _STOPWORDS

    # 2. Yes/No / Presence questions
    gt_starts_yes = clean_gt.startswith("yes")
    gt_starts_no = clean_gt.startswith("no")
    is_yes_no = gt_starts_yes or gt_starts_no or question_type == "yes_no"

    if is_yes_no:
        gt_polarity = "yes" if (gt_starts_yes or "yes" in clean_gt.split()[:2]) else "no"
        # Content keywords in GT (strip the polarity word itself)
        content_gt_tokens = gt_tokens - {"yes", "no"}
        content_pred_tokens = pred_tokens - {"yes", "no"}

        pred_polarity = _polarity_in_pred(clean_pred)

        if pred_polarity == gt_polarity:
            # Correct polarity: blend in content keyword recall
            recall = _keyword_recall(content_pred_tokens, content_gt_tokens)
            if recall >= 0.5 or not content_gt_tokens:
                return 1.0
            # Correct polarity but content diverges — still reward polarity
            return 0.8

        if pred_polarity is None:
            # No clear polarity word — fall back to keyword recall.
            # If the prediction paraphrases the GT content well, give partial credit.
            recall = _keyword_recall(content_pred_tokens, content_gt_tokens)
            if recall >= 0.6:
                # Strong content match — the prediction substantively agrees even
                # without an explicit yes/no — score as correct answer.
                return 0.9
            elif recall >= 0.3:
                return 0.5
            # Check for negation cues: if GT is "yes" and pred contains negation → 0.0
            if gt_polarity == "yes" and _polarity_in_pred(clean_pred) == "no":
                return 0.0
            return 0.0

        # Wrong polarity
        return 0.0

    # 3. Numeric / Count questions
    if clean_gt.isdigit() or question_type == "count":
        pred_numbers = re.findall(r"\d+", clean_pred)
        if clean_gt in pred_numbers:
            return 1.0
        elif pred_numbers:
            return 0.5
        return 0.0

    # 4. General / Categorical text matching — grounding-stripped token recall
    if not gt_tokens:
        return 1.0 if clean_pred else 0.0

    recall = _keyword_recall(pred_tokens, gt_tokens)

    if recall >= 0.8:
        return 1.0
    elif recall >= 0.5:
        return 0.75
    elif recall >= 0.25:
        return 0.5
    elif len(gt_tokens & pred_tokens) >= 1:
        return 0.25

    return 0.0
