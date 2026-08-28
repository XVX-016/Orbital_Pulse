#!/usr/bin/env python3
"""
Test script for Change-VQA specialist.

Runs real bi-temporal change query inference using GeoChat-7B 4-bit model
over real before/after satellite imagery from satquery-service/data/deforestation/.

Representative CDVQA Query:
  "What changed between these two dates, and where did the change occur?"
"""

import os
import sys
import time
from PIL import Image

# Ensure satquery-service path is accessible
SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
if SERVICE_DIR not in sys.path:
    sys.path.insert(0, SERVICE_DIR)

from geochat_engine import init_geochat_model
from specialists.change_vqa import run_change_vqa


def main():
    print("=" * 70)
    print("SatQuery-Service: Change-VQA Specialist Test")
    print("=" * 70)

    # 1. Initialize GeoChat Engine
    print("\n[1/3] Initializing GeoChat-7B model ...")
    success = init_geochat_model()
    if not success:
        print("[ERROR] GeoChat engine initialization failed.")
        sys.exit(1)

    # 2. Load Bi-temporal Satellite Images
    img_before_path = os.path.join(SERVICE_DIR, "data", "deforestation", "before.tif")
    img_after_path = os.path.join(SERVICE_DIR, "data", "deforestation", "after.tif")

    print("\n[2/3] Loading bi-temporal satellite image pair:")
    print(f"      Image 1 (Before): {img_before_path}")
    print(f"      Image 2 (After) : {img_after_path}")

    # 3. Test representative CDVQA query
    query = "What changed between these two dates, and where did the change occur?"
    print(f"\n[3/3] Executing Change-VQA Query: '{query}'")

    t0 = time.time()
    result = run_change_vqa(images=[img_before_path, img_after_path], query=query)
    elapsed = time.time() - t0

    print("\n" + "=" * 70)
    print("CHANGE-VQA SPECIALIST RESULT")
    print("=" * 70)
    print(f"Answer         : {result['answer']}")
    print(f"Confidence     : {result['confidence']}")
    print(f"Visual Evidence: {result['visual_evidence']}")
    print(f"Details        : {result['details']}")
    print(f"Total Test Time: {elapsed:.2f}s")
    print("=" * 70)


if __name__ == "__main__":
    main()
