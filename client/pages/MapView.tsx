import React, { Component, ErrorInfo, ReactNode, useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  AlertCircle,
  Loader2,
  Map as MapIcon,
  FlaskConical,
  Clock,
  Layers,
  BarChart2,
  Crosshair,
  Satellite,
  ExternalLink,
  Eye,
  EyeOff,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  AnalysisFeatureCollection,
  AnalysisGeoJSONFeature,
  CatalogFeatureCollection,
  CatalogGeoJSONFeature,
  ComputedMetrics,
  formatCondensedMetrics,
} from "@/lib/analysis-metrics";

// ─── Fix default Leaflet marker icons ─────────────────────────────────────────
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

// Solid analysis pin (blue pulse)
const analysisIcon = L.divIcon({
  html: `<div style="
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: hsl(218, 44%, 55%);
    border: 2.5px solid hsl(218, 44%, 75%);
    box-shadow: 0 0 0 4px hsl(218 44% 55% / 0.25), 0 2px 8px rgba(0,0,0,0.6);
  "></div>`,
  className: "",
  iconSize: [14, 14],
  iconAnchor: [7, 7],
  popupAnchor: [0, -10],
});

const analysisPolygonIcon = L.divIcon({
  html: `<div style="
    width: 12px;
    height: 12px;
    border-radius: 3px;
    background: hsl(218, 44%, 55%);
    border: 2px solid hsl(218, 44%, 75%);
    box-shadow: 0 0 0 3px hsl(218 44% 55% / 0.25), 0 2px 6px rgba(0,0,0,0.5);
    transform: rotate(45deg);
  "></div>`,
  className: "",
  iconSize: [12, 12],
  iconAnchor: [6, 6],
  popupAnchor: [0, -10],
});

// Distinct STAC catalog marker: small hollow circular ring / crosshair
const catalogHollowIcon = L.divIcon({
  html: `<div style="
    width: 13px;
    height: 13px;
    border-radius: 50%;
    background: transparent;
    border: 2px solid #06b6d4;
    box-shadow: 0 0 0 2px rgba(6, 182, 212, 0.2), 0 2px 6px rgba(0,0,0,0.6);
    display: flex;
    align-items: center;
    justify-content: center;
  "><div style="width: 3px; height: 3px; border-radius: 50%; background: #06b6d4;"></div></div>`,
  className: "",
  iconSize: [13, 13],
  iconAnchor: [6.5, 6.5],
  popupAnchor: [0, -9],
});

const AI_SERVICE_URL = import.meta.env.VITE_AI_SERVICE_URL || "http://localhost:8082";

function TaskBadge({ type }: { type?: string }) {
  const t = type || "unknown";
  const palette: Record<string, string> = {
    change_vqa: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    vqa: "bg-blue-500/15 text-blue-300 border-blue-500/30",
    grounding: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    sar_fusion: "bg-purple-500/15 text-purple-300 border-purple-500/30",
    unknown: "bg-gray-500/15 text-gray-300 border-gray-500/30",
  };
  const cls = palette[t] ?? palette.unknown;
  return (
    <span className={cn("text-[10px] font-mono font-semibold uppercase tracking-wider px-2 py-0.5 rounded border", cls)}>
      {t.replace(/_/g, " ")}
    </span>
  );
}

function CollectionBadge({ collection }: { collection: string }) {
  const collLower = collection.toLowerCase();
  let colorStyle = "background: rgba(6, 182, 212, 0.15); color: #67e8f9; border: 1px solid rgba(6, 182, 212, 0.3);";
  if (collLower.includes("sentinel-1")) {
    colorStyle = "background: rgba(168, 85, 247, 0.15); color: #d8b4fe; border: 1px solid rgba(168, 85, 247, 0.3);";
  } else if (collLower.includes("landsat")) {
    colorStyle = "background: rgba(245, 158, 11, 0.15); color: #fcd34d; border: 1px solid rgba(245, 158, 11, 0.3);";
  }
  return (
    <span style={{ fontSize: "10px", fontFamily: "monospace", fontWeight: 600, textTransform: "uppercase", padding: "2px 6px", borderRadius: "4px", ...parseInlineStyle(colorStyle) }}>
      {collection}
    </span>
  );
}

function parseInlineStyle(styleStr: string): Record<string, string> {
  const res: Record<string, string> = {};
  styleStr.split(";").forEach((pair) => {
    const [k, v] = pair.split(":");
    if (k && v) {
      const camel = k.trim().replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      res[camel] = v.trim();
    }
  });
  return res;
}

