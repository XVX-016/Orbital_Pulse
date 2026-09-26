"""Lightweight STAC Cataloging Service.

Metadata-only ingestion:
- Queries Earth Search STAC API (https://earth-search.aws.element84.com/v1/search)
- Collections vary per ROI — optical for deforestation/wildfire, SAR-first for flood regions.
- Regions: Amazon deforestation (Rondônia), California wildfire, Bangladesh flood delta,
  SE Australian bushfire zone.
- Runs as an asynchronous background loop on a configurable interval
  (CATALOG_POLL_INTERVAL_HOURS, default 24 h; or CATALOG_POLL_INTERVAL_MINUTES in dev).
- Deduplicates on scene_id in PostGIS table `catalogued_scenes`.
- Provides fetch_bitemporal_pair_for_roi() to materialise real bi-temporal GeoTIFF pairs
  from the catalog, replacing synthetic placeholder files on disk.
- After each poll cycle, runs registered alert-check functions against every ROI
  flagged `monitored` and persists triggered alerts to PostGIS `monitoring_alerts`.
"""

import asyncio
import hashlib
import io
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

import db as analysis_db

logger = logging.getLogger(__name__)

EARTH_SEARCH_URL = "https://earth-search.aws.element84.com/v1/search"

# ─── Regions of interest ──────────────────────────────────────────────────────
# Each entry carries:
#   name          – slug used in logs and as scenario dir name
#   bbox          – [min_lon, min_lat, max_lon, max_lat] in WGS-84
#   collections   – preferred STAC collections, tried in order; falls back to
#                   sentinel-2-l2a if the first multi-collection query fails
#   scenario_dir  – local data/<dir>/ folder that holds before.tif / after.tif
#                   (set None to skip bi-temporal materialisation for that ROI)
#   monitored     – when True, the daemon runs every registered alert-check
#                   function against this ROI after each poll cycle and persists
#                   any triggered alert to monitoring_alerts.  Set False to keep
#                   ingesting scenes for an ROI without raising alerts on it.
#
# Disaster relevance notes:
#   • Amazon / Rondônia   → optical only; no permanent water, SAR less useful
#   • California wildfire → optical primary; SAR detects burn-scars but noisier
#   • Bangladesh delta    → Sentinel-1 SAR is the workhorse (cloud-persistent floods)
#   • SE Australia        → optical primary; MODIS/Landsat burn-area products
DEFAULT_ROIS: List[Dict[str, Any]] = [
    {
        "name": "Amazon_Rondonia",
        "bbox": [-62.2, -10.2, -61.8, -9.8],  # Ji-Paraná / Ariquemes corridor
        "collections": ["sentinel-2-l2a", "landsat-c2-l2"],
        "scenario_dir": "deforestation",       # maps to data/deforestation/
        "monitored": True,
        "skip_materialization": True,          # Hand-verified multi-band scenario data preserved
    },
    {
        "name": "California_Wildfire",
        "bbox": [-122.5, 37.5, -121.5, 38.5],  # East Bay / Diablo Range
        "collections": ["sentinel-2-l2a", "landsat-c2-l2", "sentinel-1-grd"],
        "scenario_dir": "disaster",             # maps to data/disaster/
        "monitored": True,
    },
    {
        "name": "Bangladesh_Delta_Flood",
        "bbox": [89.5, 22.5, 91.5, 24.5],       # Brahmaputra/Ganges confluence
        "collections": ["sentinel-1-grd", "sentinel-2-l2a"],  # SAR first for flood
        "scenario_dir": None,                   # no local scenario dir yet
        "monitored": True,
    },
    {
        "name": "SE_Australia_Bushfire",
        "bbox": [147.0, -38.0, 150.0, -35.5],  # NSW south coast / Snowy Mountains
        "collections": ["sentinel-2-l2a", "landsat-c2-l2"],
        "scenario_dir": None,
        "monitored": True,
    },
]

# ─── Monitored mining regions (Track A) ───────────────────────────────────────
# Appended to DEFAULT_ROIS so the existing ingestion daemon and alert pass cover
# them with no special-casing.  Their boundary polygons are APPROXIMATIONS — see
# mining_regions.py for the full provenance caveat.
try:
    from mining_regions import MINING_REGIONS
    DEFAULT_ROIS.extend(MINING_REGIONS)
except Exception as _mining_err:  # pragma: no cover - import guard
    logger.warning("Could not load mining regions: %s", _mining_err)

# Flat list of all distinct collections across ROIs (used for fallback single-ROI fetches)
DEFAULT_COLLECTIONS = ["sentinel-2-l2a", "sentinel-1-grd", "landsat-c2-l2"]


def _extract_thumbnail(item: Dict[str, Any]) -> Optional[str]:
    """Extract accessible thumbnail URL from STAC item assets or links."""
    assets = item.get("assets", {})
    for key in ["thumbnail", "overview", "rendered_preview", "preview"]:
        if key in assets and "href" in assets[key]:
            href = assets[key]["href"]
            # Convert s3:// or keep https://
            if href.startswith("http://") or href.startswith("https://"):
                return href
            elif href.startswith("s3://"):
                # e.g., s3://sentinel-s1-l1c/...
                return href

    # Check item links for thumbnail rel
    for link in item.get("links", []):
        if link.get("rel") == "thumbnail" and "href" in link:
            return link["href"]

    return None


