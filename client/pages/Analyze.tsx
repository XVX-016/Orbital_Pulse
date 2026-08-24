import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Play, Sparkles, Terminal, Activity, ArrowRightLeft, Radio, Layers, Bot, ScanSearch, CheckCircle2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const AI_SERVICE_URL = import.meta.env.VITE_AI_SERVICE_URL || "http://localhost:8082";

type Modality = "optical" | "sar" | "both";
type Temporal = "single" | "bi-temporal";
type ScenarioId = "deforestation" | "disaster";

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
    description: "Rondônia, Brazil — Sentinel-2 L2A Bi-Temporal Pair",
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
    query: "Identify forest canopy loss and calculate surface change percentage between before and after Sentinel-2 imagery",
    modality: "optical" as Modality,
    temporal: "bi-temporal" as Temporal,
    scenario: "deforestation" as ScenarioId,
  },
  {
    label: "SAR Flood Inundation",
    query: "Detect flood inundation boundaries and water body expansion using cloud-penetrating Sentinel-1 SAR imagery",
    modality: "sar" as Modality,
    temporal: "single" as Temporal,
  },
  {
    label: "Building Infrastructure Grounding",
    query: "Where are the primary building structures, transport nodes, and industrial facilities in this optical satellite image?",
    modality: "optical" as Modality,
    temporal: "single" as Temporal,
  },
  {
    label: "Optical–SAR Multimodal Fusion",
    query: "Fuse optical multi-spectral bands with synthetic aperture radar channels to describe land cover despite cloud cover",
    modality: "both" as Modality,
    temporal: "single" as Temporal,
  },
];

interface ExecutionTrace {
  task: string;
  specialist_used: string;
  parameters: Record<string, any>;
}

interface AnalyzeResponse {
  answer: string;
  confidence: number | null;
  visual_evidence: {
    mask_url?: string | null;
    change_percentage?: number | null;
    bounding_boxes?: any[];
    fusion_type?: string;
  } | null;
  execution_trace: ExecutionTrace;
}