function escapeHtml(str: any): string {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function createAnalysisPopupHtml(feature: AnalysisGeoJSONFeature): string {
  try {
    const p = feature?.properties || ({} as any);
    const metrics = p.computed_metrics as ComputedMetrics | null | undefined;
    const condensed = formatCondensedMetrics(metrics);

    let formattedDate = "";
    if (p.created_at) {
      try {
        const d = new Date(p.created_at);
        if (!isNaN(d.getTime())) {
          formattedDate = d.toLocaleString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          });
        }
      } catch {
        formattedDate = "";
      }
    }

    const taskType = p.task_type || "unknown";
    const queryText = p.query_text || "(No query text provided)";

    const metricsHtml =
      condensed && condensed !== "No metrics available"
        ? `
      <div style="
        background: hsl(0 0% 10%);
        border: 1px solid hsl(218 44% 55% / 0.2);
        border-radius: 6px;
        padding: 8px 10px;
        margin-bottom: 10px;
      ">
        <div style="
          font-size: 10px;
          color: hsl(218, 44%, 70%);
          text-transform: uppercase;
          letter-spacing: 0.05em;
          margin-bottom: 4px;
        ">
          ⚗ Measurements
        </div>
        <p style="font-size: 11px; font-family: 'IBM Plex Mono', monospace; color: hsl(218, 44%, 75%); margin: 0; line-height: 1.6;">
          ${escapeHtml(condensed)}
        </p>
      </div>
    `
        : "";

    const taskClassColors: Record<string, string> = {
      change_vqa: "background: rgba(245, 158, 11, 0.15); color: #fcd34d; border: 1px solid rgba(245, 158, 11, 0.3);",
      vqa: "background: rgba(59, 130, 246, 0.15); color: #93c5fd; border: 1px solid rgba(59, 130, 246, 0.3);",
      grounding: "background: rgba(16, 185, 129, 0.15); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.3);",
      sar_fusion: "background: rgba(168, 85, 247, 0.15); color: #d8b4fe; border: 1px solid rgba(168, 85, 247, 0.3);",
    };
    const taskStyle =
      taskClassColors[taskType] ||
      "background: rgba(107, 114, 128, 0.15); color: #d1d5db; border: 1px solid rgba(107, 114, 128, 0.3);";

    return `
      <div style="
        background: hsl(0 0% 7%);
        border: 1px solid hsl(0 0% 16.5%);
        border-radius: 10px;
        padding: 14px 16px;
        min-width: 240px;
        max-width: 320px;
        font-family: Inter, sans-serif;
        box-shadow: 0 8px 32px rgba(0,0,0,0.7);
        color: hsl(0 0% 96%);
      ">
        <div style="margin-bottom: 10px; border-bottom: 1px solid hsl(0 0% 16.5%); padding-bottom: 8px;">
          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <span style="font-size: 10px; font-family: monospace; font-weight: 600; text-transform: uppercase; padding: 2px 6px; border-radius: 4px; ${taskStyle}">
              ${escapeHtml(taskType.replace(/_/g, " "))}
            </span>
            ${
              p.modality
                ? `
              <span style="font-size: 10px; font-family: 'IBM Plex Mono', monospace; color: hsl(0 0% 64%); text-transform: uppercase; letter-spacing: 0.05em;">
                ${escapeHtml(p.modality)}
              </span>
            `
                : ""
            }
          </div>
        </div>

        <div style="margin-bottom: 10px;">
          <div style="font-size: 10px; color: hsl(0 0% 64%); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">
            Query
          </div>
          <p style="font-size: 12px; color: hsl(0 0% 96%); line-height: 1.5; margin: 0;">
            ${escapeHtml(queryText)}
          </p>
        </div>

        ${metricsHtml}

        ${
          formattedDate
            ? `
          <div style="display: flex; align-items: center; gap: 4px; font-size: 10px; color: hsl(0 0% 48%); margin-top: 4px;">
            <span>🕐</span>
            <span>${escapeHtml(formattedDate)}</span>
          </div>
        `
            : ""
        }
      </div>
    `;
  } catch (error) {
    console.warn("createAnalysisPopupHtml failed:", error);
    return `
      <div style="background: hsl(0 0% 7%); padding: 12px; border-radius: 8px; font-size: 12px; color: hsl(0 0% 80%);">
        <strong>Analysis #${escapeHtml(feature?.properties?.id ?? "unknown")}</strong>
        <p style="margin: 4px 0 0 0; color: hsl(0 0% 50%);">Details temporarily unavailable.</p>
      </div>
    `;
  }
}

