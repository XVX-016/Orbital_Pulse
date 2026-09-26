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
    if params.get("scene_geometry_wkt"):
        return params["scene_geometry_wkt"]

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


def init_db() -> None:
    """Ensure required tables and extensions exist in PostGIS."""
    create_tables_sql = """
    CREATE EXTENSION IF NOT EXISTS postgis;

    CREATE TABLE IF NOT EXISTS analyses (
        id               BIGSERIAL PRIMARY KEY,
        created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        query_text       TEXT        NOT NULL,
        task_type        TEXT        NOT NULL,
        modality         TEXT,
        temporal         TEXT,
        vlm_answer       TEXT,
        computed_metrics JSONB,
        geom             GEOMETRY(Geometry, 4326)
    );

    CREATE INDEX IF NOT EXISTS analyses_created_at_idx ON analyses (created_at DESC);
    CREATE INDEX IF NOT EXISTS analyses_geom_idx       ON analyses USING GIST (geom);

    CREATE TABLE IF NOT EXISTS catalogued_scenes (
        id               BIGSERIAL PRIMARY KEY,
        scene_id         TEXT UNIQUE NOT NULL,
        collection       TEXT NOT NULL,
        datetime         TIMESTAMPTZ NOT NULL,
        cloud_cover      DOUBLE PRECISION,
        thumbnail_url    TEXT,
        stac_href        TEXT,
        geom             GEOMETRY(Polygon, 4326),
        created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS catalogued_scenes_datetime_idx ON catalogued_scenes (datetime DESC);
    CREATE INDEX IF NOT EXISTS catalogued_scenes_geom_idx     ON catalogued_scenes USING GIST (geom);
    CREATE INDEX IF NOT EXISTS catalogued_scenes_coll_idx     ON catalogued_scenes (collection);

    CREATE TABLE IF NOT EXISTS monitoring_alerts (
        id               BIGSERIAL PRIMARY KEY,
        region_name      TEXT        NOT NULL,
        alert_type       TEXT        NOT NULL
                         CHECK (alert_type IN ('land_change', 'severe_weather')),
        severity         TEXT        NOT NULL
                         CHECK (severity IN ('info', 'warning', 'critical')),
        computed_metrics JSONB,
        geom             GEOMETRY(Geometry, 4326),
        "timestamp"      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        acknowledged     BOOLEAN     NOT NULL DEFAULT FALSE
    );

    CREATE INDEX IF NOT EXISTS monitoring_alerts_timestamp_idx ON monitoring_alerts ("timestamp" DESC);
    CREATE INDEX IF NOT EXISTS monitoring_alerts_geom_idx      ON monitoring_alerts USING GIST (geom);
    CREATE INDEX IF NOT EXISTS monitoring_alerts_unack_idx     ON monitoring_alerts ("timestamp" DESC)
        WHERE acknowledged = FALSE;
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(create_tables_sql)
            conn.commit()
        logger.info("DB: ensured schema and tables (analyses, catalogued_scenes, monitoring_alerts)")
    except Exception as e:
        logger.warning(f"DB init_db failed: {e}")


def insert_catalogued_scene(
    scene_id: str,
    collection: str,
    dt_str: str,
    cloud_cover: Optional[float],
    thumbnail_url: Optional[str],
    stac_href: Optional[str],
    bbox: List[float],
) -> bool:
    """
    Insert a scene into catalogued_scenes if not already present (ON CONFLICT DO NOTHING).
    bbox: [min_lon, min_lat, max_lon, max_lat]
    Returns True if a new row was inserted, False if duplicate or failed.
    """
    if len(bbox) != 4:
        return False

    min_lon, min_lat, max_lon, max_lat = bbox
    polygon_wkt = (
        f"POLYGON(({min_lon} {min_lat}, {max_lon} {min_lat}, "
        f"{max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat}))"
    )

    sql = """
        INSERT INTO catalogued_scenes
            (scene_id, collection, datetime, cloud_cover, thumbnail_url, stac_href, geom)
        VALUES (%s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromText(%s), 4326))
        ON CONFLICT (scene_id) DO NOTHING
        RETURNING id;
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        scene_id,
                        collection,
                        dt_str,
                        cloud_cover,
                        thumbnail_url,
                        stac_href,
                        polygon_wkt,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
            return row is not None
    except Exception as e:
        logger.warning(f"insert_catalogued_scene failed for {scene_id}: {e}")
        return False


