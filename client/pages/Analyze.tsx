import { useState, useEffect, useRef, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { Play, Sparkles, Terminal, Loader2, ScanSearch, AlertCircle, Upload, X, FileImage, Download, Target, ArrowRightLeft, FlaskConical, Leaf, Map, BarChart2, Layers, MapPin, Calendar, Satellite, Globe2 } from "lucide-react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const AI_SERVICE_URL = import.meta.env.VITE_AI_SERVICE_URL || "http://localhost:8082";

type Modality = "optical" | "sar" | "both";
type Temporal = "single" | "bi-temporal";
type TaskHint = "auto" | "vqa" | "grounding" | "change" | "sar_fusion";
type ScenarioId = "deforestation" | "disaster";
type InputMode = "upload" | "location";
type SatCollection = "sentinel-2-l2a" | "sentinel-1-grd" | "landsat-c2-l2";

interface Scenario {
  id: ScenarioId;
  title: string;
  description: string;
  beforeImage: string;
  afterImage: string;
}

const SCENARIOS: Record<ScenarioId, Scenario> = {
  deforestation: {
    id: "deforestation",
    title: "Deforestation",
    description: "Rondônia, Brazil — Sentinel-2 L2A, 2019 vs 2023",
    beforeImage: `${AI_SERVICE_URL}/images/deforestation-before.jpg`,
    afterImage: `${AI_SERVICE_URL}/images/deforestation-after.jpg`,
  },
  disaster: {
    id: "disaster",
    title: "Disaster Response",
    description: "Post-cyclone coastal district — Sentinel-2 Bi-Temporal Pair",
    beforeImage: `${AI_SERVICE_URL}/images/disaster-before.jpg`,
    afterImage: `${AI_SERVICE_URL}/images/disaster-after.jpg`,
  },
};

const PRESET_QUERIES = [
  {
    label: "Deforestation Analysis",
    query: "What deforestation or forest cover loss is visible in these before and after images?",
    modality: "optical" as Modality,
    temporal: "bi-temporal" as Temporal,
    taskHint: "change" as TaskHint,
    scenario: "deforestation" as ScenarioId,
  },
  {
    label: "Building & Object Grounding",
    query: "Please detect and ground all major infrastructure, buildings, or structures in this aerial view.",
    modality: "optical" as Modality,
    temporal: "single" as Temporal,
    taskHint: "grounding" as TaskHint,
  },
  {
    label: "SAR Inundation Detection",
    query: "Detect flood inundation boundaries and water body expansion using cloud-penetrating Sentinel-1 SAR imagery",
    modality: "sar" as Modality,
    temporal: "single" as Temporal,
    taskHint: "sar_fusion" as TaskHint,
  },
  {
    label: "Optical–SAR Multimodal Fusion",
    query: "Fuse optical multi-spectral bands with synthetic aperture radar channels to describe land cover despite cloud cover",
    modality: "both" as Modality,
    temporal: "single" as Temporal,
    taskHint: "sar_fusion" as TaskHint,
  },
];

interface GroundingBox {
  label: string;
  box_normalized: [number, number, number, number]; // [xmin, ymin, xmax, ymax]
  box_pixels?: [number, number, number, number];
  score_token?: string;
}

interface ExecutionTrace {
  task: string;
  specialist_used: string;
  parameters: Record<string, any>;
}

interface NdviResult {
  vegetation_pct: number;
  vegetation_pct_sparse?: number;
  vegetation_pct_dense?: number;
  mean_ndvi: number;
  valid_pixels?: number;
  total_pixels?: number;
}

interface LandcoverResult {
  dense_vegetation_pct: number;
  sparse_vegetation_pct: number;
  bare_soil_pct: number;
  water_or_shadow_pct: number;
  non_vegetated_pct: number;
}

interface SpectralChangeResult {
  changed_pct: number;
  changed_pixels: number;
  total_pixels: number;
  change_area_km2: number | null;
  georeferenced: boolean;
}

interface ObjectAreaResult {
  label: string;
  box_normalized: number[];
  area_km2: number | null;
  area_m2: number | null;
  georeferenced: boolean;
}

interface ComputedMetrics {
  task: string;
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
}

interface AnalyzeResponse {
  answer: string;
  confidence: number | null;
  visual_evidence: GroundingBox[] | {
    mask_url?: string | null;
    change_percentage?: number | null;
    bounding_boxes?: any[];
  } | null;
  computed_metrics: ComputedMetrics | null;
  execution_trace: ExecutionTrace;
  preview_image_base64?: string;
  preview_images_base64?: string[];
}

// ─── Deterministic Metrics Panel ────────────────────────────────────────────

function MetricRow({ label, value, unit, highlight }: { label: string; value: string | number | null; unit?: string; highlight?: boolean }) {
  if (value === null || value === undefined) return null;
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-border/30 last:border-0">
      <span className="text-[11px] text-muted-foreground">{label}</span>
      <span className={`font-mono text-[12px] font-semibold ${highlight ? "text-amber-400" : "text-foreground"}`}>
        {typeof value === "number" ? value.toFixed(3) : value}{unit ? ` ${unit}` : ""}
      </span>
    </div>
  );
}

function NdviBlock({ label, ndvi }: { label: string; ndvi: NdviResult }) {
  const sparseVal = ndvi.vegetation_pct_sparse ?? ndvi.vegetation_pct;
  const denseVal = ndvi.vegetation_pct_dense;

  return (
    <div className="space-y-1">
      <p className="text-[10px] font-semibold text-amber-400/80 uppercase tracking-wider flex items-center gap-1">
        <Leaf className="h-3 w-3" />{label}
      </p>
      <MetricRow label="Sparse Veg. (>0.2)" value={sparseVal} unit="%" />
      {denseVal !== undefined && (
        <MetricRow label="Dense Canopy (>0.5)" value={denseVal} unit="%" highlight />
      )}
      <MetricRow label="Mean NDVI" value={ndvi.mean_ndvi} />
      <MetricRow label="Valid Pixels" value={ndvi.total_pixels ?? ndvi.valid_pixels} />
    </div>
  );
}