function createCatalogPopupHtml(feature: CatalogGeoJSONFeature): string {
  try {
    const p = feature?.properties || ({} as any);

    let formattedDate = "";
    if (p.datetime) {
      try {
        const d = new Date(p.datetime);
        if (!isNaN(d.getTime())) {
          formattedDate = d.toLocaleString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          });
        }
      } catch {
        formattedDate = "";
      }
    }

    const collLower = (p.collection || "").toLowerCase();
    let badgeColor = "background: rgba(6, 182, 212, 0.15); color: #67e8f9; border: 1px solid rgba(6, 182, 212, 0.3);";
    if (collLower.includes("sentinel-1")) {
      badgeColor = "background: rgba(168, 85, 247, 0.15); color: #d8b4fe; border: 1px solid rgba(168, 85, 247, 0.3);";
    } else if (collLower.includes("landsat")) {
      badgeColor = "background: rgba(245, 158, 11, 0.15); color: #fcd34d; border: 1px solid rgba(245, 158, 11, 0.3);";
    }

    const cloudText =
      p.cloud_cover !== null && p.cloud_cover !== undefined
        ? `Cloud cover: ${Number(p.cloud_cover).toFixed(1)}%`
        : "SAR / All-Weather (No cloud metric)";

    const isHttpThumb = p.thumbnail_url && (p.thumbnail_url.startsWith("http://") || p.thumbnail_url.startsWith("https://"));

    return `
      <div style="
        background: hsl(0 0% 7%);
        border: 1px solid hsl(186 100% 33% / 0.4);
        border-radius: 10px;
        padding: 14px 16px;
        min-width: 260px;
        max-width: 320px;
        font-family: Inter, sans-serif;
        box-shadow: 0 8px 32px rgba(0,0,0,0.7);
        color: hsl(0 0% 96%);
      ">
        <div style="margin-bottom: 10px; border-bottom: 1px solid hsl(0 0% 16.5%); padding-bottom: 8px;">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
            <span style="font-size: 10px; font-family: monospace; font-weight: 600; text-transform: uppercase; padding: 2px 6px; border-radius: 4px; ${badgeColor}">
              ${escapeHtml(p.collection)}
            </span>
            <span style="font-size: 9px; font-mono; color: #06b6d4; text-transform: uppercase; letter-spacing: 0.05em;">
              STAC Coverage
            </span>
          </div>
        </div>

        <div style="margin-bottom: 10px;">
          <div style="font-size: 10px; color: hsl(0 0% 64%); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 2px;">
            Scene ID
          </div>
          <p style="font-size: 11px; font-family: monospace; color: hsl(0 0% 90%); margin: 0; word-break: break-all;">
            ${escapeHtml(p.scene_id)}
          </p>
        </div>

        ${
          isHttpThumb
            ? `
          <div style="margin-bottom: 10px; border-radius: 6px; overflow: hidden; max-height: 120px; background: #000;">
            <img src="${escapeHtml(p.thumbnail_url)}" alt="Thumbnail" style="width: 100%; height: auto; display: block; object-fit: cover;" />
          </div>
        `
            : ""
        }

        <div style="
          background: hsl(0 0% 10%);
          border: 1px solid rgba(6, 182, 212, 0.2);
          border-radius: 6px;
          padding: 6px 10px;
          margin-bottom: 10px;
          font-size: 11px;
          color: #a5f3fc;
        ">
          ${escapeHtml(cloudText)}
        </div>

        <div style="display: flex; align-items: center; justify-content: space-between; font-size: 10px; color: hsl(0 0% 50%);">
          <span>📅 ${escapeHtml(formattedDate)}</span>
          ${
            p.stac_href
              ? `
            <a href="${escapeHtml(p.stac_href)}" target="_blank" rel="noopener noreferrer" style="color: #06b6d4; text-decoration: underline;">
              STAC JSON ↗
            </a>
          `
              : ""
          }
        </div>
      </div>
    `;
  } catch (error) {
    console.warn("createCatalogPopupHtml failed:", error);
    return `
      <div style="background: hsl(0 0% 7%); padding: 12px; border-radius: 8px; font-size: 12px; color: hsl(0 0% 80%);">
        <strong>STAC Scene: ${escapeHtml(feature?.properties?.scene_id ?? "unknown")}</strong>
      </div>
    `;
  }
}