def get_recent_catalog_scenes(limit: int = 100) -> List[Dict[str, Any]]:
    """Return recent catalogued scenes as a list with GeoJSON geometry."""
    sql = """
        SELECT
            id,
            scene_id,
            collection,
            datetime,
            cloud_cover,
            thumbnail_url,
            stac_href,
            created_at,
            CASE
                WHEN geom IS NOT NULL THEN ST_AsGeoJSON(geom)::json
                ELSE NULL
            END AS geometry
        FROM catalogued_scenes
        ORDER BY datetime DESC
        LIMIT %s
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall()

    result = []
    for row in rows:
        d = dict(row)
        if d.get("datetime"):
            d["datetime"] = d["datetime"].isoformat()
        if d.get("created_at"):
            d["created_at"] = d["created_at"].isoformat()
        result.append(d)
    return result


def find_scene_by_location(
    lon: float,
    lat: float,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    collection: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Find the most recent catalogued scene covering (lon, lat), optionally filtered
    by date range and satellite collection.
    """
    conditions = ["ST_Intersects(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326))"]
    params: List[Any] = [lon, lat]

    if collection:
        conditions.append("collection = %s")
        params.append(collection)

    if start_date:
        conditions.append("datetime >= %s")
        params.append(start_date)

    if end_date:
        conditions.append("datetime <= %s")
        params.append(end_date)

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT
            id,
            scene_id,
            collection,
            datetime,
            cloud_cover,
            thumbnail_url,
            stac_href,
            created_at,
            CASE
                WHEN geom IS NOT NULL THEN ST_AsGeoJSON(geom)::json
                ELSE NULL
            END AS geometry
        FROM catalogued_scenes
        WHERE {where_clause}
        ORDER BY datetime DESC
        LIMIT 1;
    """

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, tuple(params))
            row = cur.fetchone()

    if not row:
        return None

    d = dict(row)
    if d.get("datetime"):
        d["datetime"] = d["datetime"].isoformat()
    if d.get("created_at"):
        d["created_at"] = d["created_at"].isoformat()
    return d



# ─── Monitoring alerts ────────────────────────────────────────────────────────

# The two alert families the schema's CHECK constraint accepts.  Kept here (not
# just in SQL) so the daemon can reject a malformed check-function result before
# it ever reaches PostGIS.
VALID_ALERT_TYPES = ("land_change", "severe_weather")
VALID_SEVERITIES = ("info", "warning", "critical")


def insert_monitoring_alert(
    region_name: str,
    alert_type: str,
    severity: str,
    computed_metrics: Optional[Dict[str, Any]] = None,
    geom_wkt: Optional[str] = None,
) -> Optional[int]:
    """Insert one alert row and return its new id, or None on failure.

    Validates `alert_type` / `severity` against the same vocabularies the table's
    CHECK constraint enforces, so a buggy alert-check function surfaces as a
    logged warning rather than an aborted transaction.

    NEVER raises — the daemon must survive a bad check function.
    """
    if alert_type not in VALID_ALERT_TYPES:
        logger.warning(
            f"insert_monitoring_alert: rejected alert_type={alert_type!r} "
            f"(expected one of {VALID_ALERT_TYPES})"
        )
        return None
    if severity not in VALID_SEVERITIES:
        logger.warning(
            f"insert_monitoring_alert: rejected severity={severity!r} "
            f"(expected one of {VALID_SEVERITIES})"
        )
        return None

    sql = """
        INSERT INTO monitoring_alerts
            (region_name, alert_type, severity, computed_metrics, geom)
        VALUES (%s, %s, %s, %s,
                CASE WHEN %s IS NULL THEN NULL
                     ELSE ST_SetSRID(ST_GeomFromText(%s), 4326) END)
        RETURNING id;
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        region_name,
                        alert_type,
                        severity,
                        json.dumps(computed_metrics) if computed_metrics else None,
                        geom_wkt,
                        geom_wkt,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        alert_id = row[0] if row else None
        logger.info(
            f"DB: raised {severity} {alert_type} alert for {region_name!r} (id={alert_id})"
        )
        return alert_id
    except Exception as e:
        logger.warning(f"insert_monitoring_alert failed for {region_name!r}: {e}")
        return None


