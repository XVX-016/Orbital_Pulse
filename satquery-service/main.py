import os
import time
import logging
import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import base64
import io
import torch
from PIL import Image

from controller import route_and_execute
from geochat_engine import load_image_robust
from prompt_builder import build_geochat_prompt
from response_formatter import polish_model_output
from narrative_composer import compose_narrative
import db as analysis_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thread pool for off-event-loop DB writes (persist_analysis is sync psycopg2)
_db_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="db-writer")

app = FastAPI(title="SatQuery AI Service (Remote-Sensing VQA & Agentic Analysis)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    query: str
    scenario: Optional[str] = None
    modality: Optional[str] = "optical"
    temporal: Optional[str] = "single"

@app.on_event("startup")
async def startup_event():
    # Ensure database schema is ready
    analysis_db.init_db()

    # Launch STAC metadata-only catalog background ingestion daemon
    try:
        from stac_catalog import stac_catalog_daemon
        asyncio.create_task(stac_catalog_daemon())
        logger.info("STAC catalog background daemon scheduled.")
    except Exception as stac_err:
        logger.warning(f"Could not start STAC catalog daemon: {stac_err}")

    # Track B: INSAT-3DR thermal-IR ingestion + convective-risk alerts (idles
    # with a log line until MOSDAC credentials are configured)
    try:
        from insat_ingest import insat_daemon
        asyncio.create_task(insat_daemon())
        logger.info("INSAT ingestion daemon scheduled.")
    except Exception as insat_err:
        logger.warning(f"Could not start INSAT daemon: {insat_err}")

    # Load 4-bit GeoChat-7B model engine once at startup
    try:
        from geochat_engine import init_geochat_model
        if not init_geochat_model("MBZUAI/geochat-7B"):
            logger.warning("GeoChat is degraded; see /health geochat_error for the actionable loader failure.")
    except Exception as ge_err:
        logger.error(f"Failed to initialize GeoChat engine: {ge_err}")

    os.makedirs("data/deforestation", exist_ok=True)
    os.makedirs("data/disaster", exist_ok=True)
    os.makedirs("public/masks", exist_ok=True)
    os.makedirs("public/images", exist_ok=True)

    app.mount("/masks", StaticFiles(directory="public/masks"), name="masks")
    app.mount("/images", StaticFiles(directory="public/images"), name="images")

@app.get("/health")
def health_check():
    from geochat_engine import is_geochat_loaded, geochat_status
    peak_vram_gb = torch.cuda.max_memory_allocated() / 1024**3 if torch.cuda.is_available() else 0.0
    return {
        "status": "ok" if is_geochat_loaded() else "degraded",
        "service": "SatQuery AI Agentic Service",
        "model": "MBZUAI/geochat-7B (4-bit)",
        "geochat_loaded": is_geochat_loaded(),
        "geochat_error": geochat_status()["error"],
        "peak_vram_gb": round(peak_vram_gb, 2),
    }

@app.get("/api/satellites/{constellation}")
def get_satellites_by_constellation(constellation: str):
    """
    Fetch TLEs for a given constellation from Celestrak.
    """
    import urllib.request
    from fastapi.responses import PlainTextResponse

    celestrak_map = {
        "starlink": "GROUP=starlink",
        "active": "GROUP=active",
        "stations": "GROUP=stations",
        "gps": "GROUP=gps-ops",
    }
    
    query = celestrak_map.get(constellation.lower())
    if not query:
        raise HTTPException(status_code=400, detail="Invalid constellation name")

    url = f"https://celestrak.org/NORAD/elements/gp.php?{query}&FORMAT=tle"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})
        with urllib.request.urlopen(req, timeout=10.0) as response:
            data = response.read().decode('utf-8')
            return PlainTextResponse(data)
    except Exception as e:
        logger.error(f"Failed to fetch TLEs for {constellation}: {e}")
        raise HTTPException(status_code=502, detail="Failed to fetch constellation data from Celestrak")

