"""Mining expansion alert-check specialist (Track A).

Detects bare-soil / excavation expansion between two real Sentinel-2
acquisitions over a monitored mining region, and raises a `land_change` alert
when the expansion exceeds a configurable threshold OR when a material share of
the newly bare ground falls outside the region's boundary polygon.

REUSE, NOT REIMPLEMENTATION
    The spectral work is done entirely by the existing deterministic engine:
      • compute_landcover_breakdown()  → built-up/bare share per date (NDBI)
      • compute_change_area()          → thresholded change pixels + km²
      • get_pixel_dimensions_meters()  → geotransform → real-world pixel size
    This module only selects scenes, windows the rasters, differences the
    land-cover shares and applies thresholds.

BOUNDARY CAVEAT
    Region boundaries are APPROXIMATIONS (see mining_regions.py). The
    "outside boundary" signal is a coarse spatial cue for triage — never
    evidence of lease encroachment. Every alert this module raises carries
    `boundary_is_approximate` and the caveat text in its computed_metrics so the
    qualification travels with the number into the UI.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

import db as analysis_db
from geospatial_metrics import (
    compute_change_area,
    compute_landcover_breakdown,
    get_pixel_dimensions_meters,
)
from mining_regions import boundary_to_geojson

logger = logging.getLogger(__name__)

# Sentinel-2 L2A assets in the band order geospatial_metrics expects:
# 0=blue 1=green 2=red 3=nir 4=swir1
BAND_ASSETS = [
    ("blue", "B02"),
    ("green", "B03"),
    ("red", "B04"),
    ("nir", "B08"),
    ("swir16", "B11"),
]

# ─── Tunables ─────────────────────────────────────────────────────────────────
# Absolute newly-bare area that trips an alert on its own.
EXPANSION_THRESHOLD_KM2 = float(os.environ.get("MINING_EXPANSION_THRESHOLD_KM2", "0.5"))
# Percentage-point rise in the built-up/bare land-cover share that trips an alert.
EXPANSION_THRESHOLD_PP = float(os.environ.get("MINING_EXPANSION_THRESHOLD_PP", "2.0"))
# Share of newly bare area lying outside the (approximate) boundary that escalates.
OUTSIDE_BOUNDARY_THRESHOLD_PCT = float(
    os.environ.get("MINING_OUTSIDE_BOUNDARY_THRESHOLD_PCT", "15.0")
)
# Reject scenes cloudier than this — NDBI is meaningless under cloud.
# 35% (not 60%) because a 38%/49% cloud pair over Joda produced a nonsensical
# 74.6% "spectral change" across a 13-day gap: cloud motion, not ground change.
MAX_CLOUD_COVER_PCT = float(os.environ.get("MINING_MAX_CLOUD_PCT", "35.0"))
# A scene must cover at least this fraction of the ROI bbox. ST_Intersects alone
# admitted a tile overlapping Jharia by a 0.017-degree sliver, yielding a window
# that was 95.9% boundless zero-fill and a fabricated ~0% bare-ground reading.
MIN_SCENE_COVERAGE = float(os.environ.get("MINING_MIN_SCENE_COVERAGE", "0.6"))
# Final safety net: reject an assembled stack with more than this share of
# zero-fill, whatever the catalog geometry claimed.
MAX_ZERO_FILL_FRACTION = float(os.environ.get("MINING_MAX_ZERO_FILL", "0.10"))
# Minimum days between the two scenes, so we compare genuine successive states.
MIN_SEPARATION_DAYS = int(os.environ.get("MINING_MIN_SEPARATION_DAYS", "10"))

WINDOW_SIZE = 512  # square read size; keeps network + memory bounded


def _load_stac_item(href: str) -> Optional[Dict[str, Any]]:
    import json
    import urllib.request
    try:
        req = urllib.request.Request(href, headers={"User-Agent": "SatQuery/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.warning("mining_monitor: could not load STAC item %s: %s", href, e)
        return None


def load_region_stack(
    scene: Dict[str, Any], bbox: List[float]
) -> Optional[Tuple[np.ndarray, Any]]:
    """Read a 5-band stack clipped to `bbox`, plus the window's affine transform.

    Returns (bands[C,H,W], transform) or None when the scene is unusable.
    """
    item = _load_stac_item(scene.get("stac_href") or "")
    if not item:
        return None
    assets = item.get("assets", {})

    try:
        import rasterio
        from rasterio.warp import transform_bounds
        from rasterio.windows import from_bounds as window_from_bounds
    except Exception as e:
        logger.warning("mining_monitor: rasterio unavailable: %s", e)
        return None

    bands: List[np.ndarray] = []
    win_transform = None

    for primary, fallback in BAND_ASSETS:
        asset = assets.get(primary) or assets.get(fallback)
        if not asset or not asset.get("href"):
            logger.debug("mining_monitor: scene %s missing band %s", scene.get("scene_id"), primary)
            return None
        try:
            with rasterio.open(asset["href"]) as ds:
                # bbox is WGS-84; the COG is usually UTM — reproject the bounds.
                left, bottom, right, top = transform_bounds(
                    "EPSG:4326", ds.crs, *bbox, densify_pts=21
                )
                window = window_from_bounds(left, bottom, right, top, ds.transform)
                arr = ds.read(
                    1,
                    window=window,
                    out_shape=(WINDOW_SIZE, WINDOW_SIZE),
                    boundless=True,
                    fill_value=0,
                ).astype(float)
                if win_transform is None:
                    # Transform of the resampled window, for real-world pixel size
                    win_transform = ds.window_transform(window) * rasterio.Affine.scale(
                        window.width / WINDOW_SIZE, window.height / WINDOW_SIZE
                    )
                bands.append(arr)
        except Exception as e:
            logger.warning(
                "mining_monitor: failed reading %s for %s: %s", primary, scene.get("scene_id"), e
            )
            return None

    if len(bands) != len(BAND_ASSETS):
        return None

    stack = np.stack(bands, axis=0)

    # Guard against boundless zero-fill: a window mostly outside the scene
    # footprint produces indices computed on padding, not imagery.
    zero_fraction = float((stack[0] == 0).mean())
    if zero_fraction > MAX_ZERO_FILL_FRACTION:
        logger.warning(
            "mining_monitor: scene %s covers too little of the ROI "
            "(%.1f%% of the window is zero-fill, limit %.0f%%) — rejecting",
            scene.get("scene_id"), zero_fraction * 100, MAX_ZERO_FILL_FRACTION * 100,
        )
        return None

    return stack, win_transform


def _boundary_mask(region: Dict[str, Any], transform: Any, shape: Tuple[int, int]) -> Optional[np.ndarray]:
    """Boolean mask, True INSIDE the region's approximate boundary.

    The mask is built in the raster's own CRS by reprojecting the WGS-84 ring.
    Returns None when the boundary cannot be rasterised, in which case callers
    must skip the outside-boundary signal rather than guess.
    """
    geom = boundary_to_geojson(region)
    if not geom or transform is None:
        return None
    try:
        from rasterio.features import geometry_mask
        from rasterio.warp import transform_geom

        # transform is in the COG's CRS; reproject the boundary to match.
        # We do not know the CRS here, so callers pass a transform already in
        # the scene CRS and we reproject from EPSG:4326 using the scene CRS
        # recorded on the region dict by the caller.
        target_crs = region.get("_scene_crs")
        if target_crs is None:
            return None
        projected = transform_geom("EPSG:4326", target_crs, geom)
        inside = geometry_mask(
            [projected], out_shape=shape, transform=transform, invert=True
        )
        return inside
    except Exception as e:
        logger.debug("mining_monitor: boundary mask failed: %s", e)
        return None


def _pixel_area_km2(transform: Any) -> Optional[float]:
    """Real-world area of one pixel in km², via the shared helper."""
    dims = get_pixel_dimensions_meters(transform)
    if not dims:
        return None
    dx, dy = dims
    if dx <= 0 or dy <= 0:
        return None
    return (dx * dy) / 1_000_000.0


def analyse_expansion(
    region: Dict[str, Any],
    before_scene: Dict[str, Any],
    after_scene: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Compute bare-ground expansion between two real acquisitions.

    Returns a metrics dict, or None when the pair cannot be analysed.
    """
    bbox = region["bbox"]

    before = load_region_stack(before_scene, bbox)
    if before is None:
        return None
    after = load_region_stack(after_scene, bbox)
    if after is None:
        return None

    before_bands, before_tf = before
    after_bands, after_tf = after
    if before_bands.shape != after_bands.shape:
        logger.debug("mining_monitor: shape mismatch, skipping")
        return None

    # --- Reused deterministic engine -----------------------------------------
    lc_before = compute_landcover_breakdown(before_bands)
    lc_after = compute_landcover_breakdown(after_bands)
    change = compute_change_area(before_bands, after_bands, after_tf)

    bare_before = float(lc_before.get("builtup_pct", 0.0))
    bare_after = float(lc_after.get("builtup_pct", 0.0))
    bare_delta_pp = bare_after - bare_before

    px_km2 = _pixel_area_km2(after_tf)
    total_px = int(before_bands.shape[1] * before_bands.shape[2])
    region_area_km2 = px_km2 * total_px if px_km2 else None
    expansion_km2 = (
        (bare_delta_pp / 100.0) * region_area_km2 if region_area_km2 is not None else None
    )

    metrics: Dict[str, Any] = {
        "check": "mining_expansion_check",
        "region": region["name"],
        "commodity": region.get("commodity"),
        "before_scene_id": before_scene.get("scene_id"),
        "after_scene_id": after_scene.get("scene_id"),
        "before_date": (before_scene.get("datetime") or "")[:10],
        "after_date": (after_scene.get("datetime") or "")[:10],
        "before_cloud_cover_pct": before_scene.get("cloud_cover"),
        "after_cloud_cover_pct": after_scene.get("cloud_cover"),
        "bare_ground_pct_before": round(bare_before, 3),
        "bare_ground_pct_after": round(bare_after, 3),
        "bare_ground_delta_pp": round(bare_delta_pp, 3),
        "analysed_area_km2": round(region_area_km2, 4) if region_area_km2 else None,
        "expansion_km2": round(expansion_km2, 4) if expansion_km2 is not None else None,
        "spectral_change_pct": change.get("change_pct"),
        "spectral_changed_area_km2": change.get("changed_area_km2"),
        "thresholds": {
            "expansion_km2": EXPANSION_THRESHOLD_KM2,
            "bare_delta_pp": EXPANSION_THRESHOLD_PP,
            "outside_boundary_pct": OUTSIDE_BOUNDARY_THRESHOLD_PCT,
        },
        # The caveat travels with the numbers, all the way to the UI.
        "boundary_is_approximate": region.get("boundary_is_approximate", True),
        "boundary_caveat": region.get("boundary_caveat"),
        "boundary_source": region.get("boundary_source"),
    }

    # --- Outside-boundary share (best effort) --------------------------------
    outside_pct = None
    inside = None
    try:
        import rasterio
        from rasterio.warp import transform_bounds  # noqa: F401  (import parity)
        item = _load_stac_item(after_scene.get("stac_href") or "")
        assets = (item or {}).get("assets", {})
        ref = assets.get("blue") or assets.get("B02")
        if ref and ref.get("href"):
            with rasterio.open(ref["href"]) as ds:
                region = {**region, "_scene_crs": ds.crs}
        inside = _boundary_mask(region, after_tf, before_bands.shape[1:])
        if inside is not None:
            # Newly bare pixels: NDBI-positive after, not before.
            newly_bare = _newly_bare_mask(before_bands, after_bands)
            total_new = int(newly_bare.sum())
            if total_new > 0:
                outside = int((newly_bare & ~inside).sum())
                outside_pct = round(100.0 * outside / total_new, 2)
                metrics["newly_bare_pixels"] = total_new
                metrics["newly_bare_outside_boundary_pixels"] = outside
    except Exception as e:
        logger.debug("mining_monitor: outside-boundary computation skipped: %s", e)

    metrics["newly_bare_outside_boundary_pct"] = outside_pct

    # ── Primary signal: newly-bare AREA INSIDE the boundary ──────────────────
    # The aggregate `bare_ground_delta_pp` above is computed across the whole
    # ~900 km² search bbox, where the mine occupies only a few percent.  Over a
    # multi-week gap, seasonal greening/browning of the surrounding farmland and
    # forest swings that share by double-digit percentage points and buries the
    # mining signal — observed directly: Jharia read -14.33 pp ("bare ground
    # halved") between two clear scenes, which no excavation can produce.
    #
    # Counting pixels that newly cross the NDBI bare threshold INSIDE the
    # approximate boundary is far more targeted: it ignores the surrounding
    # landscape entirely.  It does NOT fully remove phenology inside the
    # boundary, so it remains an indicative triage signal, not a measurement.
    try:
        if inside is not None and px_km2 is not None:
            newly_bare = _newly_bare_mask(before_bands, after_bands)
            inside_new = int((newly_bare & inside).sum())
            metrics["newly_bare_inside_boundary_pixels"] = inside_new
            metrics["expansion_inside_boundary_km2"] = round(inside_new * px_km2, 4)
            metrics["boundary_area_km2"] = round(int(inside.sum()) * px_km2, 4)
        else:
            metrics["expansion_inside_boundary_km2"] = None
            metrics["boundary_area_km2"] = None
    except Exception as e:
        logger.debug("mining_monitor: inside-boundary expansion skipped: %s", e)
        metrics["expansion_inside_boundary_km2"] = None
        metrics["boundary_area_km2"] = None

    return metrics


