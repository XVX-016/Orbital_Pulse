"""PostGIS persistence layer for SatQuery AI.

Design constraints:
- Pure psycopg2 (sync) — the FastAPI handler fires this in a threadpool executor,
  so it never blocks the event loop.
- No ORM: the schema is defined in db/init.sql and is self-evident to reviewers.
- DB failures are logged but NEVER re-raised; the user always gets their analysis
  response regardless of DB availability.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

# Read from env; falls back to the compose-declared credentials
DATABASE_URL = os.environ.get(
    "SATQUERY_DATABASE_URL",
    "postgresql://orbital_user:orbital_password@localhost:5432/orbital_db",
)


def get_connection() -> psycopg2.extensions.connection:
    """Open a fresh psycopg2 connection.  Caller is responsible for closing it."""
    return psycopg2.connect(DATABASE_URL)


# ─── Geometry helpers ─────────────────────────────────────────────────────────

def _geom_from_tif_path(tif_path: str) -> Optional[str]:
    """Return a WKT POINT (scene centre in WGS-84) from a GeoTIFF, or None."""
    try:
        import rasterio
        import rasterio.warp
        with rasterio.open(tif_path) as src:
            if src.crs is None:
                return None
            bounds = src.bounds
            cx = (bounds.left + bounds.right) / 2.0
            cy = (bounds.bottom + bounds.top) / 2.0
            # Reproject centre to WGS-84 if the file is in a projected CRS
            if src.crs.to_epsg() != 4326:
                xs, ys = rasterio.warp.transform(
                    src.crs, "EPSG:4326", [cx], [cy]
                )
                lon, lat = xs[0], ys[0]
            else:
                lon, lat = cx, cy
            return f"POINT({lon} {lat})"
    except Exception as e:
        logger.debug(f"_geom_from_tif_path({tif_path!r}) failed: {e}")
        return None


def _bbox_from_tif_path(tif_path: str) -> Optional[str]:
    """Return a WKT POLYGON (bbox in WGS-84) from a GeoTIFF, or None."""
    try:
        import rasterio
        import rasterio.warp
        with rasterio.open(tif_path) as src:
            if src.crs is None:
                return None
            b = src.bounds
            if src.crs.to_epsg() != 4326:
                xs, ys = rasterio.warp.transform(
                    src.crs, "EPSG:4326",
                    [b.left, b.right, b.right, b.left, b.left],
                    [b.bottom, b.bottom, b.top, b.top, b.bottom],
                )
                coords = " , ".join(f"{x} {y}" for x, y in zip(xs, ys))
            else:
                coords = (
                    f"{b.left} {b.bottom} , {b.right} {b.bottom} , "
                    f"{b.right} {b.top} , {b.left} {b.top} , {b.left} {b.bottom}"
                )
            return f"POLYGON(({coords}))"
    except Exception as e:
        logger.debug(f"_bbox_from_tif_path({tif_path!r}) failed: {e}")
        return None


def _build_geometry(execution_trace: Dict[str, Any], computed_metrics: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    Derive a WKT geometry string for the row.
    
    Strategy (most informative wins):
    1. If a GeoTIFF path is available AND georeferencing is confirmed → store bbox polygon.
    2. If only centre derivation works → store point.
    3. If neither → None (the column is left NULL).
    """
    params = execution_trace.get("parameters", {})
    tif_path = params.get("before_tif_path") or params.get("tif_path")

    # Confirm the VLM side found a real geotransform
    georef_confirmed = False
    if computed_metrics is not None and isinstance(computed_metrics, dict):
        if computed_metrics.get("georeferenced", False):
            georef_confirmed = True
        elif computed_metrics.get("change_area", {}).get("has_georeferencing", False):
            georef_confirmed = True
        elif any(isinstance(v, dict) and v.get("has_georeferencing", False) for v in computed_metrics.values()):
            georef_confirmed = True

    if tif_path and georef_confirmed:
        bbox_wkt = _bbox_from_tif_path(tif_path)
        if bbox_wkt:
            return bbox_wkt
        centre_wkt = _geom_from_tif_path(tif_path)
        if centre_wkt:
            return centre_wkt

    # No georef but we have a path — try centre-only as best-effort
    if tif_path:
        return _geom_from_tif_path(tif_path)

    return None


# ─── Public API ───────────────────────────────────────────────────────────────

def persist_analysis(
    query_text: str,
    task_type: str,
    modality: str,
    temporal: str,
    vlm_answer: str,
    computed_metrics: Optional[Dict[str, Any]],
    execution_trace: Dict[str, Any],
) -> None:
    """Insert one completed analysis row into PostGIS.

    NEVER raises — all exceptions are caught and logged so the HTTP response
    is never blocked by a DB write failure.
    """
    try:
        geom_wkt = _build_geometry(execution_trace, computed_metrics)

        with get_connection() as conn:
            with conn.cursor() as cur:
                if geom_wkt:
                    cur.execute(
                        """
                        INSERT INTO analyses
                            (query_text, task_type, modality, temporal,
                             vlm_answer, computed_metrics, geom)
                        VALUES (%s, %s, %s, %s, %s, %s,
                                ST_SetSRID(ST_GeomFromText(%s), 4326))
                        """,
                        (
                            query_text,
                            task_type,
                            modality,
                            temporal,
                            vlm_answer,
                            json.dumps(computed_metrics) if computed_metrics else None,
                            geom_wkt,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO analyses
                            (query_text, task_type, modality, temporal,
                             vlm_answer, computed_metrics, geom)
                        VALUES (%s, %s, %s, %s, %s, %s, NULL)
                        """,
                        (
                            query_text,
                            task_type,
                            modality,
                            temporal,
                            vlm_answer,
                            json.dumps(computed_metrics) if computed_metrics else None,
                        ),
                    )
            conn.commit()
        logger.info(f"DB: persisted analysis task={task_type!r} geom={'yes' if geom_wkt else 'null'}")
    except Exception as e:
        logger.warning(f"DB persist_analysis failed (non-fatal): {e}")


def get_recent_analyses(limit: int = 50) -> List[Dict[str, Any]]:
    """Return the most recent `limit` analyses as a list of dicts.

    Each dict includes:
      - id, created_at, query_text, task_type, modality, temporal
      - vlm_answer, computed_metrics (already a dict/None)
      - geometry: GeoJSON Feature geometry object (or null)

    Raises on connection failure — the GET endpoint handles that with a 503.
    """
    sql = """
        SELECT
            id,
            created_at,
            query_text,
            task_type,
            modality,
            temporal,
            vlm_answer,
            computed_metrics,
            CASE
                WHEN geom IS NOT NULL THEN ST_AsGeoJSON(geom)::json
                ELSE NULL
            END AS geometry
        FROM analyses
        ORDER BY created_at DESC
        LIMIT %s
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()

    result = []
    for row in rows:
        d = dict(row)
        # created_at is a datetime — serialise to ISO string
        if d.get("created_at"):
            d["created_at"] = d["created_at"].isoformat()
        result.append(d)
    return result
