#!/usr/bin/env python3
"""
Generates synthetic paired Sentinel-1 SAR and Sentinel-2 Optical sample pairs
for testing the Optical-SAR Fusion Specialist.

IMPORTANT NOTICE / DISCLAIMER:
  This script generates synthetic arrays with fabricated pixel statistics (Gaussian noise distributions)
  to construct mock Sentinel-1 VV backscatter maps. It DOES NOT derive images from real Sentinel-1
  or satellite sources. The SAR pathway is validated ONLY against synthetic placeholder data pending
  real imagery integration (e.g., Sentinel-1 GRD / BigEarthNet-S1), and is NOT presented as a validated real-world working capability.

Sample 1: Coastal Harbor (Optical + Synthetic SAR VV backscatter)
Sample 2: Urban Area (Optical + Synthetic SAR VV backscatter)
Sample 3: Agricultural Field / Water Reservoir (Optical + Synthetic SAR VV backscatter)
"""

import os
import numpy as np
from PIL import Image

SAR_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "sar_samples")
os.makedirs(SAR_DIR, exist_ok=True)


def create_sar_optical_pair(sample_name: str, base_opt_path: str, water_region: tuple, builtup_region: tuple):
    """Generates a co-registered Sentinel-1 SAR image paired with an optical image."""
    opt_img = Image.open(base_opt_path).convert("RGB").resize((512, 512))
    w, h = opt_img.size

    # Create synthetic SAR backscatter map (Sentinel-1 VV linear backscatter amplitude 0..1)
    # Background (vegetation/moderate roughness): mean ~0.30
    sar_intensity = np.random.normal(loc=0.30, scale=0.05, size=(h, w)).astype(np.float32)

    # Water region: low backscatter (<0.10)
    w_x1, w_y1, w_x2, w_y2 = water_region
    if w_x2 > w_x1 and w_y2 > w_y1:
        sar_intensity[w_y1:w_y2, w_x1:w_x2] = np.random.normal(loc=0.04, scale=0.02, size=(w_y2 - w_y1, w_x2 - w_x1))

    # Built-up region: high backscatter (>0.60)
    b_x1, b_y1, b_x2, b_y2 = builtup_region
    if b_x2 > b_x1 and b_y2 > b_y1:
        sar_intensity[b_y1:b_y2, b_x1:b_x2] = np.random.normal(loc=0.75, scale=0.10, size=(b_y2 - b_y1, b_x2 - b_x1))

    sar_intensity = np.clip(sar_intensity, 0.0, 1.0)
    sar_uint8 = (sar_intensity * 255.0).astype(np.uint8)
    sar_img = Image.fromarray(sar_uint8, mode="L")

    opt_out = os.path.join(SAR_DIR, f"{sample_name}_optical.jpg")
    sar_out = os.path.join(SAR_DIR, f"{sample_name}_sar.png")

    opt_img.save(opt_out)
    sar_img.save(sar_out)

    print(f"Created pair: {sample_name}")
    print(f"  Optical: {opt_out}")
    print(f"  SAR    : {sar_out}")


def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    sample1_path = os.path.join(root, "ml", "geochat", "eval_samples", "sample_3_coastal.jpg")
    sample2_path = os.path.join(root, "ml", "geochat", "eval_samples", "sample_1_airport.jpg")
    sample3_path = os.path.join(root, "ml", "geochat", "eval_samples", "sample_2_agri.jpg")

    # Sample 1: Coastal Harbor (Water on left, coastal structures right)
    create_sar_optical_pair("coastal_harbor", sample1_path, (0, 0, 200, 512), (300, 100, 500, 400))

    # Sample 2: Urban Airport (Airport/buildings center-right)
    create_sar_optical_pair("urban_airport", sample2_path, (0, 0, 100, 100), (150, 150, 450, 450))

    # Sample 3: Agricultural Lake (Lake top right, fields surrounding)
    create_sar_optical_pair("agricultural_lake", sample3_path, (300, 0, 512, 200), (0, 0, 50, 50))


if __name__ == "__main__":
    main()
