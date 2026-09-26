"""Convective development risk from INSAT TIR-1 cloud-top cooling (Track B, Prompt 8).

Computes the cloud-top cooling rate dT_B/dt, normalised to K per 15 min, from
consecutive REAL thermal-IR frames stored by insat_ingest.py, and raises a
`severe_weather` alert reading "elevated convective development risk" when the
cooling crosses published convective-initiation criteria.

WHAT THIS IS NOT
    Not a lightning-strike, hail or location forecast.  Output is a regional
    risk flag; the alert geometry is the whole monitored region, never a point.

CRITERIA (conservative, from the literature)
    • Roberts & Rutledge (2003), "Nowcasting storm initiation and growth using
      GOES-8 and WSR-88D data", Weather and Forecasting 18:562–584:
      10.7 µm cooling of −4 K/15 min indicates weak cumulus growth and
      ≤ −8 K/15 min strong growth, typically preceding the first radar echo.
    • Mecikalski & Bedka (2006), "Forecasting convective initiation by monitoring
      the evolution of moving cumulus in daytime GOES imagery", Monthly Weather
      Review 134:49–78: 15-min IR trend < −4 K and cloud tops colder than 0 °C
      (273 K) are among the convective-initiation interest fields.
    Real severe cooling is single-digit K/15 min.  A regional rate beyond
    SUSPICIOUS_RATE (−10 K/15 min) is treated as a probable data problem
    (mis-registration, time-stamp error, fill values) and is capped at `info`
    and flagged for re-verification against the raw frame values, never trusted.

GATE
    Runs only after the Prompt 7 verification gate is open
    (db.insat_pipeline_verified) and only on frames whose automatic provenance
    checks passed.  Otherwise it returns None and says why.

METHOD
    INSAT L1C sector products sit on a fixed grid, so consecutive frames can be
    differenced pixel-by-pixel.  For each consecutive pair 10–45 min apart:
      rate = (BT_after − BT_before) × 15 / Δt_minutes          [K / 15 min]
    evaluated only on pixels whose cloud top is below freezing after the step
    (BT_after < 273.15 K).  The regional rate is the 10th percentile of those
    pixels — the strongly-cooling tail, but not a single outlier pixel.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

import db as analysis_db

logger = logging.getLogger(__name__)

WEAK_GROWTH_RATE = -4.0      # K / 15 min  (Roberts & Rutledge 2003)
STRONG_GROWTH_RATE = -8.0    # K / 15 min  (Roberts & Rutledge 2003)
SUSPICIOUS_RATE = -10.0      # K / 15 min  beyond this: re-verify, do not trust
FREEZING_K = 273.15          # cloud top colder than 0 °C (Mecikalski & Bedka 2006)
TAIL_PERCENTILE = 10
MIN_PAIR_MINUTES = 10
MAX_PAIR_MINUTES = 45
# Minimum area of cooling cloud before any flag — ignores a few noisy pixels.
MIN_AREA_KM2 = float(os.environ.get("STORM_MIN_AREA_KM2", "150"))
MIN_CANDIDATE_PIXELS = 6
FRAMES_TO_CONSIDER = 6

RISK_LABEL = "Elevated convective development risk"
DISCLAIMER = (
    "Regional risk indicator from satellite cloud-top cooling. Not a lightning, "
    "hail or storm-location forecast."
)


def _t(frame: Dict[str, Any]) -> datetime:
    return datetime.fromisoformat(str(frame["acquired_at"]).replace("Z", "+00:00"))


def cooling_step(before: Dict[str, Any], after: Dict[str, Any], minutes: float, pixel_km2: float) -> Dict[str, Any]:
    """Cooling statistics for one consecutive pair of co-registered frames.

    before/after: {"bt": 2-D K, "lat": 2-D, "lon": 2-D}
    """
    if before["bt"].shape != after["bt"].shape:
        return {"usable": False, "reason": f"grid shape changed {before['bt'].shape} → {after['bt'].shape}"}
    if float(np.nanmax(np.abs(before["lat"] - after["lat"]))) > 0.01 or \
            float(np.nanmax(np.abs(before["lon"] - after["lon"]))) > 0.01:
        return {"usable": False, "reason": "frames are not on the same grid (lat/lon differ > 0.01°)"}

    b = before["bt"].astype(np.float64)
    a = after["bt"].astype(np.float64)
    rate = (a - b) * (15.0 / minutes)
    valid = np.isfinite(rate)
    cold = valid & (a < FREEZING_K)
    n_cold = int(cold.sum())

    out: Dict[str, Any] = {
        "usable": True,
        "minutes": round(minutes, 1),
        "valid_pixels": int(valid.sum()),
        "below_freezing_pixels": n_cold,
        "pixel_area_km2": round(pixel_km2, 3),
        "median_rate_all_k_per_15min": round(float(np.nanmedian(rate[valid])), 2) if valid.any() else None,
    }
    if n_cold < MIN_CANDIDATE_PIXELS:
        out.update({"regional_rate_k_per_15min": None, "weak_growth_area_km2": 0.0, "strong_growth_area_km2": 0.0,
                    "note": "too few below-freezing cloud-top pixels to assess"})
        return out

    r = rate[cold]
    out.update({
        "regional_rate_k_per_15min": round(float(np.percentile(r, TAIL_PERCENTILE)), 2),
        "weak_growth_area_km2": round(float((r <= WEAK_GROWTH_RATE).sum()) * pixel_km2, 1),
        "strong_growth_area_km2": round(float((r <= STRONG_GROWTH_RATE).sum()) * pixel_km2, 1),
        "pixels_beyond_suspicious_rate": int((r < SUSPICIOUS_RATE).sum()),
        "coldest_bt_after_k": round(float(np.nanmin(a[cold])), 2),
    })
    return out


def assess(frames: List[Dict[str, Any]], arrays: List[Dict[str, np.ndarray]], pixel_km2: float) -> Dict[str, Any]:
    """Assess the newest consecutive pairs.  frames/arrays are oldest → newest.

    Pure function (no DB, no network) so it can be unit-tested.
    """
    steps = []
    for i in range(1, len(frames)):
        minutes = (_t(frames[i]) - _t(frames[i - 1])).total_seconds() / 60.0
        if not (MIN_PAIR_MINUTES <= minutes <= MAX_PAIR_MINUTES):
            continue
        step = cooling_step(arrays[i - 1], arrays[i], minutes, pixel_km2)
        step["before_identifier"] = frames[i - 1]["identifier"]
        step["after_identifier"] = frames[i]["identifier"]
        step["before_time"] = str(frames[i - 1]["acquired_at"])
        step["after_time"] = str(frames[i]["acquired_at"])
        steps.append(step)

    usable = [s for s in steps if s.get("usable") and s.get("regional_rate_k_per_15min") is not None]
    result: Dict[str, Any] = {
        "check": "storm_risk_check",
        "method": "INSAT TIR-1 cloud-top cooling rate, pixel-wise, below-freezing tops, p10",
        "criteria": {
            "weak_growth_k_per_15min": WEAK_GROWTH_RATE,
            "strong_growth_k_per_15min": STRONG_GROWTH_RATE,
            "suspicious_beyond_k_per_15min": SUSPICIOUS_RATE,
            "min_area_km2": MIN_AREA_KM2,
            "sources": [
                "Roberts & Rutledge (2003), Weather and Forecasting 18:562-584",
                "Mecikalski & Bedka (2006), Monthly Weather Review 134:49-78",
            ],
        },
        "steps": steps,
        "disclaimer": DISCLAIMER,
    }
    if not usable:
        result.update({"status": "insufficient_data", "risk": None})
        return result

    latest = usable[-1]
    prev = usable[-2] if len(usable) >= 2 else None
    rate = latest["regional_rate_k_per_15min"]
    suspicious = rate < SUSPICIOUS_RATE
    weak = rate <= WEAK_GROWTH_RATE and latest["weak_growth_area_km2"] >= MIN_AREA_KM2
    strong = rate <= STRONG_GROWTH_RATE and latest["strong_growth_area_km2"] >= MIN_AREA_KM2
    sustained = bool(prev and prev["regional_rate_k_per_15min"] <= WEAK_GROWTH_RATE
                     and prev["weak_growth_area_km2"] >= MIN_AREA_KM2)

    result.update({
        "latest_rate_k_per_15min": rate,
        "latest_step_minutes": latest["minutes"],
        "latest_after_time": latest["after_time"],
        "weak_growth_area_km2": latest["weak_growth_area_km2"],
        "strong_growth_area_km2": latest["strong_growth_area_km2"],
        "sustained_over_two_steps": sustained,
        "suspicious_rate": suspicious,
    })

    if suspicious:
        # A regional cooling rate this extreme is far more likely to be a data
        # fault than weather.  Surface it, but never escalate on it.
        result.update({
            "status": "needs_reverification",
            "risk": RISK_LABEL + " (UNVERIFIED — cooling rate implausibly fast)",
            "severity": "info",
            "reverify": (
                f"Regional rate {rate} K/15 min is beyond {SUSPICIOUS_RATE} K/15 min. Re-check the raw counts "
                f"and timestamps of {latest['before_identifier']} and {latest['after_identifier']} with "
                "`python insat_ingest.py verify` before trusting this."
            ),
        })
        return result

    if strong and sustained:
        severity = "warning"
    elif strong or weak:
        severity = "info"
    else:
        result.update({"status": "no_elevated_risk", "risk": None})
        return result

    result.update({"status": "elevated", "risk": RISK_LABEL, "severity": severity})
    return result


def gate_status(dataset_id: Optional[str] = None) -> Dict[str, Any]:
    from insat_ingest import DATASET_ID
    ds = dataset_id or DATASET_ID
    open_ = analysis_db.insat_pipeline_verified(ds)
    return {
        "dataset_id": ds,
        "open": open_,
        "reason": None if open_ else (
            "INSAT feed not yet manually verified against the MOSDAC archive "
            "(run `python insat_ingest.py verify`, then `confirm <frame_id>`)."
        ),
    }


def assess_region(region: Dict[str, Any]) -> Dict[str, Any]:
    """Load the region's newest verified-provenance frames and assess them."""
    from insat_ingest import DATASET_ID, load_frame_arrays

    gate = gate_status(DATASET_ID)
    if not gate["open"]:
        return {"check": "storm_risk_check", "status": "gate_closed", "risk": None, "gate": gate}

    frames = analysis_db.get_insat_frames(
        region_name=region["name"], limit=FRAMES_TO_CONSIDER, only_auto_passed=True
    )
    frames = [f for f in frames if f.get("dataset_id") == DATASET_ID]
    if len(frames) < 2:
        return {"check": "storm_risk_check", "status": "insufficient_data", "risk": None,
                "frames_available": len(frames), "gate": gate}
    frames = list(reversed(frames))  # oldest → newest
    arrays = []
    for f in frames:
        try:
            arrays.append(load_frame_arrays(f))
        except Exception as e:
            return {"check": "storm_risk_check", "status": "insufficient_data", "risk": None,
                    "error": f"could not load stored array for frame {f['id']}: {e}", "gate": gate}
    pixel_km2 = float((frames[-1].get("stats") or {}).get("pixel_area_km2") or float("nan"))
    if not np.isfinite(pixel_km2):
        return {"check": "storm_risk_check", "status": "insufficient_data", "risk": None,
                "error": "pixel area unknown", "gate": gate}
    out = assess(frames, arrays, pixel_km2)
    out["region"] = region["name"]
    out["frame_ids"] = [f["id"] for f in frames]
    out["dataset_id"] = DATASET_ID
    out["gate"] = gate
    return out


def storm_risk_check(roi: Dict[str, Any], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Alert-check function (Prompt 1 contract).  Acts only on INSAT-monitored ROIs."""
    if not roi.get("insat_monitored"):
        return None
    result = assess_region(roi)
    if result.get("status") == "gate_closed":
        logger.info("storm_risk: gate closed for %s — %s", roi["name"], result["gate"]["reason"])
        return None
    if result.get("status") not in ("elevated", "needs_reverification"):
        return None
    return {
        "alert_type": "severe_weather",
        "severity": result["severity"],
        "computed_metrics": result,
        # One alert per newest frame step, not one per poll.
        "dedupe_key": f"{result.get('dataset_id')}:{result.get('latest_after_time')}",
        # Whole-region footprint: never a point, never a strike location.
    }


def register() -> None:
    from stac_catalog import register_alert_check
    register_alert_check(storm_risk_check)
