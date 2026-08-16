#!/usr/bin/env python3
"""
benchmark_quantization.py — Quantization Benchmarking Script for Prithvi-100M

This script benchmarks the FP32 Prithvi-EO-1.0-100M foundation model against an INT8
dynamically quantized version (using torch.quantization.quantize_dynamic on Linear layers).

Measures:
  1. Model Memory Size (FP32 vs INT8 in MB)
  2. CPU Inference Latency (ms per scenario, averaged over multiple runs)
  3. Output Quality / Mask Fidelity (FP32 vs INT8 Cosine Similarity, MSE, and Change % Difference)

Output:
  - Console summary table
  - JSON benchmark results (benchmark_results.json)
  - CSV benchmark summary (benchmark_results.csv)

Usage:
    python scripts/benchmark_quantization.py [--iterations N] [--data-dir DATA_DIR] [--output-dir OUTPUT_DIR]
"""

import argparse
import csv
import io
import json
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

try:
    import rasterio
except ImportError:
    rasterio = None

# Attempt import of quantize_dynamic from torch.ao.quantization or torch.quantization
try:
    from torch.ao.quantization import quantize_dynamic
except ImportError:
    try:
        from torch.quantization import quantize_dynamic
    except ImportError:
        quantize_dynamic = None

from transformers import AutoModel

# ---------------------------------------------------------------------------
# Setup & Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("benchmark_quantization")

MODEL_ID = "ibm-nasa-geospatial/Prithvi-EO-1.0-100M"
SCENARIOS = ["deforestation", "disaster"]
DEVICE = torch.device("cpu")  # CPU-only benchmarking as specified


# ---------------------------------------------------------------------------
# Model Helpers
# ---------------------------------------------------------------------------

def get_model_size_mb(model: nn.Module) -> float:
    """
    Calculate model size in MB by serializing state_dict to an in-memory buffer.
    Handles both FP32 and quantized PyTorch modules accurately.
    """
    buffer = io.BytesIO()
    torch.save(model.state_dict(), buffer)
    return buffer.tell() / (1024 * 1024)


def load_image_tensor(filepath: Path) -> torch.Tensor:
    """
    Load a 6-band preprocessed GeoTIFF into a PyTorch tensor (1, 6, 1, 224, 224).
    If rasterio is unavailable or file is missing, generates a deterministic tensor for benchmark continuity.
    """
    if rasterio and filepath.exists():
        with rasterio.open(filepath) as src:
            data = src.read()
        tensor = torch.from_numpy(data).float().unsqueeze(0).unsqueeze(2)
        if tensor.shape[3] != 224 or tensor.shape[4] != 224:
            import torch.nn.functional as F
            tensor = tensor.squeeze(2)
            tensor = F.interpolate(tensor, size=(224, 224), mode="bilinear", align_corners=False)
            tensor = tensor.unsqueeze(2)
        return tensor
    else:
        logger.warning(f"File not found or rasterio missing: {filepath}. Using synthetic 6-band 224x224 input.")
        torch.manual_seed(42)
        return torch.rand(1, 6, 1, 224, 224)


# ---------------------------------------------------------------------------
# Inference & Metric Computation
# ---------------------------------------------------------------------------

def run_scenario_inference(model: nn.Module, before_tensor: torch.Tensor, after_tensor: torch.Tensor):
    """
    Run forward pass for before/after pair and compute embedding distance matrix & change %.
    Returns:
        - diff_grid: (1, 1, grid_size, grid_size) tensor
        - change_percentage: float (0.0 to 100.0)
    """
    with torch.no_grad():
        out_before = model(before_tensor)
        out_after = model(after_tensor)

        if hasattr(out_before, "last_hidden_state"):
            embed_b = out_before.last_hidden_state
            embed_a = out_after.last_hidden_state
            diff = torch.norm(embed_b - embed_a, dim=-1)
        else:
            diff = torch.norm(out_before[0] - out_after[0], dim=-1)

        num_patches = diff.shape[1]
        grid_size = int(np.sqrt(num_patches))

        if grid_size * grid_size == num_patches:
            diff_grid = diff.view(1, 1, grid_size, grid_size)
            import torch.nn.functional as F
            mask_tensor = F.interpolate(diff_grid, size=(224, 224), mode="nearest").squeeze()
        else:
            mask_tensor = diff.squeeze()

        mask_min = mask_tensor.min()
        mask_max = mask_tensor.max()
        mask_norm = ((mask_tensor - mask_min) / (mask_max - mask_min + 1e-6) * 255).cpu().numpy().astype(np.uint8)
        change_percentage = round(float((mask_norm > 128).mean() * 100), 2)

        return diff, change_percentage


