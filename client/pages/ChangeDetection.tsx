import { useState } from "react";
import { Play, ScanSearch, ArrowRightLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// --- Types ---
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
    description: "Rondônia, Brazil — 2019 vs 2023",
    beforeImage: "/images/deforestation-before.jpg",
    afterImage: "/images/deforestation-after.jpg",
  },
  disaster: {
    id: "disaster",
    title: "Disaster Response",
    description: "Post-cyclone imagery, coastal district — before vs after",
    beforeImage: "/images/disaster-before.jpg",
    afterImage: "/images/disaster-after.jpg",
  }
};

// --- Components ---

function ScenarioSelector({ selected, onSelect }: { selected: ScenarioId, onSelect: (id: ScenarioId) => void }) {
  return (
    <div className="flex bg-card/50 p-1 rounded-lg border border-border w-max mx-auto mb-8 relative z-10 backdrop-blur-md">
      {(Object.keys(SCENARIOS) as ScenarioId[]).map((key) => (
        <button
          key={key}
          onClick={() => onSelect(key)}
          className={cn(
            "px-6 py-2.5 text-sm font-medium rounded-md transition-all duration-200 ease-in-out",
            selected === key 
              ? "bg-primary text-primary-foreground shadow-md" 
              : "text-muted-foreground hover:text-foreground hover:bg-card/80"
          )}
        >
          {SCENARIOS[key].title}
        </button>
      ))}
    </div>
  );
}

function ImageComparisonViewer({ scenario }: { scenario: Scenario }) {
  const [comparison, setComparison] = useState(50);
  
  return (
    <section className="relative min-h-[520px] overflow-hidden rounded-lg border border-border bg-card lg:min-h-0 flex flex-col shadow-xl">
      <div className="absolute top-4 left-4 z-10 bg-background/85 backdrop-blur-md px-3.5 py-1.5 rounded-md text-sm font-medium border border-border/50 text-foreground shadow-sm">
        {scenario.description}
      </div>
      
      {/* Split view container for before/after images */}
      <div className="relative flex-1 overflow-hidden group">
        {/* After Image (Background) */}
        <div 
          className="absolute inset-0 bg-cover bg-center bg-no-repeat transition-all duration-300"
          style={{ backgroundImage: `url(${scenario.afterImage}), linear-gradient(120deg,hsl(var(--card)),hsl(var(--secondary)/0.65),hsl(var(--card)))` }}
        />
        
        {/* Before Image (Foreground, clipped) */}
        <div 
          className="absolute inset-y-0 left-0 bg-cover bg-center bg-no-repeat border-r-2 border-primary/90 transition-all duration-300 shadow-[4px_0_12px_rgba(0,0,0,0.5)]"
          style={{ 
            width: `${comparison}%`,
            backgroundImage: `url(${scenario.beforeImage}), linear-gradient(120deg,hsl(var(--card)),hsl(var(--accent)/0.55),hsl(var(--card)))` 
          }}
        />

        {/* Fallback grid if images are missing */}
        <div className="absolute inset-0 opacity-20 pointer-events-none [background-image:linear-gradient(hsl(var(--border)/0.38)_1px,transparent_1px),linear-gradient(90deg,hsl(var(--border)/0.38)_1px,transparent_1px)] [background-size:48px_48px]" />

        {/* Slider Handle */}
        <div 
          className="absolute inset-y-0 flex items-center justify-center w-8 -ml-4 pointer-events-none"
          style={{ left: `${comparison}%` }}
        >
          <div className="h-9 w-9 rounded-full bg-card/95 border border-primary flex items-center justify-center shadow-[0_0_15px_rgba(0,0,0,0.8)] text-primary transition-transform group-hover:scale-110">
            <ArrowRightLeft className="h-4 w-4" />
          </div>
        </div>

        {/* Hidden Range Input for Accessibility & Control */}
        <input
          type="range"
          min="0"
          max="100"
          value={comparison}
          onChange={(event) => setComparison(Number(event.target.value))}
          aria-label="Before and after comparison position"
          className="absolute inset-0 w-full h-full opacity-0 cursor-ew-resize z-20"
        />
      </div>

      <div className="h-14 border-t border-border flex items-center justify-between px-6 bg-card/80 backdrop-blur-sm">
        <span className="label-micro font-semibold tracking-wider text-muted-foreground">BEFORE</span>
        <ScanSearch aria-hidden="true" className="h-4 w-4 text-primary/60" />
        <span className="label-micro font-semibold tracking-wider text-muted-foreground">AFTER</span>
      </div>
    </section>
  );
}

