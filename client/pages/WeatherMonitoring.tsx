import { useCallback, useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  AlertTriangle,
  CheckCircle2,
  CloudLightning,
  ExternalLink,
  Info,
  Loader2,
  Lock,
  RefreshCw,
  Satellite,
  ShieldAlert,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { LIGHTNING_STATS } from "@shared/lightning-stats";

const AI_SERVICE_URL = import.meta.env.VITE_AI_SERVICE_URL || "http://localhost:8082";

type Severity = "info" | "warning" | "critical";
type AssessmentStatus =
  | "gate_closed"
  | "insufficient_data"
  | "no_elevated_risk"
  | "elevated"
  | "needs_reverification";

interface WeatherAlert {
  id: number;
  region_name: string;
  alert_type: string;
  severity: Severity;
  computed_metrics: Record<string, any> | null;
  timestamp: string;
  acknowledged: boolean;
}

interface Assessment {
  status: AssessmentStatus;
  risk: string | null;
  severity?: Severity;
  latest_rate_k_per_15min?: number;
  latest_step_minutes?: number;
  latest_after_time?: string;
  weak_growth_area_km2?: number;
  strong_growth_area_km2?: number;
  sustained_over_two_steps?: boolean;
  reverify?: string;
  frames_available?: number;
  error?: string;
  criteria?: { sources: string[]; weak_growth_k_per_15min: number; strong_growth_k_per_15min: number };
  disclaimer?: string;
}

interface RegionProperties {
  name: string;
  display_name: string;
  context: string | null;
  bbox: [number, number, number, number];
  latest_frame: {
    id: number;
    identifier: string;
    acquired_at: string;
    auto_checks_passed: boolean;
    stats: Record<string, number> | null;
  } | null;
  frames_24h: number;
  assessment: Assessment;
  open_alert_count: number;
  alerts: WeatherAlert[];
}

interface RegionFeature {
  type: "Feature";
  geometry: GeoJSON.Polygon;
  properties: RegionProperties;
}

interface Feed {
  source: string;
  dataset_id: string;
  credentials_configured: boolean;
  auth_disabled_reason: string | null;
  gate: { open: boolean; reason: string | null };
}

const SEVERITY_STYLE: Record<Severity, { chip: string; stroke: string }> = {
  info: { chip: "border-sky-400/30 bg-sky-400/10 text-sky-300", stroke: "#38bdf8" },
  warning: { chip: "border-amber-400/30 bg-amber-400/10 text-amber-300", stroke: "#fbbf24" },
  critical: { chip: "border-red-400/30 bg-red-400/10 text-red-400", stroke: "#f87171" },
};
const CLEAR_STROKE = "#34d399";
const IDLE_STROKE = "#71717a";

const fmtNum = (v: unknown, digits = 1) =>
  typeof v === "number" && Number.isFinite(v) ? v.toFixed(digits) : "—";
const fmtTime = (iso?: string | null) => (iso ? `${iso.replace("T", " ").slice(0, 16)} UTC` : "—");

const CHECK_LABEL: Record<string, string> = {
  storm_risk_check: "INSAT cloud-top cooling",
  severe_weather_check: "Optical cloud persistence",
};

function statusView(a: Assessment): { label: string; chip: string; stroke: string } {
  switch (a.status) {
    case "elevated":
      return { label: a.severity === "warning" ? "elevated · warning" : "elevated · info", ...SEVERITY_STYLE[a.severity ?? "info"] };
    case "needs_reverification":
      return { label: "re-verify data", ...SEVERITY_STYLE.info };
    case "no_elevated_risk":
      return { label: "no elevated risk", chip: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300", stroke: CLEAR_STROKE };
    case "gate_closed":
      return { label: "feed not verified", chip: "border-zinc-500/40 bg-zinc-500/10 text-zinc-300", stroke: IDLE_STROKE };
    default:
      return { label: "insufficient data", chip: "border-zinc-500/40 bg-zinc-500/10 text-zinc-300", stroke: IDLE_STROKE };
  }
}

function FeedBanner({ feed }: { feed: Feed | null }) {
  if (!feed) return null;
  if (feed.auth_disabled_reason) {
    return (
      <Banner tone="red" icon={<ShieldAlert className="h-4 w-4" />} title="MOSDAC login rejected.">
        {feed.auth_disabled_reason}
      </Banner>
    );
  }
  if (!feed.credentials_configured) {
    return (
      <Banner tone="amber" icon={<Lock className="h-4 w-4" />} title="INSAT feed not connected.">
        Track B reads real INSAT-3DR thermal-IR frames from MOSDAC (SAC-ISRO), which needs a MOSDAC account. Until
        MOSDAC_USERNAME and MOSDAC_PASSWORD are set, no frames are ingested and no convective risk is computed. Nothing
        on this page is simulated.
      </Banner>
    );
  }
  if (!feed.gate.open) {
    return (
      <Banner tone="amber" icon={<Lock className="h-4 w-4" />} title="Risk assessment locked.">
        {feed.gate.reason}
      </Banner>
    );
  }
  return null;
}

function Banner({
  tone,
  icon,
  title,
  children,
}: {
  tone: "amber" | "red";
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "mb-4 flex gap-2.5 rounded-md border px-3 py-2.5 text-sm",
        tone === "red" ? "border-red-400/30 bg-red-400/10 text-red-200" : "border-amber-400/30 bg-amber-400/[0.07] text-amber-100/90",
      )}
    >
      <span className={cn("mt-0.5 shrink-0", tone === "red" ? "text-red-300" : "text-amber-300")}>{icon}</span>
      <p>
        <span className="font-semibold">{title} </span>
        {children}
      </p>
    </div>
  );
}

