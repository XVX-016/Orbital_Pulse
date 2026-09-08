import os
import time
import logging
import asyncio
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

    # Load 4-bit GeoChat-7B model engine once at startup
    try:
        from geochat_engine import init_geochat_model
        init_geochat_model("MBZUAI/geochat-7B")
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
    from geochat_engine import is_geochat_loaded
    peak_vram_gb = torch.cuda.max_memory_allocated() / 1024**3 if torch.cuda.is_available() else 0.0
    return {
        "status": "ok" if is_geochat_loaded() else "degraded",
        "service": "SatQuery AI Agentic Service",
        "model": "MBZUAI/geochat-7B (4-bit)",
        "geochat_loaded": is_geochat_loaded(),
        "peak_vram_gb": round(peak_vram_gb, 2),
    }

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
                    custom_params["stac_cog_metrics"] = cog_data["ndvi_metrics"]

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
                            custom_params["stac_cog_metrics"] = _cog_data["ndvi_metrics"]

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
    response = route_and_execute(
        images=images_payload,
        query=user_query,
        modality=modality or "optical",
        temporal=temporal or "single",
        custom_parameters=custom_params,
    )

    if isinstance(response, dict) and preview_base64_list:
        response["preview_images_base64"] = preview_base64_list
        response["preview_image_base64"] = preview_base64_list[0]

    # Surface data_source as a top-level field so the frontend and execution
    # traces can read it without parsing execution_trace.parameters.
    # Values: "cached_catalog" | "live_fallback" | absent (non-location query).
    if data_source:
        response["data_source"] = data_source

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