function ResultsPanel({ scenario }: { scenario: Scenario }) {
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState<{ change_percentage: number, confidence: number | null, used_fallback_mask?: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runDetection = async () => {
    setIsRunning(true);
    setResults(null);
    setError(null);
    
    try {
      const aiServiceUrl = import.meta.env.VITE_AI_SERVICE_URL || "http://localhost:8082";
      const response = await fetch(`${aiServiceUrl}/api/change-detection`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: scenario.id })
      });
      
      if (!response.ok) {
        throw new Error(`Inference service error: ${response.statusText}`);
      }
      
      const data = await response.json();
      setResults(data);
    } catch (e) {
      console.error("Change detection API failed", e);
      setError("AI inference service is unreachable. Please ensure it is running.");
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <section className="flex flex-col justify-center lg:px-12">
      <div className="max-w-md">
        <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-accent/10 border border-accent/20 mb-5">
          <ScanSearch className="h-3.5 w-3.5 text-accent" />
          <p className="label-micro !tracking-widest !mb-0 text-accent font-semibold">EARTH OBSERVATION</p>
        </div>
        <h1 className="text-headline font-semibold text-foreground tracking-tight">
          Change Detection
        </h1>
        <p className="mt-4 text-body text-muted-foreground leading-relaxed">
          Compare two moments in time to surface meaningful environmental and structural changes. Select a scenario to begin analysis.
        </p>

        <Button
          size="lg"
          className="mt-8 shadow-lg hover:shadow-primary/20 transition-all duration-300"
          disabled={isRunning}
          onClick={runDetection}
        >
          <Play aria-hidden="true" className={cn("mr-2 h-4 w-4", isRunning && "animate-pulse text-primary-foreground/70")} />
          {isRunning ? "Detection Running..." : "Run Detection"}
        </Button>

        {error && (
          <div className="mt-4 rounded-md bg-destructive/10 p-3 border border-destructive/20 text-destructive text-sm font-medium">
            {error}
          </div>
        )}

        <div className="mt-12 border-y border-border py-6 bg-card/30 rounded-xl px-6">
          <div className="flex items-start justify-between gap-6">
            <div>
              <p className="label-micro mb-3 text-muted-foreground">Result summary</p>
              <p className="text-body text-foreground font-medium">
                {isRunning 
                  ? "Analysis in progress..." 
                  : results 
                    ? `Analysis complete for ${scenario.title}`
                    : "Ready for analysis"}
              </p>
            </div>
            <div className="text-right">
              <p className="label-micro mb-2 text-muted-foreground">Change detected</p>
              <p className="text-mono-value text-title text-foreground tracking-tight">
                {results ? `${results.change_percentage}%` : "—"}
              </p>
            </div>
          </div>
          <div className="mt-6 flex items-center justify-between border-t border-border/60 pt-5">
            <span className="label-micro text-muted-foreground">Confidence score</span>
            <span className="text-mono-value text-caption font-semibold text-primary/80">
              {results ? (results.confidence !== null ? `${(results.confidence * 100).toFixed(1)}%` : "N/A") : "—"}
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}

export default function ChangeDetection() {
  const [scenarioId, setScenarioId] = useState<ScenarioId>("deforestation");
  const currentScenario = SCENARIOS[scenarioId];

  return (
    <div className="min-h-screen px-6 pb-16 pt-24 relative">
      {/* Background ambient glow */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/5 rounded-full blur-[120px] pointer-events-none" />
      
      <ScenarioSelector selected={scenarioId} onSelect={setScenarioId} />
      
      <div className="mx-auto grid min-h-[calc(100vh-220px)] max-w-[1400px] grid-cols-1 gap-8 lg:grid-cols-2 relative z-10">
        <ImageComparisonViewer key={scenarioId} scenario={currentScenario} />
        <ResultsPanel key={`results-${scenarioId}`} scenario={currentScenario} />
      </div>
    </div>
  );
}