def has_recent_alert(region_name: str, alert_type: str, within_minutes: int = 60) -> bool:
    """True if an unacknowledged alert of this (region, type) was raised recently.

    The daemon polls on a short interval in dev (CATALOG_POLL_INTERVAL_MINUTES=5),
    so without this suppression window a persistent condition would append a near
    identical row every cycle.  Acknowledged alerts are ignored, which lets an
    operator deliberately re-arm a region by acknowledging its open alert.
    """
    sql = """
        SELECT 1
        FROM monitoring_alerts
        WHERE region_name = %s
          AND alert_type  = %s
          AND acknowledged = FALSE
          AND "timestamp" > NOW() - (%s * INTERVAL '1 minute')
        LIMIT 1;
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (region_name, alert_type, within_minutes))
                return cur.fetchone() is not None
    except Exception as e:
        # Fail "open" (report no recent alert) would risk a write storm, so fail
        # "closed": on a DB hiccup we suppress rather than duplicate.
        logger.warning(f"has_recent_alert check failed for {region_name!r}: {e}")
        return True


def get_recent_alerts(
    limit: int = 50,
    acknowledged: Optional[bool] = None,
    region_name: Optional[str] = None,
    alert_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return recent alerts, newest first, with GeoJSON geometry.

    Optional filters narrow by acknowledgement state, region, or alert family.
    Raises on connection failure — the GET endpoint turns that into a 503.
    """
    conditions: List[str] = []
    params: List[Any] = []

    if acknowledged is not None:
        conditions.append("acknowledged = %s")
        params.append(acknowledged)
    if region_name:
        conditions.append("region_name = %s")
        params.append(region_name)
    if alert_type:
        conditions.append("alert_type = %s")
        params.append(alert_type)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    sql = f"""
        SELECT
            id,
            region_name,
            alert_type,
            severity,
            computed_metrics,
            "timestamp",
            acknowledged,
            CASE
                WHEN geom IS NOT NULL THEN ST_AsGeoJSON(geom)::json
                ELSE NULL
            END AS geometry
        FROM monitoring_alerts
        {where_clause}
        ORDER BY "timestamp" DESC
        LIMIT %s
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()

    result = []
    for row in rows:
        d = dict(row)
        if d.get("timestamp"):
            d["timestamp"] = d["timestamp"].isoformat()
        result.append(d)
    return result


def get_scenes_in_bbox(
    bbox: List[float],
    limit: int = 20,
    since_days: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Return recent catalogued scenes intersecting an ROI bbox, newest first.

    This is the raw material handed to alert-check functions.
    bbox: [min_lon, min_lat, max_lon, max_lat]
    """
    if len(bbox) != 4:
        return []

    conditions = ["ST_Intersects(geom, ST_MakeEnvelope(%s, %s, %s, %s, 4326))"]
    params: List[Any] = list(bbox)

    if since_days is not None:
        conditions.append("datetime > NOW() - (%s * INTERVAL '1 day')")
        params.append(since_days)

    params.append(limit)
    sql = f"""
        SELECT
            id, scene_id, collection, datetime, cloud_cover,
            thumbnail_url, stac_href,
            CASE
                WHEN geom IS NOT NULL THEN ST_AsGeoJSON(geom)::json
                ELSE NULL
            END AS geometry
        FROM catalogued_scenes
        WHERE {' AND '.join(conditions)}
        ORDER BY datetime DESC
        LIMIT %s
    """
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
    except Exception as e:
        logger.warning(f"get_scenes_in_bbox failed: {e}")
        return []

    result = []
    for row in rows:
        d = dict(row)
        if d.get("datetime"):
            d["datetime"] = d["datetime"].isoformat()
        result.append(d)
    return result


