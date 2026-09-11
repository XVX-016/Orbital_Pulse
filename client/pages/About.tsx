import { CheckCircle2, Circle, Clock, Cpu, Database, Layers, ScanSearch, Radio, ArrowRightLeft, Sparkles, MapPin, ShieldAlert } from "lucide-react";
import { cn } from "@/lib/utils";

// Technology Stack Items
const TECH_STACK = [
  {
    name: "GeoChat-7B (4-bit Quantized)",
    category: "Vision-Language Model",
    description: "Fine-tuned via QLoRA on BigEarthNet for multimodal remote-sensing intelligence, zero-shot visual QA, and object grounding.",
    icon: Sparkles,
  },
  {
    name: "Agentic Controller & Specialists",
    category: "Multi-Specialist Orchestration",
    description: "Dynamic query routing across 4 core specialists: Visual QA, spatial grounding, bi-temporal change detection, and SAR fusion.",
    icon: Cpu,
  },

  {
    name: "Live STAC Catalog & Fallback",
    category: "Satellite Data Ingestion",
    description: "Earth Search / AWS Element84 STAC integration covering curated regions with automatic on-demand live fallback for any global location.",
    icon: MapPin,
  },
  {
    name: "PostGIS Spatial History",
    category: "Geospatial Database",
    description: "PostgreSQL 16 with PostGIS 3.4 for spatial indexing, audit log persistence, bounding-box queries, and interactive map exploration.",
    icon: Database,
  },
  {
    name: "Full-Stack Architecture",
    category: "Service Orchestration",
    description: "React / TypeScript frontend, FastAPI backend, Docker-orchestrated services (satquery-service + PostGIS), and local GPU-backed GeoChat inference.",
    icon: Layers,
  },
];

// Timeline / Roadmap Items: "What We Built vs. What's Next"
interface TimelineItem {
  phase: string;
  title: string;
  subtitle: string;
  status: "completed" | "roadmap";
  statusLabel: string;
  summary: string;
  highlights: string[];
}

const TIMELINE: TimelineItem[] = [
  {
    phase: "PHASE 01",
    title: "SatQuery AI Core Platform",
    subtitle: "Agentic VLM, Metrics & Spatial Catalog",
    status: "completed",
    statusLabel: "Current Build",
    summary: "Delivered an end-to-end remote sensing analysis system combining fine-tuned GeoChat-7B inference with deterministic pixel validation.",
    highlights: [
      "Agentic controller with dynamic query routing across 4 specialists (VQA, Grounding, Change-VQA, SAR Fusion)",
      "Zero-shot optical VQA and normalized bounding-box object grounding [xmin, ymin, xmax, ymax]",
      "Bi-temporal change detection specialist for disaster assessment, flood inundation, and deforestation monitoring",
      "Sentinel-1 SAR fusion specialist for cloud-penetrating synthetic aperture radar analysis",
      "Deterministic geospatial metrics engine (NDVI, land cover breakdown, spectral change area) computed directly from GeoTIFF pixels",
      "Live STAC catalog (Earth Search / AWS Element84) with automated on-demand global fallback",
      "PostGIS-backed spatial history database with an interactive map view and auditable execution logging",
    ],
  },
  {
    phase: "PHASE 02",
    title: "Edge & On-Device Quantization",
    subtitle: "Quantized payload & low-latency inference",
    status: "roadmap",
    statusLabel: "Future Roadmap",
    summary: "Targeting lower latency and bandwidth savings by executing INT4/INT8 quantized VQA models on satellite edge compute hardware.",
    highlights: [
      "Model quantization (INT8/FP16) for onboard satellite edge hardware execution",
      "On-satellite change detection & grounding to stream bounding boxes rather than raw heavy imagery",
      "Asynchronous tile caching for high-latency or intermittent satellite downlinks",
    ],
  },
  {
    phase: "PHASE 03",
    title: "Autonomous Fleet Tasking",
    subtitle: "Multi-satellite swarm coordination",
    status: "roadmap",
    statusLabel: "Future Roadmap",
    summary: "Expanding single-satellite AI analysis to autonomous, fleet-wide observation scheduling.",
    highlights: [
      "Automated cross-constellation tasking based on SatQuery AI detected environmental anomalies",
      "Real-time alert distribution network for disaster response teams and forest conservation agencies",
      "Global spatial query engine combining historical telemetry with multi-spectral & SAR imagery",
    ],
  },
];