function LandcoverBlock({ label, lc }: { label: string; lc: LandcoverResult }) {
  return (
    <div className="space-y-1">
      <p className="text-[10px] font-semibold text-amber-400/80 uppercase tracking-wider flex items-center gap-1">
        <Map className="h-3 w-3" />{label}
      </p>
      <MetricRow label="Dense Veg." value={lc.dense_vegetation_pct} unit="%" />
      <MetricRow label="Sparse Veg." value={lc.sparse_vegetation_pct} unit="%" />
      <MetricRow label="Bare Soil" value={lc.bare_soil_pct} unit="%" />
      <MetricRow label="Water / Shadow" value={lc.water_or_shadow_pct} unit="%" />
      <MetricRow label="Non-Vegetated" value={lc.non_vegetated_pct} unit="%" />
    </div>
  );
}

function ComputedMetricsPanel({ metrics }: { metrics: ComputedMetrics }) {
  const task = metrics.task;

  return (
    <div className="rounded-xl border border-amber-500/25 bg-[#0f0d07] p-5 shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-amber-500/20 pb-3 mb-4">
        <span className="label-micro text-amber-400/80 flex items-center gap-2">
          <FlaskConical className="h-4 w-4 text-amber-400" /> DETERMINISTIC MEASUREMENTS
        </span>
        <span
          title="Computed by geospatial_metrics.py — no LLM involved"
          className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/25 text-amber-400 cursor-help"
        >
          {metrics.georeferenced ? "GEOREF ✓" : "NO GEOREF"}
        </span>
      </div>

      <div className="space-y-4 text-xs">
        {/* ── VQA / single-image ── */}
        {task === "vqa" && (
          <>
            {metrics.ndvi && <NdviBlock label="NDVI Coverage" ndvi={metrics.ndvi} />}
            {metrics.landcover && <LandcoverBlock label="Land Cover" lc={metrics.landcover} />}
          </>
        )}

        {/* ── Change VQA ── */}
        {task === "change_vqa" && (
          <>
            {metrics.before_ndvi && <NdviBlock label="Before — NDVI" ndvi={metrics.before_ndvi} />}
            {metrics.after_ndvi && <NdviBlock label="After — NDVI" ndvi={metrics.after_ndvi} />}
            {metrics.before_landcover && <LandcoverBlock label="Before — Land Cover" lc={metrics.before_landcover} />}
            {metrics.after_landcover && <LandcoverBlock label="After — Land Cover" lc={metrics.after_landcover} />}
            {metrics.spectral_change && (
              <div className="space-y-1">
                <p className="text-[10px] font-semibold text-amber-400/80 uppercase tracking-wider flex items-center gap-1">
                  <BarChart2 className="h-3 w-3" />Spectral Change Area
                </p>
                <MetricRow label="Changed Surface" value={metrics.spectral_change.changed_pct} unit="%" highlight />
                <MetricRow label="Changed Pixels" value={metrics.spectral_change.changed_pixels} />
                <MetricRow
                  label="Area"
                  value={metrics.spectral_change.change_area_km2 !== null ? metrics.spectral_change.change_area_km2 : "N/A (no georef)"}
                  unit={metrics.spectral_change.change_area_km2 !== null ? "km²" : undefined}
                  highlight={metrics.spectral_change.change_area_km2 !== null}
                />
              </div>
            )}
          </>
        )}

        {/* ── Grounding ── */}
        {task === "grounding" && metrics.object_areas && metrics.object_areas.length > 0 && (
          <div className="space-y-2">
            <p className="text-[10px] font-semibold text-amber-400/80 uppercase tracking-wider flex items-center gap-1">
              <Layers className="h-3 w-3" />Detected Object Areas
            </p>
            <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
              {metrics.object_areas.map((obj, i) => (
                <div key={i} className="flex items-center justify-between p-2 rounded bg-[#1a1500] border border-amber-500/15 text-[11px]">
                  <span className="text-foreground font-medium truncate max-w-[160px]">{obj.label}</span>
                  <span className="font-mono text-amber-400 ml-2 shrink-0">
                    {obj.area_km2 !== null
                      ? `${obj.area_km2.toFixed(4)} km²`
                      : obj.area_m2 !== null
                      ? `${obj.area_m2.toFixed(1)} m²`
                      : "N/A"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Reliability note */}
        <p className="text-[10px] text-muted-foreground/50 pt-1 border-t border-border/20">
          These values are computed deterministically from raw pixel data — independent of the model answer above.
        </p>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────

function ImageComparisonViewer({ beforeImage, afterImage, title }: { beforeImage: string; afterImage: string; title?: string }) {
  const [comparison, setComparison] = useState(50);

  return (
    <div className="relative min-h-[440px] rounded-xl border border-border bg-[#121212] overflow-hidden flex flex-col shadow-xl group">
      {title && (
        <div className="z-20 bg-background/90 backdrop-blur-md px-3.5 py-2 border-b border-border text-xs font-semibold text-foreground flex items-center gap-2">
          <ScanSearch className="h-3.5 w-3.5 text-primary" />
          <span>{title}</span>
        </div>
      )}
      <div className="relative w-full h-[400px] bg-black overflow-hidden flex-1">
        {/* After Image (Background) */}
        <img
          src={afterImage}
          alt="After / Post-event Satellite Imagery"
          className="absolute inset-0 w-full h-full object-cover"
        />

        {/* Before Image (Foreground, clipped) */}
        <div
          className="absolute inset-y-0 left-0 overflow-hidden border-r-2 border-primary shadow-[4px_0_12px_rgba(0,0,0,0.6)]"
          style={{ width: `${comparison}%` }}
        >
          <img
            src={beforeImage}
            alt="Before / Pre-event Satellite Imagery"
            className="absolute inset-0 w-full h-full object-cover"
            style={{ width: `${(100 / Math.max(comparison, 0.1)) * 100}%`, maxWidth: "none" }}
          />
        </div>

        {/* Slider Handle — translateX(-50%) keeps handle centred on the divider at all positions */}
        <div
          className="absolute inset-y-0 flex items-center justify-center pointer-events-none z-10"
          style={{ left: `${comparison}%`, transform: "translateX(-50%)" }}
        >
          <div className="h-9 w-9 rounded-full bg-card/95 border border-primary flex items-center justify-center shadow-[0_0_15px_rgba(0,0,0,0.8)] text-primary transition-transform group-hover:scale-110">
            <ArrowRightLeft className="h-4 w-4" />
          </div>
        </div>

        {/* Range Input Control */}
        <input
          type="range"
          min="0"
          max="100"
          value={comparison}
          onChange={(e) => setComparison(Number(e.target.value))}
          aria-label="Before and after comparison position slider"
          className="absolute inset-0 w-full h-full opacity-0 cursor-ew-resize z-20"
        />
      </div>

      <div className="h-10 w-full border-t border-border flex items-center justify-between px-6 bg-card/90 backdrop-blur-sm z-10">
        <span className="label-micro font-semibold tracking-wider text-muted-foreground">BEFORE (PRE-EVENT)</span>
        <ScanSearch aria-hidden="true" className="h-4 w-4 text-primary/60" />
        <span className="label-micro font-semibold tracking-wider text-muted-foreground">AFTER (POST-EVENT)</span>
      </div>
    </div>
  );
}

// ─── Mini Leaflet map for coordinate picking ──────────────────────────────────
function LocationPickerMap({ lat, lon, onPick }: { lat: number | null; lon: number | null; onPick: (lat: number, lon: number) => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markerRef = useRef<L.Marker | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, {
      center: [lat ?? 20, lon ?? 0],
      zoom: lat !== null ? 6 : 2,
      zoomControl: true,
      attributionControl: false,
    });
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      maxZoom: 19,
    }).addTo(map);
    mapRef.current = map;

    if (lat !== null && lon !== null) {
      markerRef.current = L.marker([lat, lon]).addTo(map);
    }

    map.on("click", (e: L.LeafletMouseEvent) => {
      const { lat: clickLat, lng: clickLon } = e.latlng;
      if (markerRef.current) {
        markerRef.current.setLatLng([clickLat, clickLon]);
      } else {
        markerRef.current = L.marker([clickLat, clickLon]).addTo(map);
      }
      onPick(Math.round(clickLat * 10000) / 10000, Math.round(clickLon * 10000) / 10000);
    });

    return () => { map.remove(); mapRef.current = null; markerRef.current = null; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Sync marker when lat/lon inputs change externally
  useEffect(() => {
    if (!mapRef.current || lat === null || lon === null) return;
    if (markerRef.current) {
      markerRef.current.setLatLng([lat, lon]);
    } else {
      markerRef.current = L.marker([lat, lon]).addTo(mapRef.current);
    }
    mapRef.current.setView([lat, lon], Math.max(mapRef.current.getZoom(), 6));
  }, [lat, lon]);

  return (
    <div
      ref={containerRef}
      className="w-full rounded-lg overflow-hidden border border-border"
      style={{ height: 260, cursor: "crosshair" }}
    />
  );
}

// ─────────────────────────────────────────────────────────────────────────────

export default function Analyze() {
  const [searchParams] = useSearchParams();
  const initialQuery = searchParams.get("query") || "Please detect and ground all major infrastructure, buildings, or structures in this aerial view.";
  // True when the user arrived from an Earth Event deep-link (e.g. the home page "Query Event" button)
  const arrivedViaEventLink = searchParams.has("query");

  const [query, setQuery] = useState(initialQuery);
  const [modality, setModality] = useState<Modality>("optical");
  const [temporal, setTemporal] = useState<Temporal>("single");
  const [taskHint, setTaskHint] = useState<TaskHint>("auto");
  const [scenarioId, setScenarioId] = useState<ScenarioId | null>(null);

  // Input mode: upload or query-by-location
  const [inputMode, setInputMode] = useState<InputMode>("upload");

  // Location query state
  const [locationLat, setLocationLat] = useState<number | null>(null);
  const [locationLon, setLocationLon] = useState<number | null>(null);
  const [locationLatStr, setLocationLatStr] = useState("");
  const [locationLonStr, setLocationLonStr] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [satCollection, setSatCollection] = useState<SatCollection>("sentinel-2-l2a");

  const handleLocationPick = useCallback((lat: number, lon: number) => {
    setLocationLat(lat);
    setLocationLon(lon);
    setLocationLatStr(String(lat));
    setLocationLonStr(String(lon));
  }, []);

  const syncLatInput = (val: string) => {
    setLocationLatStr(val);
    const n = parseFloat(val);
    if (!isNaN(n) && n >= -90 && n <= 90) setLocationLat(n);
  };

  const syncLonInput = (val: string) => {
    setLocationLonStr(val);
    const n = parseFloat(val);
    if (!isNaN(n) && n >= -180 && n <= 180) setLocationLon(n);
  };

  // File upload state for user-provided satellite images
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [filePreviewUrls, setFilePreviewUrls] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const q = searchParams.get("query");
    if (q) setQuery(q);
  }, [searchParams]);

  // Clean up object URLs on unmount or file change
  useEffect(() => {
    const urls = uploadedFiles.map((f) => URL.createObjectURL(f));
    setFilePreviewUrls(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [uploadedFiles]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const filesArr = Array.from(e.target.files);
      setUploadedFiles((prev) => [...prev, ...filesArr].slice(0, 4));
      setError(null);
    }
  };

  const handleRemoveFile = (index: number) => {
    setUploadedFiles((prev) => prev.filter((_, i) => i !== index));
    // Also clear stale result so the panel resets when a file is removed
    setResult(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  /** Wipe uploaded files + previous result when the user changes modes / presets. */
  const clearWorkspace = () => {
    setUploadedFiles([]);
    setResult(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleRunAnalysis = async () => {
    if (!query.trim()) return;

    // Location mode validation
    if (inputMode === "location") {
      if (locationLat === null || locationLon === null) {
        setError("Please provide a valid latitude and longitude, or click on the map to pick a location.");
        return;
      }
    }

    setIsRunning(true);
    setError(null);
    setResult(null);

    try {
      let finalQuery = query.trim();
      if (taskHint === "grounding" && !finalQuery.toLowerCase().includes("where") && !finalQuery.toLowerCase().includes("detect") && !finalQuery.toLowerCase().includes("locate") && !finalQuery.toLowerCase().includes("ground")) {
        finalQuery = `Where are the ${finalQuery}? Locate and ground bounding boxes.`;
      }

      let response: Response;

      if (inputMode === "location") {
        // Query by location: backend looks up catalogued scene and lazily fetches pixels
        response = await fetch(`${AI_SERVICE_URL}/api/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: finalQuery,
            modality,
            temporal,
            lat: locationLat,
            lon: locationLon,
            start_date: startDate || undefined,
            end_date: endDate || undefined,
            collection: satCollection,
          }),
        });
      } else if (uploadedFiles.length > 0) {
        // Send multipart/form-data for user-uploaded satellite files
        const formData = new FormData();
        formData.append("query", finalQuery);
        formData.append("modality", modality);
        formData.append("temporal", temporal);
        if (temporal === "bi-temporal" && scenarioId) {
          formData.append("scenario", scenarioId);
        }
        uploadedFiles.forEach((file, i) => {
          formData.append(`file_${i}`, file);
        });

        response = await fetch(`${AI_SERVICE_URL}/api/analyze`, {
          method: "POST",
          body: formData,
        });
      } else {
        // Standard JSON request (scenario-based)
        response = await fetch(`${AI_SERVICE_URL}/api/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: finalQuery,
            modality,
            temporal,
            scenario: temporal === "bi-temporal" && scenarioId ? scenarioId : undefined,
          }),
        });
      }

      if (!response.ok) {
        const errJson = await response.json().catch(() => null);
        throw new Error(errJson?.detail || `Service returned HTTP ${response.status}`);
      }

      const data: AnalyzeResponse = await response.json();
      setResult(data);
    } catch (e: any) {
      console.error("Analysis query failed", e);
      setError(e.message || "Failed to reach SatQuery AI service. Please verify backend state.");
    } finally {
      setIsRunning(false);
    }
  };

  const handleExportJson = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `satquery_analysis_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const currentScenario = scenarioId ? SCENARIOS[scenarioId] : null;
  const isGroundingResult = Array.isArray(result?.visual_evidence);
  const groundingBoxes: GroundingBox[] = isGroundingResult ? (result.visual_evidence as GroundingBox[]) : [];

  return (
    <div className="min-h-screen px-6 pb-24 pt-24 relative bg-background">
      {/* Background Ambient Glow */}
      <div className="absolute top-1/4 left-1/3 w-96 h-96 bg-primary/5 rounded-full blur-[140px] pointer-events-none" />

      <div className="mx-auto max-w-[1400px]">
        {/* Header Title */}
        <div className="mb-8">
          <h1 className="text-headline font-bold text-foreground tracking-tight text-3xl sm:text-4xl">
            SatQuery AI Workspace
          </h1>
          <p className="mt-2 text-body text-muted-foreground max-w-2xl">
            Submit natural-language queries against optical, SAR, or user-uploaded satellite imagery. Requests are dynamically routed to specialized models with auditable execution traces.
          </p>
        </div>

        {/* Preset Query Pills */}
        <div className="mb-6 flex flex-wrap items-center gap-2">
          <span className="label-micro text-muted-foreground mr-2">Preset Workflows:</span>
          {PRESET_QUERIES.map((preset) => (
            <button
              key={preset.label}
              type="button"
              onClick={() => {
                clearWorkspace();
                setQuery(preset.query);
                setModality(preset.modality);
                setTemporal(preset.temporal);
                setTaskHint(preset.taskHint);
                setScenarioId(preset.scenario ?? null);
              }}
              className="text-xs px-3 py-1.5 rounded-md border border-border bg-card/60 hover:bg-card hover:border-primary/50 text-secondary-foreground transition-all duration-150"
            >
              {preset.label}
            </button>
          ))}
        </div>

        {/* Query Input Box, Selectors & Input Mode Panel */}
        <div className="rounded-xl border border-border bg-card/80 p-6 shadow-xl backdrop-blur-md mb-8">
          {/* Input Mode Toggle */}
          <div className="flex items-center gap-1 p-1 rounded-lg bg-[#121212] border border-border mb-5 w-fit">
            <button
              type="button"
              onClick={() => { setInputMode("upload"); setResult(null); setError(null); }}
              className={cn(
                "flex items-center gap-2 px-4 py-1.5 rounded-md text-xs font-medium transition-all",
                inputMode === "upload" ? "bg-primary text-primary-foreground shadow" : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Upload className="h-3.5 w-3.5" />
              Upload Image
            </button>
            <button
              type="button"
              onClick={() => { setInputMode("location"); setResult(null); setError(null); }}
              className={cn(
                "flex items-center gap-2 px-4 py-1.5 rounded-md text-xs font-medium transition-all",
                inputMode === "location" ? "bg-primary text-primary-foreground shadow" : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Globe2 className="h-3.5 w-3.5" />
              Query by Location
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <label htmlFor="query-input" className="label-micro mb-2 block text-muted-foreground">
                Query Prompt
              </label>
              <textarea
                id="query-input"
                rows={3}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask SatQuery AI a question about your satellite imagery (e.g. 'Where are the runway and building structures in this aerial view?')..."
                className="w-full rounded-lg border border-border bg-[#121212] px-4 py-3 text-body text-foreground placeholder:text-muted-foreground/60 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
              {/* Event-link nudge: shown only when arriving from an Earth Event card with no image yet */}
              {arrivedViaEventLink && uploadedFiles.length === 0 && (
                <div className="mt-2 flex items-start gap-2.5 rounded-md border border-primary/20 bg-primary/5 px-3.5 py-2.5 text-xs text-primary/80">
                  <Upload className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                  <span>
                    <span className="font-semibold">Image required to analyze this event.</span>{" "}
                    Upload a satellite image of the region using the button below, then run the query.
                  </span>
                </div>
              )}
            </div>

            {/* Task Specialist & Input Controls */}
            <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-border/50">
              <div className="flex flex-wrap items-center gap-6">
                {/* Task Type Hint */}
                <div>
                  <span className="label-micro block mb-1 text-muted-foreground">Task Specialist</span>
                  <div className="flex bg-[#121212] p-1 rounded-md border border-border text-xs">
                    {(
                      [
                        { id: "auto", label: "Auto Classifier" },
                        { id: "vqa", label: "Optical VQA" },
                        { id: "grounding", label: "Grounding" },
                        { id: "change", label: "Change VQA" },
                        { id: "sar_fusion", label: "SAR Fusion" },
                      ] as { id: TaskHint; label: string }[]
                    ).map((t) => (
                      <button
                        key={t.id}
                        type="button"
                        onClick={() => setTaskHint(t.id)}
                        className={cn(
                          "px-2.5 py-1 rounded font-medium transition-all",
                          taskHint === t.id ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Modality Selector */}
                <div>
                  <span className="label-micro block mb-1 text-muted-foreground">Modality</span>
                  <div className="flex bg-[#121212] p-1 rounded-md border border-border text-xs">
                    {(["optical", "sar", "both"] as Modality[]).map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => { setModality(m); clearWorkspace(); }}
                        className={cn(
                          "px-3 py-1 rounded font-medium capitalize transition-all",
                          modality === m ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        {m === "both" ? "Optical + SAR" : m}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Temporal Selector */}
                <div>
                  <span className="label-micro block mb-1 text-muted-foreground">Temporal Mode</span>
                  <div className="flex bg-[#121212] p-1 rounded-md border border-border text-xs">
                    {(["single", "bi-temporal"] as Temporal[]).map((t) => (
                      <button
                        key={t}
                        type="button"
                        onClick={() => {
                          setTemporal(t);
                          clearWorkspace();
                          if (t === "single") setScenarioId(null);
                        }}
                        className={cn(
                          "px-3 py-1 rounded font-medium capitalize transition-all",
                          temporal === t ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        {t === "bi-temporal" ? "Bi-Temporal Pair" : "Single Image"}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Scenario Selector (Bi-temporal mode) */}
                {temporal === "bi-temporal" && (
                  <div>
                    <span className="label-micro block mb-1 text-muted-foreground">Scenario Preset</span>
                    <div className="flex bg-[#121212] p-1 rounded-md border border-border text-xs">
                      {(Object.keys(SCENARIOS) as ScenarioId[]).map((id) => (
                        <button
                          key={id}
                          type="button"
                          onClick={() => {
                            setScenarioId(id as ScenarioId);
                            setTaskHint("change");
                            if (id === "deforestation") {
                              setQuery("What deforestation or forest cover loss is visible in these before and after images?");
                            } else if (id === "disaster") {
                              setQuery("What flood damage or structural changes are visible between the pre-event and post-event images?");
                            }
                          }}
                          className={cn(
                            "px-3 py-1 rounded font-medium capitalize transition-all",
                            scenarioId === id ? "bg-accent text-accent-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                          )}
                        >
                          {SCENARIOS[id as ScenarioId].title}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Upload Button Trigger & Submit CTA */}
              <div className="flex items-center gap-3">
                {inputMode === "upload" && (
                  <>
                    <input
                      type="file"
                      ref={fileInputRef}
                      onChange={handleFileChange}
                      multiple
                      accept=".tif,.tiff,.png,.jpg,.jpeg"
                      className="hidden"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="lg"
                      onClick={() => fileInputRef.current?.click()}
                      className="border-border bg-[#121212] hover:border-primary"
                    >
                      <Upload className="mr-2 h-4 w-4" />
                      Upload GeoTIFF / Image
                    </Button>
                  </>
                )}

                <Button
                  size="lg"
                  disabled={isRunning || !query.trim()}
                  onClick={handleRunAnalysis}
                  className={cn(
                    "shadow-lg min-w-[160px] transition-opacity",
                    isRunning ? "opacity-60 cursor-not-allowed" : "hover:shadow-primary/20"
                  )}
                >
                  {isRunning ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Play className="mr-2 h-4 w-4" />
                  )}
                  {isRunning ? "Running..." : "Run SatQuery AI"}
                </Button>
              </div>
            </div>

            {/* Location query inputs */}
            {inputMode === "location" && (
              <div className="pt-4 border-t border-border/40 space-y-4">
                <p className="text-xs text-muted-foreground flex items-center gap-2">
                  <Globe2 className="h-3.5 w-3.5 text-primary" />
                  Click the map to pick a point, or enter coordinates manually. The backend will find the best matching catalogued satellite scene and run inference on it.
                </p>

                {/* Mini map */}
                <LocationPickerMap lat={locationLat} lon={locationLon} onPick={handleLocationPick} />

                {/* Coordinate inputs */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="label-micro block mb-1 text-muted-foreground">Latitude</label>
                    <input
                      type="number"
                      step="any"
                      min="-90"
                      max="90"
                      placeholder="e.g. -10.5432"
                      value={locationLatStr}
                      onChange={(e) => syncLatInput(e.target.value)}
                      className="w-full rounded-lg border border-border bg-[#121212] px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/50 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary font-mono"
                    />
                  </div>
                  <div>
                    <label className="label-micro block mb-1 text-muted-foreground">Longitude</label>
                    <input
                      type="number"
                      step="any"
                      min="-180"
                      max="180"
                      placeholder="e.g. -62.3141"
                      value={locationLonStr}
                      onChange={(e) => syncLonInput(e.target.value)}
                      className="w-full rounded-lg border border-border bg-[#121212] px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/50 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary font-mono"
                    />
                  </div>
                </div>

                {/* Date range + collection */}
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="label-micro block mb-1 text-muted-foreground flex items-center gap-1">
                      <Calendar className="h-3 w-3" /> Start Date
                    </label>
                    <input
                      type="date"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      className="w-full rounded-lg border border-border bg-[#121212] px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                    />
                  </div>
                  <div>
                    <label className="label-micro block mb-1 text-muted-foreground flex items-center gap-1">
                      <Calendar className="h-3 w-3" /> End Date
                    </label>
                    <input
                      type="date"
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      className="w-full rounded-lg border border-border bg-[#121212] px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                    />
                  </div>
                  <div>
                    <label className="label-micro block mb-1 text-muted-foreground flex items-center gap-1">
                      <Satellite className="h-3 w-3" /> Collection
                    </label>
                    <select
                      value={satCollection}
                      onChange={(e) => setSatCollection(e.target.value as SatCollection)}
                      className="w-full rounded-lg border border-border bg-[#121212] px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                    >
                      <option value="sentinel-2-l2a">Sentinel-2 L2A</option>
                      <option value="sentinel-1-grd">Sentinel-1 GRD (SAR)</option>
                      <option value="landsat-c2-l2">Landsat C2 L2</option>
                    </select>
                  </div>
                </div>

                {/* Live coord badge */}
                {locationLat !== null && locationLon !== null && (
                  <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-primary/10 border border-primary/25 text-primary text-xs font-mono w-fit">
                    <MapPin className="h-3.5 w-3.5" />
                    {locationLat.toFixed(4)}°, {locationLon.toFixed(4)}°
                    <span className="text-muted-foreground ml-2">· {satCollection}</span>
                  </div>
                )}
              </div>
            )}

            {/* Custom Uploaded Files Bar */}
            {inputMode === "upload" && uploadedFiles.length > 0 && (
              <div className="pt-3 border-t border-border/40 flex flex-wrap items-center gap-3">
                <span className="label-micro text-muted-foreground">Uploaded Files ({uploadedFiles.length}):</span>
                {uploadedFiles.map((file, idx) => (
                  <div key={idx} className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-[#181818] border border-primary/30 text-xs text-foreground">
                    <FileImage className="h-3.5 w-3.5 text-primary" />
                    <span className="truncate max-w-[140px] font-mono">{file.name}</span>
                    <button
                      type="button"
                      onClick={() => handleRemoveFile(idx)}
                      className="text-muted-foreground hover:text-destructive transition-colors ml-1"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-8 rounded-lg bg-destructive/10 p-4 border border-destructive/20 text-destructive flex items-start gap-3">
            <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-sm">Backend API Response Error</p>
              <p className="text-xs mt-1 text-destructive/90">{error}</p>
            </div>
          </div>
        )}

        {/* Analysis Results Display */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Left Column: Visual Evidence / Canvas Viewer with Bounding Box Overlay */}
          <div className="lg:col-span-7 space-y-6">
            {temporal === "bi-temporal" && result?.preview_images_base64 && result.preview_images_base64.length >= 2 ? (
              <ImageComparisonViewer
                beforeImage={result.preview_images_base64[0]}
                afterImage={result.preview_images_base64[1]}
                title={uploadedFiles.length === 0 ? currentScenario?.description : undefined}
              />
            ) : temporal === "bi-temporal" && uploadedFiles.length >= 2 && !result ? (
              /* Bi-temporal TIF staged — browser can't render TIFF blobs, wait for backend preview */
              <div className="relative min-h-[440px] rounded-xl border border-border bg-[#0d0d0d] overflow-hidden flex flex-col justify-center items-center gap-5 shadow-xl">
                <div className="flex flex-col items-center gap-3 text-center px-8">
                  <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
                    <ScanSearch className="h-6 w-6 text-primary" />
                  </div>
                  <p className="text-sm font-semibold text-foreground">{uploadedFiles.length} GeoTIFF files staged</p>
                  <p className="text-xs text-muted-foreground max-w-xs">
                    TIFF images cannot be previewed in the browser. Run the analysis to generate a visual comparison.
                  </p>
                  <div className="flex gap-2 flex-wrap justify-center mt-1">
                    {uploadedFiles.map((f, i) => (
                      <span key={i} className="text-[10px] px-2 py-1 rounded bg-card border border-border text-muted-foreground font-mono">{f.name}</span>
                    ))}
                  </div>
                </div>
                <div className="absolute bottom-0 w-full h-10 border-t border-border flex items-center justify-between px-6 bg-card/90">
                  <span className="label-micro font-semibold tracking-wider text-muted-foreground">BEFORE (PRE-EVENT)</span>
                  <span className="label-micro font-semibold tracking-wider text-muted-foreground">AFTER (POST-EVENT)</span>
                </div>
              </div>
            ) : uploadedFiles.length > 0 ? (
              <div className="relative min-h-[440px] rounded-xl border border-border bg-[#121212] overflow-hidden flex flex-col justify-center items-center p-4 shadow-xl">
                <div className="relative w-full h-[400px] flex items-center justify-center bg-black/60 rounded-lg overflow-hidden">
                  {/* Only render preview from backend base64 — raw TIF blob URLs cannot be rendered by browsers */}
                  {result?.preview_image_base64 ? (
                    <img
                      src={result.preview_image_base64}
                      alt="User Uploaded Satellite Source"
                      className="max-h-full max-w-full object-contain"
                    />
                  ) : (
                    <div className="flex flex-col items-center gap-3 text-center px-6">
                      <ScanSearch className="h-8 w-8 text-primary/40" />
                      <p className="text-xs text-muted-foreground">
                        <span className="font-semibold text-foreground">{uploadedFiles[0].name}</span> staged —
                        TIFF preview will appear after running the analysis.
                      </p>
                    </div>
                  )}
                  {/* Render Bounding Boxes for Uploaded Image */}
                  {result?.preview_image_base64 && groundingBoxes.map((box, idx) => {
                    const [xmin, ymin, xmax, ymax] = box.box_normalized;
                    return (
                      <div
                        key={idx}
                        className="absolute border-2 border-red-500 bg-red-500/10 pointer-events-none transition-all"
                        style={{
                          left: `${xmin}%`,
                          top: `${ymin}%`,
                          width: `${xmax - xmin}%`,
                          height: `${ymax - ymin}%`,
                        }}
                      >
                        <span className="absolute -top-6 left-0 px-1.5 py-0.5 rounded bg-red-600 text-white font-mono text-[10px] whitespace-nowrap shadow">
                          {box.label}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : result?.preview_image_base64 ? (
              <div className="relative min-h-[440px] rounded-xl border border-border bg-[#121212] overflow-hidden flex flex-col justify-center items-center p-4 shadow-xl">
                <div className="relative w-full h-[400px] flex items-center justify-center bg-black/60 rounded-lg overflow-hidden">
                  <img
                    src={result.preview_image_base64}
                    alt="Satellite Source Preview"
                    className="max-h-full max-w-full object-contain"
                  />
                  {/* Render Bounding Boxes for Single Preview */}
                  {groundingBoxes.map((box, idx) => {
                    const [xmin, ymin, xmax, ymax] = box.box_normalized;
                    return (
                      <div
                        key={idx}
                        className="absolute border-2 border-red-500 bg-red-500/10 pointer-events-none transition-all"
                        style={{
                          left: `${xmin}%`,
                          top: `${ymin}%`,
                          width: `${xmax - xmin}%`,
                          height: `${ymax - ymin}%`,
                        }}
                      >
                        <span className="absolute -top-6 left-0 px-1.5 py-0.5 rounded bg-red-600 text-white font-mono text-[10px] whitespace-nowrap shadow">
                          {box.label}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : inputMode === "location" ? (
              /* Location mode empty state: show placeholder until result arrives */
              <div className="relative min-h-[440px] rounded-xl border border-border/50 bg-[#0a0c0f] overflow-hidden flex flex-col justify-center items-center gap-5 shadow-xl p-8">
                <div className="flex h-16 w-16 items-center justify-center rounded-full border border-primary/20 bg-primary/5 text-primary/50">
                  <Globe2 className="h-8 w-8" />
                </div>
                <div className="text-center space-y-1.5 max-w-xs">
                  <p className="text-sm font-semibold text-foreground">
                    {locationLat !== null ? "Location selected — ready to analyze" : "Select a location to begin"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {locationLat !== null
                      ? `Querying ${satCollection} scenes near ${locationLat.toFixed(4)}°, ${locationLon!.toFixed(4)}°. A preview will appear here after running the analysis.`
                      : "Click on the map in the panel above, or enter coordinates manually to pick an area of interest."}
                  </p>
                </div>
              </div>
            ) : (
              /* Upload mode empty-state dropzone */
              <div
                className="relative min-h-[440px] rounded-xl border-2 border-dashed border-border bg-[#0d0d0d] overflow-hidden flex flex-col justify-center items-center gap-4 p-8 shadow-xl cursor-pointer group hover:border-primary/50 transition-colors duration-200"
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  const files = Array.from(e.dataTransfer.files).filter((f) =>
                    /\.(tif|tiff|png|jpg|jpeg)$/i.test(f.name)
                  );
                  if (files.length > 0) {
                    setUploadedFiles((prev) => [...prev, ...files].slice(0, 4));
                    setError(null);
                  }
                }}
              >
                <div className="flex h-16 w-16 items-center justify-center rounded-full border border-border bg-card/60 text-muted-foreground group-hover:border-primary/40 group-hover:text-primary/70 transition-colors duration-200">
                  <Upload className="h-7 w-7" />
                </div>
                <div className="text-center space-y-1">
                  <p className="text-sm font-semibold text-foreground">
                    {temporal === "bi-temporal"
                      ? "Upload your own imagery"
                      : "Upload an image to begin"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Drag &amp; drop a GeoTIFF, JPEG, or PNG file here, or click to browse
                  </p>
                </div>
                {/* Scenario configured badge */}
                {temporal === "bi-temporal" && currentScenario ? (
                  <div className="mt-1 flex items-center gap-2 px-3 py-1.5 rounded-md bg-accent/10 border border-accent/30 text-accent text-xs font-medium">
                    <ScanSearch className="h-3.5 w-3.5 shrink-0" />
                    Scenario configured: {currentScenario.title}
                  </div>
                ) : temporal === "bi-temporal" ? (
                  <p className="text-[11px] font-mono text-muted-foreground/50 mt-1">
                    No scenario selected — use the Scenario Preset buttons above to configure
                  </p>
                ) : null}
              </div>
            )}

            {/* Generated Mask Output (if change detection returned mask) */}
            {result?.visual_evidence && "mask_url" in result.visual_evidence && result.visual_evidence.mask_url && (
              <div className="rounded-xl border border-border bg-card p-4 shadow-lg">
                <p className="label-micro mb-3 text-muted-foreground">GENERATED INFERENCE CHANGE MASK</p>
                <div className="relative rounded-lg overflow-hidden border border-border bg-black h-48 flex items-center justify-center">
                  <img
                    src={`${AI_SERVICE_URL}${result.visual_evidence.mask_url}`}
                    alt="Inference Change Mask"
                    className="max-h-full object-contain"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Right Column: Model Answer, Grounding Table & Auditable Trace */}
          <div className="lg:col-span-5 space-y-6">
            {/* Model Response Card */}
            <div className="rounded-xl border border-border bg-card p-6 shadow-xl relative overflow-hidden">
              <div className="flex items-center justify-between border-b border-border/60 pb-4 mb-4">
                <span className="label-micro text-muted-foreground flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-primary" /> MODEL ANSWER
                </span>
                <div className="flex items-center gap-2">
                  {result && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={handleExportJson}
                      className="h-7 text-xs px-2 text-muted-foreground hover:text-foreground"
                    >
                      <Download className="h-3.5 w-3.5 mr-1" /> JSON
                    </Button>
                  )}
                  <span className="text-xs font-medium px-2.5 py-0.5 rounded bg-primary/10 border border-primary/20 text-primary">
                    {result ? "Complete" : "Ready"}
                  </span>
                </div>
              </div>

              <div className="min-h-[140px]">
                {isRunning ? (
                  <div className="flex items-center justify-center h-36">
                    <Loader2 className="h-6 w-6 animate-spin text-primary" />
                  </div>
                ) : result ? (
                  <div className="space-y-4">
                    <p className="text-body text-foreground leading-relaxed font-medium">
                      {result.answer}
                    </p>

                    {/* Render Visual Grounding Evidence List */}
                    {groundingBoxes.length > 0 && (
                      <div className="pt-3 border-t border-border/40 space-y-2">
                        <span className="label-micro text-muted-foreground block flex items-center gap-1.5">
                          <Target className="h-3.5 w-3.5 text-red-400" /> Grounding Evidence ({groundingBoxes.length} Bounding Boxes)
                        </span>
                        <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                          {groundingBoxes.map((item, idx) => (
                            <div key={idx} className="flex items-center justify-between p-2 rounded bg-[#141414] border border-border/50 text-xs">
                              <span className="font-medium text-foreground truncate max-w-[200px]">{item.label}</span>
                              <span className="font-mono text-primary text-[11px]">
                                [{item.box_normalized.join(", ")}]
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Change Percentage if present */}
                    {result.visual_evidence && "change_percentage" in result.visual_evidence && result.visual_evidence.change_percentage !== undefined && result.visual_evidence.change_percentage !== null && (
                      <div className="pt-3 border-t border-border/40 flex items-center justify-between">
                        <span className="label-micro text-muted-foreground">Detected Surface Change</span>
                        <span className="font-mono text-lg font-bold text-primary">
                          {result.visual_evidence.change_percentage}%
                        </span>
                      </div>
                    )}

                    {/* Confidence Score Display (Flagged Backend Behavior: Hardcoded null by LLM) */}
                    <div className="pt-2 border-t border-border/40 flex items-center justify-between text-xs text-muted-foreground">
                      <span>Confidence Score</span>
                      <span className="font-mono text-foreground font-semibold">
                        {result.confidence !== null && result.confidence !== undefined
                          ? `${(result.confidence * 100).toFixed(1)}%`
                          : "N/A (Causal LLM)"}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-36 text-center text-muted-foreground">
                    <p className="text-xs">Enter a query prompt above and click "Run SatQuery AI" to execute analysis.</p>
                  </div>
                )}
              </div>
            </div>

            {/* Deterministic Metrics Panel — shown only when computed_metrics is present */}
            {result?.computed_metrics && (
              <ComputedMetricsPanel metrics={result.computed_metrics} />
            )}

            {/* Auditable Execution Trace Card */}
            <div className="rounded-xl border border-border bg-[#0E0E0E] p-6 shadow-xl">
              <div className="flex items-center justify-between border-b border-border/60 pb-3 mb-4">
                <span className="label-micro text-muted-foreground flex items-center gap-2">
                  <Terminal className="h-4 w-4 text-accent" /> AUDITABLE EXECUTION TRACE
                </span>
                <span className="text-xs font-mono text-accent">PS-COMPLIANT</span>
              </div>

              {result?.execution_trace ? (
                <div className="space-y-3 text-xs font-mono">
                  <div className="p-3 rounded-lg bg-[#141414] border border-border/60 space-y-2">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Task Classified:</span>
                      <span className="text-primary font-bold">{result.execution_trace.task}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Specialist Used:</span>
                      <span className="text-foreground">{result.execution_trace.specialist_used}</span>
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-[#141414] border border-border/60">
                    <p className="text-muted-foreground mb-1.5">Parameters:</p>
                    <pre className="text-[11px] text-accent/90 overflow-x-auto">
                      {JSON.stringify(result.execution_trace.parameters, null, 2)}
                    </pre>
                  </div>
                </div>
              ) : (
                <div className="py-6 text-center text-xs text-muted-foreground/60 font-mono">
                  Execution trace telemetry will populate upon query completion.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