def fetch_stac_scenes(
    collections: List[str] = DEFAULT_COLLECTIONS,
    bbox: List[float] = None,
    limit: int = 15,
    datetime_range: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Synchronous call to Earth Search STAC API to retrieve recent scenes.

    datetime_range: optional RFC-3339 interval, e.g.
        "2026-07-01T00:00:00Z/2026-09-17T23:59:59Z".
        Omitted (the default) preserves the original "most recent scenes"
        behaviour that the daemon relies on.
    """
    if bbox is None:
        bbox = DEFAULT_ROIS[0]["bbox"]

    payload = {
        "collections": collections,
        "bbox": bbox,
        "limit": limit,
    }
    if datetime_range:
        payload["datetime"] = datetime_range

    try:
        req = urllib.request.Request(
            EARTH_SEARCH_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "SatQuery-Cataloger/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("features", [])
    except urllib.error.HTTPError as e:
        logger.warning(f"STAC fetch HTTPError {e.code}: {e.reason}")
        # If multi-collection fails, fallback to sentinel-2-l2a only
        if len(collections) > 1:
            logger.info("Falling back to single collection ['sentinel-2-l2a']")
            return fetch_stac_scenes(collections=["sentinel-2-l2a"], bbox=bbox, limit=limit, datetime_range=datetime_range)
        return []
    except Exception as e:
        logger.warning(f"STAC fetch failed: {e}")
        return []


def fetch_live_scene_for_point(
    lon: float,
    lat: float,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    collection: Optional[str] = None,
    delta: float = 0.15,
    limit: int = 10,
) -> Optional[Dict[str, Any]]:
    """On-demand Earth Search STAC query for a single geographic point.

    Used as a live fallback when ``find_scene_by_location()`` returns no match,
    allowing any global coordinate to be served without pre-catalogued coverage.

    Reuses ``fetch_stac_scenes()`` internally — no logic is duplicated.

    Args:
        lon, lat:    WGS-84 coordinate of the point of interest.
        start_date:  ISO-8601 lower bound for scene datetime (optional, not yet
                     forwarded to STAC but reserved for future date filtering).
        end_date:    ISO-8601 upper bound for scene datetime (optional).
        collection:  Preferred STAC collection; if None, tries sentinel-2-l2a
                     then sentinel-1-grd then landsat-c2-l2 in order.
        delta:       Half-width of the bounding box in degrees (default 0.15°,
                     ≈ 16 km at the equator — tight enough to avoid selecting a
                     scene from a distant adjacent tile).
        limit:       Maximum number of candidate items to request from STAC.

    Returns:
        A scene dict compatible with ``fetch_scene_cog_data()``, or ``None`` if
        no suitable scene was found.  Includes the raw STAC item under key
        ``stac_item`` for callers that need extra asset links.
    """
    bbox = [lon - delta, lat - delta, lon + delta, lat + delta]
    collections = (
        [collection]
        if collection
        else ["sentinel-2-l2a", "sentinel-1-grd", "landsat-c2-l2"]
    )

    logger.info(
        "fetch_live_scene_for_point: querying STAC for (%.4f, %.4f) bbox=%s collections=%s",
        lon, lat, bbox, collections,
    )

    items = fetch_stac_scenes(collections=collections, bbox=bbox, limit=limit)
    if not items:
        logger.info(
            "fetch_live_scene_for_point: no scenes within ±%.2f° of (%.4f, %.4f) "
            "for collections %s",
            delta, lon, lat, collections,
        )
        return None

    # Pick the scene with the lowest cloud cover; fall back to first (most recent,
    # since Earth Search returns items newest-first).
    def _cloud_key(item: Dict[str, Any]) -> float:
        cc = item.get("properties", {}).get("eo:cloud_cover")
        try:
            return float(cc) if cc is not None else 100.0
        except (TypeError, ValueError):
            return 100.0

    best = min(items, key=_cloud_key)
    props = best.get("properties", {})
    dt_str = props.get("datetime") or props.get("start_datetime", "")
    cc = _cloud_key(best)
    item_collection = best.get("collection", "unknown")
    scene_id = best.get("id", "live-stac-unknown")

    # Resolve the STAC item self-link for fetch_scene_cog_data
    stac_href: Optional[str] = next(
        (lnk["href"] for lnk in best.get("links", []) if lnk.get("rel") == "self"),
        None,
    )

    scene: Dict[str, Any] = {
        "scene_id": scene_id,
        "collection": item_collection,
        "datetime": dt_str,
        "cloud_cover": cc if cc < 100.0 else None,
        "thumbnail_url": _extract_thumbnail(best),
        "stac_href": stac_href,
        "geometry": best.get("geometry"),
        "stac_item": best,  # raw item kept for callers that need extra asset hrefs
    }

    logger.info(
        "fetch_live_scene_for_point: selected scene %s (collection=%s, cloud=%.1f%%, dt=%s)",
        scene_id, item_collection, cc, dt_str,
    )
    return scene


def ingest_stac_pass() -> int:
    """
    Run one synchronous pass of fetching and persisting new STAC scenes.

    Iterates all DEFAULT_ROIS, using each ROI's preferred collection list so
    that flood-prone regions prioritise Sentinel-1 SAR and optical regions
    prioritise Sentinel-2 / Landsat.
    """
    logger.info("Starting STAC catalog ingestion pass across %d ROIs...", len(DEFAULT_ROIS))
    inserted_total = 0

    for roi in DEFAULT_ROIS:
        roi_name = roi["name"]
        roi_bbox = roi["bbox"]
        roi_collections = roi.get("collections", DEFAULT_COLLECTIONS)

        features = fetch_stac_scenes(
            collections=roi_collections,
            bbox=roi_bbox,
            limit=20,
        )
        logger.info(
            "ROI '%s': STAC API returned %d candidate items (collections=%s)",
            roi_name,
            len(features),
            roi_collections,
        )

        for item in features:
            try:
                scene_id = item.get("id")
                if not scene_id:
                    continue

                collection = item.get("collection") or "unknown"
                props = item.get("properties", {})
                dt_str = props.get("datetime") or props.get("start_datetime")
                if not dt_str:
                    continue

                cloud_cover = props.get("eo:cloud_cover")
                if cloud_cover is not None:
                    try:
                        cloud_cover = float(cloud_cover)
                    except (ValueError, TypeError):
                        cloud_cover = None

                bbox = item.get("bbox")
                if not bbox or len(bbox) != 4:
                    continue

                thumb = _extract_thumbnail(item)

                # STAC item self-link
                stac_href = None
                for link in item.get("links", []):
                    if link.get("rel") == "self":
                        stac_href = link.get("href")
                        break

                inserted = analysis_db.insert_catalogued_scene(
                    scene_id=scene_id,
                    collection=collection,
                    dt_str=dt_str,
                    cloud_cover=cloud_cover,
                    thumbnail_url=thumb,
                    stac_href=stac_href,
                    bbox=bbox,
                )
                if inserted:
                    inserted_total += 1
            except Exception as item_err:
                logger.debug("Error processing STAC item %s: %s", item.get("id"), item_err)

    logger.info("STAC catalog ingestion pass complete: %d new scenes inserted.", inserted_total)
    return inserted_total


# ─── Bi-temporal materialisation ──────────────────────────────────────────────

def _download_image_bytes(url: str, timeout: int = 30) -> Optional[bytes]:
    """GET an HTTP/HTTPS URL and return raw bytes, or None on failure."""
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return None
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "SatQuery-Cataloger/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:
        logger.warning("_download_image_bytes(%s) failed: %s", url, exc)
        return None


def _write_geotiff_from_jpeg(jpeg_bytes: bytes, out_path: str, bbox: List[float]) -> bool:
    """
    Write a minimal single-band GeoTIFF with WGS-84 extent derived from *bbox*,
    using the JPEG image converted to a 3-band (RGB) raster.

    Falls back to saving a raw JPEG at *out_path* if rasterio/numpy are unavailable,
    so callers always have *something* on disk.
    """
    try:
        import numpy as np
        import rasterio
        from rasterio.transform import from_bounds
        from PIL import Image

        with Image.open(io.BytesIO(jpeg_bytes)) as pil_img:
            pil_img = pil_img.convert("RGB")
            arr = np.array(pil_img)  # (H, W, 3) uint8

        H, W, bands = arr.shape
        min_lon, min_lat, max_lon, max_lat = bbox
        transform = from_bounds(min_lon, min_lat, max_lon, max_lat, W, H)

        # Safeguard: never overwrite an existing GeoTIFF with fewer bands
        if os.path.exists(out_path):
            try:
                with rasterio.open(out_path) as existing_src:
                    existing_bands = existing_src.count
                    if existing_bands > bands:
                        logger.warning(
                            "Refusing to overwrite %s (%d bands) with lower-fidelity %d-band data",
                            out_path, existing_bands, bands
                        )
                        return False
            except Exception as read_err:
                logger.debug("Could not check existing %s band count: %s", out_path, read_err)

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with rasterio.open(
            out_path,
            "w",
            driver="GTiff",
            height=H,
            width=W,
            count=bands,
            dtype=arr.dtype,
            crs="EPSG:4326",
            transform=transform,
        ) as dst:
            for b in range(bands):
                dst.write(arr[:, :, b], b + 1)

        logger.info("Wrote real GeoTIFF (%dx%d, %d bands) → %s", W, H, bands, out_path)
        return True

    except Exception as exc:
        logger.warning("_write_geotiff_from_jpeg failed (%s): %s — falling back to raw JPEG", out_path, exc)
        try:
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as fh:
                fh.write(jpeg_bytes)
            logger.info("Wrote raw JPEG fallback → %s", out_path)
            return True
        except Exception as write_exc:
            logger.error("Could not write fallback JPEG to %s: %s", out_path, write_exc)
            return False


def fetch_bitemporal_pair_for_roi(
    roi: Optional[Dict[str, Any]] = None,
    base_data_dir: str = "data",
) -> bool:
    """
    Find two temporally-separated catalogued scenes for *roi* (defaults to the
    first ROI with a scenario_dir) and materialise them as georeferenced GeoTIFFs
    at data/<scenario_dir>/before.tif and data/<scenario_dir>/after.tif.

    Returns True if both files were successfully written, False otherwise.

    This function closes the synthetic-data honesty gap: once the STAC catalog
    has ingested at least two scenes for the region, the scenario files on disk
    become real satellite imagery instead of placeholder arrays.
    """
    # Pick the target ROI
    target_roi: Optional[Dict[str, Any]] = roi
    if target_roi is None:
        for r in DEFAULT_ROIS:
            if r.get("scenario_dir"):
                target_roi = r
                break

    if target_roi is None:
        logger.warning("fetch_bitemporal_pair_for_roi: no ROI with a scenario_dir found")
        return False

    scenario_dir = target_roi["scenario_dir"]
    roi_bbox = target_roi["bbox"]
    roi_name = target_roi["name"]

    if target_roi.get("skip_materialization") or roi_name == "Amazon_Rondonia":
        logger.info(
            "fetch_bitemporal_pair_for_roi: skipping materialization for ROI '%s' "
            "(hand-verified real multi-band scenario data is already preserved on disk).",
            roi_name,
        )
        return False

    # Use the bbox centre as the lookup point for find_scene_by_location
    centre_lon = (roi_bbox[0] + roi_bbox[2]) / 2.0
    centre_lat = (roi_bbox[1] + roi_bbox[3]) / 2.0

    logger.info(
        "fetch_bitemporal_pair_for_roi: searching catalog for bi-temporal pair in ROI '%s'",
        roi_name,
    )

    # ── Fetch the most recent scene as the "after" image ───────────────────
    try:
        after_scene = analysis_db.find_scene_by_location(
            lon=centre_lon,
            lat=centre_lat,
        )
    except Exception as exc:
        logger.warning("fetch_bitemporal_pair_for_roi: DB query failed for 'after' scene: %s", exc)
        return False

    if not after_scene:
        logger.warning(
            "fetch_bitemporal_pair_for_roi: no catalogued scene found at (%.4f, %.4f) — "
            "run ingest_stac_pass() first",
            centre_lon,
            centre_lat,
        )
        return False

    after_dt = after_scene.get("datetime", "")
    logger.info("fetch_bitemporal_pair_for_roi: 'after' scene = %s  dt=%s", after_scene["scene_id"], after_dt)

    # ── Fetch an older scene as the "before" image ──────────────────────────
    # Query for scenes strictly older than the 'after' scene by using end_date.
    before_scene = None
    if after_dt:
        try:
            before_scene = analysis_db.find_scene_by_location(
                lon=centre_lon,
                lat=centre_lat,
                end_date=after_dt,  # strictly earlier than the 'after' scene
            )
            # Reject if we got the same scene back (happens when only 1 scene exists)
            if before_scene and before_scene["scene_id"] == after_scene["scene_id"]:
                before_scene = None
        except Exception as exc:
            logger.warning("fetch_bitemporal_pair_for_roi: DB query failed for 'before' scene: %s", exc)

    if not before_scene:
        logger.warning(
            "fetch_bitemporal_pair_for_roi: could not find a distinct 'before' scene older than %s. "
            "The catalog may have only one ingested scene for this ROI. "
            "Scheduling another ingestion pass should populate more scenes over time.",
            after_dt,
        )
        # Still write the 'after' image if we at least have one real scene
        # (useful for single-image analysis scenarios)
        _materialise_scene(
            scene=after_scene,
            out_path=os.path.join(base_data_dir, scenario_dir, "after.tif"),
            bbox=roi_bbox,
        )
        return False

    before_dt = before_scene.get("datetime", "")
    logger.info("fetch_bitemporal_pair_for_roi: 'before' scene = %s  dt=%s", before_scene["scene_id"], before_dt)

    # ── Materialise both scenes ─────────────────────────────────────────────
    before_ok = _materialise_scene(
        scene=before_scene,
        out_path=os.path.join(base_data_dir, scenario_dir, "before.tif"),
        bbox=roi_bbox,
    )
    after_ok = _materialise_scene(
        scene=after_scene,
        out_path=os.path.join(base_data_dir, scenario_dir, "after.tif"),
        bbox=roi_bbox,
    )

    if before_ok and after_ok:
        logger.info(
            "fetch_bitemporal_pair_for_roi: SUCCESS — wrote real bi-temporal pair for "
            "ROI '%s' (scenario=%s).  before=%s  after=%s",
            roi_name, scenario_dir, before_dt, after_dt,
        )
    else:
        logger.warning(
            "fetch_bitemporal_pair_for_roi: partial failure (before_ok=%s, after_ok=%s)",
            before_ok, after_ok,
        )

    return before_ok and after_ok


def _materialise_scene(
    scene: Dict[str, Any],
    out_path: str,
    bbox: List[float],
) -> bool:
    """
    Download pixel data for *scene* and write a georeferenced GeoTIFF to *out_path*.

    Strategy (best first):
    1. Try fetch_scene_cog_data() — reads actual multi-band COG overviews via rasterio.
    2. Fall back to the scene's thumbnail_url (JPEG → GeoTIFF with WGS-84 extent).
    """
    try:
        cog_data = fetch_scene_cog_data(scene)
        img_bytes = cog_data.get("image_bytes")

        if img_bytes:
            # fetch_scene_cog_data already decoded a visual COG; wrap it as GeoTIFF.
            # The bytes may already be JPEG from rasterio export; _write_geotiff converts.
            geom = scene.get("geometry")
            if geom and geom.get("type") == "Polygon":
                coords = geom["coordinates"][0]
                lons = [c[0] for c in coords]
                lats = [c[1] for c in coords]
                scene_bbox = [min(lons), min(lats), max(lons), max(lats)]
            else:
                scene_bbox = bbox

            return _write_geotiff_from_jpeg(img_bytes, out_path, scene_bbox)

    except Exception as exc:
        logger.warning("_materialise_scene: fetch_scene_cog_data failed: %s", exc)

    # Fallback: thumbnail URL
    thumb_url = scene.get("thumbnail_url")
    if thumb_url:
        raw = _download_image_bytes(thumb_url)
        if raw:
            geom = scene.get("geometry")
            if geom and geom.get("type") == "Polygon":
                coords = geom["coordinates"][0]
                lons = [c[0] for c in coords]
                lats = [c[1] for c in coords]
                scene_bbox = [min(lons), min(lats), max(lons), max(lats)]
            else:
                scene_bbox = bbox
            return _write_geotiff_from_jpeg(raw, out_path, scene_bbox)

    logger.warning("_materialise_scene: no pixel data available for scene %s", scene.get("scene_id"))
    return False


# ─── Pluggable alert checks ───────────────────────────────────────────────────
#
# An alert-check function is the extension point for the monitoring daemon.
# Contract:
#
#     def my_check(roi: dict, context: dict) -> dict | None
#
#   roi      – the DEFAULT_ROIS entry being evaluated (name, bbox, collections, …)
#   context  – recent scene/metric data assembled by _build_alert_context():
#                {
#                  "scenes":          [ …catalogued_scenes rows, newest first… ],
#                  "scene_count":     int,
#                  "mean_cloud_cover": float | None,
#                  "roi_bbox_wkt":    str,   # ROI footprint as WKT POLYGON
#                }
#
#   Returns None when nothing is wrong, or a structured alert dict:
#                {
#                  "alert_type":       "land_change" | "severe_weather",
#                  "severity":         "info" | "warning" | "critical",
#                  "computed_metrics": {…},          # optional, JSONB-serialisable
#                  "geom_wkt":         "POLYGON(…)", # optional, defaults to ROI bbox
#                }
#
# Register additional checks with @register_alert_check — no daemon changes needed.

AlertCheckFn = Callable[[Dict[str, Any], Dict[str, Any]], Optional[Dict[str, Any]]]

_ALERT_CHECKS: List[AlertCheckFn] = []

# How long a triggered (region, alert_type) pair stays suppressed before the same
# condition may raise a fresh row.  Prevents a 5-minute dev poll interval from
# appending a near-identical alert every cycle.
ALERT_SUPPRESSION_MINUTES = int(os.environ.get("ALERT_SUPPRESSION_MINUTES", "60"))


def register_alert_check(fn: AlertCheckFn) -> AlertCheckFn:
    """Register an alert-check function.  Usable as a decorator."""
    _ALERT_CHECKS.append(fn)
    logger.debug("Registered alert check: %s", getattr(fn, "__name__", repr(fn)))
    return fn


def _bbox_to_wkt(bbox: List[float]) -> Optional[str]:
    """[min_lon, min_lat, max_lon, max_lat] → WKT POLYGON, or None if malformed."""
    if not bbox or len(bbox) != 4:
        return None
    min_lon, min_lat, max_lon, max_lat = bbox
    return (
        f"POLYGON(({min_lon} {min_lat}, {max_lon} {min_lat}, "
        f"{max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat}))"
    )


def _build_alert_context(roi: Dict[str, Any]) -> Dict[str, Any]:
    """Assemble the recent scene/metric data handed to every alert check."""
    bbox = roi.get("bbox") or []
    scenes = analysis_db.get_scenes_in_bbox(bbox, limit=20, since_days=90)

    clouds = [
        s["cloud_cover"] for s in scenes
        if s.get("cloud_cover") is not None
    ]
    mean_cloud = round(sum(clouds) / len(clouds), 2) if clouds else None

    return {
        "scenes": scenes,
        "scene_count": len(scenes),
        "mean_cloud_cover": mean_cloud,
        "roi_bbox_wkt": _bbox_to_wkt(bbox),
    }


@register_alert_check
def severe_weather_check(
    roi: Dict[str, Any], context: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Flag ROIs whose recent optical scenes are persistently cloud-obscured.

    Sustained heavy cloud over a disaster-relevant ROI is both a weather signal
    in its own right and an operational one: optical analysis is degraded, so
    the region should be re-tasked to SAR.  Needs at least 3 scenes so a single
    cloudy acquisition cannot trip it.
    """
    mean_cloud = context.get("mean_cloud_cover")
    scene_count = context.get("scene_count", 0)

    if mean_cloud is None or scene_count < 3:
        return None
    if mean_cloud < 70.0:
        return None

    if mean_cloud >= 90.0:
        severity = "critical"
    elif mean_cloud >= 80.0:
        severity = "warning"
    else:
        severity = "info"

    return {
        "alert_type": "severe_weather",
        "severity": severity,
        "computed_metrics": {
            "check": "severe_weather_check",
            "mean_cloud_cover_pct": mean_cloud,
            "scenes_evaluated": scene_count,
            "threshold_pct": 70.0,
            "window_days": 90,
            "recommendation": "Re-task ROI to SAR collections (sentinel-1-grd)",
        },
    }


@register_alert_check
def land_change_check(
    roi: Dict[str, Any], context: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Flag ROIs whose materialised bi-temporal pair shows large spectral change.

    Reuses the same deterministic pixel engine that backs /api/analyze, so an
    alert's numbers are reproducible against the GeoTIFFs on disk.  Silently
    returns None for ROIs with no scenario_dir or no materialised pair yet.
    """
    scenario_dir = roi.get("scenario_dir")
    if not scenario_dir:
        return None

    before_path = os.path.join("data", scenario_dir, "before.tif")
    after_path = os.path.join("data", scenario_dir, "after.tif")
    if not (os.path.exists(before_path) and os.path.exists(after_path)):
        return None

    try:
        import rasterio
        from geospatial_metrics import compute_change_area

        with rasterio.open(before_path) as src:
            before_bands = src.read()
            geotransform = src.transform
        with rasterio.open(after_path) as src:
            after_bands = src.read()

        # Pixel-diff needs identical grids; a shape mismatch means the pair is
        # mid-materialisation, so skip this cycle rather than report nonsense.
        if before_bands.shape != after_bands.shape:
            logger.debug(
                "land_change_check: shape mismatch for ROI '%s' (%s vs %s) — skipping",
                roi.get("name"), before_bands.shape, after_bands.shape,
            )
            return None

        metrics = compute_change_area(before_bands, after_bands, geotransform)
    except Exception as e:
        logger.debug("land_change_check failed for ROI '%s': %s", roi.get("name"), e)
        return None

    change_pct = metrics.get("change_pct")
    if change_pct is None or change_pct < 10.0:
        return None

    if change_pct >= 40.0:
        severity = "critical"
    elif change_pct >= 20.0:
        severity = "warning"
    else:
        severity = "info"

    return {
        "alert_type": "land_change",
        "severity": severity,
        "computed_metrics": {
            "check": "land_change_check",
            "threshold_pct": 10.0,
            "scenario_dir": scenario_dir,
            **metrics,
        },
    }


# Track A specialist — registered on import so the daemon picks it up with no
# further wiring (see mining_monitor.register()).
try:
    import mining_monitor
    mining_monitor.register()
    logger.info("Registered mining expansion alert check.")
except Exception as _mm_err:  # pragma: no cover - import guard
    logger.warning("Could not register mining monitor: %s", _mm_err)

# Track B specialist — acts only on ROIs flagged `insat_monitored` (the weather
# regions the INSAT daemon passes in), so it is inert for DEFAULT_ROIS.
try:
    import storm_risk
    storm_risk.register()
    logger.info("Registered convective storm-risk alert check.")
except Exception as _sr_err:  # pragma: no cover - import guard
    logger.warning("Could not register storm-risk check: %s", _sr_err)


def run_alert_checks(
    rois: Optional[List[Dict[str, Any]]] = None,
    checks: Optional[List[AlertCheckFn]] = None,
) -> int:
    """Run registered checks against monitored ROIs.

    Defaults to every registered check over DEFAULT_ROIS; the INSAT daemon
    passes its own weather regions and just the convective check, because it
    polls on the 30-min imager cadence rather than the STAC interval.

    Returns the number of alerts actually persisted.  Sync (psycopg2 + rasterio),
    so the daemon calls it through a thread executor.  Never raises: one broken
    check function must not take down the ingestion loop.
    """
    checks = _ALERT_CHECKS if checks is None else checks
    if not checks:
        return 0

    raised = 0
    for roi in (DEFAULT_ROIS if rois is None else rois):
        if not roi.get("monitored"):
            continue

        roi_name = roi.get("name", "unknown")
        try:
            context = _build_alert_context(roi)
        except Exception as e:
            logger.warning("Alert context build failed for ROI '%s': %s", roi_name, e)
            continue

        for check in checks:
            check_name = getattr(check, "__name__", repr(check))
            try:
                alert = check(roi, context)
            except Exception as e:
                logger.warning(
                    "Alert check '%s' raised on ROI '%s' (non-fatal): %s",
                    check_name, roi_name, e,
                )
                continue

            if not alert:
                continue
            if not isinstance(alert, dict):
                logger.warning(
                    "Alert check '%s' returned %s, expected dict or None — ignoring",
                    check_name, type(alert).__name__,
                )
                continue

            alert_type = alert.get("alert_type")
            severity = alert.get("severity")
            if not alert_type or not severity:
                logger.warning(
                    "Alert check '%s' returned a dict missing alert_type/severity — ignoring",
                    check_name,
                )
                continue

            # One open alert per distinct triggering condition.  A check may
            # name its condition via `dedupe_key`; otherwise the metrics
            # themselves are fingerprinted.
            metrics = dict(alert.get("computed_metrics") or {})
            dedupe_key = alert.get("dedupe_key") or hashlib.sha1(
                json.dumps(metrics, sort_keys=True, default=str).encode()
            ).hexdigest()[:16]
            metrics["dedupe_key"] = dedupe_key
            if analysis_db.has_open_alert_with_key(roi_name, alert_type, dedupe_key):
                logger.debug(
                    "Suppressing repeat %s alert for ROI '%s' (condition %s still open)",
                    alert_type, roi_name, dedupe_key,
                )
                continue

            if analysis_db.has_recent_alert(
                roi_name, alert_type, ALERT_SUPPRESSION_MINUTES
            ):
                logger.debug(
                    "Suppressing duplicate %s alert for ROI '%s' (open alert within %d min)",
                    alert_type, roi_name, ALERT_SUPPRESSION_MINUTES,
                )
                continue

            alert_id = analysis_db.insert_monitoring_alert(
                region_name=roi_name,
                alert_type=alert_type,
                severity=severity,
                computed_metrics=metrics,
                geom_wkt=alert.get("geom_wkt") or context.get("roi_bbox_wkt"),
            )
            if alert_id is not None:
                raised += 1

    if raised:
        logger.info("Alert pass complete: %d new alert(s) raised.", raised)
    return raised


async def stac_catalog_daemon() -> None:
    """Background loop that polls STAC on a configurable schedule.

    After each ingestion pass it attempts to materialise real bi-temporal GeoTIFF
    pairs for every ROI that has a `scenario_dir` configured, so that the local
    scenario files gradually migrate from synthetic placeholders to actual
    satellite imagery as the catalog accumulates scenes.
    """
    loop = asyncio.get_event_loop()

    # Determine interval: check CATALOG_POLL_INTERVAL_MINUTES or CATALOG_POLL_INTERVAL_HOURS
    interval_minutes = os.environ.get("CATALOG_POLL_INTERVAL_MINUTES")
    if interval_minutes:
        try:
            sleep_seconds = max(30, float(interval_minutes) * 60)
        except ValueError:
            sleep_seconds = 300  # 5 min fallback
    else:
        hours = os.environ.get("CATALOG_POLL_INTERVAL_HOURS", "24")
        try:
            sleep_seconds = max(60, float(hours) * 3600)
        except ValueError:
            sleep_seconds = 86400

    # Initial small pause so server finishes booting
    await asyncio.sleep(2)

    while True:
        try:
            # ── Ingestion pass ──────────────────────────────────────────────
            # Off-thread execution since urllib/psycopg2 are sync
            inserted = await loop.run_in_executor(None, ingest_stac_pass)

            # ── Bi-temporal materialisation ─────────────────────────────────
            # Always attempt, regardless of whether this pass inserted new
            # scenes.  Rationale: the scenario files on disk may still be
            # synthetic placeholders from a previous run even if tonight's
            # ingestion pass found zero *new* scenes (all duplicates).  The
            # materialisation function is cheap (one PostGIS point-in-polygon
            # look-up) and idempotent — it overwrites only when pixel data is
            # successfully fetched, so running it every cycle is safe.
            for roi in DEFAULT_ROIS:
                if (
                    roi.get("scenario_dir")
                    and not roi.get("skip_materialization")
                    and roi.get("name") != "Amazon_Rondonia"
                ):
                    try:
                        await loop.run_in_executor(
                            None,
                            fetch_bitemporal_pair_for_roi,
                            roi,
                            "data",
                        )
                    except Exception as mat_err:
                        logger.warning(
                            "Bi-temporal materialisation failed for ROI '%s' (non-fatal): %s",
                            roi["name"],
                            mat_err,
                        )

            # ── Alert pass ──────────────────────────────────────────────────
            # Runs last so checks see this cycle's freshly ingested scenes and
            # freshly materialised GeoTIFF pairs.  Off-thread (psycopg2 and
            # rasterio are both sync).  run_alert_checks() swallows per-check
            # failures internally; this guard only covers executor-level faults.
            try:
                await loop.run_in_executor(None, run_alert_checks)
            except Exception as alert_err:
                logger.warning(
                    "Alert pass failed this cycle (non-fatal): %s", alert_err
                )

        except asyncio.CancelledError:
            logger.info("STAC catalog daemon cancelled.")
            break
        except Exception as e:
            logger.error("Unexpected error in STAC catalog daemon: %s", e)

        logger.info("STAC catalog daemon sleeping for %d seconds...", sleep_seconds)
        await asyncio.sleep(sleep_seconds)


def fetch_scene_cog_data(scene_row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch analysis-ready COG scene data from STAC.
    Returns:
        {
            "image_bytes": bytes (visual COG or overview JPEG for VLM),
            "ndvi_metrics": Optional[Dict[str, Any]] (computed from real multi-band COGs: B04 Red & B08 NIR),
            "source": "stac_cog" | "stac_preview",
        }
    """
    result: Dict[str, Any] = {
        "image_bytes": None,
        "ndvi_metrics": None,
        "source": "stac_preview",
        "warnings": [],
    }

    stac_href = scene_row.get("stac_href")
    item_data = None
    if stac_href and (stac_href.startswith("http://") or stac_href.startswith("https://")):
        try:
            req = urllib.request.Request(stac_href, headers={"User-Agent": "SatQuery/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                item_data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            msg = f"Could not load STAC item JSON from {stac_href}: {e}"
            logger.warning(msg)
            result["warnings"].append(msg)

    assets = item_data.get("assets", {}) if item_data else {}

    # 1. Compute REAL NDVI from genuine multi-band COGs (Red and NIR bands)
    red_asset = assets.get("red") or assets.get("B04")
    nir_asset = assets.get("nir") or assets.get("B08") or assets.get("nir08") or assets.get("B8A")

    if red_asset and nir_asset:
        red_url = red_asset.get("href")
        nir_url = nir_asset.get("href")
        if red_url and nir_url and (red_url.startswith("http://") or red_url.startswith("https://")):
            try:
                import rasterio
                import numpy as np
                with rasterio.open(red_url) as r_ds, rasterio.open(nir_url) as n_ds:
                    # Read 512x512 downsampled overview for fast, real multi-band analysis
                    r = r_ds.read(1, out_shape=(512, 512)).astype(float)
                    n = n_ds.read(1, out_shape=(512, 512)).astype(float)
                    denom = n + r
                    denom[denom == 0] = np.nan
                    ndvi = (n - r) / denom
                    valid = ndvi[~np.isnan(ndvi)]
                    if valid.size > 0:
                        veg_mask = valid > 0.2
                        dense_mask = valid > 0.5
                        veg_pct = float(np.sum(veg_mask) / valid.size * 100)
                        dense_pct = float(np.sum(dense_mask) / valid.size * 100)
                        mean_ndvi = float(np.mean(valid))
                        result["ndvi_metrics"] = {
                            "vegetation_pct": round(veg_pct, 2),
                            "vegetation_pct_sparse": round(veg_pct, 2),
                            "vegetation_pct_dense": round(dense_pct, 2),
                            "mean_ndvi": round(mean_ndvi, 4),
                            "min_ndvi": round(float(np.min(valid)), 4),
                            "max_ndvi": round(float(np.max(valid)), 4),
                            "total_pixels": int(valid.size),
                            "georeferenced": True,
                            "source": "sentinel2_l2a_cogs",
                        }
                        result["source"] = "stac_cog"
                        logger.info(
                            f"Computed genuine Sentinel-2 multi-band NDVI: mean={mean_ndvi:.4f}, veg={veg_pct:.1f}%"
                        )
            except Exception as e:
                msg = f"Failed to read real COG bands for NDVI: {e}"
                logger.warning(msg)
                result["warnings"].append(msg)

    # 2. Fetch the visual image bytes for VLM input (prioritise visual asset, fallback to thumbnail)
    visual_asset = assets.get("visual") or assets.get("rendered_preview")
    if visual_asset and visual_asset.get("href"):
        v_url = visual_asset["href"]
        if v_url.startswith("http://") or v_url.startswith("https://"):
            try:
                import rasterio
                from PIL import Image
                import io
                # Use rasterio to read overview of visual COG (TCI.tif) directly to RGB PIL
                with rasterio.open(v_url) as v_ds:
                    rgb_arr = v_ds.read([1, 2, 3], out_shape=(512, 512))
                    # Transpose (3, H, W) -> (H, W, 3)
                    rgb_hwc = np.transpose(rgb_arr, (1, 2, 0)).astype(np.uint8)
                    pil_img = Image.fromarray(rgb_hwc)
                    buf = io.BytesIO()
                    pil_img.save(buf, format="JPEG", quality=90)
                    result["image_bytes"] = buf.getvalue()
                    logger.info(f"Loaded visual COG overview: {len(result['image_bytes']):,} bytes")
            except Exception as e:
                msg = f"Could not load visual COG overview directly, falling back to thumbnail: {e}"
                logger.warning(msg)
                result["warnings"].append(msg)

    # Fallback to thumbnail URL if visual COG wasn't read
    if not result["image_bytes"]:
        thumb_url = scene_row.get("thumbnail_url")
        if thumb_url and (thumb_url.startswith("http://") or thumb_url.startswith("https://")):
            try:
                req = urllib.request.Request(thumb_url, headers={"User-Agent": "SatQuery/1.0"})
                with urllib.request.urlopen(req, timeout=25) as resp:
                    result["image_bytes"] = resp.read()
            except Exception as e:
                msg = f"Failed to fetch thumbnail_url {thumb_url}: {e}"
                logger.warning(msg)
                result["warnings"].append(msg)

    return result


def fetch_scene_image_bytes(scene_row: Dict[str, Any]) -> Optional[bytes]:
    """
    Lazily fetch pixel data for a catalogued scene (backward compatible wrapper).
    """
    data = fetch_scene_cog_data(scene_row)
    return data.get("image_bytes")