export default function Analyze() {
  const [searchParams] = useSearchParams();
  const initialQuery = searchParams.get("query") || "Identify forest canopy loss and calculate surface change percentage between before and after Sentinel-2 imagery";

  const [query, setQuery] = useState(initialQuery);
  const [modality, setModality] = useState<Modality>("optical");
  const [temporal, setTemporal] = useState<Temporal>("bi-temporal");
  const [scenarioId, setScenarioId] = useState<ScenarioId>("deforestation");
  const [comparisonPos, setComparisonPos] = useState(50);

  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const q = searchParams.get("query");
    if (q) {
      setQuery(q);
    }
  }, [searchParams]);

  const handleRunAnalysis = async () => {
    if (!query.trim()) return;
    setIsRunning(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${AI_SERVICE_URL}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          modality,
          temporal,
          scenario: temporal === "bi-temporal" ? scenarioId : undefined,
        }),
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => null);
        throw new Error(errJson?.detail || `Service returned status ${response.status}`);
      }

      const data: AnalyzeResponse = await response.json();
      setResult(data);
    } catch (e: any) {
      console.error("Analysis query failed", e);
      setError(e.message || "Failed to reach SatQuery AI service. Please ensure the backend is running.");
    } finally {
      setIsRunning(false);
    }
  };

  const currentScenario = SCENARIOS[scenarioId];

  return (
    <div className="min-h-screen px-6 pb-24 pt-24 relative bg-background">
      {/* Background Ambient Glow */}
      <div className="absolute top-1/4 left-1/3 w-96 h-96 bg-primary/5 rounded-full blur-[140px] pointer-events-none" />

      <div className="mx-auto max-w-[1400px]">
        {/* Header Title */}
        <div className="mb-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 mb-3">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            <span className="label-micro !mb-0 text-primary font-semibold tracking-wider">
              AGENTIC MULTIMODAL VQA &amp; CHANGE ANALYSIS
            </span>
          </div>
          <h1 className="text-headline font-bold text-foreground tracking-tight text-3xl sm:text-4xl">
            SatQuery AI Workspace
          </h1>
          <p className="mt-2 text-body text-muted-foreground max-w-2xl">
            Submit natural-language queries against optical, SAR, or bi-temporal satellite imagery. Requests are dynamically routed to specialized models with auditable execution traces.
          </p>
        </div>

        {/* Preset Query Pills */}
        <div className="mb-6 flex flex-wrap items-center gap-2">
          <span className="label-micro text-muted-foreground mr-2">Sample Queries:</span>
          {PRESET_QUERIES.map((preset) => (
            <button
              key={preset.label}
              type="button"
              onClick={() => {
                setQuery(preset.query);
                setModality(preset.modality);
                setTemporal(preset.temporal);
                if (preset.scenario) setScenarioId(preset.scenario);
              }}
              className="text-xs px-3 py-1.5 rounded-md border border-border bg-card/60 hover:bg-card hover:border-primary/50 text-secondary-foreground transition-all duration-150"
            >
              {preset.label}
            </button>
          ))}
        </div>

        {/* Query Input Box & Selectors */}
        <div className="rounded-xl border border-border bg-card/80 p-6 shadow-xl backdrop-blur-md mb-8">
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
                placeholder="Ask SatQuery AI a question about your satellite imagery (e.g. 'Where are the flood zones in this Sentinel-1 image?')..."
                className="w-full rounded-lg border border-border bg-[#121212] px-4 py-3 text-body text-foreground placeholder:text-muted-foreground/60 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            {/* Modality & Temporal Controls */}
            <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-border/50">
              <div className="flex flex-wrap items-center gap-6">
                {/* Modality Selector */}
                <div>
                  <span className="label-micro block mb-1 text-muted-foreground">Modality</span>
                  <div className="flex bg-[#121212] p-1 rounded-md border border-border text-xs">
                    {(["optical", "sar", "both"] as Modality[]).map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => setModality(m)}
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
                        onClick={() => setTemporal(t)}
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
                    <span className="label-micro block mb-1 text-muted-foreground">Scenario Dataset</span>
                    <div className="flex bg-[#121212] p-1 rounded-md border border-border text-xs">
                      {(Object.keys(SCENARIOS) as ScenarioId[]).map((id) => (
                        <button
                          key={id}
                          type="button"
                          onClick={() => setScenarioId(id)}
                          className={cn(
                            "px-3 py-1 rounded font-medium capitalize transition-all",
                            scenarioId === id ? "bg-accent text-accent-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                          )}
                        >
                          {SCENARIOS[id].title}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <Button
                size="lg"
                disabled={isRunning || !query.trim()}
                onClick={handleRunAnalysis}
                className="shadow-lg hover:shadow-primary/20 min-w-[160px]"
              >
                <Play className={cn("mr-2 h-4 w-4", isRunning && "animate-spin")} />
                {isRunning ? "Routing & Executing..." : "Run SatQuery AI"}
              </Button>
            </div>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mb-8 rounded-lg bg-destructive/10 p-4 border border-destructive/20 text-destructive flex items-start gap-3">
            <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-sm">Analysis Error</p>
              <p className="text-xs mt-1 text-destructive/90">{error}</p>
            </div>
          </div>
        )}

        {/* Analysis Results Display */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Left Column: Visual Evidence / Split Viewer */}
          <div className="lg:col-span-7 space-y-6">
            {temporal === "bi-temporal" ? (
              <div className="relative min-h-[440px] overflow-hidden rounded-xl border border-border bg-card shadow-xl flex flex-col">
                <div className="absolute top-4 left-4 z-10 bg-background/85 backdrop-blur-md px-3.5 py-1.5 rounded-md text-xs font-medium border border-border/50">
                  {currentScenario.description}
                </div>

                <div className="relative flex-1 overflow-hidden group min-h-[380px]">
                  {/* After Image */}
                  <div
                    className="absolute inset-0 bg-cover bg-center bg-no-repeat"
                    style={{ backgroundImage: `url(${currentScenario.afterImage})` }}
                  />

                  {/* Before Image (Clipped) */}
                  <div
                    className="absolute inset-y-0 left-0 bg-cover bg-center bg-no-repeat border-r-2 border-primary"
                    style={{
                      width: `${comparisonPos}%`,
                      backgroundImage: `url(${currentScenario.beforeImage})`,
                    }}
                  />

                  {/* Slider Handle */}
                  <div
                    className="absolute inset-y-0 flex items-center justify-center w-8 -ml-4 pointer-events-none"
                    style={{ left: `${comparisonPos}%` }}
                  >
                    <div className="h-8 w-8 rounded-full bg-card border border-primary flex items-center justify-center shadow-lg text-primary">
                      <ArrowRightLeft className="h-3.5 w-3.5" />
                    </div>
                  </div>

                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={comparisonPos}
                    onChange={(e) => setComparisonPos(Number(e.target.value))}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-ew-resize z-20"
                    aria-label="Comparison slider"
                  />
                </div>

                <div className="h-12 border-t border-border flex items-center justify-between px-6 bg-card/90">
                  <span className="label-micro font-semibold text-muted-foreground">BEFORE</span>
                  <ScanSearch className="h-4 w-4 text-primary/60" />
                  <span className="label-micro font-semibold text-muted-foreground">AFTER</span>
                </div>
              </div>
            ) : (
              <div className="relative min-h-[440px] rounded-xl border border-border bg-[#121212] overflow-hidden flex flex-col justify-center items-center p-8 shadow-xl text-center">
                <img
                  src="/hero-satellite.jpg"
                  alt="Optical Satellite Imagery"
                  className="absolute inset-0 w-full h-full object-cover filter brightness-75"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-[#121212] via-[#121212]/40 to-transparent" />
                <div className="relative z-10 max-w-md">
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-accent/20 border border-accent/40 text-accent text-xs font-semibold mb-3">
                    <Radio className="h-3.5 w-3.5" /> {modality.toUpperCase()} SATELLITE CANVASES
                  </span>
                  <p className="text-caption text-muted-foreground">
                    Single-frame optical &amp; SAR imagery loaded for natural language question answering and visual grounding.
                  </p>
                </div>
              </div>
            )}

            {/* Generated Mask Output (if available) */}
            {result?.visual_evidence?.mask_url && (
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

          {/* Right Column: Model Answer & Auditable Execution Trace */}
          <div className="lg:col-span-5 space-y-6">
            {/* Model Response Card */}
            <div className="rounded-xl border border-border bg-card p-6 shadow-xl relative overflow-hidden">
              <div className="flex items-center justify-between border-b border-border/60 pb-4 mb-4">
                <span className="label-micro text-muted-foreground flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-primary" /> MODEL ANSWER
                </span>
                <span className="text-xs font-medium px-2.5 py-0.5 rounded bg-primary/10 border border-primary/20 text-primary">
                  {result ? "Complete" : "Ready"}
                </span>
              </div>

              <div className="min-h-[140px]">
                {isRunning ? (
                  <div className="flex flex-col items-center justify-center h-36 space-y-3 text-muted-foreground">
                    <Activity className="h-6 w-6 animate-spin text-primary" />
                    <p className="text-xs">Classifying query &amp; delegating specialist...</p>
                  </div>
                ) : result ? (
                  <div className="space-y-4">
                    <p className="text-body text-foreground leading-relaxed font-medium">
                      {result.answer}
                    </p>

                    {Array.isArray(result.visual_evidence) && result.visual_evidence.length > 0 && (
                      <div className="pt-3 border-t border-border/40 space-y-2">
                        <span className="label-micro text-muted-foreground block">Visual Evidence (Grounding Bounding Boxes)</span>
                        <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                          {result.visual_evidence.map((item: any, idx: number) => (
                            <div key={idx} className="flex items-center justify-between p-2 rounded bg-[#141414] border border-border/50 text-xs">
                              <span className="font-medium text-foreground truncate max-w-[200px]">{item.label}</span>
                              <span className="font-mono text-primary text-[11px]">
                                box: [{item.box_normalized.join(", ")}]
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {result.visual_evidence?.change_percentage !== undefined && result.visual_evidence?.change_percentage !== null && (
                      <div className="pt-3 border-t border-border/40 flex items-center justify-between">
                        <span className="label-micro text-muted-foreground">Detected Surface Change</span>
                        <span className="font-mono text-lg font-bold text-primary">
                          {result.visual_evidence.change_percentage}%
                        </span>
                      </div>
                    )}

                    <div className="pt-2 border-t border-border/40 flex items-center justify-between text-xs text-muted-foreground">
                      <span>Confidence Score</span>
                      <span className="font-mono text-foreground font-semibold">
                        {result.confidence !== null && result.confidence !== undefined
                          ? `${(result.confidence * 100).toFixed(1)}%`
                          : "N/A"}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-36 text-center text-muted-foreground">
                    <Bot className="h-8 w-8 mb-2 text-muted-foreground/40" />
                    <p className="text-xs">Enter a prompt above and click "Run SatQuery AI" to execute analysis.</p>
                  </div>
                )}
              </div>
            </div>

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