export default function About() {
  return (
    <div className="min-h-screen px-6 pb-24 pt-28 relative">
      {/* Background ambient glow */}
      <div className="absolute top-1/3 right-1/4 w-96 h-96 bg-primary/5 rounded-full blur-[140px] pointer-events-none" />

      {/* Main Content Container matching landing page text background */}
      <div className="mx-auto max-w-[1050px] relative z-10 rounded-2xl border border-white/10 bg-[#121212]/90 p-8 sm:p-12 shadow-2xl space-y-14">

        {/* Section 1: Project Overview */}
        <section className="max-w-3xl">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-primary/10 border border-primary/20 mb-4">
            <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
            <p className="label-micro !tracking-widest !mb-0 text-primary font-semibold">ISRO PS-26167 &bull; SATQUERY AI</p>
          </div>
          <h1 className="text-headline font-semibold leading-tight text-foreground tracking-tight">
            SatQuery AI
          </h1>
          <p className="mt-6 text-body text-muted-foreground leading-relaxed text-lg">
            SatQuery AI is an agentic vision-language assistant for remote-sensing imagery, built for ISRO PS-26167. It integrates a fine-tuned 4-bit GeoChat-7B multimodal vision-language model into an agentic controller that routes queries across specialized analysis engines: Visual Question Answering (VQA), spatial object grounding with normalized bounding boxes, bi-temporal change detection, and Sentinel-1 SAR cloud-penetrating radar fusion. Coupled with an independent deterministic geospatial metrics layer, a live STAC catalog with on-demand global fallback, and a PostGIS-backed analysis history with interactive map exploration, SatQuery AI provides rigorous, auditable Earth observation intelligence.
          </p>
        </section>

        {/* Section 1.5: Core SatQuery AI Capabilities with bg.jpeg background */}
        <section className="relative overflow-hidden rounded-2xl border border-white/10 p-6 sm:p-8 md:p-10 my-12 shadow-2xl">
          {/* Background Image using bg.jpeg */}
          <div className="absolute inset-0 z-0">
            <img
              src="/bg.jpeg"
              alt="SatQuery AI Satellite Background"
              className="h-full w-full object-cover object-center"
            />
            {/* Subtle vignette and glass overlay so background satellite is visible while cards have crisp contrast */}
            <div className="absolute inset-0 bg-gradient-to-b from-[#0A0A0A]/85 via-black/40 to-[#0A0A0A]/85" />
            <div className="absolute inset-0 bg-black/25" />
          </div>

          <div className="relative z-10">
            <div className="mb-8">
              <p className="label-micro mb-2 text-primary-foreground/90 font-semibold tracking-wider">AI Capabilities</p>
              <h2 className="text-subhead font-semibold text-foreground">SatQuery AI Agentic Specialists</h2>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-xl border border-white/15 bg-black/65 p-5 backdrop-blur-md transition-all duration-200 hover:border-primary/50 hover:bg-black/80 shadow-lg">
                <div className="flex items-center gap-3 mb-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary/20 text-primary">
                    <Sparkles className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground text-sm">Visual QA</h3>
                    <p className="text-[11px] text-muted-foreground">Remote Sensing VQA</p>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Zero-shot visual question answering over optical satellite imagery powered by 4-bit GeoChat-7B.
                </p>
              </div>

              <div className="rounded-xl border border-white/15 bg-black/65 p-5 backdrop-blur-md transition-all duration-200 hover:border-primary/50 hover:bg-black/80 shadow-lg">
                <div className="flex items-center gap-3 mb-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-md bg-accent/20 text-accent">
                    <ScanSearch className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground text-sm">Spatial Grounding</h3>
                    <p className="text-[11px] text-muted-foreground">Object Localization</p>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Detects and highlights infrastructure, buildings, and natural features with normalized bounding box coordinates.
                </p>
              </div>

              <div className="rounded-xl border border-white/15 bg-black/65 p-5 backdrop-blur-md transition-all duration-200 hover:border-primary/50 hover:bg-black/80 shadow-lg">
                <div className="flex items-center gap-3 mb-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-md bg-emerald-500/20 text-emerald-400">
                    <ArrowRightLeft className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground text-sm">Change VQA</h3>
                    <p className="text-[11px] text-muted-foreground">Bi-Temporal Analysis</p>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Compares before/after imagery pairs to quantify deforestation, canopy loss, and disaster impact.
                </p>
              </div>

              <div className="rounded-xl border border-white/15 bg-black/65 p-5 backdrop-blur-md transition-all duration-200 hover:border-primary/50 hover:bg-black/80 shadow-lg">
                <div className="flex items-center gap-3 mb-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-md bg-blue-500/20 text-blue-400">
                    <Radio className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground text-sm">SAR Fusion</h3>
                    <p className="text-[11px] text-muted-foreground">Sentinel-1 Radar</p>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Fuses synthetic aperture radar (SAR) channels for cloud-penetrating, night-time flood inundation detection.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Section 2: The Problem */}
        <section className="border-t border-white/10 pt-12">
          <div className="mb-6">
            <p className="label-micro mb-2 text-destructive/80">The Problem</p>
            <h2 className="text-subhead font-semibold text-foreground">Why Manual Remote Sensing Doesn't Scale</h2>
          </div>
          <div className="rounded-xl border border-white/10 bg-[#121212]/80 p-6 sm:p-8 space-y-4">
            <p className="text-sm text-muted-foreground leading-relaxed">
              Satellite constellations now image every point on Earth multiple times a day — yet most of that data never reaches the people who need it most. Interpreting raw satellite imagery requires specialized domain knowledge, command-line GIS toolchains, and hours of manual analysis per scene. As PS-26167 puts it directly: <span className="text-foreground font-medium italic">"non-expert users may find it difficult to obtain meaningful information from satellite imagery through simple natural-language queries."</span>
            </p>
            <p className="text-sm text-muted-foreground leading-relaxed">
              A disaster responder asking "how much of this district is flooded?" shouldn't need to know what SAR backscatter is. A forest agency monitoring deforestation shouldn't require a GIS specialist to run NDVI differencing on each new Sentinel-2 acquisition. When analysis bottlenecks at expert availability, the satellite data arrives on time but the insight doesn't.
            </p>
            <p className="text-sm text-muted-foreground leading-relaxed">
              SatQuery AI was built to close that gap — making Earth observation intelligence as accessible as asking a question.
            </p>
          </div>
        </section>

        {/* Section 3: Tech Stack */}
        <section className="border-t border-white/10 pt-12">
          <div className="mb-8">
            <p className="label-micro mb-2">Architecture</p>
            <h2 className="text-subhead font-semibold text-foreground">Technology Stack</h2>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {TECH_STACK.map((item) => {
              const Icon = item.icon;
              return (
                <div
                  key={item.name}
                  className="group rounded-xl border border-white/10 bg-[#121212]/90 p-5 transition-all duration-200 hover:border-primary/50 hover:bg-[#181818]"
                >
                  <div className="flex items-center gap-3 mb-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-md bg-accent/20 text-accent transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground text-sm">{item.name}</h3>
                      <p className="text-[11px] text-muted-foreground">{item.category}</p>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {item.description}
                  </p>
                </div>
              );
            })}
          </div>
        </section>

        {/* Section 2.5: Honest Scope Notes */}
        <section className="border-t border-white/10 pt-12">
          <div className="rounded-xl border border-white/10 bg-[#121212]/90 p-6 sm:p-8 backdrop-blur-sm shadow-lg">
            <div className="flex items-center gap-3 mb-4">
              <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary/20 text-primary">
                <ShieldAlert className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-foreground">Honest Scope & Engineering Boundaries</h2>
                <p className="text-xs text-muted-foreground">Technical transparency and verification context</p>
              </div>
            </div>
            <ul className="space-y-3 text-xs text-muted-foreground leading-relaxed">
              <li className="flex items-start gap-2.5">
                <span className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                <span><strong className="text-foreground font-medium">SAR Fusion Validation:</strong> SAR fusion is validated on synthetic backscatter data for regions without real Sentinel-1 coverage yet.</span>
              </li>
              <li className="flex items-start gap-2.5">
                <span className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                <span><strong className="text-foreground font-medium">Global STAC Ingestion:</strong> Live STAC fallback trades latency for global coverage outside pre-cataloged regions.</span>
              </li>
              <li className="flex items-start gap-2.5">
                <span className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                <span><strong className="text-foreground font-medium">Evaluation Scoring:</strong> Benchmark evaluation is a manually-reviewed sample against real VRSBench/RSVQA-LR items, not full automated scoring.</span>
              </li>
            </ul>
          </div>
        </section>

        {/* Section 3: Vertical Timeline (What We Built vs. What's Next) */}
        <section className="border-t border-white/10 pt-12">
          <div className="mb-12 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
            <div>
              <p className="label-micro mb-2">Project Execution</p>
              <h2 className="text-subhead font-semibold text-foreground">
                What We Built vs. What’s Next
              </h2>
            </div>
            <div className="flex items-center gap-4 text-xs">
              <span className="flex items-center gap-1.5 text-emerald-400 font-medium">
                <CheckCircle2 className="h-3.5 w-3.5" /> Current Build
              </span>
              <span className="flex items-center gap-1.5 text-muted-foreground font-medium">
                <Clock className="h-3.5 w-3.5" /> Future Roadmap
              </span>
            </div>
          </div>

          {/* Vertical Timeline */}
          <div className="relative ml-4 sm:ml-6 border-l-2 border-white/10 space-y-12">
            {TIMELINE.map((item) => {
              const isCompleted = item.status === "completed";

              return (
                <div key={item.phase} className="relative pl-8 sm:pl-10 group">
                  {/* Timeline Dot */}
                  <div
                    className={cn(
                      "absolute -left-[9px] top-1 h-4 w-4 rounded-full border-2 transition-all duration-200 flex items-center justify-center bg-background",
                      isCompleted
                        ? "border-emerald-500 text-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.4)]"
                        : "border-border text-muted-foreground"
                    )}
                  >
                    {isCompleted ? (
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                    ) : (
                      <Circle className="h-1.5 w-1.5 fill-muted-foreground text-muted-foreground" />
                    )}
                  </div>

                  {/* Content Container */}
                  <div className="rounded-xl border border-white/10 bg-[#121212]/90 p-6 shadow-sm transition-all duration-200 group-hover:border-white/20 group-hover:bg-[#181818]">
                    <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                      <div className="flex items-center gap-3">
                        <span className="text-mono-value text-xs font-semibold text-muted-foreground">
                          {item.phase}
                        </span>
                        <h3 className="text-subhead font-semibold text-foreground">
                          {item.title}
                        </h3>
                      </div>

                      {/* Status Badge */}
                      <span
                        className={cn(
                          "px-2.5 py-0.5 rounded-full text-[11px] font-semibold tracking-wide border",
                          isCompleted
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                            : "bg-muted text-muted-foreground border-border"
                        )}
                      >
                        {item.statusLabel}
                      </span>
                    </div>

                    <p className="text-xs text-primary/90 font-medium mb-3">
                      {item.subtitle}
                    </p>

                    <p className="text-sm text-muted-foreground leading-relaxed mb-4">
                      {item.summary}
                    </p>

                    {/* Feature Highlights */}
                    <ul className="space-y-2 border-t border-border/50 pt-3">
                      {item.highlights.map((highlight, idx) => (
                        <li key={idx} className="flex items-start gap-2.5 text-xs text-muted-foreground">
                          {isCompleted ? (
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0 mt-0.5" />
                          ) : (
                            <Clock className="h-3.5 w-3.5 text-muted-foreground/60 shrink-0 mt-0.5" />
                          )}
                          <span>{highlight}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

      </div>
    </div>
  );
}


