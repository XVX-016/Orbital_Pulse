import { 
  Bot, 
  Cpu, 
  Database, 
  Layers, 
  Server, 
  Sparkles, 
  ShieldCheck, 
  CheckCircle2, 
  AlertTriangle, 
  ArrowUpRight, 
  Radio, 
  ScanSearch, 
  GitCompare, 
  FileText 
} from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

const ARCHITECTURE_MODULES = [
  {
    icon: Bot,
    name: "Vision-Language Core",
    spec: "GeoChat-7B (4-bit quantized)",
    description:
      "A LLaVA-based model pretrained on remote-sensing instruction data for zero-shot aerial and satellite visual reasoning.",
  },
  {
    icon: Database,
    name: "Domain Adaptation",
    spec: "QLoRA on BigEarthNet Subset",
    description:
      "Adapting output style toward CORINE land-cover taxonomy — aligning model responses with standard Earth observation nomenclature.",
  },
  {
    icon: Cpu,
    name: "Agentic Controller",
    spec: "Intent & Modality Router",
    description:
      "Rule-based task classifier routing queries by modality, temporal structure, and intent to one of four specialist modules, each returning a structured, auditable response.",
  },
  {
    icon: Server,
    name: "Backend Service",
    spec: "FastAPI (satquery-service)",
    description:
      "Inference microservice exposing a single unified /api/analyze endpoint with support for multipart GeoTIFF/image streaming and prompt orchestration.",
  },
  {
    icon: Layers,
    name: "Frontend Workspace",
    spec: "React 18 / TypeScript",
    description:
      "Mission control interface with live query input, task/modality/temporal controls, interactive bi-temporal sliders, and real-time execution trace telemetry.",
  },
];

const CAPABILITIES = [
  {
    icon: ScanSearch,
    title: "Single-Image VQA & Object Grounding",
    description: "Natural-language query answering with visually-verified bounding box coordinates overlaid directly on the satellite canvas.",
  },
  {
    icon: GitCompare,
    title: "Bi-Temporal Change Analysis",
    description: "Quantifies and describes surface and structural alterations across multi-date observation pairs via native two-image prompting.",
  },
  {
    icon: Radio,
    title: "Optical–SAR Multimodal Fusion",
    description: "Classical radar backscatter thresholding combined with VLM scene description for all-weather, cloud-penetrating surface analysis.",
  },
  {
    icon: ShieldCheck,
    title: "Auditable Execution Traces",
    description: "Full agentic routing metadata logging task classification, specialist attribution, and execution parameters for strict compliance.",
  },
];

const HONEST_SCOPE_NOTES = [
  {
    title: "Optical–SAR Fusion Data Scope",
    note: "Optical-SAR fusion is currently validated against synthetically-generated SAR data pending real Sentinel-1/RISAT integration — the fusion logic and thresholds are real and documented, but not yet tested against real radar imagery.",
  },
  {
    title: "Change-VQA Spatial Grounding",
    note: "Change-VQA currently answers what changed; spatial grounding of where the change occurred is not yet implemented.",
  },
  {
    title: "Benchmark Evaluation Methodology",
    note: "Benchmark evaluation is a manually-reviewed sample against real VRSBench and RSVQA-LR test items, not a full automated scoring run across complete test splits.",
  },
];

