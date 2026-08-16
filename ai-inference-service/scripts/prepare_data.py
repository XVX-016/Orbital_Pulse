#!/usr/bin/env python3
"""
prepare_data.py — Validate and preprocess real GeoTIFF imagery for the AI inference service.

This script takes raw source GeoTIFF files (Sentinel-2 or xBD) and produces:
  1. Preprocessed 6-band, 224×224, float32 GeoTIFFs in data/{scenario}/{before,after}.tif
  2. JPEG preview thumbnails in public/images/{scenario}-{before,after}.jpg

It fails loudly if any source file is missing, unreadable, or malformed.

Usage:
    python scripts/prepare_data.py [--raw-dir RAW_DATA_DIR] [--output-dir DATA_DIR] [--preview-dir PREVIEW_DIR]

Band Mapping (Prithvi-EO-1.0-100M expects 6 HLS bands):
    Sentinel-2 (13-band L2A):
        Band indices [1, 2, 3, 7, 10, 11] → B2(Blue), B3(Green), B4(Red), B8A(NIR), B11(SWIR1), B12(SWIR2)
        (0-indexed from the file's band ordering)
    
    xBD / RGB (3-band):
        Bands [R, G, B] → padded to 6 by duplicating: [B, G, R, R, G, B]
        ⚠ Model output will be less meaningful with padded RGB data.

    Custom band count:
        If band count is exactly 6, bands are used as-is (assumed to already be HLS-ordered).
        If band count is between 4-5 or 7-12, the script selects the first 6 bands with a warning.
        If band count is > 13, Sentinel-2 L1C/L2A mapping is attempted.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

try:
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import from_bounds
    from rasterio.windows import from_bounds as window_from_bounds
except ImportError:
    print("ERROR: rasterio is required. Install with: pip install rasterio", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("prepare_data")

TARGET_SIZE = (224, 224)  # (height, width) expected by Prithvi ViT
TARGET_BANDS = 6

# Sentinel-2 L2A band ordering (1-indexed in the file):
# B1, B2, B3, B4, B5, B6, B7, B8, B8A, B9, B10, B11, B12
# We want: B2(Blue), B3(Green), B4(Red), B8A(NIR), B11(SWIR1), B12(SWIR2)
# 0-indexed from file bands: [1, 2, 3, 8, 11, 12] for 13-band L2A
# But many downloads are already band-stacked subsets. The script handles multiple cases.
SENTINEL2_13BAND_INDICES = [1, 2, 3, 8, 11, 12]  # 0-indexed for 13-band files

SCENARIOS = ["deforestation", "disaster"]
PHASES = ["before", "after"]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_geotiff(filepath: Path) -> dict:
    """
    Validate that a file is a readable GeoTIFF and return its metadata.
    Raises SystemExit with a clear message on failure.
    """
    if not filepath.exists():
        logger.critical(f"MISSING FILE: {filepath}")
        logger.critical(
            f"  → Expected a GeoTIFF at this path. Please provide the source data.\n"
            f"  → For deforestation: Sentinel-2 L2A imagery from the Rondônia region.\n"
            f"  → For disaster: Sentinel-2 or xBD (Maxar) pre/post-disaster imagery."
        )
        sys.exit(1)

    if not filepath.is_file():
        logger.critical(f"NOT A FILE: {filepath} — expected a regular file, got something else.")
        sys.exit(1)

    try:
        with rasterio.open(filepath) as src:
            meta = {
                "path": str(filepath),
                "driver": src.driver,
                "width": src.width,
                "height": src.height,
                "count": src.count,  # number of bands
                "dtype": str(src.dtypes[0]),
                "crs": str(src.crs) if src.crs else "None",
                "bounds": src.bounds,
                "nodata": src.nodata,
            }
    except rasterio.errors.RasterioIOError as e:
        logger.critical(f"UNREADABLE FILE: {filepath}")
        logger.critical(f"  → rasterio could not open this file: {e}")
        logger.critical(f"  → Ensure it is a valid GeoTIFF (not corrupted, not a different format).")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"UNEXPECTED ERROR reading {filepath}: {e}")
        sys.exit(1)

    if meta["count"] == 0:
        logger.critical(f"MALFORMED FILE: {filepath} has 0 bands. Expected at least 3.")
        sys.exit(1)

    if meta["width"] == 0 or meta["height"] == 0:
        logger.critical(f"MALFORMED FILE: {filepath} has 0×0 pixel dimensions.")
        sys.exit(1)

    # Warn on suspicious small files
    file_size = filepath.stat().st_size
    if file_size < 1024:
        logger.warning(f"  ⚠ File is suspiciously small ({file_size} bytes): {filepath}")

    logger.info(f"  ✓ Valid GeoTIFF: {filepath.name}")
    logger.info(f"    Driver={meta['driver']}, Size={meta['width']}×{meta['height']}, "
                f"Bands={meta['count']}, Dtype={meta['dtype']}, CRS={meta['crs']}")

    return meta


# ---------------------------------------------------------------------------
# Band Selection
# ---------------------------------------------------------------------------

def select_bands(data: np.ndarray, band_count: int, filepath: Path) -> np.ndarray:
    """
    Select/map bands to produce a 6-band array for Prithvi.
    
    Args:
        data: Array of shape (C, H, W) with all bands from the source file.
        band_count: Number of bands in the source (== data.shape[0]).
        filepath: For logging context.
    
    Returns:
        Array of shape (6, H, W).
    """
    if band_count == TARGET_BANDS:
        logger.info(f"    Band count is exactly {TARGET_BANDS} — using all bands as-is (assumed HLS order).")
        return data

    if band_count == 3:
        # xBD or generic RGB imagery
        logger.warning(f"    ⚠ SOURCE IS 3-BAND RGB: {filepath.name}")
        logger.warning(f"      Prithvi expects 6 HLS bands (Blue, Green, Red, NIR, SWIR1, SWIR2).")
        logger.warning(f"      Padding RGB → 6 bands by duplicating: [B, G, R, R, G, B].")
        logger.warning(f"      Model output will be less meaningful with padded data.")
        # data shape: (3, H, W) where typically [R, G, B] or [B, G, R]
        # We'll assume [R, G, B] ordering and map to [Blue, Green, Red, NIR≈Red, SWIR1≈Green, SWIR2≈Blue]
        r, g, b = data[0], data[1], data[2]
        return np.stack([b, g, r, r, g, b], axis=0)

    if band_count == 4:
        # Likely RGBN (e.g. some commercial satellite products)
        logger.warning(f"    ⚠ SOURCE IS 4-BAND (likely RGBN): {filepath.name}")
        logger.warning(f"      Mapping: [B3≈G, B2≈R, B4≈NIR, B1≈Blue, pad, pad]")
        r, g, b, nir = data[0], data[1], data[2], data[3]
        return np.stack([b, g, r, nir, g, b], axis=0)

    if band_count >= 13:
        # Sentinel-2 L2A with all 13 bands
        logger.info(f"    Sentinel-2 13+ band file detected. Selecting HLS bands:")
        logger.info(f"      Indices (0-based): {SENTINEL2_13BAND_INDICES}")
        logger.info(f"      → B2(Blue), B3(Green), B4(Red), B8A(NIR), B11(SWIR1), B12(SWIR2)")
        selected = data[SENTINEL2_13BAND_INDICES]
        return selected

    if band_count >= 7:
        # Could be a Sentinel-2 subset with SCL or other extra bands
        logger.warning(f"    ⚠ SOURCE HAS {band_count} BANDS: {filepath.name}")
        logger.warning(f"      Taking first 6 bands. Verify the band ordering matches HLS expectation.")
        return data[:TARGET_BANDS]

    if band_count == 5:
        logger.warning(f"    ⚠ SOURCE IS 5-BAND: {filepath.name}")
        logger.warning(f"      Taking all 5 bands + duplicating last band to reach 6.")
        return np.concatenate([data, data[-1:]], axis=0)

    # Fallback for band_count in {1, 2} — not useful for Prithvi
    logger.critical(f"UNSUPPORTED BAND COUNT: {filepath.name} has {band_count} band(s).")
    logger.critical(f"  Prithvi requires at least 3 bands (RGB) to produce a padded 6-band input.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

def preprocess_geotiff(
    src_path: Path,
    dst_path: Path,
    target_size: tuple[int, int] = TARGET_SIZE,
) -> np.ndarray:
    """
    Read a GeoTIFF, select bands, resize to target_size, and write the result.
    
    Returns the preprocessed data array (6, H, W) for preview generation.
    """
    with rasterio.open(src_path) as src:
        band_count = src.count

        # Read all bands, resampled to target size
        data = src.read(
            out_shape=(band_count, target_size[0], target_size[1]),
            resampling=Resampling.bilinear,
        )

        # Select/map to 6 bands
        data_6band = select_bands(data, band_count, src_path)

        # Convert to float32 and normalize
        data_6band = data_6band.astype(np.float32)

        # Compute a simple transform for the output
        # Preserve the original CRS if available
        dst_transform = from_bounds(
            *src.bounds, target_size[1], target_size[0]
        ) if src.bounds else rasterio.transform.from_origin(0, target_size[0], 1, 1)

        dst_crs = src.crs

    # Write the preprocessed 6-band GeoTIFF
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    
    profile = {
        "driver": "GTiff",
        "height": target_size[0],
        "width": target_size[1],
        "count": TARGET_BANDS,
        "dtype": "float32",
        "crs": dst_crs,
        "transform": dst_transform,
    }

    with rasterio.open(dst_path, "w", **profile) as dst:
        dst.write(data_6band)

    logger.info(f"    ✓ Wrote preprocessed GeoTIFF: {dst_path} (6 bands, {target_size[0]}×{target_size[1]}, float32)")

    return data_6band


def generate_jpeg_preview(
    data: np.ndarray,
    output_path: Path,
    rgb_indices: tuple[int, int, int] = (2, 1, 0),
) -> None:
    """
    Generate a JPEG preview from a 6-band array using the specified RGB band indices.
    
    Default indices (2, 1, 0) = Red, Green, Blue from the HLS ordering → true-color composite.
    
    Args:
        data: Array of shape (6, H, W).
        output_path: Where to save the JPEG.
        rgb_indices: Which bands to use as R, G, B in the preview.
    """
    r = data[rgb_indices[0]]
    g = data[rgb_indices[1]]
    b = data[rgb_indices[2]]

    # Stack to (H, W, 3)
    rgb = np.stack([r, g, b], axis=-1)

    # Normalize to 0-255 using percentile stretch for better visualization
    # (satellite imagery often has a narrow dynamic range)
    for ch in range(3):
        channel = rgb[:, :, ch]
        p2, p98 = np.percentile(channel[channel > 0], (2, 98)) if np.any(channel > 0) else (0, 1)
        if p98 - p2 < 1e-6:
            p98 = p2 + 1
        rgb[:, :, ch] = np.clip((channel - p2) / (p98 - p2), 0, 1)

    rgb_uint8 = (rgb * 255).astype(np.uint8)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.fromarray(rgb_uint8, mode="RGB")
    
    # Save at reasonable quality with a slightly larger size for the slider UI
    img_resized = img.resize((512, 512), Image.LANCZOS)
    img_resized.save(output_path, "JPEG", quality=90)

    logger.info(f"    ✓ Wrote JPEG preview: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Validate and preprocess GeoTIFF imagery for the Prithvi change-detection pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("raw_data"),
        help="Directory containing raw source GeoTIFFs (default: raw_data/)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data"),
        help="Directory for preprocessed output GeoTIFFs (default: data/)",
    )
    parser.add_argument(
        "--preview-dir",
        type=Path,
        default=Path("public/images"),
        help="Directory for JPEG preview thumbnails (default: public/images/)",
    )
    args = parser.parse_args()

    raw_dir: Path = args.raw_dir
    output_dir: Path = args.output_dir
    preview_dir: Path = args.preview_dir

    logger.info("=" * 70)
    logger.info("Orbital Pulse — GeoTIFF Data Preparation Pipeline")
    logger.info("=" * 70)
    logger.info(f"Raw data directory:    {raw_dir.resolve()}")
    logger.info(f"Output directory:      {output_dir.resolve()}")
    logger.info(f"Preview directory:     {preview_dir.resolve()}")
    logger.info(f"Target size:           {TARGET_SIZE[0]}×{TARGET_SIZE[1]}")
    logger.info(f"Target bands:          {TARGET_BANDS} (HLS: Blue, Green, Red, NIR, SWIR1, SWIR2)")
    logger.info("")

    # -----------------------------------------------------------------------
    # Phase 1: Validate all source files exist and are readable
    # -----------------------------------------------------------------------
    logger.info("Phase 1: Validating source GeoTIFF files...")
    logger.info("-" * 50)

    all_metadata = {}
    for scenario in SCENARIOS:
        for phase in PHASES:
            src_path = raw_dir / scenario / f"{phase}.tif"
            key = f"{scenario}/{phase}"
            logger.info(f"  [{key}]")
            all_metadata[key] = validate_geotiff(src_path)

    logger.info("")
    logger.info("✓ All source files validated successfully.")
    logger.info("")

    # -----------------------------------------------------------------------
    # Phase 2: Preprocess (band selection + resize + write)
    # -----------------------------------------------------------------------
    logger.info("Phase 2: Preprocessing GeoTIFFs → 6-band 224×224 float32...")
    logger.info("-" * 50)

    preprocessed = {}
    for scenario in SCENARIOS:
        for phase in PHASES:
            key = f"{scenario}/{phase}"
            src_path = raw_dir / scenario / f"{phase}.tif"
            dst_path = output_dir / scenario / f"{phase}.tif"
            logger.info(f"  [{key}]")
            preprocessed[key] = preprocess_geotiff(src_path, dst_path)

    logger.info("")
    logger.info("✓ All GeoTIFFs preprocessed successfully.")
    logger.info("")

    # -----------------------------------------------------------------------
    # Phase 3: Generate JPEG previews for frontend
    # -----------------------------------------------------------------------
    logger.info("Phase 3: Generating JPEG previews for frontend thumbnails...")
    logger.info("-" * 50)

    for scenario in SCENARIOS:
        for phase in PHASES:
            key = f"{scenario}/{phase}"
            preview_path = preview_dir / f"{scenario}-{phase}.jpg"
            logger.info(f"  [{key}]")
            generate_jpeg_preview(preprocessed[key], preview_path)

    logger.info("")
    logger.info("✓ All JPEG previews generated successfully.")
    logger.info("")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    logger.info("=" * 70)
    logger.info("DATA PREPARATION COMPLETE")
    logger.info("=" * 70)
    logger.info("")
    logger.info("Preprocessed GeoTIFFs (for model inference):")
    for scenario in SCENARIOS:
        for phase in PHASES:
            dst = output_dir / scenario / f"{phase}.tif"
            logger.info(f"  → {dst}")
    logger.info("")
    logger.info("JPEG Previews (for frontend before/after slider):")
    for scenario in SCENARIOS:
        for phase in PHASES:
            preview = preview_dir / f"{scenario}-{phase}.jpg"
            logger.info(f"  → {preview}")
    logger.info("")

    # Log band mapping summary
    logger.info("Band mapping summary:")
    for key, meta in all_metadata.items():
        band_count = meta["count"]
        if band_count == 3:
            mapping = "RGB → padded [B,G,R,R,G,B] ⚠ (model quality reduced)"
        elif band_count == TARGET_BANDS:
            mapping = "6-band → used as-is (assumed HLS order)"
        elif band_count >= 13:
            mapping = f"Sentinel-2 {band_count}-band → selected HLS subset"
        else:
            mapping = f"{band_count}-band → adapted to 6 bands (see logs for details)"
        logger.info(f"  {key}: {band_count} bands → {mapping}")

    logger.info("")
    logger.info("Next steps:")
    logger.info("  1. Start the AI inference service: uvicorn main:app --host 0.0.0.0 --port 8082")
    logger.info("  2. Or build the Docker image: docker compose up --build ai-inference-service")
    logger.info("")


if __name__ == "__main__":
    main()
