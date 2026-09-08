import React, { Component, ErrorInfo, ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  CalendarDays,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Check,
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

// Solid analysis pin (deep slate blue)
const analysisIcon = L.divIcon({
  html: `<div style="
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: #3b82f6;
    border: 2px solid #ffffff;
    box-shadow: 0 2px 5px rgba(0,0,0,0.6);
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
    border-radius: 2px;
    background: #2563eb;
    border: 2px solid #ffffff;
    box-shadow: 0 2px 5px rgba(0,0,0,0.6);
    transform: rotate(45deg);
  "></div>`,
  className: "",
  iconSize: [12, 12],
  iconAnchor: [6, 6],
  popupAnchor: [0, -10],
});

// Dynamic STAC catalog marker with per-collection color coding
function getCatalogMarkerIcon(color: string): L.DivIcon {
  return L.divIcon({
    html: `<div style="
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: ${color};
      border: 2px solid #ffffff;
      box-shadow: 0 2px 5px rgba(0,0,0,0.6);
    "></div>`,
    className: "",
    iconSize: [12, 12],
    iconAnchor: [6, 6],
    popupAnchor: [0, -9],
  });
}

// STAC collection keys and metadata
export type STACCollectionKey = "sentinel-2" | "sentinel-1" | "landsat";

export function getSTACCollectionKey(collectionName?: string): STACCollectionKey {
  const coll = (collectionName || "").toLowerCase();
  if (coll.includes("sentinel-1")) return "sentinel-1";
  if (coll.includes("landsat")) return "landsat";
  return "sentinel-2";
}

export interface CollectionConfig {
  key: STACCollectionKey;
  label: string;
  subLabel: string;
  stroke: string;
  fill: string;
  textColor: string;
  badgeBg: string;
  badgeBorder: string;
  swatchClass: string;
}

export const STAC_COLLECTIONS: CollectionConfig[] = [
  {
    key: "sentinel-2",
    label: "Sentinel-2",
    subLabel: "Optical (L2A)",
    stroke: "#0d9488",
    fill: "#0f766e",
    textColor: "text-teal-400",
    badgeBg: "bg-teal-950/70",
    badgeBorder: "border-teal-800",
    swatchClass: "bg-teal-500",
  },
  {
    key: "sentinel-1",
    label: "Sentinel-1",
    subLabel: "SAR (GRD)",
    stroke: "#7e22ce",
    fill: "#6b21a8",
    textColor: "text-purple-400",
    badgeBg: "bg-purple-950/70",
    badgeBorder: "border-purple-800",
    swatchClass: "bg-purple-500",
  },
  {
    key: "landsat",
    label: "Landsat",
    subLabel: "Multispectral (C2)",
    stroke: "#b45309",
    fill: "#92400e",
    textColor: "text-amber-400",
    badgeBg: "bg-amber-950/70",
    badgeBorder: "border-amber-800",
    swatchClass: "bg-amber-500",
  },
];

const AI_SERVICE_URL = import.meta.env.VITE_AI_SERVICE_URL || "http://localhost:8082";

function TaskBadge({ type }: { type?: string }) {
  const t = type || "unknown";
  const palette: Record<string, string> = {
    change_vqa: "bg-amber-950/80 text-amber-300 border-amber-800",
    vqa: "bg-blue-950/80 text-blue-300 border-blue-800",
    grounding: "bg-emerald-950/80 text-emerald-300 border-emerald-800",
    sar_fusion: "bg-purple-950/80 text-purple-300 border-purple-800",
    unknown: "bg-zinc-900 text-zinc-400 border-zinc-700",
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
  let colorStyle = "background: #134e4a; color: #5eead4; border: 1px solid #115e59;";
  if (collLower.includes("sentinel-1")) {
    colorStyle = "background: #3b0764; color: #d8b4fe; border: 1px solid #581c87;";
  } else if (collLower.includes("landsat")) {
    colorStyle = "background: #451a03; color: #fcd34d; border: 1px solid #78350f;";
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

// ─── Overlap clustering helpers ───────────────────────────────────────────────
// Two centroids are considered "overlapping" when they are within this many
// decimal degrees of each other (≈ 8–9 km at equatorial latitudes).
const CLUSTER_THRESHOLD_DEG = 0.08;

interface CentroidGroup<T> {
  centLat: number;
  centLng: number;
  items: T[];
}

/** Group an array of items by their centroid proximity. */
function clusterByProximity<T>(
  items: T[],
  getCentroid: (item: T) => { lat: number; lng: number } | null,
): CentroidGroup<T>[] {
  const groups: CentroidGroup<T>[] = [];

  for (const item of items) {
    const c = getCentroid(item);
    if (!c) continue;

    // Find an existing group within threshold
    const existing = groups.find(
      (g) =>
        Math.abs(g.centLat - c.lat) < CLUSTER_THRESHOLD_DEG &&
        Math.abs(g.centLng - c.lng) < CLUSTER_THRESHOLD_DEG,
    );

    if (existing) {
      existing.items.push(item);
      // Update running average centroid
      const n = existing.items.length;
      existing.centLat = (existing.centLat * (n - 1) + c.lat) / n;
      existing.centLng = (existing.centLng * (n - 1) + c.lng) / n;
    } else {
      groups.push({ centLat: c.lat, centLng: c.lng, items: [item] });
    }
  }

  return groups;
}

/** Cluster marker icon — shows a count badge. */
function makeClusterIcon(count: number, color: string, textColor: string): L.DivIcon {
  return L.divIcon({
    html: `<div style="
      min-width: 26px;
      height: 26px;
      padding: 0 6px;
      border-radius: 13px;
      background: ${color};
      border: 2px solid rgba(255,255,255,0.85);
      box-shadow: 0 2px 8px rgba(0,0,0,0.7);
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: 'IBM Plex Mono', monospace;
      font-size: 11px;
      font-weight: 700;
      color: ${textColor};
      letter-spacing: -0.02em;
      white-space: nowrap;
      cursor: pointer;
    ">${count}×</div>`,
    className: "",
    iconSize: [26, 26],
    iconAnchor: [13, 13],
    popupAnchor: [0, -16],
  });
}

/** Multi-item popup listing all features in a cluster. */
function createClusterAnalysisPopupHtml(features: AnalysisGeoJSONFeature[]): string {
  const items = features
    .map((f) => {
      const p = f?.properties || ({} as any);
      const taskType = p.task_type || "unknown";
      const queryText = p.query_text || "(No query text)";
      const taskClassColors: Record<string, string> = {
        change_vqa: "background:#451a03;color:#fcd34d;border:1px solid #78350f;",
        vqa: "background:#172554;color:#93c5fd;border:1px solid #1e40af;",
        grounding: "background:#064e3b;color:#6ee7b7;border:1px solid #047857;",
        sar_fusion: "background:#3b0764;color:#d8b4fe;border:1px solid #581c87;",
      };
      const taskStyle = taskClassColors[taskType] || "background:#27272a;color:#d4d4d8;border:1px solid #3f3f46;";
      let dateStr = "";
      if (p.created_at) {
        try {
          dateStr = new Date(p.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
        } catch { /* ignore */ }
      }
      return `
        <div style="padding:8px 0;border-bottom:1px solid #27272a;">
          <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:4px;">
            <span style="font-size:9px;font-family:monospace;font-weight:600;text-transform:uppercase;padding:1px 5px;border-radius:3px;${taskStyle}">
              ${escapeHtml(taskType.replace(/_/g, " "))}
            </span>
            ${dateStr ? `<span style="font-size:9px;color:#71717a;">${escapeHtml(dateStr)}</span>` : ""}
          </div>
          <p style="font-size:11px;color:#e4e4e7;margin:0;line-height:1.45;word-break:break-word;">${escapeHtml(queryText)}</p>
        </div>
      `;
    })
    .join("");

  return `
    <div style="
      background:#09090b;
      border:1px solid #27272a;
      border-radius:8px;
      padding:12px 14px;
      min-width:260px;
      max-width:340px;
      max-height:380px;
      overflow-y:auto;
      font-family:Inter,sans-serif;
      box-shadow:0 10px 25px rgba(0,0,0,0.85);
      color:#f4f4f5;
    ">
      <div style="font-size:10px;color:#93c5fd;text-transform:uppercase;letter-spacing:.06em;font-weight:600;margin-bottom:8px;">
        ${features.length} overlapping analyses
      </div>
      ${items}
    </div>
  `;
}

/** Multi-item popup listing all STAC scenes in a cluster. */
function createClusterCatalogPopupHtml(features: CatalogGeoJSONFeature[]): string {
  const items = features
    .map((f) => {
      const p = f?.properties || ({} as any);
      const collLower = (p.collection || "").toLowerCase();
      let badgeStyle = "background:#134e4a;color:#5eead4;border:1px solid #115e59;";
      if (collLower.includes("sentinel-1")) badgeStyle = "background:#3b0764;color:#d8b4fe;border:1px solid #581c87;";
      else if (collLower.includes("landsat")) badgeStyle = "background:#451a03;color:#fcd34d;border:1px solid #78350f;";
      let dateStr = "";
      if (p.datetime) {
        try {
          dateStr = new Date(p.datetime).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
        } catch { /* ignore */ }
      }
      const cloud =
        p.cloud_cover != null
          ? `Cloud: ${Number(p.cloud_cover).toFixed(1)}%`
          : "SAR / All-Weather";
      return `
        <div style="padding:8px 0;border-bottom:1px solid #27272a;">
          <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:4px;">
            <span style="font-size:9px;font-family:monospace;font-weight:600;text-transform:uppercase;padding:1px 5px;border-radius:3px;${badgeStyle}">${escapeHtml(p.collection)}</span>
            ${dateStr ? `<span style="font-size:9px;color:#71717a;">${escapeHtml(dateStr)}</span>` : ""}
          </div>
          <p style="font-size:10px;font-family:monospace;color:#a1a1aa;margin:0 0 2px;word-break:break-all;">${escapeHtml(p.scene_id)}</p>
          <p style="font-size:10px;color:#ccfbf1;margin:0;">${escapeHtml(cloud)}</p>
        </div>
      `;
    })
    .join("");

  return `
    <div style="
      background:#09090b;
      border:1px solid #27272a;
      border-radius:8px;
      padding:12px 14px;
      min-width:260px;
      max-width:340px;
      max-height:380px;
      overflow-y:auto;
      font-family:Inter,sans-serif;
      box-shadow:0 10px 25px rgba(0,0,0,0.85);
      color:#f4f4f5;
    ">
      <div style="font-size:10px;color:#2dd4bf;text-transform:uppercase;letter-spacing:.06em;font-weight:600;margin-bottom:8px;">
        ${features.length} overlapping STAC scenes
      </div>
      ${items}
    </div>
  `;
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
        background: #18181b;
        border: 1px solid #27272a;
        border-radius: 6px;
        padding: 8px 10px;
        margin-bottom: 10px;
      ">
        <div style="
          font-size: 10px;
          color: #93c5fd;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          margin-bottom: 4px;
          font-weight: 600;
        ">
          Measurements
        </div>
        <p style="font-size: 11px; font-family: 'IBM Plex Mono', monospace; color: #cbd5e1; margin: 0; line-height: 1.6;">
          ${escapeHtml(condensed)}
        </p>
      </div>
    `
        : "";

    const taskClassColors: Record<string, string> = {
      change_vqa: "background: #451a03; color: #fcd34d; border: 1px solid #78350f;",
      vqa: "background: #172554; color: #93c5fd; border: 1px solid #1e40af;",
      grounding: "background: #064e3b; color: #6ee7b7; border: 1px solid #047857;",
      sar_fusion: "background: #3b0764; color: #d8b4fe; border: 1px solid #581c87;",
    };
    const taskStyle =
      taskClassColors[taskType] ||
      "background: #27272a; color: #d4d4d8; border: 1px solid #3f3f46;";

    return `
      <div style="
        background: #09090b;
        border: 1px solid #27272a;
        border-radius: 8px;
        padding: 14px 16px;
        min-width: 240px;
        max-width: 320px;
        font-family: Inter, sans-serif;
        box-shadow: 0 10px 25px rgba(0,0,0,0.85);
        color: #f4f4f5;
      ">
        <div style="margin-bottom: 10px; border-bottom: 1px solid #27272a; padding-bottom: 8px;">
          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <span style="font-size: 10px; font-family: monospace; font-weight: 600; text-transform: uppercase; padding: 2px 6px; border-radius: 4px; ${taskStyle}">
              ${escapeHtml(taskType.replace(/_/g, " "))}
            </span>
            ${
              p.modality
                ? `
              <span style="font-size: 10px; font-family: 'IBM Plex Mono', monospace; color: #a1a1aa; text-transform: uppercase; letter-spacing: 0.05em;">
                ${escapeHtml(p.modality)}
              </span>
            `
                : ""
            }
          </div>
        </div>

        <div style="margin-bottom: 10px;">
          <div style="font-size: 10px; color: #a1a1aa; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">
            Query
          </div>
          <p style="font-size: 12px; color: #f4f4f5; line-height: 1.5; margin: 0;">
            ${escapeHtml(queryText)}
          </p>
        </div>

        ${metricsHtml}

        ${
          formattedDate
            ? `
          <div style="display: flex; align-items: center; gap: 4px; font-size: 10px; color: #71717a; margin-top: 4px;">
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
      <div style="background: #09090b; padding: 12px; border: 1px solid #27272a; border-radius: 8px; font-size: 12px; color: #d4d4d8;">
        <strong>Analysis #${escapeHtml(feature?.properties?.id ?? "unknown")}</strong>
        <p style="margin: 4px 0 0 0; color: #71717a;">Details temporarily unavailable.</p>
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
    let badgeColor = "background: #134e4a; color: #5eead4; border: 1px solid #115e59;";
    if (collLower.includes("sentinel-1")) {
      badgeColor = "background: #3b0764; color: #d8b4fe; border: 1px solid #581c87;";
    } else if (collLower.includes("landsat")) {
      badgeColor = "background: #451a03; color: #fcd34d; border: 1px solid #78350f;";
    }

    const cloudText =
      p.cloud_cover !== null && p.cloud_cover !== undefined
        ? `Cloud cover: ${Number(p.cloud_cover).toFixed(1)}%`
        : "SAR / All-Weather (No cloud metric)";

    const isHttpThumb = p.thumbnail_url && (p.thumbnail_url.startsWith("http://") || p.thumbnail_url.startsWith("https://"));

    return `
      <div style="
        background: #09090b;
        border: 1px solid #27272a;
        border-radius: 8px;
        padding: 14px 16px;
        min-width: 260px;
        max-width: 320px;
        font-family: Inter, sans-serif;
        box-shadow: 0 10px 25px rgba(0,0,0,0.85);
        color: #f4f4f5;
      ">
        <div style="margin-bottom: 10px; border-bottom: 1px solid #27272a; padding-bottom: 8px;">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
            <span style="font-size: 10px; font-family: monospace; font-weight: 600; text-transform: uppercase; padding: 2px 6px; border-radius: 4px; ${badgeColor}">
              ${escapeHtml(p.collection)}
            </span>
            <span style="font-size: 9px; font-family: monospace; color: #2dd4bf; text-transform: uppercase; letter-spacing: 0.05em;">
              STAC Coverage
            </span>
          </div>
        </div>

        <div style="margin-bottom: 10px;">
          <div style="font-size: 10px; color: #a1a1aa; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 2px;">
            Scene ID
          </div>
          <p style="font-size: 11px; font-family: monospace; color: #e4e4e7; margin: 0; word-break: break-all;">
            ${escapeHtml(p.scene_id)}
          </p>
        </div>

        ${
          isHttpThumb
            ? `
          <div style="margin-bottom: 10px; border-radius: 6px; overflow: hidden; max-height: 120px; background: #000; border: 1px solid #27272a;">
            <img src="${escapeHtml(p.thumbnail_url)}" alt="Thumbnail" style="width: 100%; height: auto; display: block; object-fit: cover;" />
          </div>
        `
            : ""
        }

        <div style="
          background: #18181b;
          border: 1px solid #27272a;
          border-radius: 6px;
          padding: 6px 10px;
          margin-bottom: 10px;
          font-size: 11px;
          color: #ccfbf1;
        ">
          ${escapeHtml(cloudText)}
        </div>

        <div style="display: flex; align-items: center; justify-content: space-between; font-size: 10px; color: #71717a;">
          <span>📅 ${escapeHtml(formattedDate)}</span>
          ${
            p.stac_href
              ? `
            <a href="${escapeHtml(p.stac_href)}" target="_blank" rel="noopener noreferrer" style="color: #2dd4bf; text-decoration: underline;">
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
      <div style="background: #09090b; padding: 12px; border: 1px solid #27272a; border-radius: 8px; font-size: 12px; color: #d4d4d8;">
        <strong>STAC Scene: ${escapeHtml(feature?.properties?.scene_id ?? "unknown")}</strong>
      </div>
    `;
  }
}

// ─── Subtle count-up hook for numbers ─────────────────────────────────────────
function useCountUp(target: number, duration: number = 750): number {
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    const startVal = current;
    const endVal = target;
    if (startVal === endVal) return;

    let startTime: number | null = null;
    let animFrame: number;

    const step = (timestamp: number) => {
      if (!startTime) startTime = timestamp;
      const progress = Math.min((timestamp - startTime) / duration, 1);
      // Smooth cubic ease-out
      const eased = 1 - Math.pow(1 - progress, 3);
      setCurrent(Math.round(startVal + (endVal - startVal) * eased));

      if (progress < 1) {
        animFrame = requestAnimationFrame(step);
      }
    };

    animFrame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(animFrame);
  }, [target, duration]);

  return current;
}

interface StatCardProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number;
  loading?: boolean;
  colorClass?: string;
  badgeClass?: string;
}

function StatCard({
  icon: Icon,
  label,
  value,
  loading = false,
  colorClass = "text-primary",
  badgeClass = "bg-primary/10 border-primary/20",
}: StatCardProps) {
  const animatedValue = useCountUp(value);

  return (
    <div className="flex items-center gap-3.5 px-3.5 sm:px-4 py-3 rounded-lg bg-card/80 border border-border/60 backdrop-blur-sm min-w-0 shadow-sm transition-all hover:border-border">
      <div className={cn("w-9 h-9 rounded-lg flex items-center justify-center shrink-0 border", badgeClass)}>
        <Icon className={cn("h-4 w-4", colorClass)} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium truncate">{label}</p>
        {loading ? (
          <div className="h-5 w-12 rounded bg-muted/60 animate-pulse mt-0.5" />
        ) : (
          <p className="text-base sm:text-lg font-semibold text-foreground font-mono leading-tight">{animatedValue}</p>
        )}
      </div>
    </div>
  );
}

// ─── React Error Boundary for MapView ────────────────────────────────────────
interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onReset?: () => void;
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

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="min-h-[500px] flex items-center justify-center p-6">
          <div className="p-8 text-center bg-card/90 rounded-xl border border-border/60 max-w-md w-full shadow-2xl backdrop-blur-md">
            <div className="w-12 h-12 rounded-full bg-destructive/20 border border-destructive/40 flex items-center justify-center mx-auto mb-4">
              <AlertCircle className="h-6 w-6 text-destructive" />
            </div>
            <h2 className="text-base font-semibold text-foreground mb-1.5">Map View Error</h2>
            <p className="text-xs text-muted-foreground mb-5">
              An unexpected error occurred while rendering the geospatial map.
            </p>
            <button
              onClick={this.handleRetry}
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors shadow active:scale-95"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              <span>Retry Map Initialization</span>
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// ─── Date-range filter helpers ────────────────────────────────────────────────
type DateFilter = "24h" | "7d" | "30d" | "all";

const DATE_FILTER_LABELS: Record<DateFilter, string> = {
  "24h": "Last 24 h",
  "7d": "Last 7 d",
  "30d": "Last 30 d",
  all: "All time",
};

function cutoffForFilter(filter: DateFilter): Date | null {
  if (filter === "all") return null;
  const now = new Date();
  if (filter === "24h") return new Date(now.getTime() - 24 * 60 * 60 * 1000);
  if (filter === "7d") return new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  if (filter === "30d") return new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
  return null;
}

function MapViewContent() {
  const [analysesData, setAnalysesData] = useState<AnalysisFeatureCollection | null>(null);
  const [catalogData, setCatalogData] = useState<CatalogFeatureCollection | null>(null);
  const [showAnalysisLayer, setShowAnalysisLayer] = useState(true);
  const [collectionVisibility, setCollectionVisibility] = useState<Record<STACCollectionKey, boolean>>({
    "sentinel-2": true,
    "sentinel-1": true,
    landsat: true,
  });
  const [isLegendCollapsed, setIsLegendCollapsed] = useState(false);
  const [dateFilter, setDateFilter] = useState<DateFilter>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const analysisLayerGroupRef = useRef<L.LayerGroup | null>(null);
  const catalogLayerGroupRef = useRef<L.LayerGroup | null>(null);

  // Fetch both analyses and catalog data in parallel with cancel support
  const fetchData = useCallback(() => {
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
      .catch((err) => {
        if (!cancelled) {
          console.error("Fetch data error:", err);
          setError("Failed to connect to SatQuery AI service.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const cancel = fetchData();
    return cancel;
  }, [fetchData]);

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

      L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
        maxZoom: 16,
        attribution: "Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ",
      }).addTo(map);

      // Separate layer groups for independent toggling
      const catLayer = L.layerGroup().addTo(map);
      const anaLayer = L.layerGroup().addTo(map);

      catalogLayerGroupRef.current = catLayer;
      analysisLayerGroupRef.current = anaLayer;
      mapInstanceRef.current = map;
    }
  }, []);

  // ── Derived filtered datasets ──────────────────────────────────────────────
  const filteredAnalyses = useMemo(() => {
    const cutoff = cutoffForFilter(dateFilter);
    const features = analysesData?.features ?? [];
    if (!cutoff) return features;
    return features.filter((f) => {
      const ts = f?.properties?.created_at;
      if (!ts) return false;
      try { return new Date(ts) >= cutoff; } catch { return false; }
    });
  }, [analysesData, dateFilter]);

  const filteredCatalog = useMemo(() => {
    const cutoff = cutoffForFilter(dateFilter);
    const features = catalogData?.features ?? [];
    if (!cutoff) return features;
    return features.filter((f) => {
      const ts = f?.properties?.datetime;
      if (!ts) return false;
      try { return new Date(ts) >= cutoff; } catch { return false; }
    });
  }, [catalogData, dateFilter]);

  // Per-collection counts across total and date-filtered views
  const collectionCounts = useMemo(() => {
    const counts: Record<STACCollectionKey, { total: number; visible: number }> = {
      "sentinel-2": { total: 0, visible: 0 },
      "sentinel-1": { total: 0, visible: 0 },
      landsat: { total: 0, visible: 0 },
    };

    (catalogData?.features ?? []).forEach((f) => {
      const key = getSTACCollectionKey(f?.properties?.collection);
      counts[key].total++;
    });

    filteredCatalog.forEach((f) => {
      const key = getSTACCollectionKey(f?.properties?.collection);
      counts[key].visible++;
    });

    return counts;
  }, [catalogData, filteredCatalog]);

  // Catalog features actively visible on map (filtered by date & collection visibility)
  const visibleCatalog = useMemo(() => {
    return filteredCatalog.filter((f) => {
      if (!f?.geometry) return false;
      const key = getSTACCollectionKey(f.properties?.collection);
      return collectionVisibility[key];
    });
  }, [filteredCatalog, collectionVisibility]);

  // Sync Analysis features layer
  useEffect(() => {
    const layer = analysisLayerGroupRef.current;
    if (!layer) return;

    layer.clearLayers();
    if (!showAnalysisLayer) return;

    // ── Point features ────────────────────────────────────────────────────────
    const mappablePoints = filteredAnalyses.filter(
      (f) => f?.geometry?.type === "Point",
    );
    mappablePoints.forEach((feature, idx) => {
      try {
        const coords = feature.geometry!.coordinates;
        if (Array.isArray(coords) && coords.length >= 2 && !isNaN(coords[0]) && !isNaN(coords[1])) {
          const [lng, lat] = coords as number[];
          const popupHtml = createAnalysisPopupHtml(feature);
          const marker = L.marker([lat, lng], { icon: analysisIcon })
            .bindPopup(popupHtml, { className: "leaflet-popup-dark", maxWidth: 340, closeButton: false });
          layer.addLayer(marker);
        }
      } catch (e) {
        console.warn(`Analysis point #${feature?.properties?.id ?? idx}:`, e);
      }
    });

    // ── Polygon features — render outlines first, then cluster centres ────────
    const polygonFeatures = filteredAnalyses.filter(
      (f) => f?.geometry?.type === "Polygon",
    );

    // Helper to compute centroid for a polygon analysis feature
    const getAnalysisCentroid = (f: typeof polygonFeatures[0]) => {
      const rings = f?.geometry?.coordinates;
      if (!Array.isArray(rings) || !Array.isArray(rings[0])) return null;
      const latLngs: L.LatLngTuple[] = [];
      for (const pt of rings[0]) {
        if (Array.isArray(pt) && pt.length >= 2 && !isNaN(pt[0]) && !isNaN(pt[1])) {
          latLngs.push([pt[1], pt[0]]);
        }
      }
      if (latLngs.length < 3) return null;
      return {
        lat: latLngs.reduce((s, p) => s + p[0], 0) / latLngs.length,
        lng: latLngs.reduce((s, p) => s + p[1], 0) / latLngs.length,
        latLngs,
      };
    };

    // Draw every polygon outline (individual, not affected by clustering)
    const analysisPolygons: L.Polygon[] = [];
    polygonFeatures.forEach((feature, idx) => {
      try {
        const c = getAnalysisCentroid(feature);
        if (!c) return;
        const popupHtml = createAnalysisPopupHtml(feature);
        const polygon = L.polygon(c.latLngs, {
          color: "#3b82f6",
          weight: 2,
          fillColor: "#1d4ed8",
          fillOpacity: 0.06,
          opacity: 0.85,
        }).bindPopup(popupHtml, { className: "leaflet-popup-dark", maxWidth: 340, closeButton: false });

        polygon.on("mouseover", () => {
          polygon.bringToFront();
          polygon.setStyle({
            weight: 3,
            fillOpacity: 0.28,
            opacity: 1,
          });
          analysisPolygons.forEach((other) => {
            if (other !== polygon) {
              other.setStyle({
                opacity: 0.4,
                fillOpacity: 0.02,
              });
            }
          });
        });

        polygon.on("mouseout", () => {
          analysisPolygons.forEach((p) => {
            p.setStyle({
              weight: 2,
              fillOpacity: 0.06,
              opacity: 0.85,
            });
          });
        });

        analysisPolygons.push(polygon);
        layer.addLayer(polygon);
      } catch (e) {
        console.warn(`Analysis polygon #${feature?.properties?.id ?? idx}:`, e);
      }
    });

    // Cluster centre markers
    const analysisClusters = clusterByProximity(
      polygonFeatures,
      (f) => {
        const c = getAnalysisCentroid(f);
        return c ? { lat: c.lat, lng: c.lng } : null;
      },
    );

    analysisClusters.forEach((group) => {
      if (group.items.length === 1) {
        // Single feature — use the regular diamond icon
        const popupHtml = createAnalysisPopupHtml(group.items[0]);
        const marker = L.marker([group.centLat, group.centLng], { icon: analysisPolygonIcon })
          .bindPopup(popupHtml, { className: "leaflet-popup-dark", maxWidth: 340, closeButton: false });
        layer.addLayer(marker);
      } else {
        // Multiple overlapping features — cluster badge
        const clusterPopupHtml = createClusterAnalysisPopupHtml(group.items);
        const marker = L.marker([group.centLat, group.centLng], {
          icon: makeClusterIcon(group.items.length, "#1d4ed8", "#bfdbfe"),
          zIndexOffset: 500,
        }).bindPopup(clusterPopupHtml, { className: "leaflet-popup-dark", maxWidth: 360, closeButton: false });
        layer.addLayer(marker);
      }
    });
  }, [filteredAnalyses, showAnalysisLayer]);

  // Sync STAC Catalog features layer (distinct per-collection styling)
  useEffect(() => {
    const layer = catalogLayerGroupRef.current;
    if (!layer) return;

    layer.clearLayers();
    if (visibleCatalog.length === 0) return;

    const scenes = visibleCatalog;

    // Helper to resolve per-collection colours
    const getCollectionColors = (collLower: string) => {
      if (collLower.includes("sentinel-1")) return { stroke: "#7e22ce", fill: "#6b21a8" };
      if (collLower.includes("landsat")) return { stroke: "#b45309", fill: "#92400e" };
      return { stroke: "#0d9488", fill: "#0f766e" }; // Sentinel-2 default teal
    };

    // Helper to compute centroid for a catalog polygon feature
    const getCatalogCentroid = (f: CatalogGeoJSONFeature) => {
      if (f?.geometry?.type !== "Polygon") return null;
      const rings = f.geometry.coordinates;
      if (!Array.isArray(rings) || !Array.isArray(rings[0])) return null;
      const latLngs: L.LatLngTuple[] = [];
      for (const pt of rings[0]) {
        if (Array.isArray(pt) && pt.length >= 2 && !isNaN(pt[0]) && !isNaN(pt[1])) {
          latLngs.push([pt[1], pt[0]]);
        }
      }
      if (latLngs.length < 3) return null;
      return {
        lat: latLngs.reduce((s, p) => s + p[0], 0) / latLngs.length,
        lng: latLngs.reduce((s, p) => s + p[1], 0) / latLngs.length,
        latLngs,
      };
    };

    // Draw all polygon outlines first
    const catalogPolygons: { polygon: L.Polygon; defaultStyle: L.PathOptions }[] = [];
    scenes.forEach((feature, idx) => {
      try {
        if (!feature?.geometry) return;
        const c = getCatalogCentroid(feature);
        if (!c) return;
        const collLower = (feature.properties?.collection || "").toLowerCase();
        const { stroke, fill } = getCollectionColors(collLower);
        const popupHtml = createCatalogPopupHtml(feature);
        const defaultStyle: L.PathOptions = {
          color: stroke,
          weight: 1.5,
          fillColor: fill,
          fillOpacity: 0.06,
          opacity: 0.8,
        };
        const polygon = L.polygon(c.latLngs, defaultStyle).bindPopup(popupHtml, {
          className: "leaflet-popup-dark",
          maxWidth: 340,
          closeButton: false,
        });

        polygon.on("mouseover", () => {
          polygon.bringToFront();
          polygon.setStyle({
            weight: 3,
            fillOpacity: 0.28,
            opacity: 1,
          });
          catalogPolygons.forEach(({ polygon: other, defaultStyle: otherStyle }) => {
            if (other !== polygon) {
              other.setStyle({
                opacity: 0.35,
                fillOpacity: 0.02,
              });
            }
          });
        });

        polygon.on("mouseout", () => {
          catalogPolygons.forEach(({ polygon: p, defaultStyle: orig }) => {
            p.setStyle(orig);
          });
        });

        catalogPolygons.push({ polygon, defaultStyle });
        layer.addLayer(polygon);
      } catch (e) {
        console.warn(`Catalog polygon #${idx}:`, e);
      }
    });

    // Cluster centre markers
    const catalogClusters = clusterByProximity(
      scenes.filter((f) => f?.geometry?.type === "Polygon"),
      (f) => {
        const c = getCatalogCentroid(f);
        return c ? { lat: c.lat, lng: c.lng } : null;
      },
    );

    catalogClusters.forEach((group) => {
      if (group.items.length === 1) {
        const item = group.items[0];
        const collLower = (item.properties?.collection || "").toLowerCase();
        const { stroke } = getCollectionColors(collLower);
        const icon = getCatalogMarkerIcon(stroke);
        const popupHtml = createCatalogPopupHtml(item);
        const marker = L.marker([group.centLat, group.centLng], { icon })
          .bindPopup(popupHtml, { className: "leaflet-popup-dark", maxWidth: 340, closeButton: false });
        layer.addLayer(marker);
      } else {
        // Mix of collections — pick dominant colour
        const colCounts: Record<string, number> = {};
        group.items.forEach((f) => {
          const c = (f.properties?.collection || "other").toLowerCase();
          colCounts[c] = (colCounts[c] || 0) + 1;
        });
        const dominant = Object.entries(colCounts).sort((a, b) => b[1] - a[1])[0][0];
        const { stroke } = getCollectionColors(dominant);

        const clusterPopupHtml = createClusterCatalogPopupHtml(group.items);
        const marker = L.marker([group.centLat, group.centLng], {
          icon: makeClusterIcon(group.items.length, stroke, "#ffffff"),
          zIndexOffset: 500,
        }).bindPopup(clusterPopupHtml, { className: "leaflet-popup-dark", maxWidth: 360, closeButton: false });
        layer.addLayer(marker);
      }
    });
  }, [visibleCatalog]);

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

  // Visible counts after date filter
  const visibleAnalysisCount = filteredAnalyses.filter((f) => f?.geometry !== null).length;
  const visibleCatalogCount = visibleCatalog.length;

  return (
    <div
      className="min-h-screen pt-16 flex flex-col"
      style={{ background: "hsl(0 0% 4%)" }}
    >
      {/* ── Header ── */}
      <div className="px-4 sm:px-6 pt-8 sm:pt-10 pb-4 max-w-[1400px] mx-auto w-full">
        <div className="flex items-center justify-between flex-wrap gap-4 mb-2">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10 border border-primary/20 shrink-0">
              <MapIcon className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-foreground tracking-tight flex items-center gap-2">
                Orbital Pulse Map &amp; STAC Catalog
              </h1>
              <p className="text-xs text-muted-foreground mt-0.5">
                Geospatial view of persisted analyses and live multi-collection STAC scene ingestion
              </p>
            </div>
          </div>

          {/* Layer toggles bar */}
          <div className="flex items-center flex-wrap gap-2 text-xs">
            {/* Analyses toggle pill */}
            <button
              type="button"
              onClick={() => setShowAnalysisLayer(!showAnalysisLayer)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-xs font-medium transition-all select-none",
                showAnalysisLayer
                  ? "bg-blue-950/40 border-blue-600/70 text-blue-400 shadow-[0_0_8px_rgba(59,130,246,0.2)]"
                  : "bg-zinc-950/80 border-zinc-800 text-zinc-500 hover:border-zinc-700 line-through"
              )}
            >
              <div className="w-2 h-2 rounded-full bg-blue-500 shrink-0" />
              <span>Analyses ({mappedAnalyses})</span>
              {showAnalysisLayer ? <Eye className="h-3 w-3 ml-0.5 text-blue-400/70" /> : <EyeOff className="h-3 w-3 ml-0.5 text-zinc-600" />}
            </button>

            {/* STAC Per-Collection Toggles */}
            {STAC_COLLECTIONS.map((col) => {
              const isVisible = collectionVisibility[col.key];
              const count = collectionCounts[col.key].visible;
              return (
                <button
                  key={col.key}
                  type="button"
                  onClick={() =>
                    setCollectionVisibility((prev) => ({
                      ...prev,
                      [col.key]: !prev[col.key],
                    }))
                  }
                  className={cn(
                    "flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-md border text-xs font-medium transition-all select-none",
                    isVisible
                      ? cn(col.badgeBg, col.badgeBorder, col.textColor)
                      : "bg-zinc-950/80 border-zinc-800 text-zinc-500 hover:border-zinc-700 line-through"
                  )}
                >
                  <div className={cn("w-2 h-2 rounded-full shrink-0", col.swatchClass)} />
                  <span>{col.label} ({count})</span>
                  {isVisible ? <Eye className="h-3 w-3 ml-0.5 opacity-70" /> : <EyeOff className="h-3 w-3 ml-0.5 text-zinc-600" />}
                </button>
              );
            })}
          </div>
        </div>

        {/* Stats row: 4 responsive cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-4">
          <StatCard
            icon={Layers}
            label="Persisted analyses"
            value={totalAnalyses}
            loading={loading}
            colorClass="text-blue-400"
            badgeClass="bg-blue-950/60 border-blue-800/60 text-blue-400"
          />
          <StatCard
            icon={Crosshair}
            label="Mapped analyses"
            value={mappedAnalyses}
            loading={loading}
            colorClass="text-sky-400"
            badgeClass="bg-sky-950/60 border-sky-800/60 text-sky-400"
          />
          <StatCard
            icon={Satellite}
            label="Catalogued STAC scenes"
            value={totalCatalogScenes}
            loading={loading}
            colorClass="text-teal-400"
            badgeClass="bg-teal-950/60 border-teal-800/60 text-teal-400"
          />
          <StatCard
            icon={AlertCircle}
            label="No geom"
            value={withoutGeomAnalyses}
            loading={loading}
            colorClass={withoutGeomAnalyses > 0 ? "text-amber-400" : "text-emerald-400"}
            badgeClass={
              withoutGeomAnalyses > 0
                ? "bg-amber-950/60 border-amber-800/60 text-amber-400"
                : "bg-emerald-950/50 border-emerald-800/50 text-emerald-400"
            }
          />
        </div>

        {/* ── Date-range filter bar ── */}
        <div className="flex items-center gap-2.5 sm:gap-3 mt-4 sm:mt-5 flex-wrap text-xs">
          <div className="flex items-center gap-1.5 text-muted-foreground shrink-0">
            <CalendarDays className="h-3.5 w-3.5" />
            <span className="uppercase tracking-wider font-medium text-[11px]">Showing</span>
          </div>
          <div className="flex items-center gap-1.5 flex-wrap">
            {(["24h", "7d", "30d", "all"] as DateFilter[]).map((f) => (
              <button
                key={f}
                onClick={() => setDateFilter(f)}
                className={cn(
                  "px-2.5 sm:px-3 py-1 rounded-md text-xs font-medium border transition-all duration-150",
                  dateFilter === f
                    ? "bg-primary/20 border-primary/60 text-primary shadow-[0_0_8px_rgba(99,131,193,0.3)]"
                    : "bg-zinc-900 border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200",
                )}
              >
                {DATE_FILTER_LABELS[f]}
              </button>
            ))}
          </div>
          {dateFilter !== "all" && (
            <span className="text-xs text-muted-foreground w-full sm:w-auto mt-1 sm:mt-0">
              — showing{" "}
              <span className="text-blue-400 font-medium">{visibleAnalysisCount}</span> analyses
              {" "}&amp;{" "}
              <span className="text-teal-400 font-medium">{visibleCatalogCount}</span> STAC scenes
            </span>
          )}
        </div>
      </div>

      {/* ── Map area ── */}
      <div className="flex-1 px-4 sm:px-6 pb-6 sm:pb-8 max-w-[1400px] mx-auto w-full">
        <div
          className="relative rounded-xl overflow-hidden border border-border shadow-2xl"
          style={{ height: "calc(100vh - 340px)", minHeight: "440px" }}
        >
          {/* Loading state: Scanner Radar Skeleton */}
          {loading && (
            <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-zinc-950/85 backdrop-blur-sm p-6 text-center">
              <div className="relative flex items-center justify-center mb-4">
                <div className="absolute w-20 h-20 rounded-full border border-primary/30 animate-ping opacity-30" />
                <div className="w-16 h-16 rounded-full border-2 border-primary/20 border-t-primary animate-spin" />
                <div className="absolute w-10 h-10 rounded-full bg-primary/10 border border-primary/40 flex items-center justify-center">
                  <Satellite className="h-5 w-5 text-primary" />
                </div>
              </div>
              <p className="text-sm font-medium text-foreground tracking-tight">Fetching Geospatial History &amp; STAC Catalog</p>
              <p className="text-xs text-muted-foreground mt-1 max-w-xs">
                Connecting to SatQuery AI engine and querying PostgreSQL/PostGIS spatial features…
              </p>
            </div>
          )}

          {/* Fetch Error state with working Retry button */}
          {error && !loading && totalAnalyses === 0 && (
            <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-zinc-950/95 backdrop-blur-md p-6 sm:p-8 text-center">
              <div className="w-12 h-12 rounded-full bg-destructive/20 border border-destructive/40 flex items-center justify-center mb-4">
                <AlertCircle className="h-6 w-6 text-destructive" />
              </div>
              <h2 className="text-base font-semibold text-foreground mb-1.5">Could not load analysis history</h2>
              <p className="text-xs text-muted-foreground text-center max-w-xs mb-2">{error}</p>
              <p className="text-xs text-muted-foreground/60 text-center max-w-xs mb-5">
                Make sure the SatQuery AI service is running and the database connection is healthy.
              </p>
              <button
                type="button"
                onClick={() => fetchData()}
                className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors shadow-lg active:scale-95"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                <span>Retry Connection</span>
              </button>
            </div>
          )}

          {/* Leaflet map DOM mount point */}
          <div
            ref={mapContainerRef}
            style={{ height: "100%", width: "100%", background: "#0a0a0a" }}
          />

          {/* Interactive Collapsible Layer Legend Overlay */}
          <div
            className={cn(
              "absolute top-3 right-3 z-[1000] rounded-xl border border-zinc-700/80 bg-zinc-950/95 backdrop-blur-md shadow-2xl transition-all duration-200",
              isLegendCollapsed ? "w-auto" : "w-[260px] sm:w-[280px] max-w-[calc(100%-24px)]"
            )}
          >
            {/* Legend Header with Collapse Toggle */}
            <div
              onClick={() => setIsLegendCollapsed(!isLegendCollapsed)}
              className="flex items-center justify-between gap-2 px-3.5 py-2.5 cursor-pointer select-none hover:bg-zinc-900/50 rounded-xl"
            >
              <div className="flex items-center gap-2">
                <Layers className="h-3.5 w-3.5 text-primary" />
                <span className="font-semibold text-[11px] text-zinc-300 uppercase tracking-wider">
                  Layers &amp; Legend
                </span>
              </div>
              <button
                type="button"
                className="p-0.5 text-zinc-400 hover:text-zinc-200 rounded transition-colors"
                aria-label={isLegendCollapsed ? "Expand legend" : "Collapse legend"}
              >
                {isLegendCollapsed ? (
                  <ChevronDown className="h-3.5 w-3.5" />
                ) : (
                  <ChevronUp className="h-3.5 w-3.5" />
                )}
              </button>
            </div>

            {/* Expanded Content */}
            {!isLegendCollapsed && (
              <div className="px-3.5 pb-3.5 pt-1 space-y-2 border-t border-zinc-800/80 text-[11px]">
                {/* Analyses layer row */}
                <div className="pt-1">
                  <label
                    htmlFor="layer-toggle-analyses"
                    className="flex items-center justify-between gap-2 cursor-pointer group py-1 select-none"
                  >
                    <div className="flex items-center gap-2.5">
                      <input
                        id="layer-toggle-analyses"
                        type="checkbox"
                        checked={showAnalysisLayer}
                        onChange={(e) => setShowAnalysisLayer(e.target.checked)}
                        className="h-3.5 w-3.5 rounded border-zinc-700 bg-zinc-900 text-blue-600 focus:ring-blue-500 focus:ring-offset-0 cursor-pointer"
                      />
                      <div className="w-2.5 h-2.5 rounded-full bg-blue-600 border border-white/80 shrink-0" />
                      <span className="text-zinc-200 font-medium group-hover:text-white transition-colors">
                        Analyses
                      </span>
                    </div>
                    <span className="font-mono text-[10px] text-zinc-400">
                      {mappedAnalyses}
                    </span>
                  </label>
                </div>

                <div className="h-px bg-zinc-800/80 my-1.5" />

                {/* STAC Collections sub-heading */}
                <div className="flex items-center justify-between text-[10px] font-semibold text-zinc-400 uppercase tracking-wider">
                  <span>STAC Collections</span>
                  <button
                    type="button"
                    onClick={() => {
                      const allOn = STAC_COLLECTIONS.every((c) => collectionVisibility[c.key]);
                      setCollectionVisibility({
                        "sentinel-2": !allOn,
                        "sentinel-1": !allOn,
                        landsat: !allOn,
                      });
                    }}
                    className="text-primary hover:text-primary/80 transition-colors lowercase font-mono text-[10px]"
                  >
                    {STAC_COLLECTIONS.every((c) => collectionVisibility[c.key]) ? "hide all" : "show all"}
                  </button>
                </div>

                {/* Individual STAC collections */}
                {STAC_COLLECTIONS.map((col) => {
                  const isChecked = collectionVisibility[col.key];
                  const count = collectionCounts[col.key].visible;
                  return (
                    <label
                      key={col.key}
                      htmlFor={`layer-toggle-${col.key}`}
                      className="flex items-center justify-between gap-2 cursor-pointer group py-1 select-none"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <input
                          id={`layer-toggle-${col.key}`}
                          type="checkbox"
                          checked={isChecked}
                          onChange={() =>
                            setCollectionVisibility((prev) => ({
                              ...prev,
                              [col.key]: !prev[col.key],
                            }))
                          }
                          className="h-3.5 w-3.5 rounded border-zinc-700 bg-zinc-900 text-teal-600 focus:ring-teal-500 focus:ring-offset-0 cursor-pointer shrink-0"
                        />
                        <div className={cn("w-2.5 h-2.5 rounded-full border border-white/80 shrink-0", col.swatchClass)} />
                        <div className="min-w-0">
                          <span className={cn("font-medium block leading-tight truncate transition-colors", isChecked ? "text-zinc-200 group-hover:text-white" : "text-zinc-500 line-through")}>
                            {col.label}
                          </span>
                          <span className="text-[9px] text-zinc-400 block leading-tight font-mono">
                            {col.subLabel}
                          </span>
                        </div>
                      </div>
                      <span className={cn("font-mono text-[10px] shrink-0", isChecked ? col.textColor : "text-zinc-600")}>
                        {count}
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          {/* Leaflet attribution overlay */}
          <div className="absolute bottom-2 right-2 z-10 text-[9px] text-zinc-400 bg-zinc-950/80 backdrop-blur-sm border border-zinc-800 px-2 py-0.5 rounded pointer-events-none">
            &copy; Esri &middot; DeLorme &middot; Earth Search STAC (AWS Element84)
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
  const [retryKey, setRetryKey] = useState(0);

  return (
    <MapErrorBoundary onReset={() => setRetryKey((k) => k + 1)}>
      <MapViewContent key={retryKey} />
    </MapErrorBoundary>
  );
}