@app.post("/api/analyze")
async def analyze_query(request: Request):
    """Main Agentic VQA & Remote-Sensing Analysis Endpoint.

    Accepts JSON body (`{"query": "...", "scenario": "...", ...}`) or multipart form data.
    Routes execution to appropriate specialist via Controller and returns structured output
    with auditable execution trace.
    """
    content_type = request.headers.get("content-type", "")
    
    user_query = ""
    scenario = None
    modality = "optical"
    temporal = "single"
    images_payload = []
    preview_base64_list = []

    if "application/json" in content_type:
        body = await request.json()
        user_query = body.get("query", "")
        scenario = body.get("scenario")
        scenario_preset = body.get("scenario_preset") or scenario
        modality = body.get("modality", "optical")
        temporal = body.get("temporal", "single")
        lat = body.get("lat")
        lon = body.get("lon")
        start_date = body.get("start_date")
        end_date = body.get("end_date")
        collection = body.get("collection")
    else:
        form = await request.form()
        user_query = form.get("query", "")
        scenario = form.get("scenario")
        scenario_preset = form.get("scenario_preset") or scenario
        modality = form.get("modality", "optical")
        temporal = form.get("temporal", "single")
        lat = form.get("lat")
        lon = form.get("lon")
        start_date = form.get("start_date")
        end_date = form.get("end_date")
        collection = form.get("collection")
        
        # Collect file uploads if present
        for key in form:
            val = form[key]
            if hasattr(val, "filename") and val.filename:
                contents = await val.read()
                img = load_image_robust(contents)
                if img is not None:
                    images_payload.append(img)
                    try:
                        buf = io.BytesIO()
                        img.save(buf, format="JPEG", quality=85)
                        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
                        preview_base64_list.append(f"data:image/jpeg;base64,{b64_str}")
                    except Exception as e:
                        logger.warning(f"Could not generate base64 preview: {e}")
                else:
                    logger.warning(f"Could not decode uploaded file '{val.filename}' via PIL or rasterio — skipping.")

    if not user_query:
        raise HTTPException(status_code=400, detail="Query string is required.")

    custom_params: dict = {}
    scenario_preset = str(scenario_preset or "")
    custom_params["scenario_preset"] = scenario_preset
    # Tracks which data path served the location query; surfaced in the response.
    data_source: Optional[str] = None

    # Query by location: lookup matching catalogued scene and lazily fetch pixels
    matched_scene = None
    data_warnings: list = []
    if lat is not None and lon is not None and not images_payload and not scenario:
        try:
            f_lat = float(lat)
            f_lon = float(lon)
            matched_scene = analysis_db.find_scene_by_location(
                lon=f_lon,
                lat=f_lat,
                start_date=start_date,
                end_date=end_date,
                collection=collection,
            )
            if matched_scene:
                logger.info(f"Query by location: matched scene {matched_scene['scene_id']} ({matched_scene['collection']}) [cached catalog]")
                data_source = "cached_catalog"
                custom_params["data_source_path"] = "cached_catalog"
                data_warnings.append(
                    f"Data source: pre-catalogued scene {matched_scene['scene_id']} "
                    f"(collection={matched_scene['collection']}) — "
                    "instant result from background-ingested catalog."
                )
                from stac_catalog import fetch_scene_cog_data
                cog_data = fetch_scene_cog_data(matched_scene)
                raw_bytes = cog_data.get("image_bytes")
                if cog_data.get("ndvi_metrics"):
                    custom_params["stac_cog_metrics"] = {
                        **cog_data["ndvi_metrics"],
                        "scene_id": matched_scene["scene_id"],
                        "cloud_cover": matched_scene.get("cloud_cover"),
                    }

                if raw_bytes:
                    logger.info(f"Query by location: fetched {len(raw_bytes):,} bytes from scene {matched_scene['scene_id']}")
                    scene_img = load_image_robust(raw_bytes)
                    if scene_img:
                        logger.info(f"Query by location: decoded image {scene_img.size} mode={scene_img.mode}")
                        images_payload.append(scene_img)
                        # A single lazily-fetched scene is always a single-image query;
                        # override temporal so the controller doesn't misroute to change_vqa
                        # based purely on query text keywords (e.g. "deforestation").
                        temporal = "single"
                        buf = io.BytesIO()
                        scene_img.save(buf, format="JPEG", quality=85)
                        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
                        preview_base64_list.append(f"data:image/jpeg;base64,{b64_str}")
                    else:
                        warn = f"Image decode failed for scene {matched_scene['scene_id']} — fetched {len(raw_bytes):,} bytes but PIL could not decode"
                        logger.warning(warn)
                        data_warnings.append(warn)
                else:
                    warn = f"No pixel data available for scene {matched_scene['scene_id']} (collection={matched_scene.get('collection')}): all fetch strategies failed"
                    logger.warning(warn)
                    data_warnings.append(warn)
                # Propagate any per-step warnings from fetch_scene_cog_data
                data_warnings.extend(cog_data.get("warnings") or [])

                # Pass matched scene geometry and metadata into trace params
                geom = matched_scene.get("geometry")
                if geom and geom.get("type") == "Polygon":
                    coords = geom.get("coordinates", [[]])[0]
                    if len(coords) >= 4:
                        pts = ", ".join(f"{c[0]} {c[1]}" for c in coords)
                        custom_params["scene_geometry_wkt"] = f"POLYGON(({pts}))"
                custom_params["catalog_scene_id"] = matched_scene.get("scene_id")
                custom_params["catalog_collection"] = matched_scene.get("collection")
                if matched_scene.get("thumbnail_url"):
                    custom_params["catalog_thumbnail_url"] = matched_scene["thumbnail_url"]
            else:
                # ── Live STAC fallback ────────────────────────────────────────────
                # No pre-catalogued scene covers this point. Delegate to
                # fetch_live_scene_for_point() in stac_catalog.py — all bbox
                # construction, cloud-cover ranking, and scene-dict assembly live
                # there; nothing is duplicated here.
                logger.info(
                    "No cached scene for (%.4f, %.4f) — attempting live Earth Search STAC fallback",
                    f_lon, f_lat,
                )
                data_warnings.append(
                    f"No pre-catalogued scene found for ({f_lon:.4f}, {f_lat:.4f}). "
                    "Falling back to a live Earth Search STAC query — expect higher latency "
                    "than results from the pre-warmed catalog regions."
                )
                try:
                    from stac_catalog import fetch_live_scene_for_point, fetch_scene_cog_data

                    _live_scene = fetch_live_scene_for_point(
                        lon=f_lon,
                        lat=f_lat,
                        start_date=start_date,
                        end_date=end_date,
                        collection=collection,
                    )

                    if _live_scene:
                        _scene_id = _live_scene["scene_id"]
                        _item_collection = _live_scene["collection"]
                        _dt_str = _live_scene.get("datetime", "")
                        _cc = _live_scene.get("cloud_cover") or 100.0

                        _cog_data = fetch_scene_cog_data(_live_scene)
                        _raw_bytes = _cog_data.get("image_bytes")
                        if _cog_data.get("ndvi_metrics"):
                            custom_params["stac_cog_metrics"] = {
                                **_cog_data["ndvi_metrics"],
                                "scene_id": _scene_id,
                                "cloud_cover": _cc,
                            }

                        if _raw_bytes:
                            _scene_img = load_image_robust(_raw_bytes)
                            if _scene_img:
                                images_payload.append(_scene_img)
                                temporal = "single"
                                _buf = io.BytesIO()
                                _scene_img.save(_buf, format="JPEG", quality=85)
                                preview_base64_list.append(
                                    "data:image/jpeg;base64,"
                                    + base64.b64encode(_buf.getvalue()).decode("utf-8")
                                )
                                logger.info(
                                    "Live STAC fallback: decoded image %s mode=%s",
                                    _scene_img.size, _scene_img.mode,
                                )
                            else:
                                data_warnings.append(
                                    f"Live STAC fallback: image decode failed for scene {_scene_id} "
                                    f"— fetched {len(_raw_bytes):,} bytes but PIL could not decode."
                                )
                        else:
                            data_warnings.append(
                                f"Live STAC fallback: no pixel data available for scene {_scene_id} "
                                f"(collection={_item_collection}) — all fetch strategies failed."
                            )

                        data_warnings.extend(_cog_data.get("warnings") or [])

                        # Surface scene provenance in the trace params and top-level response
                        data_source = "live_fallback"
                        custom_params["data_source_path"] = "live_stac_fallback"
                        custom_params["catalog_scene_id"] = _scene_id
                        custom_params["catalog_collection"] = _item_collection
                        if _live_scene.get("thumbnail_url"):
                            custom_params["catalog_thumbnail_url"] = _live_scene["thumbnail_url"]
                        _geom = _live_scene.get("geometry")
                        if _geom and _geom.get("type") == "Polygon":
                            _coords = _geom.get("coordinates", [[]])[0]
                            if len(_coords) >= 4:
                                _pts = ", ".join(f"{c[0]} {c[1]}" for c in _coords)
                                custom_params["scene_geometry_wkt"] = f"POLYGON(({_pts}))"

                        data_warnings.append(
                            f"Live STAC fallback succeeded: scene {_scene_id} "
                            f"(collection={_item_collection}, cloud_cover={_cc:.1f}%, "
                            f"datetime={_dt_str}). "
                            "Results were fetched on-demand; pre-cataloguing this region "
                            "would eliminate this latency."
                        )
                    else:
                        warn = (
                            f"Live STAC fallback found no scenes within ±0.15° of "
                            f"({f_lon:.4f}, {f_lat:.4f}). "
                            "The requested location may have no recent satellite coverage."
                        )
                        logger.warning(warn)
                        data_warnings.append(warn)
                        custom_params["data_source_path"] = "live_stac_fallback_empty"

                except Exception as live_err:
                    warn = f"Live STAC fallback failed: {live_err}"
                    logger.warning(warn, exc_info=True)
                    data_warnings.append(warn)
                    custom_params["data_source_path"] = "live_stac_fallback_error"

        except Exception as loc_err:
            warn = f"Location-based scene lookup/fetch failed: {loc_err}"
            logger.warning(warn, exc_info=True)
            data_warnings.append(warn)

    # If scenario specified, load bi-temporal pair for change detection / change-VQA
    if scenario:
        before_path = f"data/{scenario}/before.tif"
        after_path = f"data/{scenario}/after.tif"
        if os.path.exists(before_path) and os.path.exists(after_path):
            before_img = load_image_robust(before_path)
            after_img = load_image_robust(after_path)
            if before_img and after_img:
                images_payload = [before_img, after_img]
                temporal = "bi-temporal"
                # Encode both scenario images to base64 for frontend slider preview
                scenario_previews = []
                for s_img in [before_img, after_img]:
                    try:
                        buf = io.BytesIO()
                        s_img.save(buf, format="JPEG", quality=85)
                        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
                        scenario_previews.append(f"data:image/jpeg;base64,{b64_str}")
                    except Exception as e:
                        logger.warning(f"Could not generate scenario base64 preview: {e}")
                if len(scenario_previews) == 2:
                    preview_base64_list = scenario_previews

    # Inject TIF paths into params so controller / metrics / db can reference them
    if scenario:
        before_path = f"data/{scenario}/before.tif"
        after_path = f"data/{scenario}/after.tif"
        if os.path.exists(before_path):
            custom_params["before_tif_path"] = before_path
        if os.path.exists(after_path):
            custom_params["after_tif_path"] = after_path

    # Route through controller
    geochat_prompt = build_geochat_prompt(scenario_preset, user_query)
    response = route_and_execute(
        images=images_payload,
        query=geochat_prompt,
        modality=modality or "optical",
        temporal=temporal or "single",
        custom_parameters=custom_params,
    )

    if isinstance(response, dict):
        response["answer"] = polish_model_output(
            response.get("answer", ""), scenario_preset, custom_params.get("stac_cog_metrics"), user_query,
        )

    if isinstance(response, dict) and preview_base64_list:
        response["preview_images_base64"] = preview_base64_list
        response["preview_image_base64"] = preview_base64_list[0]

    # Surface data_source as a top-level field so the frontend and execution
    # traces can read it without parsing execution_trace.parameters.
    # Values: "cached_catalog" | "live_fallback" | absent (non-location query).
    if data_source:
        response["data_source"] = data_source

    # ── Deterministic narrative ──────────────────────────────────────────────
    # Template-based composition of the model answer + the independently computed
    # metrics.  Pure string work — no second model call.
    if isinstance(response, dict):
        try:
            response["narrative"] = compose_narrative(
                answer=response.get("answer", ""),
                computed_metrics=response.get("computed_metrics"),
                task_type=response.get("execution_trace", {}).get("task"),
            )
        except Exception as e:
            logger.warning(f"Narrative composition failed (non-fatal): {e}")

    # Surface any STAC fetch warnings to the caller so they appear in the frontend
    if data_warnings:
        response["data_warnings"] = data_warnings
        logger.warning("Returning %d data warning(s) in API response: %s", len(data_warnings), data_warnings)

    # ── Non-blocking DB persist ──────────────────────────────────────────────
    # Fire-and-forget: submit to the thread pool and do NOT await the result.
    # If the write fails, persist_analysis logs a warning but never propagates.
    try:
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            _db_executor,
            _sync_persist,
            user_query,
            response.get("execution_trace", {}),
            modality,
            temporal,
            response.get("answer", ""),
            response.get("computed_metrics"),
        )
    except Exception as e:
        logger.warning(f"Could not schedule DB persist (non-fatal): {e}")

    return response


