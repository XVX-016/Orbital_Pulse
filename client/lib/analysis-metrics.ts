export interface NdviResult {
  vegetation_pct?: number;
  vegetation_pct_sparse?: number;
  vegetation_pct_dense?: number;
  mean_ndvi?: number;
  min_ndvi?: number;
  max_ndvi?: number;
  vegetated_pixel_count?: number;
  dense_pixel_count?: number;
  valid_pixels?: number;
  total_pixels?: number;
}

export interface LandcoverResult {
  water_pct?: number;
  vegetation_pct?: number;
  builtup_pct?: number;
  other_pct?: number;
  dense_vegetation_pct?: number;
  sparse_vegetation_pct?: number;
  bare_soil_pct?: number;
  water_or_shadow_pct?: number;
  non_vegetated_pct?: number;
  total_pixels?: number;
}

export interface SpectralChangeResult {
  change_pct?: number;
  changed_pct?: number; // legacy alias fallback
  changed_pixels?: number;
  total_pixels?: number;
  changed_area_km2?: number | null;
  change_area_km2?: number | null; // legacy alias fallback
  changed_area_m2?: number | null;
  mean_spectral_distance?: number;
  max_spectral_distance?: number;
  georeferenced?: boolean;
}

export interface ObjectAreaResult {
  label?: string;
  box_normalized?: number[];
  area_km2?: number | null;
  area_m2?: number | null;
  width_km?: number;
  height_km?: number;
  pixel_count?: number;
  georeferenced?: boolean;
}

export interface ComputedMetrics {
  task?: string;
  georeferenced?: boolean;
  // VQA / single-image
  ndvi?: NdviResult;
  landcover?: LandcoverResult;
  // Change-VQA
  before_ndvi?: NdviResult;
  after_ndvi?: NdviResult;
  before_landcover?: LandcoverResult;
  after_landcover?: LandcoverResult;
  spectral_change?: SpectralChangeResult;
  // Grounding
  object_areas?: ObjectAreaResult[];
  // Dynamic arbitrary keys from evolving models or specialists
  [key: string]: any;
}

export interface AnalysisRecord {
  id: number | string;
  created_at?: string;
  query_text: string;
  task_type: string;
  modality?: string;
  temporal?: string;
  vlm_answer?: string;
  computed_metrics?: ComputedMetrics | null;
  [key: string]: any;
}

export interface AnalysisGeoJSONFeature {
  type: "Feature";
  geometry: {
    type: "Point" | "Polygon" | "MultiPolygon" | "LineString";
    coordinates: any;
  } | null;
  properties: AnalysisRecord;
}

export interface AnalysisFeatureCollection {
  type: "FeatureCollection";
  count: number;
  features: AnalysisGeoJSONFeature[];
}

export interface CatalogSceneRecord {
  id: number | string;
  scene_id: string;
  collection: string;
  datetime: string;
  cloud_cover: number | null;
  thumbnail_url: string | null;
  stac_href: string | null;
  created_at: string;
  [key: string]: any;
}

export interface CatalogGeoJSONFeature {
  type: "Feature";
  geometry: {
    type: "Polygon" | "Point";
    coordinates: any;
  } | null;
  properties: CatalogSceneRecord;
}

export interface CatalogFeatureCollection {
  type: "FeatureCollection";
  count: number;
  features: CatalogGeoJSONFeature[];
}


/**
 * Format a condensed computed-metrics summary string.
 *
 * Fully defensive against:
 * - null/undefined metrics
 * - malformed records with missing fields
 * - unexpected types (numbers as strings, non-array object_areas, etc.)
 * - field name variations between model versions (e.g. change_pct vs changed_pct,
 *   changed_area_km2 vs change_area_km2, vegetation_pct vs vegetation_pct_dense).
 */
export function formatCondensedMetrics(metrics?: ComputedMetrics | null): string {
  if (!metrics || typeof metrics !== "object") {
    return "No metrics available";
  }

  try {
    const parts: string[] = [];

    // 1. Spectral change metrics (change_vqa)
    const spectral = metrics.spectral_change;
    if (spectral && typeof spectral === "object") {
      const changePct = spectral.change_pct ?? spectral.changed_pct;
      if (typeof changePct === "number" && !isNaN(changePct)) {
        parts.push(`Change: ${changePct.toFixed(1)}%`);
      }

      const areaKm2 = spectral.changed_area_km2 ?? spectral.change_area_km2;
      if (typeof areaKm2 === "number" && !isNaN(areaKm2)) {
        parts.push(`Area: ${areaKm2.toFixed(2)} km²`);
      }
    }

    // 2. NDVI vegetation metrics (change_vqa after/before, or single-image vqa)
    const ndvi = metrics.after_ndvi || metrics.ndvi || metrics.before_ndvi;
    if (ndvi && typeof ndvi === "object") {
      if (typeof ndvi.vegetation_pct_dense === "number" && !isNaN(ndvi.vegetation_pct_dense)) {
        parts.push(`Dense canopy: ${ndvi.vegetation_pct_dense.toFixed(1)}%`);
      } else {
        const vegPct = ndvi.vegetation_pct_sparse ?? ndvi.vegetation_pct;
        if (typeof vegPct === "number" && !isNaN(vegPct)) {
          parts.push(`Veg: ${vegPct.toFixed(1)}%`);
        }
      }

      if (
        typeof ndvi.mean_ndvi === "number" &&
        !isNaN(ndvi.mean_ndvi) &&
        !spectral &&
        parts.length < 2
      ) {
        parts.push(`Mean NDVI: ${ndvi.mean_ndvi.toFixed(3)}`);
      }
    }

    // 3. Landcover metrics (landcover breakdown from geospatial_metrics.py)
    const lc = metrics.after_landcover || metrics.landcover || metrics.before_landcover;
    if (lc && typeof lc === "object" && parts.length < 2) {
      if (typeof lc.water_pct === "number" && !isNaN(lc.water_pct) && lc.water_pct > 0) {
        parts.push(`Water: ${lc.water_pct.toFixed(1)}%`);
      } else if (typeof lc.dense_vegetation_pct === "number" && !isNaN(lc.dense_vegetation_pct)) {
        parts.push(`Dense veg: ${lc.dense_vegetation_pct.toFixed(1)}%`);
      } else if (typeof lc.builtup_pct === "number" && !isNaN(lc.builtup_pct) && lc.builtup_pct > 0) {
        parts.push(`Built-up: ${lc.builtup_pct.toFixed(1)}%`);
      } else if (typeof lc.bare_soil_pct === "number" && !isNaN(lc.bare_soil_pct)) {
        parts.push(`Bare soil: ${lc.bare_soil_pct.toFixed(1)}%`);
      }
    }

    // 4. Object grounding areas (grounding task)
    if (Array.isArray(metrics.object_areas) && metrics.object_areas.length > 0 && parts.length === 0) {
      const validObjects = metrics.object_areas.filter((o) => o && typeof o === "object");
      const totalAreaKm2 = validObjects.reduce((acc, curr) => {
        const a = typeof curr.area_km2 === "number" ? curr.area_km2 : 0;
        return acc + a;
      }, 0);

      if (totalAreaKm2 > 0) {
        parts.push(`${validObjects.length} objects: ${totalAreaKm2.toFixed(3)} km²`);
      } else {
        parts.push(`${validObjects.length} detected objects`);
      }
    }

    return parts.length > 0 ? parts.join(" · ") : "No metrics available";
  } catch (err) {
    console.warn("formatCondensedMetrics caught unexpected error:", err);
    return "No metrics available";
  }
}
