#!/usr/bin/env python3
"""
SatQuery VQA Benchmark Evaluation Harness.

Pulls test subsets from VRSBench and RSVQA-LR public test benchmarks,
executes inference through the core SatQuery /api/analyze controller pipeline,
and computes Accuracy (Exact Match & Soft Keyword Match), BLEU-1, and BLEU-4 scores.

Usage:
    python satquery-service/eval/run_benchmark.py
"""

import os
import sys
import json
import time
import math
from collections import Counter
from typing import Dict, List, Any
from PIL import Image

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_DIR = os.path.abspath(os.path.join(EVAL_DIR, ".."))
if SERVICE_DIR not in sys.path:
    sys.path.insert(0, SERVICE_DIR)

from geochat_engine import init_geochat_model
from controller import route_and_execute


def compute_bleu_n(reference: str, hypothesis: str, n: int = 1) -> float:
    """Computes simple BLEU-N precision score with brevity penalty."""
    ref_tokens = reference.lower().strip().split()
    hyp_tokens = hypothesis.lower().strip().split()

    if not hyp_tokens:
        return 0.0

    # N-gram counts
    def get_ngrams(tokens, n_val):
        return [tuple(tokens[i : i + n_val]) for i in range(len(tokens) - n_val + 1)]

    ref_ngrams = Counter(get_ngrams(ref_tokens, n))
    hyp_ngrams = Counter(get_ngrams(hyp_tokens, n))

    if not hyp_ngrams:
        return 0.0

    clipped_matches = sum(min(count, ref_ngrams[ngram]) for ngram, count in hyp_ngrams.items())
    precision = clipped_matches / sum(hyp_ngrams.values())

    # Brevity penalty
    ref_len = len(ref_tokens)
    hyp_len = len(hyp_tokens)

    if hyp_len > ref_len:
        bp = 1.0
    elif hyp_len == 0:
        bp = 0.0
    else:
        bp = math.exp(1.0 - ref_len / hyp_len)

    return round(bp * precision, 4)


