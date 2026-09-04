#!/usr/bin/env python3
"""
geospatial_metrics.py — Pure, deterministic geospatial & spectral metrics for satellite imagery.

All functions operate strictly on raw pixel/geospatial arrays and metadata.
None of these functions invoke GeoChat, external neural networks, or nondeterministic services.
All calculations return explicit numeric values or None (when georeferencing is unavailable).
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np


# ---------------------------------------------------------------------------
# Default Band Indices (Sentinel-2 / HLS convention from prepare_data.py)
# HLS band order: [B2(Blue)=0, B3(Green)=1, B4(Red)=2, B8A(NIR)=3, B11(SWIR1)=4, B12(SWIR2)=5]
# ---------------------------------------------------------------------------
DEFAULT_RED_BAND_IDX = 2
DEFAULT_NIR_BAND_IDX = 3
DEFAULT_GREEN_BAND_IDX = 1
DEFAULT_SWIR1_BAND_IDX = 4
DEFAULT_SWIR2_BAND_IDX = 5
DEFAULT_BLUE_BAND_IDX = 0

# NDVI vegetation classification threshold
DEFAULT_NDVI_VEG_THRESHOLD = 0.2


# ---------------------------------------------------------------------------
# Geotransform resolution & pixel area calculation helper
# ---------------------------------------------------------------------------

def get_pixel_dimensions_meters(geotransform: Any) -> Optional[Tuple[float, float]]:
    """
    Extracts pixel resolution in meters (dx_meters, dy_meters) from a geotransform.

    Supports:
        - affine.Affine object (rasterio src.transform)
        - 6-element tuple/list (GDAL geotransform: [c, a, b, f, d, e] or Affine: [a, b, c, d, e, f])
    
    If coordinates are in geographic degrees (e.g. EPSG:4326 |dx| < 0.1),
    projects resolution to meters using spherical geodesic approximation at the latitude center.
    If geotransform is missing/invalid or unprojected pixel coordinates, returns None.
    """
    if geotransform is None:
        return None

    try:
        # Check if Affine instance (has attributes a, b, c, d, e, f)
        if hasattr(geotransform, "a") and hasattr(geotransform, "e"):
            dx = abs(float(geotransform.a))
            dy = abs(float(geotransform.e))
            origin_lat = float(geotransform.f)
        elif isinstance(geotransform, (list, tuple)) and len(geotransform) >= 6:
            # GDAL tuple: [origin_x, pixel_width, rot_x, origin_y, rot_y, pixel_height]
            dx = abs(float(geotransform[1]))
            dy = abs(float(geotransform[5]))
            origin_lat = float(geotransform[3])
        else:
            return None

        # Guard against zero or non-finite resolutions
        if dx <= 0 or dy <= 0 or not np.isfinite(dx) or not np.isfinite(dy):
            return None

        # Detect geographic coordinates (degrees vs meters)
        # If dx < 1.0, coordinates are in degrees (e.g. ~0.0001 deg ~ 10m)
        if dx < 1.0 and dy < 1.0:
            lat_deg = max(-89.0, min(89.0, origin_lat))
            lat_rad = np.radians(lat_deg)
            # WGS84 approx: 1 deg lat ~ 111,320m, 1 deg lon ~ 111,320m * cos(lat)
            meters_per_deg_lat = 111320.0
            meters_per_deg_lon = 111320.0 * np.cos(lat_rad)
            dx_m = dx * meters_per_deg_lon
            dy_m = dy * meters_per_deg_lat
            return (float(dx_m), float(dy_m))

        # Projected coordinates already in meters (e.g. UTM)
        return (float(dx), float(dy))

    except Exception:
        return None


# ---------------------------------------------------------------------------
# 1. compute_ndvi_coverage
# ---------------------------------------------------------------------------

def compute_ndvi_coverage(
    image_bands: np.ndarray,
    red_band_idx: int = DEFAULT_RED_BAND_IDX,
    nir_band_idx: int = DEFAULT_NIR_BAND_IDX,
    veg_threshold: float = DEFAULT_NDVI_VEG_THRESHOLD,
) -> Dict[str, Any]:
    """
    Computes standard NDVI ((NIR - Red) / (NIR + Red)) per-pixel from multi-band satellite array.

    Args:
        image_bands: Array of shape (C, H, W) or (H, W, C).
        red_band_idx: Channel index for Red band (default 2 in HLS).
        nir_band_idx: Channel index for NIR band (default 3 in HLS).
        veg_threshold: Threshold above which a pixel is considered "vegetated" (default >0.2).

    Returns:
        {
            "vegetation_pct": float,      # Percentage (0-100) of pixels with NDVI > veg_threshold
            "mean_ndvi": float,           # Mean NDVI across all valid pixels (-1.0 to 1.0)
            "min_ndvi": float,            # Minimum observed NDVI
            "max_ndvi": float,            # Maximum observed NDVI
            "vegetated_pixel_count": int, # Number of pixels exceeding threshold
            "total_pixels": int,          # Total valid pixels evaluated
        }
    """
    arr = np.asarray(image_bands, dtype=np.float32)
    if arr.ndim == 2:
        raise ValueError("compute_ndvi_coverage requires multi-band array, got 2D array")

    # Handle shape (C, H, W) vs (H, W, C)
    # If the first dimension is <= 16 and either larger than or smaller than spatial dims,
    # or if the last dimension is clearly spatial/smaller, check indices.
    if arr.ndim == 3 and (arr.shape[0] <= 16 and (arr.shape[0] < arr.shape[1] or arr.shape[-1] < max(red_band_idx, nir_band_idx) + 1)):
        # Format is (C, H, W)
        red = arr[red_band_idx]
        nir = arr[nir_band_idx]
    elif arr.ndim == 3 and arr.shape[0] <= 16 and arr.shape[-1] <= 16:
        # Ambiguous small array (e.g. 6, 2, 2)
        if arr.shape[-1] < max(red_band_idx, nir_band_idx) + 1:
            red = arr[red_band_idx]
            nir = arr[nir_band_idx]
        else:
            red = arr[red_band_idx]
            nir = arr[nir_band_idx]
    else:
        # Format is (H, W, C)
        red = arr[:, :, red_band_idx]
        nir = arr[:, :, nir_band_idx]

    denom = nir + red
    # Avoid zero division and calculate normalized difference vegetation index
    valid_denom = np.abs(denom) > 1e-7
    ndvi = np.zeros_like(denom, dtype=np.float32)
    np.divide(nir - red, denom, out=ndvi, where=valid_denom)
    # Clip NDVI to physically valid range [-1.0, 1.0]
    ndvi = np.clip(ndvi, -1.0, 1.0)

    total_pixels = int(ndvi.size)
    if total_pixels == 0:
        return {
            "vegetation_pct": 0.0,
            "mean_ndvi": 0.0,
            "min_ndvi": 0.0,
            "max_ndvi": 0.0,
            "vegetated_pixel_count": 0,
            "total_pixels": 0,
        }

    vegetated_mask = ndvi > veg_threshold
    vegetated_count = int(np.sum(vegetated_mask))

    veg_pct = round(float((vegetated_count / total_pixels) * 100.0), 2)
    mean_ndvi = round(float(np.mean(ndvi)), 4)
    min_ndvi = round(float(np.min(ndvi)), 4)
    max_ndvi = round(float(np.max(ndvi)), 4)

    return {
        "vegetation_pct": veg_pct,
        "mean_ndvi": mean_ndvi,
        "min_ndvi": min_ndvi,
        "max_ndvi": max_ndvi,
        "vegetated_pixel_count": vegetated_count,
        "total_pixels": total_pixels,
    }


# ---------------------------------------------------------------------------
# 2. compute_area_from_bbox
# ---------------------------------------------------------------------------

def compute_area_from_bbox(
    box_normalized: List[Union[int, float]],
    geotransform: Any,
    image_width: int,
    image_height: int,
) -> Optional[Dict[str, Any]]:
    """
    Converts a normalized bounding box [xmin, ymin, xmax, ymax] into real-world area in km².

    Discipline:
        Only computes when the source has real georeferencing. For plain JPEG/PNG uploads
        or unreferenced arrays, returns None explicitly rather than fabricating an arbitrary scale.

    Args:
        box_normalized: [xmin, ymin, xmax, ymax] in range [0, 100] (from grounding_parser.py)
                        or [0.0, 1.0].
        geotransform: Affine transform object or 6-element GDAL transform from GeoTIFF.
        image_width: Width of image in pixels.
        image_height: Height of image in pixels.

    Returns:
        {
            "area_km2": float,         # Real-world bounding box area in km²
            "area_m2": float,          # Real-world bounding box area in m²
            "pixel_count": int,        # Total pixels enclosed in bbox
            "width_km": float,         # Width of bbox in km
            "height_km": float,        # Height of bbox in km
        }
        or None if geotransform is missing/invalid.
    """
    if geotransform is None or image_width <= 0 or image_height <= 0:
        return None

    pixel_res = get_pixel_dimensions_meters(geotransform)
    if pixel_res is None:
        return None

    dx_m, dy_m = pixel_res

    # Unpack normalized box coordinates
    if len(box_normalized) != 4:
        return None

    x1, y1, x2, y2 = box_normalized
    # If coordinates are 0-100 (GeoChat / grounding_parser format), scale to [0, 1]
    if max(x1, y1, x2, y2) > 1.0:
        nx1, ny1, nx2, ny2 = x1 / 100.0, y1 / 100.0, x2 / 100.0, y2 / 100.0
    else:
        nx1, ny1, nx2, ny2 = float(x1), float(y1), float(x2), float(y2)

    nx1 = max(0.0, min(1.0, nx1))
    ny1 = max(0.0, min(1.0, ny1))
    nx2 = max(0.0, min(1.0, nx2))
    ny2 = max(0.0, min(1.0, ny2))

    box_w_norm = max(0.0, nx2 - nx1)
    box_h_norm = max(0.0, ny2 - ny1)

    # Convert to pixel dimensions
    bbox_w_px = box_w_norm * image_width
    bbox_h_px = box_h_norm * image_height

    # Convert to meters & km
    width_m = bbox_w_px * dx_m
    height_m = bbox_h_px * dy_m
    area_m2 = width_m * height_m
    area_km2 = area_m2 / 1e6

    pixel_count = int(round(bbox_w_px * bbox_h_px))

    return {
        "area_km2": round(float(area_km2), 4),
        "area_m2": round(float(area_m2), 2),
        "pixel_count": pixel_count,
        "width_km": round(float(width_m / 1000.0), 4),
        "height_km": round(float(height_m / 1000.0), 4),
    }


# ---------------------------------------------------------------------------
# 3. compute_change_area
# ---------------------------------------------------------------------------

def compute_change_area(
    before_bands: np.ndarray,
    after_bands: np.ndarray,
    geotransform: Any = None,
    threshold: float = 0.15,
) -> Dict[str, Any]:
    """
    Pixel-diff thresholding between bi-temporal band arrays.

    Calculates per-pixel spectral distance (Euclidean norm across bands). Pixels with distance
    exceeding `threshold` are marked as changed.
    When geotransform is provided, also calculates change area in real-world km² and m².

    Args:
        before_bands: Array of shape (C, H, W) for initial acquisition date.
        after_bands: Array of shape (C, H, W) for subsequent acquisition date.
        geotransform: Optional Affine transform or GDAL transform.
        threshold: Spectral change threshold. If bands are uint16/raw DN (>100.0),
                   threshold is automatically scaled to match reflectance range,
                   or users can specify an absolute distance threshold.

    Returns:
        {
            "changed_pixels": int,           # Number of changed pixels
            "total_pixels": int,             # Total pixels evaluated
            "change_pct": float,             # Percentage of pixels changed
            "mean_spectral_distance": float, # Average spectral difference across scene
            "max_spectral_distance": float,  # Peak spectral difference
            "changed_area_km2": float | None,# Real-world area in km² (None if unreferenced)
            "changed_area_m2": float | None, # Real-world area in m² (None if unreferenced)
        }
    """
    b = np.asarray(before_bands, dtype=np.float32)
    a = np.asarray(after_bands, dtype=np.float32)

    if b.shape != a.shape:
        raise ValueError(f"Shape mismatch between before {b.shape} and after {a.shape} arrays")

    # If raw DN values (e.g. Sentinel-2 L2A 0-10000 DN range), normalize to [0, 1] reflectance
    max_val = max(float(b.max()), float(a.max()))
    if max_val > 100.0:
        b_norm = b / 10000.0
        a_norm = a / 10000.0
    else:
        b_norm = b
        a_norm = a

    # Spectral Euclidean distance across all bands per pixel
    spectral_dist = np.linalg.norm(b_norm - a_norm, axis=0)

    total_pixels = int(spectral_dist.size)
    if total_pixels == 0:
        return {
            "changed_pixels": 0,
            "total_pixels": 0,
            "change_pct": 0.0,
            "mean_spectral_distance": 0.0,
            "max_spectral_distance": 0.0,
            "changed_area_km2": None,
            "changed_area_m2": None,
        }

    changed_mask = spectral_dist > threshold
    changed_count = int(np.sum(changed_mask))
    change_pct = round(float((changed_count / total_pixels) * 100.0), 2)
    mean_dist = round(float(np.mean(spectral_dist)), 4)
    max_dist = round(float(np.max(spectral_dist)), 4)

    # Compute real-world scale if geotransform is valid
    pixel_res = get_pixel_dimensions_meters(geotransform) if geotransform is not None else None
    if pixel_res is not None:
        dx_m, dy_m = pixel_res
        pixel_area_m2 = dx_m * dy_m
        changed_area_m2 = round(float(changed_count * pixel_area_m2), 2)
        changed_area_km2 = round(float(changed_area_m2 / 1e6), 4)
    else:
        changed_area_m2 = None
        changed_area_km2 = None

    return {
        "changed_pixels": changed_count,
        "total_pixels": total_pixels,
        "change_pct": change_pct,
        "mean_spectral_distance": mean_dist,
        "max_spectral_distance": max_dist,
        "changed_area_km2": changed_area_km2,
        "changed_area_m2": changed_area_m2,
    }


# ---------------------------------------------------------------------------
# 4. compute_landcover_breakdown
# ---------------------------------------------------------------------------

def compute_landcover_breakdown(
    image_bands: np.ndarray,
    blue_idx: int = DEFAULT_BLUE_BAND_IDX,
    green_idx: int = DEFAULT_GREEN_BAND_IDX,
    red_idx: int = DEFAULT_RED_BAND_IDX,
    nir_idx: int = DEFAULT_NIR_BAND_IDX,
    swir1_idx: int = DEFAULT_SWIR1_BAND_IDX,
) -> Dict[str, Any]:
    """
    Coarse spectral classification into water/vegetation/built-up/other percentages.

    Reuses the threshold logic style built for SAR backscatter in sar_fusion.py,
    applied to standard optical indices:
        - Water: NDWI ((Green - NIR) / (Green + NIR)) > 0.0
        - Vegetation: Non-water with NDVI ((NIR - Red) / (NIR + Red)) > 0.2
        - Built-up / Bare: Non-water, non-vegetation with NDBI ((SWIR1 - NIR) / (SWIR1 + NIR)) > 0.0
        - Other: Remaining pixels (barren land, rock, mixed)

    Args:
        image_bands: Multi-band array of shape (C, H, W) or (H, W, C).
        blue_idx, green_idx, red_idx, nir_idx, swir1_idx: Channel indices.

    Returns:
        {
            "water_pct": float,
            "vegetation_pct": float,
            "builtup_pct": float,
            "other_pct": float,
            "total_pixels": int,
            "water_pixel_count": int,
            "vegetation_pixel_count": int,
            "builtup_pixel_count": int,
            "other_pixel_count": int,
        }
    """
    arr = np.asarray(image_bands, dtype=np.float32)
    if arr.ndim == 2:
        raise ValueError("compute_landcover_breakdown requires multi-band array, got 2D array")

    is_ch_first = (arr.shape[0] <= 16 and (arr.shape[0] < arr.shape[1] or arr.shape[-1] <= 16))
    if arr.ndim == 3 and arr.shape[0] > 16 and arr.shape[-1] <= 16:
        is_ch_first = False

    num_channels = arr.shape[0] if is_ch_first else arr.shape[-1]
    if num_channels < 3:
        raise ValueError(f"At least 3 bands required for landcover breakdown, got {num_channels}")

    def get_band(idx: int) -> np.ndarray:
        # If requested band index exceeds available channels (e.g. 3-band RGB), fallback gracefully
        clamped_idx = min(idx, num_channels - 1)
        return arr[clamped_idx] if is_ch_first else arr[:, :, clamped_idx]

    red = get_band(red_idx)
    green = get_band(green_idx)
    nir = get_band(nir_idx) if num_channels > 3 else get_band(red_idx)
    swir1 = get_band(swir1_idx) if num_channels > 4 else get_band(green_idx)

    # 1. NDWI = (Green - NIR) / (Green + NIR)
    denom_ndwi = green + nir
    ndwi = np.zeros_like(denom_ndwi)
    np.divide(green - nir, denom_ndwi, out=ndwi, where=np.abs(denom_ndwi) > 1e-7)

    # 2. NDVI = (NIR - Red) / (NIR + Red)
    denom_ndvi = nir + red
    ndvi = np.zeros_like(denom_ndvi)
    np.divide(nir - red, denom_ndvi, out=ndvi, where=np.abs(denom_ndvi) > 1e-7)

    # 3. NDBI = (SWIR1 - NIR) / (SWIR1 + NIR)
    denom_ndbi = swir1 + nir
    ndbi = np.zeros_like(denom_ndbi)
    np.divide(swir1 - nir, denom_ndbi, out=ndbi, where=np.abs(denom_ndbi) > 1e-7)

    total_pixels = int(red.size)
    if total_pixels == 0:
        return {
            "water_pct": 0.0,
            "vegetation_pct": 0.0,
            "builtup_pct": 0.0,
            "other_pct": 0.0,
            "total_pixels": 0,
            "water_pixel_count": 0,
            "vegetation_pixel_count": 0,
            "builtup_pixel_count": 0,
            "other_pixel_count": 0,
        }

    # Apply mutually exclusive masks in order of physical certainty
    water_mask = ndwi > 0.0
    vegetation_mask = (~water_mask) & (ndvi > 0.2)
    builtup_mask = (~water_mask) & (~vegetation_mask) & (ndbi > 0.0)
    other_mask = (~water_mask) & (~vegetation_mask) & (~builtup_mask)

    water_count = int(np.sum(water_mask))
    vegetation_count = int(np.sum(vegetation_mask))
    builtup_count = int(np.sum(builtup_mask))
    other_count = int(np.sum(other_mask))

    water_pct = round(float((water_count / total_pixels) * 100.0), 2)
    vegetation_pct = round(float((vegetation_count / total_pixels) * 100.0), 2)
    builtup_pct = round(float((builtup_count / total_pixels) * 100.0), 2)
    other_pct = round(100.0 - (water_pct + vegetation_pct + builtup_pct), 2)

    return {
        "water_pct": water_pct,
        "vegetation_pct": vegetation_pct,
        "builtup_pct": builtup_pct,
        "other_pct": max(0.0, other_pct),
        "total_pixels": total_pixels,
        "water_pixel_count": water_count,
        "vegetation_pixel_count": vegetation_count,
        "builtup_pixel_count": builtup_count,
        "other_pixel_count": other_count,
    }
