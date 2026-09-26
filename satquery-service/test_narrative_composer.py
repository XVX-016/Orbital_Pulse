"""Verification harness for narrative_composer.compose_narrative().

Runs the composer against TWO different real bi-temporal Sentinel-2 pairs drawn
from the live PostGIS catalog, and asserts:

  1. The two pairs really do have different NDVI / land-cover numbers
     (otherwise the test proves nothing).
  2. Their composed narratives differ.
  3. REGRESSION — the "same number rendered twice" bug.
     compute_ndvi_coverage() and compute_landcover_breakdown() both emit a key
     named `vegetation_pct` holding DIFFERENT values.  When those two source
     values differ, both must appear verbatim in the narrative.  A composer that
     flattens the metric families would print one of them twice and fail here.

Requires network access (reads public Sentinel-2 L2A COGs from AWS) and a
populated catalogued_scenes table.  Run inside the service container:

    docker compose exec satquery-service python test_narrative_composer.py
"""

import sys
from typing import Any, Dict, List, Optional

import numpy as np
import rasterio

import db as analysis_db
from geospatial_metrics import (
    compute_change_area,
    compute_landcover_breakdown,
    compute_ndvi_coverage,
)
from narrative_composer import compose_narrative

# Two ROIs far enough apart that their surface cover genuinely differs.
ROI_TARGETS = [
    {"name": "Amazon_Rondonia", "bbox": [-62.2, -10.2, -61.8, -9.8]},
    {"name": "California_Wildfire", "bbox": [-122.5, 37.5, -121.5, 38.5]},
]

# Sentinel-2 L2A asset keys in the band order geospatial_metrics expects:
# index 0=blue, 1=green, 2=red, 3=nir, 4=swir1
BAND_ASSETS = [
    ("blue", "B02"),
    ("green", "B03"),
    ("red", "B04"),
    ("nir", "B08"),
    ("swir16", "B11"),
]

OVERVIEW = 256  # downsampled read — keeps the network cost sane