def acknowledge_alert(alert_id: int) -> bool:
    """Mark one alert acknowledged.  Returns True if a row was updated."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE monitoring_alerts SET acknowledged = TRUE "
                    "WHERE id = %s AND acknowledged = FALSE RETURNING id;",
                    (alert_id,),
                )
                row = cur.fetchone()
            conn.commit()
        return row is not None
    except Exception as e:
        logger.warning(f"acknowledge_alert({alert_id}) failed: {e}")
        return False


def get_scenes_covering_bbox(
    bbox: List[float],
    min_coverage: float = 0.6,
    limit: int = 100,
    since_days: Optional[int] = None,
    collection: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return scenes whose footprint COVERS at least `min_coverage` of an ROI bbox.

    ST_Intersects (used by get_scenes_in_bbox) accepts a scene that clips the
    ROI by a single sliver.  Reading a window from such a scene yields a raster
    that is almost entirely boundless zero-fill, and every index computed on it
    is meaningless — NDBI over zeros reads as "not bare", silently reporting a
    heavily mined landscape as ~0% bare ground.

    This variant computes the real overlap ratio and filters on it, returning
    `coverage_ratio` on each row so callers can order or log it.
    """
    if len(bbox) != 4:
        return []

    conditions = [
        "ST_Intersects(geom, ST_MakeEnvelope(%s, %s, %s, %s, 4326))",
        """ST_Area(ST_Intersection(geom, ST_MakeEnvelope(%s, %s, %s, %s, 4326)))
           / NULLIF(ST_Area(ST_MakeEnvelope(%s, %s, %s, %s, 4326)), 0) >= %s""",
    ]
    params: List[Any] = list(bbox) + list(bbox) + list(bbox) + [min_coverage]

    if collection:
        conditions.append("collection = %s")
        params.append(collection)
    if since_days is not None:
        conditions.append("datetime > NOW() - (%s * INTERVAL '1 day')")
        params.append(since_days)

    params.extend(list(bbox) + list(bbox))  # for the SELECT-list coverage_ratio
    params.append(limit)

    sql = f"""
        SELECT
            id, scene_id, collection, datetime, cloud_cover,
            thumbnail_url, stac_href,
            ST_Area(ST_Intersection(geom, ST_MakeEnvelope(%s, %s, %s, %s, 4326)))
              / NULLIF(ST_Area(ST_MakeEnvelope(%s, %s, %s, %s, 4326)), 0) AS coverage_ratio,
            CASE WHEN geom IS NOT NULL THEN ST_AsGeoJSON(geom)::json ELSE NULL END AS geometry
        FROM catalogued_scenes
        WHERE {' AND '.join(conditions)}
        ORDER BY datetime DESC
        LIMIT %s
    """
    # The SELECT list is evaluated before WHERE placeholders in our param order,
    # so rebuild the tuple in textual placeholder order: SELECT first, then WHERE.
    select_params = list(bbox) + list(bbox)
    where_params: List[Any] = list(bbox) + list(bbox) + list(bbox) + [min_coverage]
    if collection:
        where_params.append(collection)
    if since_days is not None:
        where_params.append(since_days)
    ordered = tuple(select_params + where_params + [limit])

    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, ordered)
                rows = cur.fetchall()
    except Exception as e:
        logger.warning(f"get_scenes_covering_bbox failed: {e}")
        return []

    result = []
    for row in rows:
        d = dict(row)
        if d.get("datetime"):
            d["datetime"] = d["datetime"].isoformat()
        if d.get("coverage_ratio") is not None:
            d["coverage_ratio"] = float(d["coverage_ratio"])
        result.append(d)
    return result
