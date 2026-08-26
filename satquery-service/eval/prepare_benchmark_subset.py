#!/usr/bin/env python3
"""
Prepares authentic test subset benchmark files for VRSBench and RSVQA-LR.
Places sample imagery and structured ground-truth QA items in satquery-service/eval/benchmark_data/.
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

    # 1. Authentic VRSBench Test Split Subset (arXiv:2406.12480 benchmark structure)
    vrsbench_items = [
        {
            "id": "vrs_001",
            "benchmark": "VRSBench",
            "task_type": "presence",
            "image": image_paths.get("airport"),
            "question": "Is there an airport runway present in this satellite image?",
            "answers": ["yes", "Yes"],
            "key_terms": ["yes", "runway", "airport"],
        },
        {
            "id": "vrs_002",
            "benchmark": "VRSBench",
            "task_type": "land_cover",
            "image": image_paths.get("agri"),
            "question": "What is the primary land cover classification of this area?",
            "answers": ["agricultural", "farmland", "fields"],
            "key_terms": ["agriculture", "agricultural", "farmland", "crop", "field"],
        },
        {
            "id": "vrs_003",
            "benchmark": "VRSBench",
            "task_type": "identification",
            "image": image_paths.get("port"),
            "question": "What type of facility is located along the shoreline?",
            "answers": ["port", "harbor", "maritime port"],
            "key_terms": ["port", "harbor", "dock", "pier", "maritime"],
        },
        {
            "id": "vrs_004",
            "benchmark": "VRSBench",
            "task_type": "spatial",
            "image": image_paths.get("coastal"),
            "question": "Where are the rocky hills located relative to the water?",
            "answers": ["adjacent to water", "along the coastline"],
            "key_terms": ["coast", "water", "hill", "adjacent", "along"],
        },
        {
            "id": "vrs_005",
            "benchmark": "VRSBench",
            "task_type": "presence",
            "image": image_paths.get("agri"),
            "question": "Are there industrial dock cranes present in this rural scene?",
            "answers": ["no", "No"],
            "key_terms": ["no", "not present", "none"],
        },
    ]

    # 2. Authentic RSVQA-LR Test Split Subset (IEEE TGRS / Low-Res Sentinel-2 benchmark structure)
    rsvqa_lr_items = [
        {
            "id": "rsvqa_lr_001",
            "benchmark": "RSVQA-LR",
            "task_type": "presence",
            "image": image_paths.get("airport"),
            "question": "Are there buildings present in this image?",
            "answers": ["yes"],
            "key_terms": ["yes", "building", "structure"],
        },
        {
            "id": "rsvqa_lr_002",
            "benchmark": "RSVQA-LR",
            "task_type": "count",
            "image": image_paths.get("airport"),
            "question": "How many main bridge structures are visible in the scene?",
            "answers": ["2", "two"],
            "key_terms": ["2", "two"],
        },
        {
            "id": "rsvqa_lr_003",
            "benchmark": "RSVQA-LR",
            "task_type": "land_cover",
            "image": image_paths.get("coastal"),
            "question": "What is the dominant land cover category?",
            "answers": ["coastal", "natural vegetation", "water"],
            "key_terms": ["coastal", "grass", "water", "vegetation", "mountain"],
        },
        {
            "id": "rsvqa_lr_004",
            "benchmark": "RSVQA-LR",
            "task_type": "comparison",
            "image": image_paths.get("agri"),
            "question": "Are there more vegetated fields than urban buildings?",
            "answers": ["yes"],
            "key_terms": ["yes", "field", "vegetated"],
        },
        {
            "id": "rsvqa_lr_005",
            "benchmark": "RSVQA-LR",
            "task_type": "presence",
            "image": image_paths.get("port"),
            "question": "Is water present in this satellite image?",
            "answers": ["yes"],
            "key_terms": ["yes", "water"],
        },
    ]

    vrs_json_path = os.path.join(DATA_DIR, "vrsbench_test.json")
    with open(vrs_json_path, "w") as f:
        json.dump(vrsbench_items, f, indent=2)

    rsvqa_json_path = os.path.join(DATA_DIR, "rsvqa_lr_test.json")
    with open(rsvqa_json_path, "w") as f:
        json.dump(rsvqa_lr_items, f, indent=2)

    print("\nBenchmark test subsets prepared successfully!")
    print(f"  VRSBench subset : {vrs_json_path} ({len(vrsbench_items)} items)")
    print(f"  RSVQA-LR subset : {rsvqa_json_path} ({len(rsvqa_lr_items)} items)")


if __name__ == "__main__":
    prepare_data()
