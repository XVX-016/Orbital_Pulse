-- SatQuery AI — PostGIS schema initialisation
-- Runs automatically on first container boot via /docker-entrypoint-initdb.d/

CREATE EXTENSION IF NOT EXISTS postgis;

-- One row per completed /api/analyze request
CREATE TABLE IF NOT EXISTS analyses (
    id               BIGSERIAL PRIMARY KEY,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    query_text       TEXT        NOT NULL,
    task_type        TEXT        NOT NULL,
    modality         TEXT,
    temporal         TEXT,
    vlm_answer       TEXT,
    computed_metrics JSONB,
    -- WGS-84 geometry: point (scene centre) or bbox polygon when georef is available,
    -- NULL when no geotransform is present (plain JPEG/PNG upload with no projection)
    geom             GEOMETRY(Geometry, 4326)
);

-- Descending time index — the /api/analyses endpoint always ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS analyses_created_at_idx ON analyses (created_at DESC);

-- Spatial index for future map queries (bbox intersects, nearby, etc.)
CREATE INDEX IF NOT EXISTS analyses_geom_idx       ON analyses USING GIST (geom);

-- Lightweight STAC catalogued scenes metadata table
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


-- ─── Monitoring alerts ────────────────────────────────────────────────────────
-- Raised by the STAC ingestion daemon's pluggable alert-check hooks (one row per
-- triggered check).  `computed_metrics` carries whatever the check function used
-- to reach its verdict, so an alert is always auditable after the fact.
CREATE TABLE IF NOT EXISTS monitoring_alerts (
    id               BIGSERIAL PRIMARY KEY,
    region_name      TEXT        NOT NULL,
    alert_type       TEXT        NOT NULL
                     CHECK (alert_type IN ('land_change', 'severe_weather')),
    severity         TEXT        NOT NULL
                     CHECK (severity IN ('info', 'warning', 'critical')),
    computed_metrics JSONB,
    -- WGS-84 ROI footprint (polygon) or scene centre (point); NULL when the
    -- triggering check had no georeferenced context
    geom             GEOMETRY(Geometry, 4326),
    "timestamp"      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged     BOOLEAN     NOT NULL DEFAULT FALSE
);

-- Descending time index — /api/alerts always ORDER BY "timestamp" DESC
CREATE INDEX IF NOT EXISTS monitoring_alerts_timestamp_idx ON monitoring_alerts ("timestamp" DESC);

-- Spatial index for map overlay queries (alerts intersecting a viewport)
CREATE INDEX IF NOT EXISTS monitoring_alerts_geom_idx      ON monitoring_alerts USING GIST (geom);

-- Partial index for the common "show me what still needs attention" query
CREATE INDEX IF NOT EXISTS monitoring_alerts_unack_idx     ON monitoring_alerts ("timestamp" DESC)
    WHERE acknowledged = FALSE;


-- ─── INSAT thermal-IR frames (Track B) ───────────────────────────────────────
-- One row per (INSAT frame, weather region).  Every column that lets a
-- reader trace a brightness temperature back to a real MOSDAC archive file
-- is kept: the exact search/download requests, the file hash, the HDF5
-- acquisition attributes and a raw count -> BT sample.
CREATE TABLE IF NOT EXISTS insat_frames (
    id                    BIGSERIAL PRIMARY KEY,
    dataset_id            TEXT        NOT NULL,
    identifier            TEXT        NOT NULL,
    record_id             TEXT        NOT NULL,
    region_name           TEXT        NOT NULL,
    acquired_at           TIMESTAMPTZ NOT NULL,
    search_url            TEXT,
    download_request      TEXT,
    archive_link          TEXT,
    file_sha256           TEXT,
    file_bytes            BIGINT,
    h5_attrs              JSONB,
    geoloc_method         TEXT,
    raw_sample            JSONB,
    stats                 JSONB,
    array_path            TEXT,
    auto_checks           JSONB,
    auto_checks_passed    BOOLEAN     NOT NULL DEFAULT FALSE,
    manually_verified_at  TIMESTAMPTZ,
    manually_verified_note TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (identifier, region_name)
);

CREATE INDEX IF NOT EXISTS insat_frames_region_time_idx ON insat_frames (region_name, acquired_at DESC);