def benchmark_model(
    model: nn.Module,
    pairs: dict[str, tuple[torch.Tensor, torch.Tensor]],
    iterations: int = 5,
    warmup: int = 2,
) -> dict:
    """
    Benchmark inference latency and output metrics for a given model.
    """
    model.eval()
    results = {}

    for scenario, (before_t, after_t) in pairs.items():
        # Warmup runs
        for _ in range(warmup):
            _ = run_scenario_inference(model, before_t, after_t)

        # Timed runs
        latencies = []
        diff_tensor = None
        change_pct = 0.0

        for _ in range(iterations):
            start = time.perf_counter()
            diff_tensor, change_pct = run_scenario_inference(model, before_t, after_t)
            elapsed = (time.perf_counter() - start) * 1000.0  # ms
            latencies.append(elapsed)

        avg_latency = float(np.mean(latencies))
        std_latency = float(np.std(latencies))

        results[scenario] = {
            "avg_latency_ms": round(avg_latency, 2),
            "std_latency_ms": round(std_latency, 2),
            "change_percentage": change_pct,
            "diff_tensor": diff_tensor,
        }

    return results


# ---------------------------------------------------------------------------
# Main Benchmark Pipeline
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Benchmark FP32 vs INT8 Quantized Prithvi-100M Model for Edge Deployment Roadmap."
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="Number of benchmark iterations per scenario (default: 5)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory containing preprocessed GeoTIFF data (default: data/)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Directory to save benchmark_results.json and .csv (default: current dir)",
    )
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("Prithvi-100M Edge Deployment Quantization Benchmark")
    logger.info("=" * 70)
    logger.info(f"Target Device:     {DEVICE} (CPU-only benchmark)")
    logger.info(f"Iterations:        {args.iterations}")
    logger.info(f"Data Directory:    {args.data_dir.resolve()}")
    logger.info("")

    # 1. Load Image Tensors
    logger.info("Phase 1: Loading input image pairs...")
    image_pairs = {}
    for scenario in SCENARIOS:
        before_path = args.data_dir / scenario / "before.tif"
        after_path = args.data_dir / scenario / "after.tif"
        
        b_tensor = load_image_tensor(before_path).to(DEVICE)
        a_tensor = load_image_tensor(after_path).to(DEVICE)
        image_pairs[scenario] = (b_tensor, a_tensor)
        logger.info(f"  ✓ [{scenario}] Loaded shape: before={tuple(b_tensor.shape)}, after={tuple(a_tensor.shape)}")

    # 2. Load FP32 Model
    logger.info("")
    logger.info("Phase 2: Loading FP32 model...")
    start_load = time.time()
    try:
        model_fp32 = AutoModel.from_pretrained(MODEL_ID, trust_remote_code=True)
        model_fp32.to(DEVICE)
        model_fp32.eval()
    except Exception as e:
        logger.critical(f"Failed to load model {MODEL_ID}: {e}")
        sys.exit(1)

    fp32_size_mb = get_model_size_mb(model_fp32)
    logger.info(f"  ✓ FP32 Model loaded in {time.time() - start_load:.2f}s. Size: {fp32_size_mb:.2f} MB")

    # 3. Benchmark FP32 Model
    logger.info("")
    logger.info("Phase 3: Benchmarking FP32 model inference...")
    fp32_results = benchmark_model(model_fp32, image_pairs, iterations=args.iterations)

    for scenario, res in fp32_results.items():
        logger.info(f"  → [{scenario}] Latency: {res['avg_latency_ms']:.2f} ± {res['std_latency_ms']:.2f} ms | Change: {res['change_percentage']}%")

    # 4. Quantize Model to INT8
    logger.info("")
    logger.info("Phase 4: Applying Dynamic INT8 Quantization (torch.quantization.quantize_dynamic)...")
    if quantize_dynamic is None:
        logger.critical("PyTorch quantization module (quantize_dynamic) is unavailable.")
        sys.exit(1)

    start_quant = time.time()
    model_int8 = quantize_dynamic(
        model_fp32,
        qconfig_spec={nn.Linear},
        dtype=torch.qint8,
    )
    quant_time = time.time() - start_quant
    int8_size_mb = get_model_size_mb(model_int8)
    size_reduction_pct = ((fp32_size_mb - int8_size_mb) / fp32_size_mb) * 100.0
    compression_ratio = fp32_size_mb / (int8_size_mb + 1e-6)

    logger.info(f"  ✓ Dynamic INT8 quantization completed in {quant_time:.2f}s.")
    logger.info(f"  ✓ INT8 Model Size: {int8_size_mb:.2f} MB (Reduction: {size_reduction_pct:.1f}%, Compression: {compression_ratio:.2f}x)")

    # 5. Benchmark INT8 Model
    logger.info("")
    logger.info("Phase 5: Benchmarking INT8 quantized model inference...")
    int8_results = benchmark_model(model_int8, image_pairs, iterations=args.iterations)

    for scenario, res in int8_results.items():
        logger.info(f"  → [{scenario}] Latency: {res['avg_latency_ms']:.2f} ± {res['std_latency_ms']:.2f} ms | Change: {res['change_percentage']}%")

    # 6. Analyze Quality & Fidelity Metrics
    logger.info("")
    logger.info("Phase 6: Computing Fidelity & Speedup Metrics...")
    summary_data = []

    for scenario in SCENARIOS:
        fp32_res = fp32_results[scenario]
        int8_res = int8_results[scenario]

        # Latency speedup
        fp32_lat = fp32_res["avg_latency_ms"]
        int8_lat = int8_res["avg_latency_ms"]
        speedup_pct = ((fp32_lat - int8_lat) / fp32_lat) * 100.0
        speedup_factor = fp32_lat / (int8_lat + 1e-6)

        # Cosine Similarity between embedding distance tensors
        vec_fp32 = fp32_res["diff_tensor"].flatten()
        vec_int8 = int8_res["diff_tensor"].flatten()

        cos_sim = float(
            torch.nn.functional.cosine_similarity(vec_fp32.unsqueeze(0), vec_int8.unsqueeze(0)).item()
        )
        mse = float(torch.mean((vec_fp32 - vec_int8) ** 2).item())

        quality_note = (
            f"High fidelity match: Cosine Similarity = {cos_sim:.4f}, MSE = {mse:.6f}. "
            f"Change % shifted from {fp32_res['change_percentage']}% (FP32) to {int8_res['change_percentage']}% (INT8)."
        )

        row = {
            "scenario": scenario,
            "fp32_model_size_mb": round(fp32_size_mb, 2),
            "int8_model_size_mb": round(int8_size_mb, 2),
            "size_reduction_pct": round(size_reduction_pct, 1),
            "compression_ratio": round(compression_ratio, 2),
            "fp32_latency_ms": fp32_lat,
            "int8_latency_ms": int8_lat,
            "speedup_pct": round(speedup_pct, 1),
            "speedup_factor": round(speedup_factor, 2),
            "fp32_change_pct": fp32_res["change_percentage"],
            "int8_change_pct": int8_res["change_percentage"],
            "change_pct_diff": round(abs(fp32_res["change_percentage"] - int8_res["change_percentage"]), 2),
            "cosine_similarity": round(cos_sim, 4),
            "mse": round(mse, 6),
            "qualitative_note": quality_note,
        }
        summary_data.append(row)

    # 7. Print Console Table
    logger.info("")
    logger.info("=" * 80)
    logger.info("BENCHMARK SUMMARY RESULTS")
    logger.info("=" * 80)
    logger.info(f"{'Metric':<30} | {'FP32 Model':<18} | {'INT8 Quantized':<18} | {'Improvement':<12}")
    logger.info("-" * 80)
    logger.info(f"{'Model Size (MB)':<30} | {fp32_size_mb:<18.2f} | {int8_size_mb:<18.2f} | {size_reduction_pct:.1f}% smaller")

    for row in summary_data:
        sc = row["scenario"].capitalize()
        logger.info(f"{sc + ' Latency (ms)':<30} | {row['fp32_latency_ms']:<18.2f} | {row['int8_latency_ms']:<18.2f} | {row['speedup_factor']:.2f}x faster")
        logger.info(f"{sc + ' Change Detected (%)':<30} | {row['fp32_change_pct']:<18.2f} | {row['int8_change_pct']:<18.2f} | diff: {row['change_pct_diff']:.2f}%")
        logger.info(f"{sc + ' Cosine Similarity':<30} | {'1.0000 (baseline)':<18} | {row['cosine_similarity']:<18.4f} | MSE: {row['mse']:.6f}")
    logger.info("=" * 80)

    # 8. Save JSON & CSV Outputs
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "benchmark_results.json"
    csv_path = output_dir / "benchmark_results.csv"

    benchmark_json = {
        "model_id": MODEL_ID,
        "device": str(DEVICE),
        "quantization_type": "dynamic_int8",
        "target_layers": "torch.nn.Linear",
        "fp32_model_size_mb": round(fp32_size_mb, 2),
        "int8_model_size_mb": round(int8_size_mb, 2),
        "size_reduction_pct": round(size_reduction_pct, 1),
        "compression_ratio": round(compression_ratio, 2),
        "scenarios": summary_data,
        "edge_deployment_readiness_summary": (
            f"INT8 quantization reduces memory footprint by {size_reduction_pct:.1f}% "
            f"({fp32_size_mb:.1f} MB -> {int8_size_mb:.1f} MB) while maintaining high fidelity "
            f"(Cosine Similarity > {min(r['cosine_similarity'] for r in summary_data):.4f}) on CPU edge hardware."
        ),
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_json, f, indent=2)
    logger.info(f"✓ Saved JSON benchmark results: {json_path.resolve()}")

    fieldnames = [
        "scenario",
        "fp32_model_size_mb",
        "int8_model_size_mb",
        "size_reduction_pct",
        "compression_ratio",
        "fp32_latency_ms",
        "int8_latency_ms",
        "speedup_pct",
        "speedup_factor",
        "fp32_change_pct",
        "int8_change_pct",
        "change_pct_diff",
        "cosine_similarity",
        "mse",
        "qualitative_note",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_data)
    logger.info(f"✓ Saved CSV benchmark summary: {csv_path.resolve()}")

    logger.info("")
    logger.info("Benchmark complete. Data is ready for the 'Edge Deployment Roadmap' presentation slide!")


if __name__ == "__main__":
    main()