def evaluate_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Runs single benchmark item through SatQuery route_and_execute controller."""
    img_path = item["image"]
    query = item["question"]

    img = Image.open(img_path).convert("RGB")

    t0 = time.time()
    res = route_and_execute(images=[img], query=query)
    elapsed = time.time() - t0

    prediction = res.get("answer", "").strip()
    pred_lower = prediction.lower()

    answers = [a.lower() for a in item["answers"]]
    key_terms = [k.lower() for k in item["key_terms"]]

    # 1. Exact Match
    exact_match = 1.0 if any(pred_lower == a for a in answers) else 0.0

    # 2. Soft / Substring Keyword Match
    soft_match = 1.0 if any(kt in pred_lower for kt in key_terms) else 0.0

    # 3. BLEU Scores against primary ground truth answer
    ref_primary = item["answers"][0]
    bleu1 = compute_bleu_n(ref_primary, prediction, n=1)
    bleu4 = compute_bleu_n(ref_primary, prediction, n=4)

    return {
        "id": item["id"],
        "benchmark": item["benchmark"],
        "task_type": item["task_type"],
        "question": query,
        "reference_answers": item["answers"],
        "key_terms": item["key_terms"],
        "model_prediction": prediction,
        "specialist_used": res.get("execution_trace", {}).get("specialist_used", ""),
        "exact_match": exact_match,
        "soft_match": soft_match,
        "bleu1": bleu1,
        "bleu4": bleu4,
        "latency_seconds": round(elapsed, 2),
    }


def main():
    print("=" * 70)
    print("SatQuery AI Service — Public VQA Benchmark Evaluation")
    print("Benchmarks: VRSBench & RSVQA-LR (Public Test Splits)")
    print("=" * 70)

    # 1. Initialize GeoChat Base Model Engine
    print("\n[1/4] Initializing base GeoChat-7B model ...")
    success = init_geochat_model()
    if not success:
        print("[ERROR] GeoChat engine initialization failed.")
        sys.exit(1)

    # 2. Load Benchmark Items
    print("\n[2/4] Loading benchmark test subsets ...")
    data_dir = os.path.join(EVAL_DIR, "benchmark_data")

    vrs_file = os.path.join(data_dir, "vrsbench_test.json")
    rsvqa_file = os.path.join(data_dir, "rsvqa_lr_test.json")

    with open(vrs_file, "r") as f:
        vrs_items = json.load(f)
    with open(rsvqa_file, "r") as f:
        rsvqa_items = json.load(f)

    all_items = vrs_items + rsvqa_items
    print(f"      Loaded {len(vrs_items)} VRSBench items and {len(rsvqa_items)} RSVQA-LR items.")

    # 3. Execute Inference & Scoring
    print(f"\n[3/4] Running evaluation across {len(all_items)} benchmark samples ...")

    eval_results = []
    for idx, item in enumerate(all_items, 1):
        print(f"  [{idx}/{len(all_items)}] Eval [{item['benchmark']} - {item['task_type']}] id={item['id']} ...", end="", flush=True)
        res = evaluate_item(item)
        eval_results.append(res)
        print(f" (EM={res['exact_match']}, Soft={res['soft_match']}, BLEU1={res['bleu1']}, Latency={res['latency_seconds']}s)")

    # 4. Aggregate Metrics
    def aggregate(items: List[Dict[str, Any]]) -> Dict[str, float]:
        if not items:
            return {"count": 0, "exact_match_acc": 0.0, "soft_match_acc": 0.0, "bleu1": 0.0, "bleu4": 0.0, "avg_latency": 0.0}
        n = len(items)
        return {
            "count": n,
            "exact_match_acc": round(sum(i["exact_match"] for i in items) / n, 4),
            "soft_match_acc": round(sum(i["soft_match"] for i in items) / n, 4),
            "bleu1": round(sum(i["bleu1"] for i in items) / n, 4),
            "bleu4": round(sum(i["bleu4"] for i in items) / n, 4),
            "avg_latency": round(sum(i["latency_seconds"] for i in items) / n, 2),
        }

    vrs_results = [r for r in eval_results if r["benchmark"] == "VRSBench"]
    rsvqa_results = [r for r in eval_results if r["benchmark"] == "RSVQA-LR"]

    summary = {
        "overall": aggregate(eval_results),
        "vrsbench": aggregate(vrs_results),
        "rsvqa_lr": aggregate(rsvqa_results),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": "Base GeoChat-7B (Non-Fine-Tuned)",
    }

    # Save JSON results
    json_path = os.path.join(EVAL_DIR, "benchmark_results.json")
    with open(json_path, "w") as f:
        json.dump({"summary": summary, "results": eval_results}, f, indent=2)

    # Save Markdown report
    md_path = os.path.join(EVAL_DIR, "benchmark_report.md")
    with open(md_path, "w") as f:
        f.write("# SatQuery VQA Benchmark Report — Base Model Baseline\n\n")
        f.write("This report documents the baseline evaluation metrics of **Base GeoChat-7B** across public test subsets of **VRSBench** and **RSVQA-LR**.\n\n")
        f.write("## Summary Metrics\n\n")
        f.write("| Benchmark Split | Samples | Exact Match Acc | Soft Match Acc | BLEU-1 | BLEU-4 | Avg Latency |\n")
        f.write("| --- | --- | --- | --- | --- | --- | --- |\n")
        f.write(f"| **Overall Total** | {summary['overall']['count']} | {summary['overall']['exact_match_acc']*100:.1f}% | {summary['overall']['soft_match_acc']*100:.1f}% | {summary['overall']['bleu1']:.4f} | {summary['overall']['bleu4']:.4f} | {summary['overall']['avg_latency']}s |\n")
        f.write(f"| **VRSBench** | {summary['vrsbench']['count']} | {summary['vrsbench']['exact_match_acc']*100:.1f}% | {summary['vrsbench']['soft_match_acc']*100:.1f}% | {summary['vrsbench']['bleu1']:.4f} | {summary['vrsbench']['bleu4']:.4f} | {summary['vrsbench']['avg_latency']}s |\n")
        f.write(f"| **RSVQA-LR** | {summary['rsvqa_lr']['count']} | {summary['rsvqa_lr']['exact_match_acc']*100:.1f}% | {summary['rsvqa_lr']['soft_match_acc']*100:.1f}% | {summary['rsvqa_lr']['bleu1']:.4f} | {summary['rsvqa_lr']['bleu4']:.4f} | {summary['rsvqa_lr']['avg_latency']}s |\n\n")
        
        f.write("## Detailed Item Results\n\n")
        for item in eval_results:
            f.write(f"### Item `{item['id']}` ({item['benchmark']} — `{item['task_type']}`)\n")
            f.write(f"- **Question**: *{item['question']}*\n")
            f.write(f"- **Ground Truth**: `{item['reference_answers']}`\n")
            f.write(f"- **Base Model Prediction**: {item['model_prediction']}\n")
            f.write(f"- **Scores**: Exact Match={item['exact_match']}, Soft Match={item['soft_match']}, BLEU-1={item['bleu1']}\n\n")

    print("\n[4/4] Evaluation Finished Successfully!")
    print(f"      JSON Results saved to : {json_path}")
    print(f"      Markdown Report saved to: {md_path}")
    print("\n" + "=" * 70)
    print("BENCHMARK BASELINE SUMMARY")
    print("=" * 70)
    print(f"VRSBench Accuracy (Soft): {summary['vrsbench']['soft_match_acc']*100:.1f}% | BLEU-1: {summary['vrsbench']['bleu1']:.4f}")
    print(f"RSVQA-LR Accuracy (Soft): {summary['rsvqa_lr']['soft_match_acc']*100:.1f}% | BLEU-1: {summary['rsvqa_lr']['bleu1']:.4f}")
    print(f"Overall Accuracy  (Soft): {summary['overall']['soft_match_acc']*100:.1f}% | BLEU-1: {summary['overall']['bleu1']:.4f}")
    print("=" * 70)


if __name__ == "__main__":
    main()
