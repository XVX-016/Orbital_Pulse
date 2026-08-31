import { CheckCircle2, Circle, Clock, Cpu, Database, Globe, Layers, Server, ScanSearch, Radio, ArrowRightLeft, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

// Technology Stack Items
const TECH_STACK = [
  {
    name: "SatQuery AI (GeoChat-7B)",
    category: "Geospatial Vision-Language Model",
    description: "Fine-tuned 4-bit GeoChat-7B multi-modal LLM powering zero-shot VQA, visual grounding, and remote sensing intelligence.",
    icon: Sparkles,
  },
  {
    name: "CesiumJS + satellite.js",
    category: "3D Globe & Orbital Physics",
    description: "Renders interactive 3D Earth visualization and performs real-time SGP4 orbital propagation from NORAD TLE data.",
    icon: Globe,
  },
  {
    name: "Agentic Router & Specialists",
    category: "Multi-Specialist Controller",
    description: "Dynamic query routing across VQA, spatial grounding, bi-temporal change detection, and Sentinel-1 SAR fusion engines.",
    icon: Cpu,
  },
  {
    name: "PostGIS & Vector Store",
    category: "Geospatial Database",
    description: "PostgreSQL 16 with PostGIS 3.4 for spatial indexing, satellite catalog persistence, and geometric query processing.",
    icon: Database,
  },
  {
    name: "React / TypeScript",
    category: "Frontend Application",
    description: "Powers the mission control interface with type-safe state management, auditable trace panels, and interactive image viewers.",
    icon: Layers,
  },
  {
    name: "Docker Microservices",
    category: "Containerized Orchestration",
    description: "Orchestrates multi-container environment (Frontend, Express Orbit Service, Python SatQuery AI Engine, PostGIS) for seamless deployment.",
    icon: Server,
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
    title: "SatQuery AI Agent Engine",
    subtitle: "VQA, Grounding & Multimodal Analysis",
    status: "completed",
    statusLabel: "Current Build",
    summary: "Integrated fine-tuned GeoChat-7B 4-bit vision-language model into an agentic multi-specialist routing pipeline.",
    highlights: [
      "SatQuery AI Agentic Controller with automated query routing (VQA, Grounding, Change VQA, SAR Fusion)",
      "Zero-shot geospatial visual question answering and spatial bounding box object grounding [xmin, ymin, xmax, ymax]",
      "Bi-temporal change detection & change-VQA engine for deforestation and flood disaster monitoring",
      "Optical-SAR multimodal fusion specialist combining Sentinel-1 synthetic aperture radar and optical imagery",
      "Live satellite tracking on a 3D CesiumJS globe with automated NORAD CelesTrak TLE fetching",
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
            <p className="label-micro !tracking-widest !mb-0 text-primary font-semibold">MISSION CONTROL & SATQUERY AI</p>
          </div>
          <h1 className="text-headline font-semibold leading-tight text-foreground tracking-tight">
            Orbital Pulse & SatQuery AI
          </h1>
          <p className="mt-6 text-body text-muted-foreground leading-relaxed text-lg">
            Orbital Pulse is a next-generation real-time satellite tracking and Earth observation platform powered by <strong className="text-foreground font-semibold">SatQuery AI</strong>. It unifies live NORAD orbital telemetry on an interactive 3D CesiumJS globe with fine-tuned GeoChat-7B vision-language intelligence. SatQuery AI functions as an agentic remote-sensing controller—routing queries across specialized VQA engines, spatial object grounding, bi-temporal change detection, and Sentinel-1 SAR cloud-penetrating radar fusion.
          </p>
        </section>

        {/* Section 1.5: Core SatQuery AI Capabilities */}
        <section className="border-t border-white/10 pt-12">
          <div className="mb-8">
            <p className="label-micro mb-2">AI Capabilities</p>
            <h2 className="text-subhead font-semibold text-foreground">SatQuery AI Agentic Specialists</h2>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-white/10 bg-[#121212]/90 p-5 transition-all duration-200 hover:border-primary/50 hover:bg-[#181818]">
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

            <div className="rounded-xl border border-white/10 bg-[#121212]/90 p-5 transition-all duration-200 hover:border-primary/50 hover:bg-[#181818]">
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

            <div className="rounded-xl border border-white/10 bg-[#121212]/90 p-5 transition-all duration-200 hover:border-primary/50 hover:bg-[#181818]">
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

            <div className="rounded-xl border border-white/10 bg-[#121212]/90 p-5 transition-all duration-200 hover:border-primary/50 hover:bg-[#181818]">
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
        </section>

        {/* Section 2: Tech Stack */}
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