def _sync_persist(
    query_text: str,
    execution_trace: dict,
    modality: str,
    temporal: str,
    vlm_answer: str,
    computed_metrics,
) -> None:
    """Synchronous wrapper called from the thread-pool executor."""
    task_type = execution_trace.get("task", "unknown")
    analysis_db.persist_analysis(
        query_text=query_text,
        task_type=task_type,
        modality=modality,
        temporal=temporal,
        vlm_answer=vlm_answer,
        computed_metrics=computed_metrics,
        execution_trace=execution_trace,
    )


@app.get("/api/analyses")
async def list_analyses(limit: int = 50):
    """Return recent persisted analyses with geometries (GeoJSON-friendly).

    Consumed by the future map page. Returns a FeatureCollection so the
    frontend can drop it directly onto a Cesium / Leaflet layer.

    Query params:
      limit (int, default 50) — max number of results, capped at 200.
    """
    limit = min(max(1, limit), 200)
    try:
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(
            _db_executor,
            analysis_db.get_recent_analyses,
            limit,
        )
    except Exception as e:
        logger.error(f"GET /api/analyses DB error: {e}")
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")

    # Shape as a GeoJSON FeatureCollection for map consumers
    features = []
    for row in rows:
        geom = row.pop("geometry", None)
        features.append({
            "type": "Feature",
            "geometry": geom,       # None → GeoJSON null geometry (allowed)
            "properties": row,
        })

    return {
        "type": "FeatureCollection",
        "count": len(features),
        "features": features,
    }