def _load_stac_item(href: str) -> Optional[Dict[str, Any]]:
    import json
    import urllib.request
    try:
        req = urllib.request.Request(href, headers={"User-Agent": "SatQuery/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"    ! could not load STAC item {href}: {e}")
        return None


def load_band_stack(scene: Dict[str, Any]) -> Optional[np.ndarray]:
    """Read a real 5-band stack for one catalogued scene. None if unavailable."""
    item = _load_stac_item(scene.get("stac_href") or "")
    if not item:
        return None
    assets = item.get("assets", {})

    bands: List[np.ndarray] = []
    for primary, fallback in BAND_ASSETS:
        asset = assets.get(primary) or assets.get(fallback)
        if not asset or not asset.get("href"):
            print(f"    ! scene {scene.get('scene_id')} missing band {primary}/{fallback}")
            return None
        try:
            with rasterio.open(asset["href"]) as ds:
                bands.append(ds.read(1, out_shape=(OVERVIEW, OVERVIEW)).astype(float))
        except Exception as e:
            print(f"    ! failed reading {primary} for {scene.get('scene_id')}: {e}")
            return None

    return np.stack(bands, axis=0)


def build_pair_metrics(roi: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Assemble a real change-VQA metrics dict for one ROI, or None."""
    print(f"  [{roi['name']}] querying catalog...")
    scenes = analysis_db.get_scenes_in_bbox(roi["bbox"], limit=40, since_days=365)
    scenes = [s for s in scenes if s.get("collection") == "sentinel-2-l2a"]
    if len(scenes) < 2:
        print(f"    ! only {len(scenes)} sentinel-2 scenes catalogued for this ROI")
        return None

    # scenes come back newest-first; pick the newest and the oldest DISTINCT date
    after_scene = scenes[0]
    after_date = after_scene["datetime"][:10]
    before_scene = next(
        (s for s in scenes if s["datetime"][:10] != after_date), None
    )
    if before_scene is None:
        print("    ! no second distinct acquisition date available")
        return None

    print(f"    before: {before_scene['scene_id']} ({before_scene['datetime'][:10]})")
    print(f"    after:  {after_scene['scene_id']} ({after_scene['datetime'][:10]})")

    before_bands = load_band_stack(before_scene)
    if before_bands is None:
        return None
    after_bands = load_band_stack(after_scene)
    if after_bands is None:
        return None

    metrics = {
        "task": "change_vqa",
        "georeferenced": True,
        "before_ndvi": compute_ndvi_coverage(before_bands),
        "after_ndvi": compute_ndvi_coverage(after_bands),
        "before_landcover": compute_landcover_breakdown(before_bands),
        "after_landcover": compute_landcover_breakdown(after_bands),
        "spectral_change": compute_change_area(before_bands, after_bands),
    }
    # Single-image families too, so the collision regression has something to bite on
    metrics["ndvi"] = metrics["after_ndvi"]
    metrics["landcover"] = metrics["after_landcover"]
    return metrics


def check_collision(tag: str, metrics: Dict[str, Any], narrative: str) -> List[str]:
    """The core regression: distinct `vegetation_pct` values must both render."""
    failures: List[str] = []
    ndvi_veg = metrics["ndvi"].get("vegetation_pct")
    lc_veg = metrics["landcover"].get("vegetation_pct")

    print(f"    ndvi.vegetation_pct      = {ndvi_veg}")
    print(f"    landcover.vegetation_pct = {lc_veg}")

    if ndvi_veg is None or lc_veg is None:
        failures.append(f"[{tag}] missing vegetation_pct on one metric family")
        return failures

    if abs(float(ndvi_veg) - float(lc_veg)) < 1e-9:
        print(f"    (source values coincide here — collision check not "
              f"discriminating for {tag}, skipping)")
        return failures

    ndvi_str = f"{float(ndvi_veg):.1f}%"
    lc_str = f"{float(lc_veg):.1f}%"
    if ndvi_str not in narrative:
        failures.append(
            f"[{tag}] NDVI vegetation_pct {ndvi_str} absent from narrative "
            f"(collision bug: likely overwritten by land-cover's key)"
        )
    if lc_str not in narrative:
        failures.append(
            f"[{tag}] land-cover vegetation_pct {lc_str} absent from narrative "
            f"(collision bug: likely overwritten by NDVI's key)"
        )
    return failures


def main() -> int:
    print("=" * 78)
    print("Narrative composer verification — two real Sentinel-2 pairs")
    print("=" * 78)

    results = []
    for roi in ROI_TARGETS:
        m = build_pair_metrics(roi)
        if m is None:
            print(f"\nFAILED: could not assemble a real pair for {roi['name']}.")
            print("This test requires live network access and a populated catalog.")
            return 1
        results.append((roi["name"], m))

    failures: List[str] = []
    narratives = []

    for name, metrics in results:
        narrative = compose_narrative(
            answer=f"The imagery over {name.replace('_', ' ')} shows visible surface change between the two dates.",
            computed_metrics=metrics,
            task_type="change_vqa",
        )
        narratives.append((name, narrative))

        print(f"\n--- {name} " + "-" * (70 - len(name)))
        print(f"    mean NDVI before = {metrics['before_ndvi']['mean_ndvi']:.4f}")
        print(f"    mean NDVI after  = {metrics['after_ndvi']['mean_ndvi']:.4f}")
        print(f"    change_pct       = {metrics['spectral_change']['change_pct']:.2f}")
        failures += check_collision(name, metrics, narrative)
        print(f"\n    NARRATIVE:\n    {narrative}\n")

    # --- Cross-pair assertions -----------------------------------------------
    print("=" * 78)
    print("Cross-pair assertions")
    print("=" * 78)

    (name_a, m_a), (name_b, m_b) = results
    ndvi_a = m_a["after_ndvi"]["mean_ndvi"]
    ndvi_b = m_b["after_ndvi"]["mean_ndvi"]
    lc_a = m_a["after_landcover"]["vegetation_pct"]
    lc_b = m_b["after_landcover"]["vegetation_pct"]

    print(f"  mean NDVI:        {name_a}={ndvi_a:.4f}  {name_b}={ndvi_b:.4f}")
    print(f"  landcover veg %:  {name_a}={lc_a:.2f}   {name_b}={lc_b:.2f}")

    if abs(ndvi_a - ndvi_b) < 1e-6:
        failures.append("The two pairs have identical mean NDVI — test is not discriminating.")
    if abs(lc_a - lc_b) < 1e-6:
        failures.append("The two pairs have identical land-cover vegetation % — test is not discriminating.")
    if narratives[0][1] == narratives[1][1]:
        failures.append("Both pairs produced an IDENTICAL narrative.")

    print()
    if failures:
        print("FAILURES:")
        for f in failures:
            print(f"  ✗ {f}")
        return 1

    print("  ✓ the two pairs have genuinely different NDVI and land-cover numbers")
    print("  ✓ their narratives differ")
    print("  ✓ distinct vegetation_pct values both render — no key-collision regression")
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