def _ndbi(bands: np.ndarray) -> np.ndarray:
    """NDBI = (SWIR1 - NIR)/(SWIR1 + NIR). Mirrors compute_landcover_breakdown."""
    nir = bands[3]
    swir1 = bands[4]
    denom = swir1 + nir
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(denom != 0, (swir1 - nir) / denom, -1.0)
    return np.nan_to_num(out, nan=-1.0)


def _ndwi(bands: np.ndarray) -> np.ndarray:
    """NDWI = (Green - NIR)/(Green + NIR). Mirrors compute_landcover_breakdown."""
    green = bands[1]
    nir = bands[3]
    denom = green + nir
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(denom != 0, (green - nir) / denom, -1.0)
    return np.nan_to_num(out, nan=-1.0)


def _newly_bare_mask(before_bands: np.ndarray, after_bands: np.ndarray) -> np.ndarray:
    """Pixels that became built-up/bare between the two dates (NDBI crossing 0).

    Water exclusion — why it is here:
        Visual inspection of the Feb->Apr Jharia mask showed a large share of the
        flagged pixels tracing the river channel, not mine workings. Pre-monsoon
        drawdown exposes sandy riverbed, which NDBI legitimately reads as "newly
        bare" but which is seasonal hydrology, not excavation. Any pixel that was
        water on the BEFORE date is therefore excluded: a mine cannot expand into
        what was open water within one season, so this only removes false
        positives.
    """
    became_bare = (_ndbi(after_bands) > 0.0) & (_ndbi(before_bands) <= 0.0)
    was_water = _ndwi(before_bands) > 0.0
    return became_bare & ~was_water


