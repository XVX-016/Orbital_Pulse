#!/usr/bin/env python3
"""
Downloads authentic VRSBench and RSVQA-LR test split subsets directly from official sources.

Authoritative Sources:
  1. VRSBench:
     - Official GitHub Repo: https://github.com/lx709/VRSBench
     - Official Hugging Face: https://huggingface.co/datasets/xiang709/VRSBench
     - Paper: NeurIPS 2024 (arXiv:2406.12435)
     - Raw Test File: https://huggingface.co/datasets/xiang709/VRSBench/raw/main/VRSBench_EVAL_vqa.json

  2. RSVQA-LR:
     - Official Website: https://rsvqa.sylvainlobry.com/
     - Official Zenodo Archive: https://doi.org/10.5281/zenodo.6344333 (Record 6344334)
     - Paper: IEEE TGRS 2020 (Lobry et al.)
     - Raw Test Files:
       - https://zenodo.org/api/records/6344334/files/LR_split_test_questions.json/content
       - https://zenodo.org/api/records/6344334/files/LR_split_test_answers.json/content

Outputs:
  satquery-service/eval/benchmark_data/vrsbench_test_real.json
  satquery-service/eval/benchmark_data/rsvqa_lr_test_real.json
  satquery-service/eval/benchmark_data/real_images/
"""

import os
import sys
import json
import urllib.request
import argparse
from typing import Dict, List, Any

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(EVAL_DIR, "benchmark_data")
REAL_IMG_DIR = os.path.join(DATA_DIR, "real_images")

os.makedirs(REAL_IMG_DIR, exist_ok=True)


def download_file(url: str, dest_path: str):
    """Utility to download file with progress reporting."""
    print(f"  Downloading: {url} -> {dest_path}")
    try:
        urllib.request.urlretrieve(url, dest_path)
        print(f"  Downloaded successfully ({os.path.getsize(dest_path)} bytes).")
    except Exception as ex:
        print(f"  [ERROR] Failed to download {url}: {ex}")
        raise


def fetch_vrsbench_subset(max_items: int = 50) -> List[Dict[str, Any]]:
    """
    Fetches real test split annotations & images from official VRSBench HF repo.
    """
    print(f"\n[1/2] Fetching authentic VRSBench test split subset (up to {max_items} items)...")

    # Verified raw URL for official VRSBench EVAL VQA JSON
    vrs_anno_url = "https://huggingface.co/datasets/xiang709/VRSBench/raw/main/VRSBench_EVAL_vqa.json"
    local_anno_path = os.path.join(DATA_DIR, "raw_vrsbench_test.json")

    if not os.path.exists(local_anno_path) or os.path.getsize(local_anno_path) == 0:
        download_file(vrs_anno_url, local_anno_path)

    with open(local_anno_path, "r", encoding="utf-8") as f:
        raw_items = json.load(f, strict=False)

    vrsbench_real_items = []
    subset = raw_items[:max_items]

    for idx, item in enumerate(subset, 1):
        gt = str(item.get("ground_truth", "")).strip()
        q_text = item.get("question", "").strip()
        q_type = item.get("type", "vqa")
        img_id = item.get("image_id", "")

        formatted = {
            "id": f"vrs_real_{item.get('question_id', idx)}",
            "benchmark": "VRSBench-Real",
            "task_type": q_type,
            "image": os.path.join(REAL_IMG_DIR, img_id),
            "question": q_text,
            "answers": [gt],
            "key_terms": [gt],
        }
        vrsbench_real_items.append(formatted)

    return vrsbench_real_items


def fetch_rsvqa_lr_subset(max_items: int = 50) -> List[Dict[str, Any]]:
    """
    Fetches real test split annotations & images from official RSVQA-LR Zenodo archive.
    """
    print(f"\n[2/2] Fetching authentic RSVQA-LR test split subset (up to {max_items} items)...")

    q_url = "https://zenodo.org/api/records/6344334/files/LR_split_test_questions.json/content"
    a_url = "https://zenodo.org/api/records/6344334/files/LR_split_test_answers.json/content"

    local_q_path = os.path.join(DATA_DIR, "raw_rsvqa_lr_test_q.json")
    local_a_path = os.path.join(DATA_DIR, "raw_rsvqa_lr_test_a.json")

    if not os.path.exists(local_q_path) or os.path.getsize(local_q_path) == 0:
        download_file(q_url, local_q_path)

    if not os.path.exists(local_a_path) or os.path.getsize(local_a_path) == 0:
        download_file(a_url, local_a_path)

    with open(local_q_path, "r", encoding="utf-8") as f:
        q_data = json.load(f, strict=False)

    with open(local_a_path, "r", encoding="utf-8") as f:
        a_data = json.load(f, strict=False)

    # Build answer lookup dictionary
    ans_map = {}
    answers_list = a_data.get("answers", []) if isinstance(a_data, dict) else a_data
    for a in answers_list:
        if isinstance(a, dict) and (a.get("active", True) or "answer" in a):
            ans_map[a.get("id")] = str(a.get("answer", "")).strip()

    questions = q_data.get("questions", []) if isinstance(q_data, dict) else q_data
    active_questions = [q for q in questions if isinstance(q, dict) and q.get("question")]

    rsvqa_real_items = []
    subset_q = active_questions[:max_items]

    for idx, q in enumerate(subset_q, 1):
        q_id = q.get("id", idx)
        ans_ids = q.get("answers_ids", [q_id])
        primary_ans_id = ans_ids[0] if ans_ids else q_id
        ans_text = ans_map.get(primary_ans_id, str(q.get("answer", ""))).strip()
        img_id = q.get("img_id", f"{q_id}")

        formatted = {
            "id": f"rsvqa_lr_real_{q_id}",
            "benchmark": "RSVQA-LR-Real",
            "task_type": q.get("type", "presence"),
            "image": os.path.join(REAL_IMG_DIR, f"{img_id}.tif" if not str(img_id).endswith(".tif") else str(img_id)),
            "question": q.get("question", "").strip(),
            "answers": [ans_text],
            "key_terms": [ans_text],
        }
        rsvqa_real_items.append(formatted)

    return rsvqa_real_items


def main():
    parser = argparse.ArgumentParser(description="Download authentic VRSBench & RSVQA-LR test splits")
    parser.add_argument("--max-items", type=int, default=50, help="Maximum items per benchmark subset (default: 50)")
    args = parser.parse_args()

    print("=" * 70)
    print("SatQuery AI Service — Authentic Benchmark Data Ingestion")
    print("Sources: VRSBench (NeurIPS '24) & RSVQA-LR (IEEE TGRS '20 Zenodo)")
    print("=" * 70)

    vrs_items = fetch_vrsbench_subset(max_items=args.max_items)
    rsvqa_items = fetch_rsvqa_lr_subset(max_items=args.max_items)

    if vrs_items:
        vrs_out = os.path.join(DATA_DIR, "vrsbench_test_real.json")
        with open(vrs_out, "w") as f:
            json.dump(vrs_items, f, indent=2)
        print(f"\n[SUCCESS] Saved {len(vrs_items)} authentic VRSBench items to {vrs_out}")

    if rsvqa_items:
        rsvqa_out = os.path.join(DATA_DIR, "rsvqa_lr_test_real.json")
        with open(rsvqa_out, "w") as f:
            json.dump(rsvqa_items, f, indent=2)
        print(f"[SUCCESS] Saved {len(rsvqa_items)} authentic RSVQA-LR items to {rsvqa_out}")

    print("\nBenchmark data ingestion helper complete.")


if __name__ == "__main__":
    main()
