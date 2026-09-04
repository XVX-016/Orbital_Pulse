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