def select_scene_pair(region: Dict[str, Any]) -> Optional[Tuple[Dict, Dict]]:
    """Pick the two least-cloudy, well-separated scenes for a region.

    Monsoon months over Indian mining belts run 90-100% cloud, so a naive
    "two most recent scenes" choice yields meaningless NDBI. This picks the
    clearest recent scene as `after` and the clearest sufficiently-older scene
    as `before`.
    """
    scenes = analysis_db.get_scenes_covering_bbox(
        region["bbox"],
        min_coverage=MIN_SCENE_COVERAGE,
        limit=100,
        since_days=365,
        collection="sentinel-2-l2a",
    )
    usable = [
        s for s in scenes
        if s.get("cloud_cover") is not None
        and float(s["cloud_cover"]) <= MAX_CLOUD_COVER_PCT
    ]
    if len(usable) < 2:
        logger.info(
            "mining_monitor: %s has %d scene(s) meeting BOTH >=%.0f%% ROI coverage "
            "and <=%.0f%% cloud — need 2. Refusing to analyse on unusable imagery.",
            region["name"], len(usable), MIN_SCENE_COVERAGE * 100, MAX_CLOUD_COVER_PCT,
        )
        return None

    from datetime import datetime

    def parsed(s):
        return datetime.fromisoformat(s["datetime"].replace("Z", "+00:00"))

    # Enumerate every (before, after) pair separated by at least the minimum
    # interval and score them, rather than fixing `after` first.  Choosing the
    # clearest of the N most recent scenes up front can land on the OLDEST of
    # that group, leaving no valid `before` and silently reporting "no data".
    candidates = []
    for after_scene in usable:
        for before_scene in usable:
            gap = (parsed(after_scene) - parsed(before_scene)).days
            if gap < MIN_SEPARATION_DAYS:
                continue
            cloud_sum = float(after_scene["cloud_cover"]) + float(before_scene["cloud_cover"])
            # Prefer clear imagery first, then the more recent `after`.
            candidates.append((cloud_sum, -parsed(after_scene).timestamp(), before_scene, after_scene))

    if not candidates:
        logger.info(
            "mining_monitor: %s has %d usable scene(s) but no pair separated by "
            ">=%d days. Refusing to analyse.",
            region["name"], len(usable), MIN_SEPARATION_DAYS,
        )
        return None

    candidates.sort(key=lambda c: (c[0], c[1]))
    _, _, before, after = candidates[0]
    logger.info(
        "mining_monitor: %s pair selected before=%s (%.1f%% cloud) after=%s (%.1f%% cloud), gap=%dd",
        region["name"], before["scene_id"], before["cloud_cover"],
        after["scene_id"], after["cloud_cover"],
        (parsed(after) - parsed(before)).days,
    )
    return before, after


