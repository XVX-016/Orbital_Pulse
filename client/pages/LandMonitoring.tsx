import { useCallback, useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  AlertTriangle,
  CheckCircle2,
  Info,
  Loader2,
  Mountain,
  RefreshCw,
  Satellite,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const AI_SERVICE_URL = import.meta.env.VITE_AI_SERVICE_URL || "http://localhost:8082";

type Severity = "info" | "warning" | "critical";

interface SceneSummary {
  scene_id: string;
  datetime: string;
  cloud_cover: number | null;
  thumbnail_url: string | null;
}

interface RegionAlert {
  id: number;
  region_name: string;
  alert_type: string;
  severity: Severity;
  computed_metrics: Record<string, any> | null;
  timestamp: string;
  acknowledged: boolean;
}

interface RegionProperties {
  name: string;
  display_name: string;
  commodity: string | null;
  bbox: [number, number, number, number];
  monitored: boolean;
  boundary_is_approximate: boolean;
  boundary_caveat: string | null;
  boundary_source: string | null;
  scene_count: number;
  clear_scene_count: number;
  latest_scene: SceneSummary | null;
  latest_clear_scene: SceneSummary | null;
  open_alert_count: number;
  alerts: RegionAlert[];
}

interface RegionFeature {
  type: "Feature";
  geometry: GeoJSON.Polygon | null;
  properties: RegionProperties;
}

const SEVERITY_STYLE: Record<Severity, { text: string; chip: string; stroke: string }> = {
  info: { text: "text-sky-300", chip: "border-sky-400/30 bg-sky-400/10 text-sky-300", stroke: "#38bdf8" },
  warning: { text: "text-amber-300", chip: "border-amber-400/30 bg-amber-400/10 text-amber-300", stroke: "#fbbf24" },
  critical: { text: "text-red-400", chip: "border-red-400/30 bg-red-400/10 text-red-400", stroke: "#f87171" },
};
const CLEAR_STROKE = "#34d399";

const fmtDate = (iso?: string | null) => (iso ? iso.slice(0, 10) : "—");
const fmtNum = (v: unknown, digits = 2) =>
  typeof v === "number" && Number.isFinite(v) ? v.toFixed(digits) : "—";

/** Highest severity among a region's unacknowledged alerts, or null when clear. */
const SEVERITY_RANK: Severity[] = ["info", "warning", "critical"];

function openSeverity(region: RegionProperties): Severity | null {
  let best = -1;
  for (const a of region.alerts) {
    if (!a.acknowledged) best = Math.max(best, SEVERITY_RANK.indexOf(a.severity));
  }
  return best >= 0 ? SEVERITY_RANK[best] : null;
}

/** Region with the most severe open alert (first region on ties or when all are clear). */
function mostUrgentRegion(features: RegionFeature[]): string | null {
  let best: RegionFeature | null = null;
  let bestRank = -2;
  for (const f of features) {
    const sev = openSeverity(f.properties);
    const r = sev ? SEVERITY_RANK.indexOf(sev) : -1;
    if (r > bestRank) {
      best = f;
      bestRank = r;
    }
  }
  return best?.properties.name ?? null;
}

/** Always-visible provenance caveat for an approximate boundary. */
function BoundaryCaveat({ region, compact = false }: { region: RegionProperties; compact?: boolean }) {
  if (!region.boundary_is_approximate) return null;
  return (
    <div
      className={cn(
        "flex gap-2 rounded-md border border-amber-400/30 bg-amber-400/[0.07] text-amber-200/90",
        compact ? "px-2 py-1.5 text-[11px]" : "px-3 py-2 text-xs",
      )}
    >
      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-300" />
      <p>
        <span className="font-semibold text-amber-300">Approximate boundary. </span>
        {region.boundary_caveat}
      </p>
    </div>
  );
}

function AlertRow({ alert, onAck }: { alert: RegionAlert; onAck: (id: number) => void }) {
  const m = alert.computed_metrics ?? {};
  const triggers = m.triggers ? Object.entries(m.triggers).filter(([, v]) => v).map(([k]) => k) : [];
  const isMining = m.check === "mining_expansion_check";

  return (
    <div className={cn("rounded-lg border border-border bg-[#0E0E0E] p-3", alert.acknowledged && "opacity-50")}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className={cn("rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase", SEVERITY_STYLE[alert.severity].chip)}>
          {alert.severity}
        </span>
        <span className="font-mono text-[11px] text-muted-foreground">#{alert.id}</span>
        <span className="font-mono text-[11px] text-muted-foreground">{alert.timestamp.replace("T", " ").slice(0, 16)} UTC</span>
        {alert.acknowledged ? (
          <span className="ml-auto text-[11px] text-muted-foreground">acknowledged</span>
        ) : (
          <Button variant="ghost" size="sm" className="ml-auto h-6 px-2 text-[11px]" onClick={() => onAck(alert.id)}>
            Acknowledge
          </Button>
        )}
      </div>

      {isMining ? (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-3">
          <div>
            <dt className="text-muted-foreground">Scene pair</dt>
            <dd className="font-mono">{m.before_date} → {m.after_date}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">New bare ground inside boundary</dt>
            <dd className="font-mono">{fmtNum(m.expansion_inside_boundary_km2, 3)} km²*</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Of new bare ground, outside boundary</dt>
            <dd className="font-mono">{fmtNum(m.newly_bare_outside_boundary_pct, 1)}%*</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Bare share (whole search area)</dt>
            <dd className="font-mono">
              {fmtNum(m.bare_ground_pct_before, 2)}% → {fmtNum(m.bare_ground_pct_after, 2)}%
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Cloud cover</dt>
            <dd className="font-mono">
              {fmtNum(m.before_cloud_cover_pct, 1)}% / {fmtNum(m.after_cloud_cover_pct, 1)}%
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Triggered by</dt>
            <dd className="font-mono">{triggers.length ? triggers.join(", ") : "—"}</dd>
          </div>
        </dl>
      ) : (
        <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-[11px] text-muted-foreground">
          {JSON.stringify(m, null, 2)}
        </pre>
      )}
      {isMining && (
        <p className="mt-2 text-[11px] text-muted-foreground">
          * Measured against an approximate boundary: indicative only. Seasonal change in crops and vegetation can also
          register as new bare ground.
        </p>
      )}
    </div>
  );
}

export default function LandMonitoring() {
  const [regions, setRegions] = useState<RegionFeature[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const fittedRef = useRef(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${AI_SERVICE_URL}/api/monitored-regions`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setRegions(data.features ?? []);
      setSelected((cur) => cur ?? mostUrgentRegion(data.features ?? []));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const acknowledge = async (id: number) => {
    try {
      const res = await fetch(`${AI_SERVICE_URL}/api/alerts/${id}/acknowledge`, { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await load();
    } catch (e) {
      setError(`Could not acknowledge alert #${id}: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  // Map is created once; region layers are redrawn whenever data changes.
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;
    const map = L.map(mapContainerRef.current, { center: [22.8, 85.9], zoom: 8, attributionControl: false });
    L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
      maxZoom: 17,
    }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
      fittedRef.current = false;
    };
  }, []);

  useEffect(() => {
    const layer = layerRef.current;
    const map = mapRef.current;
    if (!layer || !map) return;
    layer.clearLayers();

    const bounds = L.latLngBounds([]);
    for (const f of regions) {
      if (!f.geometry) continue;
      const p = f.properties;
      const sev = openSeverity(p);
      const color = sev ? SEVERITY_STYLE[sev].stroke : CLEAR_STROKE;
      const poly = L.geoJSON(f.geometry as GeoJSON.GeoJsonObject, {
        style: {
          color,
          weight: p.name === selected ? 3 : 2,
          // Dashed outline marks the boundary as approximate on the map itself.
          dashArray: p.boundary_is_approximate ? "6 5" : undefined,
          fillOpacity: p.name === selected ? 0.18 : 0.08,
        },
      });
      poly.bindTooltip(
        `${p.display_name}${p.boundary_is_approximate ? " (approximate boundary)" : ""}`,
        { sticky: true },
      );
      poly.on("click", () => setSelected(p.name));
      poly.addTo(layer);
      bounds.extend(poly.getBounds());
    }
    // Frame the regions once on first load; afterwards leave the user's pan/zoom alone.
    if (bounds.isValid() && !fittedRef.current) {
      map.fitBounds(bounds, { padding: [40, 40], animate: false });
      fittedRef.current = true;
    }
  }, [regions, selected]);

  const active = regions.find((f) => f.properties.name === selected)?.properties ?? null;

  return (
    <div className="min-h-screen bg-background px-4 pb-16 pt-24 text-foreground sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="mb-2 flex items-center gap-2.5">
              <Mountain className="h-5 w-5 shrink-0 text-accent" />
              <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">Land Monitoring</h1>
            </div>
            <p className="max-w-2xl text-sm text-muted-foreground">
              Mining regions under continuous watch. Each STAC poll cycle compares the two clearest well-separated
              Sentinel-2 scenes and raises an alert when bare-ground or excavation expansion crosses its threshold.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            {loading ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="mr-1.5 h-3.5 w-3.5" />}
            Refresh
          </Button>
        </div>

        {error && (
          <div className="mb-4 rounded-md border border-red-400/30 bg-red-400/10 px-3 py-2 text-sm text-red-300">
            Could not reach the monitoring service: {error}
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <div className="overflow-hidden rounded-xl border border-border">
            <div ref={mapContainerRef} className="h-[420px] w-full lg:h-[560px]" />
            <div className="flex flex-wrap items-center gap-4 border-t border-border bg-[#0E0E0E] px-3 py-2 text-[11px] text-muted-foreground">
              <span className="flex items-center gap-1.5"><span className="h-2 w-3 rounded-sm" style={{ background: CLEAR_STROKE }} /> no open alerts</span>
              <span className="flex items-center gap-1.5"><span className="h-2 w-3 rounded-sm" style={{ background: SEVERITY_STYLE.info.stroke }} /> info</span>
              <span className="flex items-center gap-1.5"><span className="h-2 w-3 rounded-sm" style={{ background: SEVERITY_STYLE.warning.stroke }} /> warning</span>
              <span className="flex items-center gap-1.5"><span className="h-2 w-3 rounded-sm" style={{ background: SEVERITY_STYLE.critical.stroke }} /> critical</span>
              <span>dashed outline = approximate boundary</span>
            </div>
          </div>

          <div className="space-y-3">
            {regions.map((f) => {
              const p = f.properties;
              const sev = openSeverity(p);
              return (
                <button
                  key={p.name}
                  onClick={() => setSelected(p.name)}
                  className={cn(
                    "w-full rounded-xl border bg-[#0E0E0E] p-4 text-left transition-colors",
                    p.name === selected ? "border-accent" : "border-border hover:border-white/20",
                  )}
                >
                  <div className="mb-2 flex items-start justify-between gap-2">
                    <div>
                      <p className="font-medium">{p.display_name}</p>
                      <p className="text-xs capitalize text-muted-foreground">{(p.commodity ?? "").replace("_", " ")}</p>
                    </div>
                    {sev ? (
                      <span className={cn("flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px]", SEVERITY_STYLE[sev].chip)}>
                        <AlertTriangle className="h-3 w-3" /> {p.open_alert_count} open
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 rounded border border-emerald-400/30 bg-emerald-400/10 px-1.5 py-0.5 text-[11px] text-emerald-300">
                        <CheckCircle2 className="h-3 w-3" /> clear
                      </span>
                    )}
                  </div>
                  <dl className="mb-3 grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <dt className="text-muted-foreground">Latest scene</dt>
                      <dd className="font-mono">
                        {fmtDate(p.latest_scene?.datetime)} · {fmtNum(p.latest_scene?.cloud_cover, 0)}% cloud
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Latest clear scene</dt>
                      <dd className="font-mono">{fmtDate(p.latest_clear_scene?.datetime)}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Scenes (365 d)</dt>
                      <dd className="font-mono">{p.scene_count} ({p.clear_scene_count} clear)</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Alerts on record</dt>
                      <dd className="font-mono">{p.alerts.length}</dd>
                    </div>
                  </dl>
                  <BoundaryCaveat region={p} compact />
                </button>
              );
            })}
            {!loading && regions.length === 0 && !error && (
              <p className="rounded-xl border border-border bg-[#0E0E0E] p-6 text-center text-sm text-muted-foreground">
                No monitored regions configured.
              </p>
            )}
          </div>
        </div>

        {active && (
          <section className="mt-6">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <Satellite className="h-4 w-4 text-accent" />
              <h2 className="text-base font-semibold">Triggered alerts: {active.display_name}</h2>
            </div>
            <div className="mb-3">
              <BoundaryCaveat region={active} />
              {active.boundary_source && (
                <p className="mt-1.5 flex gap-1.5 text-[11px] text-muted-foreground">
                  <Info className="mt-0.5 h-3 w-3 shrink-0" /> Source: {active.boundary_source}
                </p>
              )}
            </div>
            {active.alerts.length === 0 ? (
              <p className="rounded-lg border border-border bg-[#0E0E0E] p-4 text-sm text-muted-foreground">
                No land-change alerts raised for this region yet.
              </p>
            ) : (
              <div className="space-y-2">
                {active.alerts.map((a) => (
                  <AlertRow key={a.id} alert={a} onAck={acknowledge} />
                ))}
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
