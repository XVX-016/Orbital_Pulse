"""Lightweight STAC Cataloging Service.

Metadata-only ingestion:
- Queries Earth Search STAC API (https://earth-search.aws.element84.com/v1/search)
- Collections: sentinel-2-l2a, sentinel-1-grd, landsat-c2-l2
- Region: Rondônia, Brazil (matching the primary scenario and GeoTIFFs)
- Runs as an asynchronous background loop on a configurable interval (CATALOG_POLL_INTERVAL_HOURS, default 24h, or minutes in dev).
- Deduplicates on scene_id in PostGIS table `catalogued_scenes`.
"""

import asyncio
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

import db as analysis_db

logger = logging.getLogger(__name__)

EARTH_SEARCH_URL = "https://earth-search.aws.element84.com/v1/search"

# Target collections
DEFAULT_COLLECTIONS = [
    "sentinel-2-l2a",
    "sentinel-1-grd",
    "landsat-c2-l2",
]

# Regions of interest: [min_lon, min_lat, max_lon, max_lat]
# Rondônia, Brazil scene area: ~[-62.2, -10.2, -61.8, -9.8]
DEFAULT_ROIS = [
    {"name": "Rondonia_Brazil", "bbox": [-62.2, -10.2, -61.8, -9.8]},
]


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


def ingest_stac_pass() -> int:
    """Run one synchronous pass of fetching and persisting new STAC scenes."""
    logger.info("Starting STAC catalog ingestion pass...")
    inserted_total = 0

    for roi in DEFAULT_ROIS:
        features = fetch_stac_scenes(collections=DEFAULT_COLLECTIONS, bbox=roi["bbox"], limit=20)
        logger.info(f"STAC API returned {len(features)} candidate items for ROI '{roi['name']}'")

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

                # STAC href self link
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
                logger.debug(f"Error processing STAC item {item.get('id')}: {item_err}")

    logger.info(f"STAC catalog ingestion pass complete: {inserted_total} new scenes inserted.")
    return inserted_total


async def stac_catalog_daemon() -> None:
    """Background loop that polls STAC on a configurable schedule."""
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
            # Off-thread execution since urllib/psycopg2 are sync
            await loop.run_in_executor(None, ingest_stac_pass)
        except asyncio.CancelledError:
            logger.info("STAC catalog daemon cancelled.")
            break
        except Exception as e:
            logger.error(f"Unexpected error in STAC catalog daemon: {e}")

        logger.info(f"STAC catalog daemon sleeping for {sleep_seconds} seconds...")
        await asyncio.sleep(sleep_seconds)


def fetch_scene_image_bytes(scene_row: Dict[str, Any]) -> Optional[bytes]:
    """
    Lazily fetch the actual pixel data (JPEG preview or asset) for a catalogued scene.
    Only executed on demand when a user submits a query for this scene.
    """
    thumb_url = scene_row.get("thumbnail_url")
    if thumb_url and (thumb_url.startswith("http://") or thumb_url.startswith("https://")):
        try:
            req = urllib.request.Request(thumb_url, headers={"User-Agent": "SatQuery/1.0"})
            with urllib.request.urlopen(req, timeout=25) as resp:
                return resp.read()
        except Exception as e:
            logger.warning(f"Failed to fetch thumbnail_url {thumb_url}: {e}")

    # Fallback: check stac_href to inspect other assets
    stac_href = scene_row.get("stac_href")
    if stac_href and (stac_href.startswith("http://") or stac_href.startswith("https://")):
        try:
            req = urllib.request.Request(stac_href, headers={"User-Agent": "SatQuery/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                item_data = json.loads(resp.read().decode("utf-8"))

            assets = item_data.get("assets", {})
            for key in ["thumbnail", "overview", "visual", "rendered_preview"]:
                if key in assets:
                    asset_href = assets[key].get("href")
                    if asset_href and (asset_href.startswith("http://") or asset_href.startswith("https://")):
                        req_asset = urllib.request.Request(asset_href, headers={"User-Agent": "SatQuery/1.0"})
                        with urllib.request.urlopen(req_asset, timeout=30) as asset_resp:
                            return asset_resp.read()
        except Exception as e:
            logger.warning(f"Failed to fetch assets via stac_href {stac_href}: {e}")

    return None

