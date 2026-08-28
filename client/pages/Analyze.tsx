import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { Play, Sparkles, Terminal, Activity, ArrowRightLeft, Radio, ScanSearch, AlertCircle, Upload, X, FileImage, Download, Target } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const AI_SERVICE_URL = import.meta.env.VITE_AI_SERVICE_URL || "http://localhost:8082";

type Modality = "optical" | "sar" | "both";
type Temporal = "single" | "bi-temporal";
type TaskHint = "auto" | "vqa" | "grounding" | "change" | "sar_fusion";
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

interface AnalyzeResponse {
  answer: string;
  confidence: number | null;
  visual_evidence: GroundingBox[] | {
    mask_url?: string | null;
    change_percentage?: number | null;
    bounding_boxes?: any[];
  } | null;
  execution_trace: ExecutionTrace;
}

export default function Analyze() {
  const [searchParams] = useSearchParams();
  const initialQuery = searchParams.get("query") || "Please detect and ground all major infrastructure, buildings, or structures in this aerial view.";

  const [query, setQuery] = useState(initialQuery);
  const [modality, setModality] = useState<Modality>("optical");
  const [temporal, setTemporal] = useState<Temporal>("single");
  const [taskHint, setTaskHint] = useState<TaskHint>("auto");
  const [scenarioId, setScenarioId] = useState<ScenarioId>("deforestation");
  const [comparisonPos, setComparisonPos] = useState(50);

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
  };

  const handleRunAnalysis = async () => {
    if (!query.trim()) return;
    setIsRunning(true);
    setError(null);
    setResult(null);

    try {
      let finalQuery = query.trim();
      if (taskHint === "grounding" && !finalQuery.toLowerCase().includes("where") && !finalQuery.toLowerCase().includes("detect") && !finalQuery.toLowerCase().includes("locate") && !finalQuery.toLowerCase().includes("ground")) {
        finalQuery = `Where are the ${finalQuery}? Locate and ground bounding boxes.`;
      }

      let response: Response;

      if (uploadedFiles.length > 0) {
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
        // Standard JSON request
        response = await fetch(`${AI_SERVICE_URL}/api/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: finalQuery,
            modality,
            temporal,
            scenario: temporal === "bi-temporal" ? scenarioId : undefined,
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

  const currentScenario = SCENARIOS[scenarioId];
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
                setQuery(preset.query);
                setModality(preset.modality);
                setTemporal(preset.temporal);
                setTaskHint(preset.taskHint);
                if (preset.scenario) setScenarioId(preset.scenario);
              }}
              className="text-xs px-3 py-1.5 rounded-md border border-border bg-card/60 hover:bg-card hover:border-primary/50 text-secondary-foreground transition-all duration-150"
            >
              {preset.label}
            </button>
          ))}
        </div>

        {/* Query Input Box, Selectors & File Upload Zone */}
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
                placeholder="Ask SatQuery AI a question about your satellite imagery (e.g. 'Where are the runway and building structures in this aerial view?')..."
                className="w-full rounded-lg border border-border bg-[#121212] px-4 py-3 text-body text-foreground placeholder:text-muted-foreground/60 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
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
                {temporal === "bi-temporal" && uploadedFiles.length === 0 && (
                  <div>
                    <span className="label-micro block mb-1 text-muted-foreground">Scenario Preset</span>
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

              {/* Upload Button Trigger & Submit CTA */}
              <div className="flex items-center gap-3">
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
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  className="border-border bg-[#121212] hover:border-primary text-xs"
                >
                  <Upload className="mr-1.5 h-3.5 w-3.5" />
                  Upload GeoTIFF / Image
                </Button>

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

            {/* Custom Uploaded Files Bar */}
            {uploadedFiles.length > 0 && (
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
            {uploadedFiles.length > 0 ? (
              <div className="relative min-h-[440px] rounded-xl border border-border bg-[#121212] overflow-hidden flex flex-col justify-center items-center p-4 shadow-xl">
                <div className="relative w-full h-[400px] flex items-center justify-center bg-black/60 rounded-lg overflow-hidden">
                  <img
                    src={filePreviewUrls[0]}
                    alt="User Uploaded Satellite Source"
                    className="max-h-full max-w-full object-contain"
                  />
                  {/* Render Bounding Boxes for Uploaded Image */}
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
            ) : temporal === "bi-temporal" ? (
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
              <div className="relative min-h-[440px] rounded-xl border border-border bg-[#121212] overflow-hidden flex flex-col justify-center items-center p-4 shadow-xl">
                <div className="relative w-full h-[400px] flex items-center justify-center bg-black/60 rounded-lg overflow-hidden">
                  <img
                    src="/hero-satellite.jpg"
                    alt="Optical Satellite Imagery"
                    className="w-full h-full object-cover filter brightness-90"
                  />
                  {/* Render Bounding Boxes Overlay on Default Canvas */}
                  {groundingBoxes.map((box, idx) => {
                    const [xmin, ymin, xmax, ymax] = box.box_normalized;
                    return (
                      <div
                        key={idx}
                        className="absolute border-2 border-red-500 bg-red-500/15 pointer-events-none transition-all"
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
                <div className="mt-3 text-caption text-muted-foreground text-center">
                  <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-accent">
                    <Radio className="h-3.5 w-3.5" /> {modality.toUpperCase()} SATELLITE CANVAS
                  </span>
                </div>
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
                  <div className="flex flex-col items-center justify-center h-36 space-y-3 text-muted-foreground">
                    <Activity className="h-6 w-6 animate-spin text-primary" />
                    <p className="text-xs font-mono">Routing task &amp; executing inference...</p>
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
