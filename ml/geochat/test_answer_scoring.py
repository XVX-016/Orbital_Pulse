#!/usr/bin/env python3
"""
Unit tests for the VQA answer scoring module.

Covers the 5 eyeball examples from Prompt 60, plus edge cases
for each scoring tier (yes/no, numeric, categorical).

Run with:
    python -m pytest ml/geochat/test_answer_scoring.py -v
    # or standalone:
    python ml/geochat/test_answer_scoring.py
"""

import sys
import os

# Ensure the module is importable regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from answer_scoring import compute_answer_score


# ─────────────────────────────────────────────────────────────────────
# Eyeball Examples (from Prompt 60)
# ─────────────────────────────────────────────────────────────────────

def test_eyeball_1_binary_yes():
    """Example 1: Binary / Presence — leading 'Yes' matches GT 'yes'."""
    score = compute_answer_score(
        prediction="Yes, there are several visible roads connecting the blocks.",
        ground_truth="yes",
    )
    assert score == 1.0, f"Expected 1.0, got {score}"


def test_eyeball_2_count_exact():
    """Example 2: Count — digit '403' extracted from prose matches GT '403'."""
    score = compute_answer_score(
        prediction="There are approximately 403 roads visible in this grid.",
        ground_truth="403",
    )
    assert score == 1.0, f"Expected 1.0, got {score}"


def test_eyeball_3_count_near_miss():
    """Example 3: Count near-miss — numbers present but exact target '12' absent."""
    score = compute_answer_score(
        prediction="I count around 10 to 15 buildings in the cluster.",
        ground_truth="12",
    )
    assert score == 0.5, f"Expected 0.5, got {score}"


def test_eyeball_4_categorical_containment():
    """Example 4: Categorical — GT token 'forest' contained in prediction tokens."""
    score = compute_answer_score(
        prediction="The patch is predominantly covered by dense forest and trees.",
        ground_truth="forest",
    )
    assert score == 1.0, f"Expected 1.0, got {score}"


def test_eyeball_5_binary_no():
    """Example 5: Negative binary — leading 'No' matches GT 'no'."""
    score = compute_answer_score(
        prediction="No water bodies can be identified in this image patch.",
        ground_truth="no",
    )
    assert score == 1.0, f"Expected 1.0, got {score}"


# ─────────────────────────────────────────────────────────────────────
# Additional Edge Cases
# ─────────────────────────────────────────────────────────────────────

def test_exact_match():
    """Exact string match should always return 1.0."""
    assert compute_answer_score("forest", "forest") == 1.0
    assert compute_answer_score("403", "403") == 1.0
    assert compute_answer_score("yes", "yes") == 1.0


def test_yes_no_wrong_polarity():
    """Model says yes when GT is no → 0.0."""
    score = compute_answer_score(
        prediction="Yes, there appears to be a water body.",
        ground_truth="no",
    )
    assert score == 0.0, f"Expected 0.0, got {score}"


def test_yes_no_negation_cue():
    """Negation cue 'Not' treated as 'no' polarity."""
    score = compute_answer_score(
        prediction="Not visible in this image.",
        ground_truth="no",
    )
    assert score == 1.0, f"Expected 1.0, got {score}"


def test_count_no_numbers():
    """Model gives prose with no digits for a count question → 0.0."""
    score = compute_answer_score(
        prediction="There are many buildings in this area.",
        ground_truth="12",
    )
    assert score == 0.0, f"Expected 0.0, got {score}"


def test_categorical_no_overlap():
    """Zero token overlap between prediction and GT → 0.0."""
    score = compute_answer_score(
        prediction="Urban area with dense roads and parking lots.",
        ground_truth="forest",
    )
    assert score == 0.0, f"Expected 0.0, got {score}"


def test_categorical_partial_jaccard():
    """Partial overlap triggers Jaccard fallback."""
    # GT: "mountainous forest terrain" (3 tokens)
    # Pred has "mountainous" and "terrain" (2/3 overlap)
    score = compute_answer_score(
        prediction="The area shows mountainous terrain with sparse vegetation.",
        ground_truth="mountainous forest terrain",
    )
    # Jaccard = intersection / union.  GT tokens = {mountainous, forest, terrain}
    # Pred tokens = {the, area, shows, mountainous, terrain, with, sparse, vegetation}
    # Intersection = {mountainous, terrain} = 2
    # Union = 9
    # Jaccard = 2/9 ≈ 0.22, below 0.5 threshold → 0.0
    assert score == 0.0, f"Expected 0.0, got {score}"


def test_question_type_hint_overrides():
    """Explicit question_type hint forces the right scoring branch."""
    # Force count scoring even though GT doesn't look numeric (edge case)
    score = compute_answer_score(
        prediction="I see about 5 structures.",
        ground_truth="5",
        question_type="count",
    )
    assert score == 1.0, f"Expected 1.0, got {score}"


# ─────────────────────────────────────────────────────────────────────
# Standalone runner
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_funcs = [
        test_eyeball_1_binary_yes,
        test_eyeball_2_count_exact,
        test_eyeball_3_count_near_miss,
        test_eyeball_4_categorical_containment,
        test_eyeball_5_binary_no,
        test_exact_match,
        test_yes_no_wrong_polarity,
        test_yes_no_negation_cue,
        test_count_no_numbers,
        test_categorical_no_overlap,
        test_categorical_partial_jaccard,
        test_question_type_hint_overrides,
    ]

    passed = 0
    failed = 0
    for fn in test_funcs:
        try:
            fn()
            print(f"  [PASS] {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {fn.__name__}: {e}")
            failed += 1

    print(f"\n{'=' * 50}")
    print(f"Results: {passed} passed, {failed} failed out of {len(test_funcs)}")
    print(f"{'=' * 50}")
    sys.exit(1 if failed else 0)