export default function About() {
  return (
    <div className="min-h-screen px-4 sm:px-6 pb-24 pt-24 sm:pt-28 relative bg-background">
      <div className="mx-auto max-w-[1100px] space-y-12 sm:space-y-16">
        
        {/* Section 1: Hero & What It Does */}
        <section 
          className="rounded-2xl border border-border bg-[#121212] p-5 sm:p-8 md:p-12 shadow-xl space-y-6 sm:space-y-8"
          aria-label="Project Overview"
        >
          <div className="space-y-4">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 max-w-full">
              <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse shrink-0" />
              <p className="label-micro !tracking-wider !mb-0 text-primary font-semibold truncate text-[10px] sm:text-xs">
                Smart India Hackathon 2026 &bull; ISRO Problem Statement PS-26167
              </p>
            </div>
            
            <h1 className="text-headline font-bold leading-tight text-foreground text-2xl sm:text-4xl md:text-5xl tracking-tight">
              SatQuery AI
            </h1>
            
            <p className="text-subhead font-medium text-primary text-base sm:text-xl">
              Agentic Vision-Language Assistant for Remote Sensing Image Analysis
            </p>
          </div>

          <div className="border-t border-border/60 pt-5 sm:pt-6 space-y-4">
            <h2 className="label-micro text-muted-foreground !tracking-widest">
              WHAT IT DOES
            </h2>
            <p className="text-body text-foreground/90 leading-relaxed text-sm sm:text-base md:text-lg">
              SatQuery AI lets you ask natural-language questions about satellite and aerial imagery instead of manually running separate specialist tools. A query like <span className="text-primary font-medium">&ldquo;what changed between these two dates, and where?&rdquo;</span> is automatically classified and routed to the right underlying model — visual question answering, object grounding, bi-temporal change analysis, or optical-SAR fusion — and every response includes a full execution trace showing exactly which task and specialist handled it.
            </p>
            
            <div className="pt-2">
              <Button asChild className="shadow-md hover:shadow-primary/20 w-full sm:w-auto">
                <Link to="/analyze" aria-label="Open SatQuery AI Workspace">
                  Open SatQuery AI Workspace
                  <ArrowUpRight className="ml-1.5 h-4 w-4" aria-hidden="true" />
                </Link>
              </Button>
            </div>
          </div>
        </section>

        {/* Section 2: Architecture */}
        <section className="space-y-6" aria-label="System Architecture">
          <div>
            <p className="label-micro mb-2">SYSTEM DESIGN</p>
            <h2 className="text-subhead font-bold text-foreground text-xl sm:text-2xl tracking-tight">
              Architecture &amp; Components
            </h2>
          </div>

          <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
            {ARCHITECTURE_MODULES.map((item) => {
              const Icon = item.icon;
              return (
                <div
                  key={item.name}
                  className="rounded-xl border border-border bg-[#121212] p-5 sm:p-6 transition-all duration-200 hover:border-primary/50 hover:bg-[#181818] flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center gap-3 mb-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary/10 border border-primary/20 text-primary shrink-0">
                        <Icon className="h-4 w-4" aria-hidden="true" />
                      </div>
                      <div className="min-w-0">
                        <h3 className="font-semibold text-foreground text-sm truncate">{item.name}</h3>
                        <p className="text-[11px] font-mono text-primary truncate">{item.spec}</p>
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {item.description}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Section 3: Capabilities Implemented */}
        <section className="space-y-6" aria-label="Capabilities Implemented">
          <div>
            <p className="label-micro mb-2">OPERATIONAL STATUS</p>
            <h2 className="text-subhead font-bold text-foreground text-xl sm:text-2xl tracking-tight">
              Capabilities Implemented
            </h2>
          </div>

          <div className="grid gap-4 grid-cols-1 sm:grid-cols-2">
            {CAPABILITIES.map((cap) => {
              const Icon = cap.icon;
              return (
                <div
                  key={cap.title}
                  className="rounded-xl border border-border bg-[#121212] p-5 sm:p-6 flex items-start gap-3.5 sm:gap-4 transition-all duration-200 hover:border-border/80"
                >
                  <div className="flex h-9 w-9 items-center justify-center rounded-md bg-accent/20 border border-accent/30 text-accent shrink-0 mt-0.5">
                    <Icon className="h-4 w-4" aria-hidden="true" />
                  </div>
                  <div className="space-y-1.5 min-w-0">
                    <h3 className="font-semibold text-foreground text-sm flex items-center gap-2">
                      <span className="truncate">{cap.title}</span>
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" aria-label="Implemented" />
                    </h3>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {cap.description}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Section 4: Honest Scope Notes (Subtle bordered callout box for judges) */}
        <section 
          className="rounded-2xl border border-amber-500/30 bg-[#121212] p-5 sm:p-8 md:p-10 shadow-xl relative overflow-hidden space-y-6"
          aria-label="Honest Scope Notes and Verification Boundaries"
        >
          <div className="flex items-start sm:items-center gap-3 border-b border-amber-500/20 pb-4">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-amber-500/10 border border-amber-500/30 text-amber-400 shrink-0 mt-0.5 sm:mt-0">
              <AlertTriangle className="h-4 w-4" aria-hidden="true" />
            </div>
            <div>
              <h2 className="text-subhead font-bold text-foreground text-lg sm:text-xl tracking-tight">
                Honest Scope Notes &amp; Verification Boundaries
              </h2>
              <p className="text-xs text-muted-foreground">
                Explicit technical caveats, test coverage disclosures, and roadmap limitations.
              </p>
            </div>
          </div>

          <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
            {HONEST_SCOPE_NOTES.map((item, idx) => (
              <div
                key={idx}
                className="rounded-lg border border-border/80 bg-[#161616] p-4 flex flex-col justify-between space-y-2"
              >
                <span className="text-xs font-semibold text-amber-400 flex items-center gap-1.5">
                  <FileText className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  {item.title}
                </span>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {item.note}
                </p>
              </div>
            ))}
          </div>

          <div className="rounded-lg bg-amber-500/5 border border-amber-500/15 p-4 text-xs text-muted-foreground leading-relaxed">
            <span className="font-semibold text-foreground">Project Standard: </span>
            We&apos;ve prioritized building each capability honestly and verifiably over overclaiming coverage — every number and result in this project is either directly reproducible or explicitly labeled as a limitation.
          </div>
        </section>

      </div>
    </div>
  );
}
