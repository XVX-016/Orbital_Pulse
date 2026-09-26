"""Ingest a real Sentinel-2 time series for the monitored mining regions.

Pulls genuine Earth Search / AWS Element84 scenes for Jharia Coalfield and the
Joda-Barbil belt across a multi-week window and persists their metadata to the
PostGIS `catalogued_scenes` table via the existing ingestion pipeline.

Run inside the service container:

    docker compose exec satquery-service python scripts/ingest_mining_regions.py
    docker compose exec satquery-service python scripts/ingest_mining_regions.py --weeks 16

Idempotent: catalogued_scenes dedupes on scene_id, so re-running only adds
genuinely new acquisitions.
"""

import argparse
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

# Allow running as `python scripts/ingest_mining_regions.py` from /app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import db as analysis_db  # noqa: E402
from mining_regions import MINING_REGIONS  # noqa: E402
from stac_catalog import _extract_thumbnail, fetch_stac_scenes  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("ingest_mining")

MIN_DATES_REQUIRED = 3   # the plan asks for at least 3-4 dates per region


def ingest_region(region, weeks: int, limit: int) -> dict:
    """Fetch and persist a real time series for one region."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(weeks=weeks)
    window = (
        f"{start.strftime('%Y-%m-%dT%H:%M:%SZ')}/"
        f"{end.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    )

    print(f"\n── {region['display_name']} " + "─" * 30)
    print(f"   bbox   : {region['bbox']}")
    print(f"   window : {window}  ({weeks} weeks)")

    items = fetch_stac_scenes(
        collections=region.get("collections", ["sentinel-2-l2a"]),
        bbox=region["bbox"],
        limit=limit,
        datetime_range=window,
    )
    print(f"   STAC returned {len(items)} candidate items")

    inserted = 0
    by_date = defaultdict(list)

    for item in items:
        props = item.get("properties", {})
        scene_id = item.get("id")
        dt_str = props.get("datetime")
        if not scene_id or not dt_str:
            continue

        cloud = props.get("eo:cloud_cover")
        bbox = item.get("bbox")
        if not bbox or len(bbox) != 4:
            continue

        collection = item.get("collection", "sentinel-2-l2a")
        stac_href = None
        for link in item.get("links", []):
            if link.get("rel") == "self":
                stac_href = link.get("href")
                break

        ok = analysis_db.insert_catalogued_scene(
            scene_id=scene_id,
            collection=collection,
            dt_str=dt_str,
            cloud_cover=cloud,
            thumbnail_url=_extract_thumbnail(item),
            stac_href=stac_href,
            bbox=bbox,
        )
        if ok:
            inserted += 1
        by_date[dt_str[:10]].append((scene_id, cloud))

    dates = sorted(by_date.keys())
    print(f"   inserted {inserted} new scene(s); {len(dates)} distinct acquisition dates")
    for d in dates:
        clouds = [c for _, c in by_date[d] if c is not None]
        avg = f"{sum(clouds)/len(clouds):.1f}%" if clouds else "n/a"
        print(f"     {d}  scenes={len(by_date[d]):<3} avg_cloud={avg}")

    return {
        "region": region["name"],
        "returned": len(items),
        "inserted": inserted,
        "dates": dates,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--weeks", type=int, default=12,
                    help="How far back to search (default 12 weeks).")
    ap.add_argument("--limit", type=int, default=100,
                    help="Max STAC items per region (default 100).")
    args = ap.parse_args()

    print("=" * 74)
    print("Mining region time-series ingestion (real Earth Search STAC)")
    print("=" * 74)
    print("NOTE: region boundary polygons are APPROXIMATIONS, not lease GIS.")

    results = [ingest_region(r, args.weeks, args.limit) for r in MINING_REGIONS]

    print("\n" + "=" * 74)
    print("Summary")
    print("=" * 74)
    shortfall = False
    for r in results:
        n = len(r["dates"])
        status = "OK" if n >= MIN_DATES_REQUIRED else "INSUFFICIENT"
        if n < MIN_DATES_REQUIRED:
            shortfall = True
        span = f"{r['dates'][0]} → {r['dates'][-1]}" if r["dates"] else "none"
        print(f"  {r['region']:<20} dates={n:<3} span={span:<26} [{status}]")

    if shortfall:
        print(f"\nAt least one region has fewer than {MIN_DATES_REQUIRED} distinct dates.")
        print("Re-run with a longer --weeks window.")
        return 1

    print("\nPASS — every region has a real multi-date time series.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