function StatCard({ icon: Icon, label, value, colorClass }: { icon: any; label: string; value: string | number; colorClass?: string }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-card/80 border border-border/60 backdrop-blur-sm">
      <Icon className={cn("h-4 w-4 shrink-0", colorClass || "text-primary")} />
      <div>
        <p className="text-[10px] text-muted-foreground uppercase tracking-wider">{label}</p>
        <p className="text-sm font-semibold text-foreground font-mono">{value}</p>
      </div>
    </div>
  );
}

// ─── React Error Boundary for MapView ────────────────────────────────────────
interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class MapErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("MapErrorBoundary caught an error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="p-8 text-center bg-card/90 rounded-xl border border-border/60 m-6">
          <AlertCircle className="h-10 w-10 text-destructive mx-auto mb-3" />
          <h2 className="text-base font-semibold text-foreground mb-1">Map View Error</h2>
          <p className="text-xs text-muted-foreground mb-4">
            An unexpected error occurred while rendering the map history view.
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="px-3 py-1.5 text-xs bg-primary text-primary-foreground rounded hover:bg-primary/90 transition-colors"
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function MapViewContent() {
  const [analysesData, setAnalysesData] = useState<AnalysisFeatureCollection | null>(null);
  const [catalogData, setCatalogData] = useState<CatalogFeatureCollection | null>(null);
  const [showCatalogLayer, setShowCatalogLayer] = useState(true);
  const [showAnalysisLayer, setShowAnalysisLayer] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const analysisLayerGroupRef = useRef<L.LayerGroup | null>(null);
  const catalogLayerGroupRef = useRef<L.LayerGroup | null>(null);

  // Fetch both analyses and catalog data in parallel
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.allSettled([
      fetch(`${AI_SERVICE_URL}/api/analyses?limit=200`).then((res) => {
        if (!res.ok) throw new Error(`Analyses: HTTP ${res.status}`);
        return res.json() as Promise<AnalysisFeatureCollection>;
      }),
      fetch(`${AI_SERVICE_URL}/api/catalog?limit=100`).then((res) => {
        if (!res.ok) throw new Error(`Catalog: HTTP ${res.status}`);
        return res.json() as Promise<CatalogFeatureCollection>;
      }),
    ])
      .then(([analysesRes, catalogRes]) => {
        if (cancelled) return;

        if (analysesRes.status === "fulfilled") {
          setAnalysesData(analysesRes.value);
        } else {
          console.warn("Failed to load analyses:", analysesRes.reason);
          setError("Failed to fetch analysis history.");
        }

        if (catalogRes.status === "fulfilled") {
          setCatalogData(catalogRes.value);
        } else {
          console.warn("Catalog fetch non-fatal error:", catalogRes.reason);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // Initialize pure Leaflet map instance once
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: [-10.01, -62.0],
        zoom: 7,
        zoomControl: false,
        attributionControl: false,
      });

      L.tileLayer("https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png", {
        maxZoom: 20,
      }).addTo(map);

      // Separate layer groups for independent toggling
      const catLayer = L.layerGroup().addTo(map);
      const anaLayer = L.layerGroup().addTo(map);

      catalogLayerGroupRef.current = catLayer;
      analysisLayerGroupRef.current = anaLayer;
      mapInstanceRef.current = map;
    }
  }, []);

  // Sync Analysis features layer
  useEffect(() => {
    const layer = analysisLayerGroupRef.current;
    if (!layer) return;

    layer.clearLayers();
    if (!showAnalysisLayer) return;

    const mappable = analysesData?.features?.filter((f) => f && f.geometry !== null) ?? [];

    mappable.forEach((feature, idx) => {
      try {
        if (!feature || !feature.geometry) return;
        const popupHtml = createAnalysisPopupHtml(feature);

        if (feature.geometry.type === "Point") {
          const coords = feature.geometry.coordinates;
          if (Array.isArray(coords) && coords.length >= 2 && !isNaN(coords[0]) && !isNaN(coords[1])) {
            const [lng, lat] = coords as number[];
            const marker = L.marker([lat, lng], { icon: analysisIcon })
              .bindPopup(popupHtml, { className: "leaflet-popup-dark", maxWidth: 340, closeButton: false });
            layer.addLayer(marker);
          }
        } else if (feature.geometry.type === "Polygon") {
          const rings = feature.geometry.coordinates;
          if (Array.isArray(rings) && rings.length > 0 && Array.isArray(rings[0])) {
            const latLngs: L.LatLngTuple[] = [];
            for (const pt of rings[0]) {
              if (Array.isArray(pt) && pt.length >= 2 && !isNaN(pt[0]) && !isNaN(pt[1])) {
                latLngs.push([pt[1], pt[0]]);
              }
            }

            if (latLngs.length >= 3) {
              const centLat = latLngs.reduce((s, p) => s + p[0], 0) / latLngs.length;
              const centLng = latLngs.reduce((s, p) => s + p[1], 0) / latLngs.length;

              const polygon = L.polygon(latLngs, {
                color: "hsl(218, 44%, 65%)",
                weight: 2,
                fillColor: "hsl(218, 44%, 55%)",
                fillOpacity: 0.18,
                opacity: 0.85,
                dashArray: "4 3",
              }).bindPopup(popupHtml, { className: "leaflet-popup-dark", maxWidth: 340, closeButton: false });

              const centerMarker = L.marker([centLat, centLng], { icon: analysisPolygonIcon })
                .bindPopup(popupHtml, { className: "leaflet-popup-dark", maxWidth: 340, closeButton: false });

              layer.addLayer(polygon);
              layer.addLayer(centerMarker);
            }
          }
        }
      } catch (pinErr) {
        console.warn(`Skipping malformed analysis pin #${feature?.properties?.id ?? idx}:`, pinErr);
      }
    });
  }, [analysesData, showAnalysisLayer]);

  // Sync STAC Catalog features layer (distinct cyan hollow styling)
  useEffect(() => {
    const layer = catalogLayerGroupRef.current;
    if (!layer) return;

    layer.clearLayers();
    if (!showCatalogLayer) return;

    const scenes = catalogData?.features?.filter((f) => f && f.geometry !== null) ?? [];

    scenes.forEach((feature, idx) => {
      try {
        if (!feature || !feature.geometry) return;
        const popupHtml = createCatalogPopupHtml(feature);
        const collLower = (feature.properties?.collection || "").toLowerCase();

        // Color theme by collection
        let strokeColor = "#06b6d4"; // Sentinel-2 default cyan
        let fillColor = "#06b6d4";
        if (collLower.includes("sentinel-1")) {
          strokeColor = "#c084fc"; // SAR Purple
          fillColor = "#c084fc";
        } else if (collLower.includes("landsat")) {
          strokeColor = "#fbbf24"; // Landsat Amber
          fillColor = "#fbbf24";
        }

        if (feature.geometry.type === "Polygon") {
          const rings = feature.geometry.coordinates;
          if (Array.isArray(rings) && rings.length > 0 && Array.isArray(rings[0])) {
            const latLngs: L.LatLngTuple[] = [];
            for (const pt of rings[0]) {
              if (Array.isArray(pt) && pt.length >= 2 && !isNaN(pt[0]) && !isNaN(pt[1])) {
                latLngs.push([pt[1], pt[0]]);
              }
            }

            if (latLngs.length >= 3) {
              const centLat = latLngs.reduce((s, p) => s + p[0], 0) / latLngs.length;
              const centLng = latLngs.reduce((s, p) => s + p[1], 0) / latLngs.length;

              // Thin crisp outline with hollow fill
              const polygon = L.polygon(latLngs, {
                color: strokeColor,
                weight: 1.5,
                fillColor: fillColor,
                fillOpacity: 0.05,
                opacity: 0.7,
                dashArray: "2 2",
              }).bindPopup(popupHtml, { className: "leaflet-popup-dark", maxWidth: 340, closeButton: false });

              const centerMarker = L.marker([centLat, centLng], { icon: catalogHollowIcon })
                .bindPopup(popupHtml, { className: "leaflet-popup-dark", maxWidth: 340, closeButton: false });

              layer.addLayer(polygon);
              layer.addLayer(centerMarker);
            }
          }
        }
      } catch (catErr) {
        console.warn(`Skipping malformed catalog scene #${feature?.properties?.scene_id ?? idx}:`, catErr);
      }
    });
  }, [catalogData, showCatalogLayer]);

  // Auto-fit bounds once initial data arrives
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    const allPoints: L.LatLngTuple[] = [];

    (analysesData?.features ?? []).forEach((f) => {
      if (!f?.geometry) return;
      if (f.geometry.type === "Point") {
        const coords = f.geometry.coordinates;
        if (Array.isArray(coords) && coords.length >= 2) allPoints.push([coords[1], coords[0]]);
      } else if (f.geometry.type === "Polygon") {
        const rings = f.geometry.coordinates;
        if (Array.isArray(rings) && rings[0]) {
          rings[0].forEach((pt: any) => {
            if (Array.isArray(pt) && pt.length >= 2) allPoints.push([pt[1], pt[0]]);
          });
        }
      }
    });

    if (allPoints.length > 0) {
      try {
        const bounds = L.latLngBounds(allPoints);
        map.fitBounds(bounds, { padding: [48, 48], maxZoom: 14 });
      } catch (boundsErr) {
        console.warn("Failed to auto-fit map bounds:", boundsErr);
      }
    }
  }, [analysesData]);

  // Clean up Leaflet on unmount
  useEffect(() => {
    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  const totalAnalyses = analysesData?.features?.length ?? 0;
  const mappedAnalyses = (analysesData?.features ?? []).filter((f) => f && f.geometry !== null).length;
  const withoutGeomAnalyses = totalAnalyses - mappedAnalyses;

  const totalCatalogScenes = catalogData?.features?.length ?? 0;

  return (
    <div
      className="min-h-screen pt-16 flex flex-col"
      style={{ background: "hsl(0 0% 4%)" }}
    >
      {/* ── Header ── */}
      <div className="px-6 pt-10 pb-4 max-w-[1400px] mx-auto w-full">
        <div className="flex items-center justify-between flex-wrap gap-4 mb-2">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10 border border-primary/20">
              <MapIcon className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-foreground tracking-tight flex items-center gap-2">
                Orbital Pulse Map &amp; STAC Catalog
              </h1>
              <p className="text-xs text-muted-foreground mt-0.5">
                Geospatial view of persisted analyses and live metadata-only Earth Search STAC scene ingestion
              </p>
            </div>
          </div>

          {/* Layer toggles */}
          <div className="flex items-center gap-2 text-xs">
            <button
              onClick={() => setShowAnalysisLayer(!showAnalysisLayer)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg border transition-all",
                showAnalysisLayer
                  ? "bg-blue-500/15 border-blue-500/40 text-blue-300 shadow-sm"
                  : "bg-card/40 border-border/40 text-muted-foreground line-through opacity-60"
              )}
            >
              <div className="w-2.5 h-2.5 rounded-full bg-blue-500/80 border border-blue-300" />
              <span>Analyses ({mappedAnalyses})</span>
              {showAnalysisLayer ? <Eye className="h-3 w-3 ml-1" /> : <EyeOff className="h-3 w-3 ml-1" />}
            </button>

            <button
              onClick={() => setShowCatalogLayer(!showCatalogLayer)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg border transition-all",
                showCatalogLayer
                  ? "bg-cyan-500/15 border-cyan-500/40 text-cyan-300 shadow-sm"
                  : "bg-card/40 border-border/40 text-muted-foreground line-through opacity-60"
              )}
            >
              <div className="w-2.5 h-2.5 rounded-full border border-cyan-400" />
              <span>STAC Scenes ({totalCatalogScenes})</span>
              {showCatalogLayer ? <Eye className="h-3 w-3 ml-1" /> : <EyeOff className="h-3 w-3 ml-1" />}
            </button>
          </div>
        </div>

        {/* Stats row */}
        <div className="flex flex-wrap gap-3 mt-4">
          <StatCard icon={Layers} label="Persisted analyses" value={totalAnalyses} />
          <StatCard icon={Crosshair} label="Mapped analyses" value={mappedAnalyses} />
          <StatCard
            icon={Satellite}
            label="Catalogued STAC scenes"
            value={totalCatalogScenes}
            colorClass="text-cyan-400"
          />
          {withoutGeomAnalyses > 0 && (
            <StatCard icon={AlertCircle} label="No geom" value={withoutGeomAnalyses} />
          )}
        </div>
      </div>

      {/* ── Map area ── */}
      <div className="flex-1 px-6 pb-8 max-w-[1400px] mx-auto w-full">
        <div
          className="relative rounded-xl overflow-hidden border border-border/60 shadow-2xl"
          style={{ height: "calc(100vh - 340px)", minHeight: "480px" }}
        >
          {/* Loading state */}
          {loading && (
            <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-card/80 backdrop-blur-sm">
              <Loader2 className="h-8 w-8 text-primary animate-spin mb-3" />
              <p className="text-sm text-muted-foreground">Fetching analyses and STAC scenes…</p>
            </div>
          )}

          {/* Error state */}
          {error && !loading && totalAnalyses === 0 && (
            <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-card/90 backdrop-blur-sm p-8">
              <AlertCircle className="h-10 w-10 text-destructive mb-4" />
              <h2 className="text-base font-semibold text-foreground mb-2">Could not load analysis history</h2>
              <p className="text-xs text-muted-foreground text-center max-w-xs mb-2">{error}</p>
              <p className="text-xs text-muted-foreground/60 text-center max-w-xs">
                Make sure the SatQuery AI service is running and the Docker stack (PostGIS) is up.
              </p>
            </div>
          )}

          {/* Leaflet map DOM mount point */}
          <div
            ref={mapContainerRef}
            style={{ height: "100%", width: "100%", background: "#0a0a0a" }}
          />

          {/* Layer Legend Overlay */}
          <div className="absolute top-3 right-3 z-10 p-2.5 rounded-lg border border-border/60 bg-background/80 backdrop-blur-md text-[11px] space-y-1.5 shadow-lg">
            <p className="font-semibold text-[10px] text-muted-foreground uppercase tracking-wider mb-1">
              Active Layers
            </p>
            <div className="flex items-center gap-2 text-blue-300">
              <div className="w-3 h-3 rounded-full bg-blue-500/80 border border-blue-300 shadow" />
              <span>Analyses (Filled Polygon + Solid Pin)</span>
            </div>
            <div className="flex items-center gap-2 text-cyan-300">
              <div className="w-3 h-3 rounded-full border-2 border-cyan-400 flex items-center justify-center">
                <div className="w-1 h-1 rounded-full bg-cyan-400" />
              </div>
              <span>STAC Catalog (Hollow Ring + Thin Bbox)</span>
            </div>
          </div>

          {/* Leaflet attribution overlay */}
          <div className="absolute bottom-2 right-2 z-10 text-[9px] text-muted-foreground/50 bg-background/70 px-1.5 py-0.5 rounded pointer-events-none">
            © Stadia Maps · OpenMapTiles · Earth Search STAC (AWS Element84)
          </div>
        </div>

        {/* Non-mappable table */}
        {!loading && withoutGeomAnalyses > 0 && (
          <div className="mt-6">
            <p className="text-xs text-muted-foreground mb-3 flex items-center gap-1.5">
              <AlertCircle className="h-3.5 w-3.5" />
              {withoutGeomAnalyses} {withoutGeomAnalyses === 1 ? "analysis" : "analyses"} without geolocation:
            </p>
            <div className="space-y-2">
              {(analysesData?.features ?? [])
                .filter((f) => !f?.geometry)
                .map((f, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 px-4 py-3 rounded-lg border border-border/50 bg-card/60 backdrop-blur-sm text-xs"
                  >
                    <TaskBadge type={f?.properties?.task_type} />
                    <span className="text-foreground flex-1 line-clamp-1">
                      {f?.properties?.query_text || "(No query text)"}
                    </span>
                    {f?.properties?.created_at && (
                      <span className="text-muted-foreground shrink-0 flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {new Date(f.properties.created_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>

      {/* Inline styles for Leaflet popup dark theme */}
      <style>{`
        .leaflet-popup-content-wrapper {
          background: transparent !important;
          border: none !important;
          box-shadow: none !important;
          padding: 0 !important;
          border-radius: 10px !important;
          overflow: hidden !important;
        }
        .leaflet-popup-content {
          margin: 0 !important;
        }
        .leaflet-popup-tip-container {
          display: none !important;
        }
        .leaflet-popup {
          filter: drop-shadow(0 8px 32px rgba(0,0,0,0.8));
        }
        .leaflet-container {
          background: hsl(0 0% 4%);
          font-family: Inter, sans-serif;
        }
        .leaflet-marker-icon {
          background: transparent !important;
          border: none !important;
        }
      `}</style>
    </div>
  );
}

export default function MapView() {
  return (
    <MapErrorBoundary>
      <MapViewContent />
    </MapErrorBoundary>
  );
}