function AssessmentPanel({ region }: { region: RegionProperties }) {
  const a = region.assessment;
  const s = region.latest_frame?.stats ?? null;
  return (
    <div className="rounded-lg border border-border bg-[#0E0E0E] p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className={cn("rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase", statusView(a).chip)}>
          {statusView(a).label}
        </span>
        {a.risk && <span className="text-sm font-medium">{a.risk}</span>}
      </div>

      {a.status === "needs_reverification" && a.reverify && (
        <p className="mb-3 rounded-md border border-sky-400/30 bg-sky-400/10 px-3 py-2 text-xs text-sky-200">{a.reverify}</p>
      )}

      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-3">
        <div>
          <dt className="text-muted-foreground">Cloud-top cooling (p10)</dt>
          <dd className="font-mono">{fmtNum(a.latest_rate_k_per_15min)} K / 15 min</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Area cooling ≤ −4 K / ≤ −8 K</dt>
          <dd className="font-mono">
            {fmtNum(a.weak_growth_area_km2, 0)} / {fmtNum(a.strong_growth_area_km2, 0)} km²
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Sustained over two steps</dt>
          <dd className="font-mono">{a.sustained_over_two_steps === undefined ? "—" : a.sustained_over_two_steps ? "yes" : "no"}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Latest frame</dt>
          <dd className="font-mono">{fmtTime(region.latest_frame?.acquired_at)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Coldest / mean BT</dt>
          <dd className="font-mono">
            {fmtNum(s?.bt_min_k)} / {fmtNum(s?.bt_mean_k)} K
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Cloud colder than 235 K</dt>
          <dd className="font-mono">{s ? `${fmtNum((s.cold_cloud_frac_lt235k ?? NaN) * 100)}%` : "—"}</dd>
        </div>
      </dl>

      {region.latest_frame && (
        <p className="mt-3 break-all font-mono text-[11px] text-muted-foreground">
          Source file: {region.latest_frame.identifier}
          {region.latest_frame.auto_checks_passed ? "" : " (failed provenance checks, excluded)"}
        </p>
      )}
      <p className="mt-3 flex gap-1.5 text-[11px] text-muted-foreground">
        <Info className="mt-0.5 h-3 w-3 shrink-0" />
        {a.disclaimer ??
          "Regional risk indicator from satellite cloud-top cooling. Not a lightning, hail or storm-location forecast."}{" "}
        Criteria: Roberts &amp; Rutledge (2003); Mecikalski &amp; Bedka (2006).
      </p>
    </div>
  );
}

function AlertLog({ alerts, onAck }: { alerts: WeatherAlert[]; onAck: (id: number) => void }) {
  if (alerts.length === 0) {
    return (
      <p className="rounded-lg border border-border bg-[#0E0E0E] p-4 text-sm text-muted-foreground">
        No severe-weather alerts on record.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full min-w-[640px] text-left text-xs">
        <thead className="bg-[#0E0E0E] text-muted-foreground">
          <tr>
            <th className="px-3 py-2 font-normal">Raised</th>
            <th className="px-3 py-2 font-normal">Region</th>
            <th className="px-3 py-2 font-normal">Severity</th>
            <th className="px-3 py-2 font-normal">Signal</th>
            <th className="px-3 py-2 font-normal">Detail</th>
            <th className="px-3 py-2 font-normal" />
          </tr>
        </thead>
        <tbody>
          {alerts.map((a) => {
            const m = a.computed_metrics ?? {};
            const detail =
              m.check === "storm_risk_check"
                ? `${m.risk ?? "—"} · ${fmtNum(m.latest_rate_k_per_15min)} K/15 min`
                : m.check === "severe_weather_check"
                  ? `${fmtNum(m.mean_cloud_cover_pct)}% mean cloud over ${m.scenes_evaluated ?? "?"} scenes`
                  : "—";
            return (
              <tr key={a.id} className={cn("border-t border-border", a.acknowledged && "opacity-50")}>
                <td className="whitespace-nowrap px-3 py-2 font-mono">{fmtTime(a.timestamp)}</td>
                <td className="px-3 py-2">{a.region_name.replace(/_/g, " ")}</td>
                <td className="px-3 py-2">
                  <span className={cn("rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase", SEVERITY_STYLE[a.severity].chip)}>
                    {a.severity}
                  </span>
                </td>
                <td className="px-3 py-2">{CHECK_LABEL[m.check] ?? m.check ?? "manual"}</td>
                <td className="px-3 py-2 text-muted-foreground">{detail}</td>
                <td className="px-3 py-2 text-right">
                  {a.acknowledged ? (
                    <span className="text-[11px] text-muted-foreground">acknowledged</span>
                  ) : (
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-[11px]" onClick={() => onAck(a.id)}>
                      Acknowledge
                    </Button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function LightningContext() {
  return (
    <section className="mt-8">
      <div className="mb-3 flex items-center gap-2">
        <CloudLightning className="h-4 w-4 text-accent" />
        <h2 className="text-base font-semibold">Why this region: published lightning statistics</h2>
      </div>
      <p className="mb-3 max-w-3xl text-xs text-muted-foreground">
        Every figure is taken directly from the linked source. Financial-year (SRC Odisha) and calendar-year (NCRB)
        counts cover different periods and are not combined.
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        {LIGHTNING_STATS.map((s) => (
          <div key={`${s.figure}-${s.region}`} className="rounded-lg border border-border bg-[#0E0E0E] p-3 text-xs">
            <p className="font-medium text-foreground">{s.figure}</p>
            <p className="text-muted-foreground">
              {s.region} · {s.period}
            </p>
            <a
              href={s.url}
              target="_blank"
              rel="noreferrer"
              className="mt-1.5 inline-flex items-center gap-1 text-accent hover:underline"
            >
              {s.publisher}, {s.source} ({s.location}) <ExternalLink className="h-3 w-3" />
            </a>
            {s.caveat && <p className="mt-1 text-[11px] text-amber-200/80">{s.caveat}</p>}
          </div>
        ))}
      </div>
    </section>
  );
}

export default function WeatherMonitoring() {
  const [regions, setRegions] = useState<RegionFeature[]>([]);
  const [feed, setFeed] = useState<Feed | null>(null);
  const [history, setHistory] = useState<WeatherAlert[]>([]);
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
      const [regionsRes, alertsRes] = await Promise.all([
        fetch(`${AI_SERVICE_URL}/api/weather-regions`),
        fetch(`${AI_SERVICE_URL}/api/alerts?alert_type=severe_weather&limit=100`),
      ]);
      if (!regionsRes.ok) throw new Error(`weather regions: HTTP ${regionsRes.status}`);
      if (!alertsRes.ok) throw new Error(`alerts: HTTP ${alertsRes.status}`);
      const data = await regionsRes.json();
      const alerts = await alertsRes.json();
      setRegions(data.features ?? []);
      setFeed(data.feed ?? null);
      setHistory((alerts.features ?? []).map((f: { properties: WeatherAlert }) => f.properties));
      setSelected((cur) => cur ?? data.features?.[0]?.properties.name ?? null);
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

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;
    const map = L.map(mapContainerRef.current, { center: [22.7, 85.9], zoom: 7, attributionControl: false });
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
      const p = f.properties;
      const poly = L.geoJSON(f.geometry as GeoJSON.GeoJsonObject, {
        style: {
          color: statusView(p.assessment).stroke,
          weight: p.name === selected ? 3 : 2,
          fillOpacity: p.name === selected ? 0.18 : 0.08,
        },
      });
      poly.bindTooltip(`${p.display_name}: ${statusView(p.assessment).label}`, { sticky: true });
      poly.on("click", () => setSelected(p.name));
      poly.addTo(layer);
      bounds.extend(poly.getBounds());
    }
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
              <CloudLightning className="h-5 w-5 shrink-0 text-accent" />
              <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">Weather Monitoring</h1>
            </div>
            <p className="max-w-2xl text-sm text-muted-foreground">
              Thunderstorm-prone regions of Odisha and Jharkhand, watched every 30 minutes with INSAT-3DR thermal-IR
              (TIR-1, 10.8 µm) from MOSDAC. Rapid cooling of cloud tops colder than 0 °C raises an elevated convective
              development risk flag.
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
        <FeedBanner feed={feed} />

        <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <div className="overflow-hidden rounded-xl border border-border">
            <div ref={mapContainerRef} className="h-[420px] w-full lg:h-[520px]" />
            <div className="flex flex-wrap items-center gap-4 border-t border-border bg-[#0E0E0E] px-3 py-2 text-[11px] text-muted-foreground">
              <span className="flex items-center gap-1.5"><span className="h-2 w-3 rounded-sm" style={{ background: IDLE_STROKE }} /> not assessed</span>
              <span className="flex items-center gap-1.5"><span className="h-2 w-3 rounded-sm" style={{ background: CLEAR_STROKE }} /> no elevated risk</span>
              <span className="flex items-center gap-1.5"><span className="h-2 w-3 rounded-sm" style={{ background: SEVERITY_STYLE.info.stroke }} /> elevated · info</span>
              <span className="flex items-center gap-1.5"><span className="h-2 w-3 rounded-sm" style={{ background: SEVERITY_STYLE.warning.stroke }} /> elevated · warning</span>
            </div>
          </div>

          <div className="space-y-3">
            {regions.map((f) => {
              const p = f.properties;
              const v = statusView(p.assessment);
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
                      {p.context && <p className="text-xs text-muted-foreground">{p.context}</p>}
                    </div>
                    <span className={cn("flex shrink-0 items-center gap-1 rounded border px-1.5 py-0.5 text-[11px]", v.chip)}>
                      {p.assessment.status === "elevated" ? <AlertTriangle className="h-3 w-3" /> : p.assessment.status === "no_elevated_risk" ? <CheckCircle2 className="h-3 w-3" /> : null}
                      {v.label}
                    </span>
                  </div>
                  <dl className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <dt className="text-muted-foreground">Latest INSAT frame</dt>
                      <dd className="font-mono">{fmtTime(p.latest_frame?.acquired_at)}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Frames (24 h)</dt>
                      <dd className="font-mono">{p.frames_24h}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Open alerts</dt>
                      <dd className="font-mono">{p.open_alert_count}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Cooling (p10)</dt>
                      <dd className="font-mono">{fmtNum(p.assessment.latest_rate_k_per_15min)} K/15 min</dd>
                    </div>
                  </dl>
                </button>
              );
            })}
          </div>
        </div>

        {active && (
          <section className="mt-6">
            <div className="mb-3 flex items-center gap-2">
              <Satellite className="h-4 w-4 text-accent" />
              <h2 className="text-base font-semibold">Current risk status: {active.display_name}</h2>
            </div>
            <AssessmentPanel region={active} />
          </section>
        )}

        <section className="mt-6">
          <div className="mb-3 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-accent" />
            <h2 className="text-base font-semibold">Historical alert log</h2>
          </div>
          <AlertLog alerts={history} onAck={acknowledge} />
        </section>

        <LightningContext />
      </div>
    </div>
  );
}