def evaluate_region(region: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Full pipeline for one region: select a pair, analyse, decide severity."""
    pair = select_scene_pair(region)
    if pair is None:
        return None
    before, after = pair

    metrics = analyse_expansion(region, before, after)
    if metrics is None:
        return None

    # Primary: newly-bare area inside the boundary. Falls back to the whole-bbox
    # figure only when the boundary could not be rasterised, and that fallback is
    # recorded so a reader knows which signal drove the alert.
    inside_km2 = metrics.get("expansion_inside_boundary_km2")
    if inside_km2 is not None:
        expansion_km2 = inside_km2
        metrics["trigger_basis"] = "inside_boundary"
    else:
        expansion_km2 = metrics.get("expansion_km2")
        metrics["trigger_basis"] = "whole_bbox_fallback"

    bare_delta = metrics.get("bare_ground_delta_pp") or 0.0
    outside_pct = metrics.get("newly_bare_outside_boundary_pct")

    area_trip = expansion_km2 is not None and expansion_km2 >= EXPANSION_THRESHOLD_KM2
    pp_trip = bare_delta >= EXPANSION_THRESHOLD_PP
    outside_trip = (
        outside_pct is not None and outside_pct >= OUTSIDE_BOUNDARY_THRESHOLD_PCT
    )

    metrics["triggers"] = {
        "expansion_area": bool(area_trip),
        "bare_share_rise": bool(pp_trip),
        "outside_boundary": bool(outside_trip),
    }

    if not (area_trip or pp_trip or outside_trip):
        return None

    # Outside-boundary expansion escalates, but never beyond "warning" on an
    # approximate boundary — an approximation must not drive a critical call.
    if area_trip and pp_trip and outside_trip:
        severity = "warning" if region.get("boundary_is_approximate", True) else "critical"
    elif area_trip or pp_trip:
        severity = "warning"
    else:
        severity = "info"

    return {"severity": severity, "computed_metrics": metrics}


def mining_expansion_check(
    roi: Dict[str, Any], context: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Alert-check function registered with the STAC daemon (Prompt 1 contract).

    Only acts on ROIs that carry a mining `commodity` key, so it stays inert for
    the disaster/flood ROIs the daemon also polls.
    """
    if not roi.get("commodity"):
        return None

    try:
        verdict = evaluate_region(roi)
    except Exception as e:
        logger.warning("mining_expansion_check failed for %s: %s", roi.get("name"), e)
        return None

    if not verdict:
        return None

    return {
        "alert_type": "land_change",
        "severity": verdict["severity"],
        "computed_metrics": verdict["computed_metrics"],
        # Same scene pair = same condition: raise it once, not every cycle.
        "dedupe_key": "{}->{}".format(
            verdict["computed_metrics"].get("before_scene_id"),
            verdict["computed_metrics"].get("after_scene_id"),
        ),
    }


def register() -> None:
    """Attach this specialist to the daemon's alert-check registry."""
    from stac_catalog import register_alert_check
    register_alert_check(mining_expansion_check)
