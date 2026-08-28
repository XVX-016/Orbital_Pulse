#!/usr/bin/env python3
"""
SatQuery VQA Benchmark & Sanity-Check Evaluation Harness.

Executes evaluation against configured dataset splits (self-authored sanity checks or authentic VRSBench/RSVQA-LR test splits),
runs inference through the core SatQuery /api/analyze controller pipeline,
and computes Accuracy (Exact Match & Soft Keyword Match), BLEU-1, and BLEU-4 scores.

Usage:
    python satquery-service/eval/run_benchmark.py
"""

import os
import sys
import json
import time
import math
import argparse
import re
from collections import Counter
from typing import Dict, List, Any
from PIL import Image

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(EVAL_DIR, "benchmark_data")
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

    def get_ngrams(tokens, n_val):
        return [tuple(tokens[i : i + n_val]) for i in range(len(tokens) - n_val + 1)]

    ref_ngrams = Counter(get_ngrams(ref_tokens, n))
    hyp_ngrams = Counter(get_ngrams(hyp_tokens, n))

    if not hyp_ngrams:
        return 0.0

    clipped_matches = sum(min(count, ref_ngrams[ngram]) for ngram, count in hyp_ngrams.items())
    precision = clipped_matches / sum(hyp_ngrams.values())

    ref_len = len(ref_tokens)
    hyp_len = len(hyp_tokens)

    if hyp_len > ref_len:
        bp = 1.0
    elif hyp_len == 0:
        bp = 0.0
    else:
        bp = math.exp(1.0 - ref_len / hyp_len)

    return round(bp * precision, 4)


def compute_soft_match(prediction: str, answers: List[str]) -> float:
    """Match a contiguous whole-token answer alias, excluding noisy keyword metadata."""
    prediction_tokens = re.findall(r"\w+", prediction.casefold())
    if not prediction_tokens:
        return 0.0

    for answer in answers:
        answer_tokens = re.findall(r"\w+", answer.casefold())
        if answer_tokens and any(
            prediction_tokens[index : index + len(answer_tokens)] == answer_tokens
            for index in range(len(prediction_tokens) - len(answer_tokens) + 1)
        ):
            return 1.0
    return 0.0


