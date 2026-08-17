import { CheckCircle2, Circle, Clock, Cpu, Database, Globe, Layers, Server } from "lucide-react";
import { cn } from "@/lib/utils";

// Technology Stack Items
const TECH_STACK = [
  {
    name: "CesiumJS + satellite.js",
    category: "3D Globe & Orbital Physics",
    description: "Renders interactive 3D Earth visualization and performs real-time SGP4 orbital propagation from NORAD TLE data.",
    icon: Globe,
  },
  {
    name: "React / TypeScript",
    category: "Frontend Application",
    description: "Powers the mission control interface with type-safe state management and responsive UI components.",
    icon: Layers,
  },
  {
    name: "FastAPI + Prithvi-100M",
    category: "AI Inference Service",
    description: "Executes geospatial change detection using NASA & IBM's vision transformer foundation model on multi-temporal Sentinel-2 imagery.",
    icon: Cpu,
  },
  {
    name: "PostGIS",
    category: "Geospatial Database",
    description: "PostgreSQL 16 with PostGIS 3.4 for spatial indexing, satellite catalog persistence, and geometric query processing.",
    icon: Database,
  },
  {
    name: "Docker",
    category: "Microservice Containerization",
    description: "Orchestrates multi-container environment (Frontend, Orbit Proxy, AI Inference, PostGIS) for consistent deployment.",
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
    title: "Hackathon Build",
    subtitle: "Live tracking & change detection",
    status: "completed",
    statusLabel: "Current Build",
    summary: "Built and integrated the core Earth observation workspace during the hackathon.",
    highlights: [
      "Live satellite tracking on a 3D CesiumJS globe with automated CelesTrak TLE fetching",
      "FastAPI inference pipeline consuming 6-band Sentinel-2 imagery via IBM/NASA Prithvi-100M",
      "Interactive before/after change-detection viewer with real GeoTIFF preprocessing",
      "Containerized 4-tier microservice architecture managed via Docker Compose",
    ],
  },
  {
    phase: "PHASE 02",
    title: "Edge Deployment",
    subtitle: "Quantized on-device inference",
    status: "roadmap",
    statusLabel: "Future Roadmap",
    summary: "Targeting lower latency and reduced bandwidth by shifting inference directly onto satellite edge compute hardware.",
    highlights: [
      "Model quantization (INT8/FP16) for low-power edge hardware execution",
      "On-satellite change detection to stream change masks rather than heavy raw imagery",
      "Asynchronous tile caching for high-latency or intermittent satellite downlinks",
    ],
  },
  {
    phase: "PHASE 03",
    title: "Fleet Scaling",
    subtitle: "Multi-satellite coordination",
    status: "roadmap",
    statusLabel: "Future Roadmap",
    summary: "Expanding single-satellite analysis to autonomous, fleet-wide observation scheduling.",
    highlights: [
      "Automated cross-constellation tasking based on detected environmental anomalies",
      "Real-time alert distribution network for disaster response teams",
      "Global spatial query engine combining historical telemetry with multi-spectral imagery",
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
            <p className="label-micro !tracking-widest !mb-0 text-primary font-semibold">MISSION CONTROL</p>
          </div>
          <h1 className="text-headline font-semibold leading-tight text-foreground tracking-tight">
            Orbital Pulse
          </h1>
          <p className="mt-6 text-body text-muted-foreground leading-relaxed text-lg">
            Orbital Pulse is a real-time satellite tracking and Earth observation mission control platform designed to unify live orbital telemetry and AI-powered surface intelligence into a single interface. It streams live NORAD TLE data to visualize satellite trajectories on an interactive 3D globe while utilizing NASA and IBM’s Prithvi geospatial foundation model to detect environmental and structural changes across multi-temporal satellite imagery.
          </p>
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

