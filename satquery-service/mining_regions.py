"""Monitored Indian mining regions — Jharia Coalfield and Joda Iron Ore belt.

═══════════════════════════════════════════════════════════════════════════════
 BOUNDARY PROVENANCE — READ BEFORE USING THESE POLYGONS FOR ANY CLAIM
═══════════════════════════════════════════════════════════════════════════════
The `boundary` polygons below are **APPROXIMATIONS**.  They were digitised by
eye from public satellite imagery and published descriptions of each field's
extent.  They are NOT official mining-lease boundaries: no authoritative lease
GIS file (IBM / DGMS / state DoM cadastral shapefile) was available when this
module was written.

Consequences, which every consumer must respect:
  • Any area figure computed against these polygons is indicative, not legal.
  • "Inside / outside the boundary" is a rough spatial cue, not a compliance
    determination, and must never be presented as evidence of encroachment.
  • `boundary_is_approximate` is True and `boundary_caveat` carries the text
    that MUST be shown wherever a boundary-derived number reaches a user.
    /api/monitored-regions serves both fields for exactly that purpose.

To replace an approximation with a real lease boundary: drop the authoritative
polygon into `boundary`, set `boundary_is_approximate = False`, and update
`boundary_source`.  Nothing else needs to change.
═══════════════════════════════════════════════════════════════════════════════
"""

from typing import Any, Dict, List, Optional

# Shown verbatim in the UI next to any boundary-derived figure.
APPROXIMATE_BOUNDARY_CAVEAT = (
    "Boundary is an approximation digitised from public imagery and reporting, "
    "not an official mining-lease GIS file. Area and inside/outside figures are "
    "indicative only and must not be treated as evidence of lease compliance or "
    "encroachment."
)


MINING_REGIONS: List[Dict[str, Any]] = [
    {
        "name": "Jharia_Coalfield",
        "display_name": "Jharia Coalfield, Dhanbad, Jharkhand",
        "commodity": "coal",
        # Search footprint — deliberately wider than the boundary so scenes
        # covering the field's edges are still catalogued.
        "bbox": [86.10, 23.63, 86.50, 23.83],
        # APPROXIMATE extent of the coalfield (~38 km E-W, ~18 km N-S), traced
        # around the visible mine-spoil and subsidence belt west/south of
        # Dhanbad town. NOT a lease boundary.
        "boundary": [
            [86.135, 23.700],
            [86.200, 23.672],
            [86.300, 23.660],
            [86.400, 23.668],
            [86.470, 23.698],
            [86.478, 23.752],
            [86.430, 23.795],
            [86.330, 23.812],
            [86.225, 23.800],
            [86.150, 23.762],
            [86.135, 23.700],
        ],
        "boundary_is_approximate": True,
        "boundary_source": (
            "Digitised by eye from public Sentinel-2 imagery and published "
            "descriptions of the Jharia field extent. No official lease GIS available."
        ),
        "boundary_caveat": APPROXIMATE_BOUNDARY_CAVEAT,
        "collections": ["sentinel-2-l2a"],
        "monitored": True,
        "scenario_dir": None,
    },
    {
        "name": "Joda_Iron_Ore",
        "display_name": "Joda–Barbil Iron Ore Belt, Keonjhar, Odisha",
        "commodity": "iron_ore",
        "bbox": [85.30, 21.90, 85.60, 22.15],
        # APPROXIMATE extent of the Joda-Barbil working belt, traced around the
        # visible open-cast benches and overburden dumps. NOT a lease boundary.
        "boundary": [
            [85.345, 21.945],
            [85.430, 21.930],
            [85.520, 21.948],
            [85.565, 21.995],
            [85.558, 22.065],
            [85.495, 22.112],
            [85.410, 22.118],
            [85.352, 22.080],
            [85.332, 22.010],
            [85.345, 21.945],
        ],
        "boundary_is_approximate": True,
        "boundary_source": (
            "Digitised by eye from public Sentinel-2 imagery and published "
            "descriptions of the Joda-Barbil belt. No official lease GIS available."
        ),
        "boundary_caveat": APPROXIMATE_BOUNDARY_CAVEAT,
        "collections": ["sentinel-2-l2a"],
        "monitored": True,
        "scenario_dir": None,
    },
]


def get_mining_region(name: str) -> Optional[Dict[str, Any]]:
    """Look up one region by its `name` slug."""
    for region in MINING_REGIONS:
        if region["name"] == name:
            return region
    return None


def boundary_to_wkt(region: Dict[str, Any]) -> Optional[str]:
    """Render a region's approximate boundary as a WGS-84 WKT POLYGON."""
    ring = region.get("boundary")
    if not ring or len(ring) < 4:
        return None
    # Close the ring if the literal above did not already repeat the first vertex
    closed = list(ring)
    if closed[0] != closed[-1]:
        closed.append(closed[0])
    coords = ", ".join(f"{lon} {lat}" for lon, lat in closed)
    return f"POLYGON(({coords}))"


def boundary_to_geojson(region: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Render a region's approximate boundary as a GeoJSON Polygon geometry."""
    ring = region.get("boundary")
    if not ring or len(ring) < 4:
        return None
    closed = [list(pt) for pt in ring]
    if closed[0] != closed[-1]:
        closed.append(list(closed[0]))
    return {"type": "Polygon", "coordinates": [closed]}
