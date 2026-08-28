#!/usr/bin/env python3
"""
Prepares self-authored sanity-check QA items for pipeline smoke testing.

IMPORTANT DISCLAIMER:
  These questions are SELF-AUTHORED using project sample images from ml/geochat/eval_samples/.
  They are NOT sourced from any published benchmark dataset. They must NOT be cited or
  presented as VRSBench, RSVQA-LR, or any other published benchmark results.

  For real benchmark evaluation, use download_real_benchmarks.py to obtain authentic
  test splits from:
    - VRSBench: https://github.com/lx709/VRSBench (HF: xiang709/VRSBench)
    - RSVQA-LR: https://doi.org/10.5281/zenodo.6344333

Places sample imagery and structured QA items in satquery-service/eval/benchmark_data/.
"""

import os
import json
import shutil
from PIL import Image

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(EVAL_DIR, "benchmark_data")
os.makedirs(DATA_DIR, exist_ok=True)

ROOT_DIR = os.path.abspath(os.path.join(EVAL_DIR, "..", ".."))

# Source sample images from eval_samples and public data
SAMPLE_IMAGES = {
    "airport": os.path.join(ROOT_DIR, "ml", "geochat", "eval_samples", "sample_1_airport.jpg"),
    "port": os.path.join(ROOT_DIR, "ml", "geochat", "eval_samples", "sample_1_port.jpg"),
    "agri": os.path.join(ROOT_DIR, "ml", "geochat", "eval_samples", "sample_2_agri.jpg"),
    "coastal": os.path.join(ROOT_DIR, "ml", "geochat", "eval_samples", "sample_3_coastal.jpg"),
}


def prepare_data():
    image_paths = {}

    for name, src in SAMPLE_IMAGES.items():
        dst = os.path.join(DATA_DIR, f"{name}.jpg")
        if os.path.exists(src):
            shutil.copy(src, dst)
            image_paths[name] = dst
            print(f"Copied image {name} -> {dst}")

    # 1. Self-authored VQA-style sanity-check questions (NOT from VRSBench)
    sanitycheck_vqa_items = [
        {
            "id": "sanity_vqa_001",
            "benchmark": "SanityCheck-VQA",
            "task_type": "presence",
            "image": image_paths.get("airport"),
            "question": "Is there an airport runway present in this satellite image?",
            "answers": ["yes", "Yes"],
            "key_terms": ["yes", "runway", "airport"],
        },
        {
            "id": "sanity_vqa_002",
            "benchmark": "SanityCheck-VQA",
            "task_type": "land_cover",
            "image": image_paths.get("agri"),
            "question": "What is the primary land cover classification of this area?",
            "answers": ["agricultural", "farmland", "fields"],
            "key_terms": ["agriculture", "agricultural", "farmland", "crop", "field"],
        },
        {
            "id": "sanity_vqa_003",
            "benchmark": "SanityCheck-VQA",
            "task_type": "identification",
            "image": image_paths.get("port"),
            "question": "What type of facility is located along the shoreline?",
            "answers": ["port", "harbor", "maritime port"],
            "key_terms": ["port", "harbor", "dock", "pier", "maritime"],
        },
        {
            "id": "sanity_vqa_004",
            "benchmark": "SanityCheck-VQA",
            "task_type": "spatial",
            "image": image_paths.get("coastal"),
            "question": "Where are the rocky hills located relative to the water?",
            "answers": ["adjacent to water", "along the coastline"],
            "key_terms": ["coast", "water", "hill", "adjacent", "along"],
        },
        {
            "id": "sanity_vqa_005",
            "benchmark": "SanityCheck-VQA",
            "task_type": "presence",
            "image": image_paths.get("agri"),
            "question": "Are there industrial dock cranes present in this rural scene?",
            "answers": ["no", "No"],
            "key_terms": ["no", "not present", "none"],
        },
    ]

    # 2. Self-authored RSVQA-style sanity-check questions (NOT from RSVQA-LR)
    sanitycheck_rsvqa_items = [
        {
            "id": "sanity_rsvqa_001",
            "benchmark": "SanityCheck-RSVQA",
            "task_type": "presence",
            "image": image_paths.get("airport"),
            "question": "Are there buildings present in this image?",
            "answers": ["yes"],
            "key_terms": ["yes", "building", "structure"],
        },
        {
            "id": "sanity_rsvqa_002",
            "benchmark": "SanityCheck-RSVQA",
            "task_type": "count",
            "image": image_paths.get("airport"),
            "question": "How many main bridge structures are visible in the scene?",
            "answers": ["2", "two"],
            "key_terms": ["2", "two"],
        },
        {
            "id": "sanity_rsvqa_003",
            "benchmark": "SanityCheck-RSVQA",
            "task_type": "land_cover",
            "image": image_paths.get("coastal"),
            "question": "What is the dominant land cover category?",
            "answers": ["coastal", "natural vegetation", "water"],
            "key_terms": ["coastal", "grass", "water", "vegetation", "mountain"],
        },
        {
            "id": "sanity_rsvqa_004",
            "benchmark": "SanityCheck-RSVQA",
            "task_type": "comparison",
            "image": image_paths.get("agri"),
            "question": "Are there more vegetated fields than urban buildings?",
            "answers": ["yes"],
            "key_terms": ["yes", "field", "vegetated"],
        },
        {
            "id": "sanity_rsvqa_005",
            "benchmark": "SanityCheck-RSVQA",
            "task_type": "presence",
            "image": image_paths.get("port"),
            "question": "Is water present in this satellite image?",
            "answers": ["yes"],
            "key_terms": ["yes", "water"],
        },
    ]

    vqa_json_path = os.path.join(DATA_DIR, "sanitycheck_vqa.json")
    with open(vqa_json_path, "w") as f:
        json.dump(sanitycheck_vqa_items, f, indent=2)

    rsvqa_json_path = os.path.join(DATA_DIR, "sanitycheck_rsvqa.json")
    with open(rsvqa_json_path, "w") as f:
        json.dump(sanitycheck_rsvqa_items, f, indent=2)

    print("\nSanity-check QA items prepared successfully!")
    print(f"  VQA-style sanity checks : {vqa_json_path} ({len(sanitycheck_vqa_items)} items)")
    print(f"  RSVQA-style sanity checks: {rsvqa_json_path} ({len(sanitycheck_rsvqa_items)} items)")
    print("\n  NOTE: These are self-authored questions, NOT published benchmark data.")


if __name__ == "__main__":
    prepare_data()