@app.get("/api/catalog")
async def list_catalog(limit: int = 100):
    """Return recent catalogued scenes as GeoJSON FeatureCollection.

    Query params:
      limit (int, default 100) — max number of scenes, capped at 300.
    """
    limit = min(max(1, limit), 300)
    try:
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(
            _db_executor,
            analysis_db.get_recent_catalog_scenes,
            limit,
        )
    except Exception as e:
        logger.error(f"GET /api/catalog DB error: {e}")
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")

    features = []
    for row in rows:
        geom = row.pop("geometry", None)
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": row,
        })

    return {
        "type": "FeatureCollection",
        "count": len(features),
        "features": features,
    }


def _sync_region_status(region: dict) -> dict:
    """Latest catalog + alert state for one monitored mining region."""
    from mining_monitor import MAX_CLOUD_COVER_PCT, MIN_SCENE_COVERAGE

    scenes = analysis_db.get_scenes_covering_bbox(
        region["bbox"],
        min_coverage=MIN_SCENE_COVERAGE,
        limit=100,
        since_days=365,
        collection="sentinel-2-l2a",
    )
    clear = [
        s for s in scenes
        if s.get("cloud_cover") is not None and float(s["cloud_cover"]) <= MAX_CLOUD_COVER_PCT
    ]
    alerts = analysis_db.get_recent_alerts(
        limit=20, region_name=region["name"], alert_type="land_change"
    )
    return {
        "scene_count": len(scenes),
        "clear_scene_count": len(clear),
        "latest_scene": scenes[0] if scenes else None,
        "latest_clear_scene": clear[0] if clear else None,
        "open_alert_count": sum(1 for a in alerts if not a.get("acknowledged")),
        "alerts": alerts,
    }


