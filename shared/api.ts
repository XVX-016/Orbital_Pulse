/**
 * Shared code between client and backend services
 * Useful to share types between client and services
 * and/or small pure JS functions that can be used on both client and services
 */

/**
 * Example response type for /api/demo
 */
export interface DemoResponse {
  message: string;
}

// ---------------------------------------------------------------------------
// /api/analyze
// ---------------------------------------------------------------------------

/**
 * Discriminator that indicates which data path served a location-based query.
 *
 * - `"cached_catalog"` — the scene was found in the pre-ingested PostGIS catalog
 *   (fast, sub-second lookup via `find_scene_by_location()`).
 * - `"live_fallback"` — no cached scene covered the requested coordinate; the
 *   service fell back to a real-time Earth Search STAC query via
 *   `fetch_live_scene_for_point()` (higher latency, works for any global point).
 *
 * `undefined` when the request was not a location-based query (e.g. direct
 * image upload or scenario-based analysis).
 */
export type DataSource = "cached_catalog" | "live_fallback";

/** Structured response returned by POST /api/analyze */
export interface AnalyzeResponse {
  /** Primary qualitative answer from the VLM (GeoChat). */
  answer: string;
  /** Model confidence score, if available. */
  confidence?: number | null;
  /** Bounding boxes / SAR metrics from the VLM, task-dependent. */
  visual_evidence?: unknown | null;
  /** Deterministic geospatial measurements (NDVI, change area, etc.). */
  computed_metrics?: unknown | null;
  /** Auditable trace: task type, specialist used, and all parameters. */
  execution_trace: {
    task: string;
    specialist_used: string;
    parameters: Record<string, unknown>;
  };
  /**
   * Which data path served this result.
   * Present only for location-based queries (lat/lon provided without images).
   */
  data_source?: DataSource;
  /** Non-fatal warnings from STAC fetch / image decode steps. */
  data_warnings?: string[];
  /** Base64-encoded JPEG preview of the first image sent to the VLM. */
  preview_image_base64?: string;
  /** All preview images (e.g. bi-temporal before/after pair). */
  preview_images_base64?: string[];
}
