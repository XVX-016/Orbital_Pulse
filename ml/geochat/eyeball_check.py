#!/usr/bin/env python3
"""
Eyeball-check for the GeoChat answer_scoring module.

Runs the 3 benchmark samples with plausible predictions and prints
scored results side-by-side so a human can judge sanity.

Run from the repo root:
    python ml/geochat/eyeball_check.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from answer_scoring import compute_answer_score, strip_grounding_markup

SEP = "=" * 72

# ── Simulated model outputs ──────────────────────────────────────────────
# These represent the kinds of responses GeoChat actually produces.
# Grounding tags present in sample_1 to validate strip_grounding_markup().

EYEBALL_CASES = [
    # ── sample_1_airport ── general / grounding ────────────────────────
    {
        "id": "sample_1_airport",
        "question_type": "general",
        "ground_truth": "Urban development, roads, building structures, and surrounding spatial layout.",
        # GeoChat typically emits grounding tokens alongside prose
        "predictions": [
            # A: rich grounding response (should score well)
            "I can see <p>runway</p>{<10><5><20><15>|<1>} and <p>terminal building</p>"
            "{<30><20><50><40>|<2>} along with roads and urban structures.",
            # B: pure prose paraphrase (should still score well)
            "The image shows an urban area with roads, building structures and spatial layout.",
            # C: wrong content (should score low)
            "Dense forest with natural vegetation and no visible buildings.",
        ],
        "expected_ranges": [
            (0.2, 1.0, "grounding + prose with partial content-keyword overlap"),
            (0.7, 1.0, "good prose paraphrase, high keyword overlap"),
            (0.0, 0.3, "wrong content, minimal overlap with GT"),
        ],
    },
    # ── sample_2_agri ── YES/NO presence ──────────────────────────────
    {
        "id": "sample_2_agri",
        "question_type": "yes_no",
        "ground_truth": "Yes, clear agricultural vegetation, green crop fields, and rural landscape features.",
        "predictions": [
            # A: the paraphrase that scored 0.0 before the fix
            "The image clearly shows green agricultural fields and rural crop land with vegetation.",
            # B: explicit yes + content (should score 1.0)
            "Yes, I can see agricultural vegetation, green fields, and rural landscape.",
            # C: explicit wrong polarity (should score 0.0)
            "No, there is no agricultural land or vegetation in this image.",
            # D: bare 'yes' (correct polarity, no content — should still be ≥0.8)
            "Yes.",
        ],
        "expected_ranges": [
            (0.5, 1.0, "paraphrase fix — was 0.0, now should get content-recall credit"),
            (0.8, 1.0, "explicit yes + matching content"),
            (0.0, 0.1, "explicit wrong polarity"),
            (0.7, 1.0, "bare correct polarity"),
        ],
    },
    # ── sample_3_coastal ── general / captioning ───────────────────────
    {
        "id": "sample_3_coastal",
        "question_type": "general",
        "ground_truth": "Mountainous forest terrain with natural vegetation, mist/fog layer, and scenic landscape.",
        "predictions": [
            # A: good match (should score high)
            "The scene depicts mountainous terrain covered in dense forest vegetation with a misty fog layer.",
            # B: partial match — mentions terrain, vegetation but not mountains/fog
            "Natural vegetation and green terrain with trees and hills.",
            # C: grounding-polluted response that strips cleanly
            "I see <p>mountain</p>{<5><10><40><60>|<1>} with <p>forest</p>{<30><40><80><90>|<2>} "
            "and fog in the background.",
            # D: completely wrong
            "Urban area with skyscrapers and industrial zones.",
        ],
        "expected_ranges": [
            (0.7, 1.0, "strong keyword match after strip"),
            (0.3, 0.8, "partial overlap"),
            (0.25, 1.0, "grounding tags strip cleanly, 'mountain' and 'forest' match GT"),
            (0.0, 0.1, "wrong content"),
        ],
    },
]


def run_eyeball():
    total = 0
    sane = 0
    failures = []

    print(SEP)
    print("  GeoChat answer_scoring.py — Eyeball Sanity Check")
    print(SEP)

    for case in EYEBALL_CASES:
        print(f"\n{'─'*72}")
        print(f"  Sample : {case['id']}  (question_type={case['question_type']})")
        print(f"  GT     : {case['ground_truth']}")
        print(f"{'─'*72}")

        for i, (pred, (lo, hi, note)) in enumerate(
            zip(case["predictions"], case["expected_ranges"])
        ):
            clean = strip_grounding_markup(pred)
            score = compute_answer_score(
                prediction=pred,
                ground_truth=case["ground_truth"],
                question_type=case["question_type"],
            )
            ok = lo <= score <= hi
            flag = "✓" if ok else "✗ UNEXPECTED"
            total += 1
            if ok:
                sane += 1
            else:
                failures.append({
                    "sample": case["id"],
                    "pred_idx": i,
                    "score": score,
                    "expected": f"[{lo}, {hi}]",
                    "note": note,
                })

            print(f"  Pred {i+1}: {pred[:80]}{'…' if len(pred)>80 else ''}")
            print(f"  Clean : {clean[:80]}{'…' if len(clean)>80 else ''}")
            print(f"  Score : {score:.2f}  expected [{lo}–{hi}]  {flag}")
            print(f"  Note  : {note}")
            print()

    print(SEP)
    print(f"  Result: {sane}/{total} predictions in expected score range")
    if failures:
        print(f"\n  ── UNEXPECTED SCORES ──")
        for f in failures:
            print(f"  [{f['sample']} pred_{f['pred_idx']+1}] score={f['score']:.2f}  expected={f['expected']}")
            print(f"    note: {f['note']}")
    print(SEP)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(run_eyeball())