@app.get("/api/monitored-regions")
async def list_monitored_regions():
    """Monitored mining regions as a GeoJSON FeatureCollection of boundaries.

    Every feature carries `boundary_is_approximate` and `boundary_caveat` so the
    UI can show the provenance caveat next to any boundary-derived figure.
    """
    from mining_regions import MINING_REGIONS, boundary_to_geojson

    loop = asyncio.get_event_loop()
    features = []
    for region in MINING_REGIONS:
        try:
            status = await loop.run_in_executor(_db_executor, _sync_region_status, region)
        except Exception as e:
            logger.error(f"GET /api/monitored-regions DB error: {e}")
            raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")
        features.append({
            "type": "Feature",
            "geometry": boundary_to_geojson(region),
            "properties": {
                "name": region["name"],
                "display_name": region.get("display_name", region["name"]),
                "commodity": region.get("commodity"),
                "bbox": region["bbox"],
                "monitored": region.get("monitored", False),
                "boundary_is_approximate": region.get("boundary_is_approximate", True),
                "boundary_caveat": region.get("boundary_caveat"),
                "boundary_source": region.get("boundary_source"),
                **status,
            },
        })

    return {"type": "FeatureCollection", "count": len(features), "features": features}


def _sync_weather_region_status(region: dict) -> dict:
    """Latest INSAT frame, gate state, live risk assessment and alerts for one region."""
    import storm_risk

    frames = analysis_db.get_insat_frames(region_name=region["name"], limit=1)
    recent = analysis_db.get_insat_frames(region_name=region["name"], limit=200, since_hours=24)
    alerts = analysis_db.get_recent_alerts(
        limit=30, region_name=region["name"], alert_type="severe_weather"
    )
    latest = frames[0] if frames else None
    return {
        "latest_frame": {
            "id": latest["id"],
            "identifier": latest["identifier"],
            "acquired_at": latest["acquired_at"],
            "auto_checks_passed": latest["auto_checks_passed"],
            "stats": latest["stats"],
        } if latest else None,
        "frames_24h": len(recent),
        "assessment": storm_risk.assess_region(region),
        "open_alert_count": sum(1 for a in alerts if not a.get("acknowledged")),
        "alerts": alerts,
    }


