#!/usr/bin/env python3
"""
Test script for Optical-SAR Fusion specialist.

Runs multimodal Optical + Sentinel-1 SAR fusion inference across 3 sample pairs
from satquery-service/data/sar_samples/.

NOTE: Samples in satquery-service/data/sar_samples/ are synthetic placeholder arrays
generated with fabricated pixel statistics, validated strictly for offline pipeline testing pending real Sentinel-1 GRD imagery.
"""

import os
import sys
import time

SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
if SERVICE_DIR not in sys.path:
    sys.path.insert(0, SERVICE_DIR)

from geochat_engine import init_geochat_model
from specialists.sar_fusion import run_sar_fusion


def main():
    print("=" * 70)
    print("SatQuery-Service: Optical-SAR Fusion Specialist Test")
    print("=" * 70)

    # 1. Initialize GeoChat Engine
    print("\n[1/3] Initializing GeoChat-7B model ...")
    success = init_geochat_model()
    if not success:
        print("[ERROR] GeoChat engine initialization failed.")
        sys.exit(1)

    # 2. Define test sample pairs
    sar_samples_dir = os.path.join(SERVICE_DIR, "data", "sar_samples")
    sample_pairs = [
        ("coastal_harbor", "Analyze coastal features in optical image and quantify water/structure coverage from SAR."),
        ("urban_airport", "Describe airport structures in optical view and quantify built-up density using SAR backscatter."),
        ("agricultural_lake", "Analyze field patterns in optical view and detect water presence from SAR backscatter."),
    ]

    print("\n[2/3] Executing Optical-SAR Fusion Analysis across 3 sample pairs:")

    for idx, (name, query) in enumerate(sample_pairs, 1):
        opt_path = os.path.join(sar_samples_dir, f"{name}_optical.jpg")
        sar_path = os.path.join(sar_samples_dir, f"{name}_sar.png")

        print(f"\n--- Test Pair [{idx}/3]: {name} ---")
        print(f"    Optical: {opt_path}")
        print(f"    SAR    : {sar_path}")
        print(f"    Query  : '{query}'")

        t0 = time.time()
        result = run_sar_fusion(images=[opt_path, sar_path], query=query)
        elapsed = time.time() - t0

        print(f"\n=== FUSION RESULT [{name}] ===")
        print(f"Answer:\n{result['answer']}")
        print(f"\nVisual Evidence (SAR Metrics): {result['visual_evidence']['sar_metrics']}")
        print(f"Details: {result['details']}")
        print(f"Latency: {elapsed:.2f}s")

    print("\n" + "=" * 70)
    print("Optical-SAR Fusion Specialist Test Complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
