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
"""

import asyncio
import io
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

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
        "skip_materialization": True,          # Hand-verified multi-band scenario data preserved
    },
    {
        "name": "California_Wildfire",
        "bbox": [-122.5, 37.5, -121.5, 38.5],  # East Bay / Diablo Range
        "collections": ["sentinel-2-l2a", "landsat-c2-l2", "sentinel-1-grd"],
        "scenario_dir": "disaster",             # maps to data/disaster/
    },
    {
        "name": "Bangladesh_Delta_Flood",
        "bbox": [89.5, 22.5, 91.5, 24.5],       # Brahmaputra/Ganges confluence
        "collections": ["sentinel-1-grd", "sentinel-2-l2a"],  # SAR first for flood
        "scenario_dir": None,                   # no local scenario dir yet
    },
    {
        "name": "SE_Australia_Bushfire",
        "bbox": [147.0, -38.0, 150.0, -35.5],  # NSW south coast / Snowy Mountains
        "collections": ["sentinel-2-l2a", "landsat-c2-l2"],
        "scenario_dir": None,
    },
]

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
) -> List[Dict[str, Any]]:
    """Synchronous call to Earth Search STAC API to retrieve recent scenes."""
    if bbox is None:
        bbox = DEFAULT_ROIS[0]["bbox"]

    payload = {
        "collections": collections,
        "bbox": bbox,
        "limit": limit,
    }

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
            return fetch_stac_scenes(collections=["sentinel-2-l2a"], bbox=bbox, limit=limit)
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


