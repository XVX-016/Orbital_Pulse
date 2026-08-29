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
  const [loadingStage, setLoadingStage] = useState<number>(1);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<{ title: string; message: string } | null>(null);

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

  // Animate loading stages while inference is in flight
  useEffect(() => {
    let timer1: NodeJS.Timeout;
    let timer2: NodeJS.Timeout;
    if (isRunning) {
      setLoadingStage(1);
      timer1 = setTimeout(() => setLoadingStage(2), 1800);
      timer2 = setTimeout(() => setLoadingStage(3), 4200);
    }
    return () => {
      clearTimeout(timer1);
      clearTimeout(timer2);
    };
  }, [isRunning]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const filesArr = Array.from(e.target.files);
      const validExtensions = ["tif", "tiff", "png", "jpg", "jpeg", "webp"];
      const validFiles: File[] = [];
      const invalidFiles: string[] = [];

      for (const file of filesArr) {
        const ext = file.name.split(".").pop()?.toLowerCase();
        if (ext && validExtensions.includes(ext)) {
          validFiles.push(file);
        } else {
          invalidFiles.push(file.name);
        }
      }

      if (invalidFiles.length > 0) {
        setError({
          title: "Unsupported File Format",
          message: `The file(s) "${invalidFiles.join(", ")}" are not supported. Please upload GeoTIFF (.tif, .tiff) or standard satellite imagery (.png, .jpg, .jpeg).`,
        });
      } else {
        setError(null);
      }

      if (validFiles.length > 0) {
        setUploadedFiles((prev) => [...prev, ...validFiles].slice(0, 4));
      }
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

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 45000);

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
          signal: controller.signal,
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
          signal: controller.signal,
        });
      }

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errJson = await response.json().catch(() => null);
        throw new Error(errJson?.detail || `Service returned HTTP ${response.status} (${response.statusText})`);
      }

      const data: AnalyzeResponse = await response.json();
      setResult(data);
    } catch (e: any) {
      clearTimeout(timeoutId);
      console.error("Analysis query failed", e);
      if (e.name === "AbortError") {
        setError({
          title: "Inference Request Timeout",
          message: "The analysis request timed out after 45 seconds. GeoChat-7B vision-language inference requires active GPU compute or the service may be initializing. Please check the backend service.",
        });
      } else if (e.message?.includes("Failed to fetch") || e.message?.includes("NetworkError")) {
        setError({
          title: "Backend Service Unreachable",
          message: `Unable to connect to SatQuery AI backend at ${AI_SERVICE_URL}. Please ensure the satquery-service FastAPI server is running.`,
        });
      } else {
        setError({
          title: "Backend API Response Error",
          message: e.message || "Failed to reach SatQuery AI service. Please verify backend state.",
        });
      }
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
        <div className="mb-6 flex flex-wrap items-center gap-2" role="region" aria-label="Preset Query Workflows">
          <span className="label-micro text-muted-foreground mr-2 shrink-0">Preset Workflows:</span>
          <div className="flex flex-wrap items-center gap-2">
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
                className="text-xs px-3 py-1.5 rounded-md border border-border bg-card/60 hover:bg-card hover:border-primary/50 text-secondary-foreground transition-all duration-150 focus:outline-none focus:ring-1 focus:ring-primary"
                aria-label={`Load preset workflow: ${preset.label}`}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>

        {/* Query Input Box, Selectors & File Upload Zone */}
        <div className="rounded-xl border border-border bg-card/80 p-4 sm:p-6 shadow-xl backdrop-blur-md mb-8">
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
                className="w-full rounded-lg border border-border bg-[#121212] px-4 py-3 text-body text-foreground placeholder:text-muted-foreground/60 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary text-sm sm:text-base"
                aria-label="Natural language satellite query prompt"
              />
            </div>

            {/* Task Specialist & Input Controls */}
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pt-2 border-t border-border/50">
              <div className="grid grid-cols-1 sm:grid-cols-2 md:flex md:flex-wrap items-start md:items-center gap-4 sm:gap-6">
                {/* Task Type Hint */}
                <div className="w-full sm:w-auto">
                  <span className="label-micro block mb-1 text-muted-foreground">Task Specialist</span>
                  <div 
                    className="flex bg-[#121212] p-1 rounded-md border border-border text-xs overflow-x-auto max-w-full"
                    role="radiogroup" 
                    aria-label="Task Specialist Classifier Selection"
                  >
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
                        role="radio"
                        aria-checked={taskHint === t.id}
                        onClick={() => setTaskHint(t.id)}
                        className={cn(
                          "px-2.5 py-1 rounded font-medium whitespace-nowrap transition-all focus:outline-none focus:ring-1 focus:ring-primary",
                          taskHint === t.id ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Modality Selector */}
                <div className="w-full sm:w-auto">
                  <span className="label-micro block mb-1 text-muted-foreground">Modality</span>
                  <div 
                    className="flex bg-[#121212] p-1 rounded-md border border-border text-xs overflow-x-auto max-w-full"
                    role="radiogroup" 
                    aria-label="Imagery Modality Selection"
                  >
                    {(["optical", "sar", "both"] as Modality[]).map((m) => (
                      <button
                        key={m}
                        type="button"
                        role="radio"
                        aria-checked={modality === m}
                        onClick={() => setModality(m)}
                        className={cn(
                          "px-3 py-1 rounded font-medium capitalize whitespace-nowrap transition-all focus:outline-none focus:ring-1 focus:ring-primary",
                          modality === m ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        {m === "both" ? "Optical + SAR" : m}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Temporal Selector */}
                <div className="w-full sm:w-auto">
                  <span className="label-micro block mb-1 text-muted-foreground">Temporal Mode</span>
                  <div 
                    className="flex bg-[#121212] p-1 rounded-md border border-border text-xs overflow-x-auto max-w-full"
                    role="radiogroup" 
                    aria-label="Temporal Mode Selection"
                  >
                    {(["single", "bi-temporal"] as Temporal[]).map((t) => (
                      <button
                        key={t}
                        type="button"
                        role="radio"
                        aria-checked={temporal === t}
                        onClick={() => setTemporal(t)}
                        className={cn(
                          "px-3 py-1 rounded font-medium capitalize whitespace-nowrap transition-all focus:outline-none focus:ring-1 focus:ring-primary",
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
                  <div className="w-full sm:w-auto">
                    <span className="label-micro block mb-1 text-muted-foreground">Scenario Preset</span>
                    <div 
                      className="flex bg-[#121212] p-1 rounded-md border border-border text-xs overflow-x-auto max-w-full"
                      role="radiogroup" 
                      aria-label="Scenario Preset Selection"
                    >
                      {(Object.keys(SCENARIOS) as ScenarioId[]).map((id) => (
                        <button
                          key={id}
                          type="button"
                          role="radio"
                          aria-checked={scenarioId === id}
                          onClick={() => setScenarioId(id)}
                          className={cn(
                            "px-3 py-1 rounded font-medium capitalize whitespace-nowrap transition-all focus:outline-none focus:ring-1 focus:ring-primary",
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
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-2 lg:pt-0">
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  multiple
                  accept=".tif,.tiff,.png,.jpg,.jpeg,.webp"
                  className="hidden"
                  aria-label="Upload satellite file input"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  className="border-border bg-[#121212] hover:border-primary text-xs h-10 sm:h-9"
                  aria-label="Upload GeoTIFF or Image"
                >
                  <Upload className="mr-1.5 h-3.5 w-3.5" />
                  Upload GeoTIFF / Image
                </Button>

                <Button
                  size="lg"
                  disabled={isRunning || !query.trim()}
                  onClick={handleRunAnalysis}
                  className="shadow-lg hover:shadow-primary/20 min-w-[170px] h-11 sm:h-10 text-sm font-semibold"
                  aria-label={isRunning ? "Inference currently in progress" : "Execute SatQuery AI analysis"}
                >
                  <Play className={cn("mr-2 h-4 w-4", isRunning && "animate-spin text-primary")} />
                  {isRunning ? "Inference in Progress..." : "Run SatQuery AI"}
                </Button>
              </div>
            </div>

            {/* Custom Uploaded Files Bar */}
            {uploadedFiles.length > 0 && (
              <div className="pt-3 border-t border-border/40 flex flex-wrap items-center gap-3" role="region" aria-label="Uploaded Files List">
                <span className="label-micro text-muted-foreground">Uploaded Files ({uploadedFiles.length}):</span>
                {uploadedFiles.map((file, idx) => (
                  <div key={idx} className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-[#181818] border border-primary/30 text-xs text-foreground">
                    <FileImage className="h-3.5 w-3.5 text-primary" />
                    <span className="truncate max-w-[140px] font-mono">{file.name}</span>
                    <button
                      type="button"
                      onClick={() => handleRemoveFile(idx)}
                      className="text-muted-foreground hover:text-destructive transition-colors ml-1 p-0.5"
                      aria-label={`Remove uploaded file ${file.name}`}
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Error Alert Display */}
        {error && (
          <div 
            className="mb-8 rounded-xl bg-destructive/10 p-4 sm:p-5 border border-destructive/30 text-destructive shadow-lg flex flex-col sm:flex-row items-start justify-between gap-4"
            role="alert"
          >
            <div className="flex items-start gap-3.5">
              <AlertCircle className="h-5 w-5 shrink-0 mt-0.5 text-destructive" />
              <div className="space-y-1">
                <p className="font-semibold text-sm text-foreground">{error.title}</p>
                <p className="text-xs text-destructive leading-relaxed">{error.message}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 self-end sm:self-auto shrink-0">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleRunAnalysis}
                className="h-8 text-xs bg-background/50 border-destructive/30 text-foreground hover:bg-background"
                aria-label="Retry failed query analysis"
              >
                Retry
              </Button>
              <button
                type="button"
                onClick={() => setError(null)}
                className="text-muted-foreground hover:text-foreground p-1 rounded transition-colors"
                aria-label="Dismiss error message"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        {/* Analysis Results Display */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Left Column: Visual Evidence / Canvas Viewer with Bounding Box Overlay */}
          <div className="lg:col-span-7 space-y-6">
            {uploadedFiles.length > 0 ? (
              <div className="relative min-h-[340px] sm:min-h-[440px] rounded-xl border border-border bg-[#121212] overflow-hidden flex flex-col justify-center items-center p-3 sm:p-4 shadow-xl">
                <div className="relative w-full h-[300px] sm:h-[400px] flex items-center justify-center bg-black/60 rounded-lg overflow-hidden">
                  <img
                    src={filePreviewUrls[0]}
                    alt="User Uploaded Remote Sensing Source Image"
                    className="max-h-full max-w-full object-contain"
                  />
                  {/* Active Ingestion Scan Overlay */}
                  {isRunning && (
                    <div className="absolute inset-0 bg-primary/10 border border-primary/30 flex items-center justify-center pointer-events-none animate-pulse">
                      <span className="px-3 py-1 rounded bg-black/80 border border-primary/40 text-primary font-mono text-xs flex items-center gap-2">
                        <Activity className="h-3.5 w-3.5 animate-spin" /> ENCODING USER SATELLITE TENSORS
                      </span>
                    </div>
                  )}
                  {/* Render Bounding Boxes for Uploaded Image */}
                  {!isRunning && groundingBoxes.map((box, idx) => {
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
                        <span className="absolute -top-5 sm:-top-6 left-0 px-1 sm:px-1.5 py-0.5 rounded bg-red-600 text-white font-mono text-[9px] sm:text-[10px] whitespace-nowrap shadow">
                          {box.label}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : temporal === "bi-temporal" ? (
              <div className="relative min-h-[340px] sm:min-h-[440px] overflow-hidden rounded-xl border border-border bg-card shadow-xl flex flex-col">
                <div className="absolute top-3 left-3 sm:top-4 sm:left-4 z-10 bg-background/85 backdrop-blur-md px-3 py-1 rounded-md text-xs font-medium border border-border/50 truncate max-w-[85%]">
                  {currentScenario.description}
                </div>

                <div className="relative flex-1 overflow-hidden group min-h-[300px] sm:min-h-[380px]">
                  {/* After Image */}
                  <div
                    className="absolute inset-0 bg-cover bg-center bg-no-repeat"
                    style={{ backgroundImage: `url(${currentScenario.afterImage})` }}
                    role="img"
                    aria-label={`Post-event observation: ${currentScenario.title}`}
                  />

                  {/* Before Image (Clipped) */}
                  <div
                    className="absolute inset-y-0 left-0 bg-cover bg-center bg-no-repeat border-r-2 border-primary"
                    style={{
                      width: `${comparisonPos}%`,
                      backgroundImage: `url(${currentScenario.beforeImage})`,
                    }}
                    role="img"
                    aria-label={`Pre-event baseline observation: ${currentScenario.title}`}
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
                    aria-label="Bi-temporal before/after satellite image comparison slider"
                  />

                  {/* In-Flight Scan Overlay */}
                  {isRunning && (
                    <div className="absolute inset-0 bg-primary/10 flex items-center justify-center pointer-events-none z-30 animate-pulse">
                      <span className="px-3 py-1.5 rounded-md bg-black/85 border border-primary/50 text-primary font-mono text-xs flex items-center gap-2 shadow-lg">
                        <Activity className="h-4 w-4 animate-spin" /> BI-TEMPORAL DIFFERENCE EXTRACTION
                      </span>
                    </div>
                  )}
                </div>

                <div className="h-11 sm:h-12 border-t border-border flex items-center justify-between px-4 sm:px-6 bg-card/90">
                  <span className="label-micro font-semibold text-muted-foreground text-[10px] sm:text-xs">PRE-EVENT (BEFORE)</span>
                  <ScanSearch className="h-4 w-4 text-primary/60" />
                  <span className="label-micro font-semibold text-muted-foreground text-[10px] sm:text-xs">POST-EVENT (AFTER)</span>
                </div>
              </div>
            ) : (
              <div className="relative min-h-[340px] sm:min-h-[440px] rounded-xl border border-border bg-[#121212] overflow-hidden flex flex-col justify-center items-center p-3 sm:p-4 shadow-xl">
                <div className="relative w-full h-[300px] sm:h-[400px] flex items-center justify-center bg-black/60 rounded-lg overflow-hidden">
                  <img
                    src="/hero-satellite.jpg"
                    alt="Optical Satellite Imagery Surface Canvas"
                    className="w-full h-full object-cover filter brightness-90"
                  />
                  {/* In-Flight Scan Overlay */}
                  {isRunning && (
                    <div className="absolute inset-0 bg-primary/10 flex items-center justify-center pointer-events-none z-30 animate-pulse">
                      <span className="px-3 py-1.5 rounded-md bg-black/85 border border-primary/50 text-primary font-mono text-xs flex items-center gap-2 shadow-lg">
                        <Activity className="h-4 w-4 animate-spin" /> RUNNING GEOCHAT-7B REMOTE-SENSING INFERENCE
                      </span>
                    </div>
                  )}
                  {/* Render Bounding Boxes Overlay on Default Canvas */}
                  {!isRunning && groundingBoxes.map((box, idx) => {
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
                        <span className="absolute -top-5 sm:-top-6 left-0 px-1 sm:px-1.5 py-0.5 rounded bg-red-600 text-white font-mono text-[9px] sm:text-[10px] whitespace-nowrap shadow">
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
                    alt="Inference Generated Surface Alteration Mask"
                    className="max-h-full object-contain"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Right Column: Clear Visual Hierarchy — Primary Model Answer > Grounding Evidence > Auditable Trace */}
          <div className="lg:col-span-5 space-y-6">
            
            {/* LEVEL 1: PRIMARY MODEL ANSWER HERO CARD */}
            <div className={cn(
              "rounded-xl p-5 sm:p-6 shadow-2xl relative overflow-hidden transition-all duration-300",
              result
                ? "border-2 border-primary/40 bg-[#121212] ring-1 ring-primary/20"
                : "border border-border bg-card"
            )}>
              <div className="flex items-center justify-between border-b border-border/60 pb-3.5 mb-4">
                <div className="flex items-center gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/15 border border-primary/30 text-primary">
                    <Sparkles className="h-4 w-4" />
                  </div>
                  <div>
                    <span className="text-xs font-bold uppercase tracking-wider text-foreground block">
                      Primary Model Answer
                    </span>
                    <span className="text-[10px] font-mono text-muted-foreground">
                      GeoChat-7B Remote-Sensing VLM
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {result && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={handleExportJson}
                      className="h-7 text-xs px-2 text-muted-foreground hover:text-foreground border border-border/60 hover:border-primary"
                      aria-label="Export analysis result as JSON file"
                    >
                      <Download className="h-3.5 w-3.5 mr-1" /> JSON
                    </Button>
                  )}
                  <span className={cn(
                    "text-[11px] font-semibold px-2.5 py-0.5 rounded border tracking-wide uppercase",
                    isRunning 
                      ? "bg-amber-500/10 border-amber-500/30 text-amber-400 animate-pulse" 
                      : result 
                      ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-400 shadow-sm" 
                      : "bg-muted border-border text-muted-foreground"
                  )}>
                    {isRunning ? "Executing" : result ? "Complete" : "Ready"}
                  </span>
                </div>
              </div>

              <div className="min-h-[140px]">
                {isRunning ? (
                  <div className="py-6 space-y-4">
                    <div className="flex items-center gap-3">
                      <Activity className="h-5 w-5 animate-spin text-primary shrink-0" />
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-foreground">Inference Pipeline In Flight</p>
                        <p className="text-xs text-muted-foreground">GeoChat-7B vision-language execution (~3–8s)</p>
                      </div>
                    </div>

                    {/* Step-by-Step Progress Pipeline */}
                    <div className="space-y-2 pt-2 border-t border-border/40 font-mono text-xs">
                      <div className="flex items-center gap-2">
                        <span className={cn(
                          "h-2 w-2 rounded-full",
                          loadingStage >= 1 ? "bg-primary" : "bg-neutral-700"
                        )} />
                        <span className={loadingStage >= 1 ? "text-foreground font-medium" : "text-muted-foreground"}>
                          1. Agentic intent &amp; task classification
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={cn(
                          "h-2 w-2 rounded-full",
                          loadingStage >= 2 ? "bg-primary" : "bg-neutral-700"
                        )} />
                        <span className={loadingStage >= 2 ? "text-foreground font-medium" : "text-muted-foreground"}>
                          2. Multi-spectral tensor projection
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={cn(
                          "h-2 w-2 rounded-full",
                          loadingStage >= 3 ? "bg-primary animate-ping" : "bg-neutral-700"
                        )} />
                        <span className={loadingStage >= 3 ? "text-primary font-medium" : "text-muted-foreground"}>
                          3. Autoregressive remote-sensing decoding
                        </span>
                      </div>
                    </div>
                  </div>
                ) : result ? (
                  <div className="space-y-4">
                    {/* Highlighted Primary Text Answer */}
                    <div className="p-3.5 sm:p-4 rounded-lg bg-[#161616] border border-border/80">
                      <p className="text-foreground leading-relaxed text-sm sm:text-base font-normal">
                        {result.answer}
                      </p>
                    </div>

                    {/* Key Metrics / Change Percentage Highlight */}
                    {result.visual_evidence && "change_percentage" in result.visual_evidence && result.visual_evidence.change_percentage !== undefined && result.visual_evidence.change_percentage !== null && (
                      <div className="flex items-center justify-between p-3 rounded-lg bg-primary/10 border border-primary/25">
                        <span className="text-xs font-semibold text-primary uppercase tracking-wide">
                          Quantified Surface Alteration
                        </span>
                        <span className="font-mono text-base sm:text-lg font-bold text-primary">
                          {result.visual_evidence.change_percentage}%
                        </span>
                      </div>
                    )}

                    {/* Confidence Telemetry */}
                    <div className="flex items-center justify-between text-xs text-muted-foreground pt-1">
                      <span>Model Confidence:</span>
                      <span className="font-mono text-foreground font-semibold">
                        {result.confidence !== null && result.confidence !== undefined
                          ? `${(result.confidence * 100).toFixed(1)}%`
                          : "N/A (Autoregressive GeoChat)"}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-36 text-center text-muted-foreground">
                    <p className="text-xs sm:text-sm">Enter a query prompt above and click &ldquo;Run SatQuery AI&rdquo; to execute remote-sensing analysis.</p>
                  </div>
                )}
              </div>
            </div>

            {/* LEVEL 2: GROUNDING VISUAL EVIDENCE TABLE (WHEN PRESENT) */}
            {groundingBoxes.length > 0 && (
              <div className="rounded-xl border border-border bg-[#101010] p-5 shadow-lg space-y-3">
                <div className="flex items-center justify-between border-b border-border/50 pb-2.5">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <Target className="h-4 w-4 text-red-400" /> Grounded Detections
                  </span>
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/20">
                    {groundingBoxes.length} Bounding Boxes
                  </span>
                </div>
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

            {/* LEVEL 3: AUDITABLE EXECUTION TRACE (SUPPORTING TELEMETRY) */}
            <div className="rounded-xl border border-border bg-[#0B0B0B] p-5 sm:p-6 shadow-xl">
              <div className="flex items-center justify-between border-b border-border/60 pb-3 mb-3.5">
                <span className="label-micro text-muted-foreground flex items-center gap-2">
                  <Terminal className="h-4 w-4 text-accent" /> AUDITABLE EXECUTION TRACE
                </span>
                <span className="text-[10px] font-mono text-accent bg-accent/15 px-2 py-0.5 rounded border border-accent/30">
                  PS-COMPLIANT
                </span>
              </div>

              {isRunning ? (
                <div className="py-6 text-center text-xs text-primary font-mono animate-pulse flex items-center justify-center gap-2">
                  <Activity className="h-4 w-4 animate-spin" /> Awaiting telemetry from agentic controller...
                </div>
              ) : result?.execution_trace ? (
                <div className="space-y-3 text-xs font-mono">
                  <div className="p-3 rounded-lg bg-[#121212] border border-border/60 space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-muted-foreground">Task Classified:</span>
                      <span className="text-primary font-bold">{result.execution_trace.task}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-muted-foreground">Specialist Used:</span>
                      <span className="text-foreground">{result.execution_trace.specialist_used}</span>
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-[#121212] border border-border/60">
                    <p className="text-muted-foreground mb-1.5 text-[11px]">Execution Parameters:</p>
                    <pre className="text-[11px] text-accent/90 overflow-x-auto max-h-40 p-1">
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