@app.get("/api/weather-regions")
async def list_weather_regions():
    """Monitored severe-weather regions as GeoJSON, with INSAT feed state.

    `feed` reports whether MOSDAC credentials are configured and whether the
    Prompt 7 manual verification gate is open; the per-region `assessment` is
    computed live from stored frames and is `gate_closed` until it is.
    """
    import insat_ingest
    import storm_risk
    from weather_regions import WEATHER_REGIONS, bbox_to_geojson

    loop = asyncio.get_event_loop()
    try:
        gate = await loop.run_in_executor(_db_executor, storm_risk.gate_status)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")

    features = []
    for region in WEATHER_REGIONS:
        try:
            status = await loop.run_in_executor(_db_executor, _sync_weather_region_status, region)
        except Exception as e:
            logger.error(f"GET /api/weather-regions DB error: {e}")
            raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")
        features.append({
            "type": "Feature",
            "geometry": bbox_to_geojson(region["bbox"]),
            "properties": {
                "name": region["name"],
                "display_name": region["display_name"],
                "context": region.get("context"),
                "bbox": region["bbox"],
                **status,
            },
        })

    return {
        "type": "FeatureCollection",
        "feed": {
            "source": "MOSDAC (SAC-ISRO)",
            "dataset_id": insat_ingest.DATASET_ID,
            "credentials_configured": insat_ingest.credentials_configured(),
            "auth_disabled_reason": insat_ingest.auth_disabled_reason(),
            "gate": gate,
        },
        "features": features,
    }