def evaluate_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Runs single benchmark item through SatQuery route_and_execute controller."""
    img_path = item["image"]
    query = item["question"]

    if os.path.exists(img_path):
        img = Image.open(img_path).convert("RGB")
    else:
        # Fallback to available sample image for benchmarking when full image zips are omitted
        fallback_path = os.path.join(DATA_DIR, "airport.jpg")
        if os.path.exists(fallback_path):
            img = Image.open(fallback_path).convert("RGB")
        else:
            img = Image.new("RGB", (512, 512), color=(128, 128, 128))

    t0 = time.time()
    res = route_and_execute(images=[img], query=query)
    elapsed = time.time() - t0

    prediction = res.get("answer", "").strip()
    pred_lower = prediction.lower()

    answers = [a.lower() for a in item["answers"]]
    key_terms = [k.lower() for k in item["key_terms"]]

    # 1. Exact Match
    exact_match = 1.0 if any(pred_lower == a for a in answers) else 0.0

    # 2. Soft answer-alias match using whole tokens, not noisy key-term metadata
    soft_match = compute_soft_match(prediction, item["answers"])

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
    parser = argparse.ArgumentParser(description="Run the SatQuery VQA benchmark harness.")
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="Maximum number of items to evaluate from each benchmark dataset.",
    )
    parser.add_argument(
        "--dataset",
        choices=("auto", "real", "sanity"),
        default="auto",
        help="Dataset family to evaluate (default: auto-detect real files).",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("SatQuery AI Service — VQA Evaluation Harness")
    print("=" * 70)

    # 1. Initialize GeoChat Base Model Engine
    print("\n[1/4] Initializing base GeoChat-7B model ...")
    success = init_geochat_model()
    if not success:
        print("[ERROR] GeoChat engine initialization failed.")
        sys.exit(1)

    # 2. Load Evaluation Items
    print("\n[2/4] Loading evaluation test subsets ...")
    data_dir = os.path.join(EVAL_DIR, "benchmark_data")

    # Detect if authentic benchmark files or self-authored sanity check files exist
    real_vrs_file = os.path.join(data_dir, "vrsbench_test_real.json")
    real_rsvqa_file = os.path.join(data_dir, "rsvqa_lr_test_real.json")

    sanity_vqa_file = os.path.join(data_dir, "sanitycheck_vqa.json")
    sanity_rsvqa_file = os.path.join(data_dir, "sanitycheck_rsvqa.json")

    real_files_available = os.path.exists(real_vrs_file) and os.path.exists(real_rsvqa_file)
    if args.dataset == "real" and not real_files_available:
        parser.error("real benchmark files were not found")
    is_real_benchmark = args.dataset == "real" or (args.dataset == "auto" and real_files_available)

    if is_real_benchmark:
        print("      Found authentic VRSBench & RSVQA-LR dataset files.")
        vqa_file = real_vrs_file
        rsvqa_file = real_rsvqa_file
        dataset_label = "Authentic VRSBench & RSVQA-LR Test Splits"
    else:
        print("      Using Self-Authored Sanity-Check Question Sets.")
        vqa_file = sanity_vqa_file
        rsvqa_file = sanity_rsvqa_file
        dataset_label = "Self-Authored Sanity-Check Questions (NOT Official VRSBench/RSVQA-LR)"

    with open(vqa_file, "r") as f:
        vqa_items = json.load(f)
    with open(rsvqa_file, "r") as f:
        rsvqa_items = json.load(f)

    if args.max_items is not None:
        if args.max_items < 1:
            parser.error("--max-items must be at least 1")
        vqa_items = vqa_items[:args.max_items]
        rsvqa_items = rsvqa_items[:args.max_items]

    all_items = vqa_items + rsvqa_items
    print(f"      Loaded {len(vqa_items)} items from {os.path.basename(vqa_file)} and {len(rsvqa_items)} items from {os.path.basename(rsvqa_file)}.")

    # 3. Execute Inference & Scoring
    print(f"\n[3/4] Running evaluation across {len(all_items)} samples ({dataset_label}) ...")

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

    b1_name = vqa_items[0]["benchmark"] if vqa_items else "Group_1"
    b2_name = rsvqa_items[0]["benchmark"] if rsvqa_items else "Group_2"

    group1_results = [r for r in eval_results if r["benchmark"] == b1_name]
    group2_results = [r for r in eval_results if r["benchmark"] == b2_name]

    summary = {
        "dataset_type": "Real Benchmarks" if is_real_benchmark else "Self-Authored Sanity Checks",
        "dataset_label": dataset_label,
        "overall": aggregate(eval_results),
        b1_name.lower(): aggregate(group1_results),
        b2_name.lower(): aggregate(group2_results),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": "Base GeoChat-7B (Non-Fine-Tuned)",
    }

    # Save JSON results
    json_path = os.path.join(EVAL_DIR, "benchmark_results.json")
    with open(json_path, "w") as f:
        json.dump({"summary": summary, "results": eval_results}, f, indent=2)

    # Save Markdown report
    md_path = os.path.join(EVAL_DIR, "benchmark_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        if is_real_benchmark:
            f.write("# SatQuery VQA Benchmark Report — Base Model Baseline\n\n")
            f.write(f"This report documents baseline evaluation metrics of **Base GeoChat-7B** across authentic public test splits of **VRSBench** and **RSVQA-LR**.\n\n")
        else:
            f.write("# SatQuery VQA Evaluation Report — Self-Authored Sanity-Check Baseline\n\n")
            f.write("> [!IMPORTANT]\n")
            f.write("> **DISCLAIMER**: The evaluation below uses **self-authored sanity-check questions** generated against local sample imagery (`ml/geochat/eval_samples/`). These results are strictly internal sanity checks and MUST NOT be cited or presented as official VRSBench or RSVQA-LR benchmark scores.\n\n")

        f.write("## Summary Metrics\n\n")
        f.write("| Benchmark / Subset | Samples | Exact Match Acc | Soft Match Acc | BLEU-1 | BLEU-4 | Avg Latency |\n")
        f.write("| --- | --- | --- | --- | --- | --- | --- |\n")
        f.write(f"| **Overall Total** | {summary['overall']['count']} | {summary['overall']['exact_match_acc']*100:.1f}% | {summary['overall']['soft_match_acc']*100:.1f}% | {summary['overall']['bleu1']:.4f} | {summary['overall']['bleu4']:.4f} | {summary['overall']['avg_latency']}s |\n")
        f.write(f"| **{b1_name}** | {summary[b1_name.lower()]['count']} | {summary[b1_name.lower()]['exact_match_acc']*100:.1f}% | {summary[b1_name.lower()]['soft_match_acc']*100:.1f}% | {summary[b1_name.lower()]['bleu1']:.4f} | {summary[b1_name.lower()]['bleu4']:.4f} | {summary[b1_name.lower()]['avg_latency']}s |\n")
        f.write(f"| **{b2_name}** | {summary[b2_name.lower()]['count']} | {summary[b2_name.lower()]['exact_match_acc']*100:.1f}% | {summary[b2_name.lower()]['soft_match_acc']*100:.1f}% | {summary[b2_name.lower()]['bleu1']:.4f} | {summary[b2_name.lower()]['bleu4']:.4f} | {summary[b2_name.lower()]['avg_latency']}s |\n\n")
        
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
    print("EVALUATION BASELINE SUMMARY")
    print("=" * 70)
    print(f"Dataset Type     : {dataset_label}")
    print(f"{b1_name} Accuracy (Soft): {summary[b1_name.lower()]['soft_match_acc']*100:.1f}% | BLEU-1: {summary[b1_name.lower()]['bleu1']:.4f}")
    print(f"{b2_name} Accuracy (Soft): {summary[b2_name.lower()]['soft_match_acc']*100:.1f}% | BLEU-1: {summary[b2_name.lower()]['bleu1']:.4f}")
    print(f"Overall Accuracy  (Soft): {summary['overall']['soft_match_acc']*100:.1f}% | BLEU-1: {summary['overall']['bleu1']:.4f}")
    print("=" * 70)


if __name__ == "__main__":
    main()
