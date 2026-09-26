"""Monitored severe-weather regions (Track B).

These are the regions the INSAT-3DR thermal-IR pipeline (insat_ingest.py) clips
each frame to, and that storm_risk.py assesses for rapid cloud-top cooling.

They are deliberately kept OUT of stac_catalog.DEFAULT_ROIS: that list drives
Sentinel-2 ingestion and the optical cloud-cover heuristic, neither of which is
relevant here.  The INSAT daemon runs the convective check over this list
directly (see insat_ingest.insat_daemon()).

Bounding boxes are administrative-extent approximations taken from published
district coordinates; they are search windows for a ~4 km thermal-IR grid, not
precise boundaries, and no figure derived from them depends on edge accuracy.
"""

from typing import Any, Dict, List

WEATHER_REGIONS: List[Dict[str, Any]] = [
    {
        "name": "Mayurbhanj_Odisha",
        "display_name": "Mayurbhanj district, Odisha",
        # 21.27–22.57 N, 85.67–87.18 E (district extent)
        "bbox": [85.67, 21.27, 87.18, 22.57],
        "insat_monitored": True,
        "context": "Northern Odisha; pre-monsoon (Apr–Jun) thunderstorm belt.",
    },
    {
        "name": "Ranchi_Chota_Nagpur",
        "display_name": "Ranchi, Chota Nagpur plateau, Jharkhand",
        # Ranchi district and surrounding plateau
        "bbox": [84.75, 22.75, 85.85, 23.75],
        "insat_monitored": True,
        "context": "Plateau terrain that favours afternoon convective initiation.",
    },
    {
        "name": "Dhanbad_Jharkhand",
        "display_name": "Dhanbad / Jharia, Jharkhand",
        # Covers the Jharia coalfield monitored by Track A, so both tracks can
        # be shown for the same place.
        "bbox": [86.00, 23.45, 86.80, 24.05],
        "insat_monitored": True,
        "context": "Same area as the Track A Jharia coalfield region.",
    },
]


def bbox_to_geojson(bbox: List[float]) -> Dict[str, Any]:
    """[min_lon, min_lat, max_lon, max_lat] → GeoJSON Polygon."""
    w, s, e, n = bbox
    return {
        "type": "Polygon",
        "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
    }