class AlertCreateRequest(BaseModel):
    """Manual alert insertion payload (operator-raised or test alerts).

    Mirrors what an alert-check function returns, so the same validation path in
    db.insert_monitoring_alert() covers both the daemon and this endpoint.
    """
    region_name: str
    alert_type: str                              # 'land_change' | 'severe_weather'
    severity: str                                # 'info' | 'warning' | 'critical'
    computed_metrics: Optional[dict] = None
    geom_wkt: Optional[str] = None               # WGS-84 WKT; NULL geometry if omitted


@app.get("/api/alerts")
async def list_alerts(
    limit: int = 50,
    acknowledged: Optional[bool] = None,
    region_name: Optional[str] = None,
    alert_type: Optional[str] = None,
):
    """Return recent monitoring alerts as a GeoJSON FeatureCollection.

    Alerts are raised by the STAC daemon's registered alert-check functions after
    each poll cycle, or inserted manually via POST /api/alerts.

    Query params:
      limit        (int, default 50)  — max results, capped at 200.
      acknowledged (bool, optional)   — filter by acknowledgement state.
      region_name  (str, optional)    — filter to one ROI.
      alert_type   (str, optional)    — 'land_change' | 'severe_weather'.
    """
    limit = min(max(1, limit), 200)

    if alert_type is not None and alert_type not in analysis_db.VALID_ALERT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"alert_type must be one of {list(analysis_db.VALID_ALERT_TYPES)}",
        )

    try:
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(
            _db_executor,
            functools.partial(
                analysis_db.get_recent_alerts,
                limit=limit,
                acknowledged=acknowledged,
                region_name=region_name,
                alert_type=alert_type,
            ),
        )
    except Exception as e:
        logger.error(f"GET /api/alerts DB error: {e}")
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")

    features = []
    for row in rows:
        geom = row.pop("geometry", None)
        features.append({
            "type": "Feature",
            "geometry": geom,       # None → GeoJSON null geometry (allowed)
            "properties": row,
        })

    return {
        "type": "FeatureCollection",
        "count": len(features),
        "features": features,
    }


@app.post("/api/alerts", status_code=201)
async def create_alert(req: AlertCreateRequest):
    """Insert one alert manually and return the created row.

    Used for operator-raised alerts and for end-to-end verification of the
    alerting path without waiting for a daemon poll cycle.
    """
    if req.alert_type not in analysis_db.VALID_ALERT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"alert_type must be one of {list(analysis_db.VALID_ALERT_TYPES)}",
        )
    if req.severity not in analysis_db.VALID_SEVERITIES:
        raise HTTPException(
            status_code=400,
            detail=f"severity must be one of {list(analysis_db.VALID_SEVERITIES)}",
        )

    loop = asyncio.get_event_loop()
    alert_id = await loop.run_in_executor(
        _db_executor,
        functools.partial(
            analysis_db.insert_monitoring_alert,
            region_name=req.region_name,
            alert_type=req.alert_type,
            severity=req.severity,
            computed_metrics=req.computed_metrics,
            geom_wkt=req.geom_wkt,
        ),
    )

    if alert_id is None:
        raise HTTPException(
            status_code=503,
            detail="Alert insert failed — see service logs for the DB error.",
        )

    return {"id": alert_id, "status": "created"}


@app.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert_endpoint(alert_id: int):
    """Mark an alert acknowledged, re-arming its region for a fresh alert."""
    loop = asyncio.get_event_loop()
    updated = await loop.run_in_executor(
        _db_executor, analysis_db.acknowledge_alert, alert_id
    )
    if not updated:
        raise HTTPException(
            status_code=404,
            detail=f"No unacknowledged alert with id={alert_id}",
        )
    return {"id": alert_id, "acknowledged": True}
