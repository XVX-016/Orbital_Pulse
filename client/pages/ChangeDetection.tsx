import { useState } from "react";
import { Play, ScanSearch } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function ChangeDetection() {
  const [isRunning, setIsRunning] = useState(false);
  const [comparison, setComparison] = useState(50);

  return (
    <div className="min-h-screen px-6 pb-16 pt-24">
      <div className="mx-auto grid min-h-[calc(100vh-160px)] max-w-[1400px] grid-cols-1 gap-6 lg:grid-cols-2">
        <section className="relative min-h-[520px] overflow-hidden rounded-lg border border-border bg-card lg:min-h-0">
          <div className="absolute inset-0 bg-[linear-gradient(120deg,hsl(var(--card)),hsl(var(--secondary)/0.65),hsl(var(--card)))]" />
          <div className="absolute inset-0 opacity-50 [background-image:linear-gradient(hsl(var(--border)/0.38)_1px,transparent_1px),linear-gradient(90deg,hsl(var(--border)/0.38)_1px,transparent_1px)] [background-size:48px_48px]" />
          <div className="absolute left-[24%] top-[29%] h-[32%] w-[40%] border border-primary/70" />
          <div className="absolute left-[24%] top-[29%] -translate-y-7 text-micro uppercase tracking-[0.05em] text-muted-foreground">
            Draw area of interest
          </div>
          <div className="absolute bottom-6 left-6 flex items-center gap-3">
            <ScanSearch aria-hidden="true" className="h-4 w-4 text-accent" />
            <span className="label-micro">Imagery viewer / awaiting input</span>
          </div>
        </section>

        <section className="flex flex-col justify-center lg:px-12">
          <div className="max-w-md">
            <p className="label-micro mb-4">Earth observation tool</p>
            <h1 className="text-headline font-semibold text-foreground">
              Change Detection
            </h1>
            <p className="mt-4 text-body text-muted-foreground">
              Compare two moments in time to surface meaningful change.
            </p>

            <Button
              size="lg"
              className="mt-8"
              onClick={() => setIsRunning((running) => !running)}
            >
              <Play aria-hidden="true" />
              {isRunning ? "Detection Running" : "Run Detection"}
            </Button>

            <div className="mt-12 border-y border-border py-6">
              <div className="flex items-start justify-between gap-6">
                <div>
                  <p className="label-micro mb-3">Result summary</p>
                  <p className="text-body text-foreground">
                    {isRunning ? "Analysis in progress" : "No analysis run"}
                  </p>
                </div>
                <div className="text-right">
                  <p className="label-micro mb-2">Change detected</p>
                  <p className="text-mono-value text-title text-foreground">
                    {isRunning ? "—" : "—"}
                  </p>
                </div>
              </div>
              <div className="mt-6 flex items-center justify-between border-t border-border pt-4">
                <span className="label-micro">Confidence score</span>
                <span className="text-mono-value text-caption text-muted-foreground">—</span>
              </div>
            </div>

            <div className="mt-10">
              <div className="mb-4 flex items-center justify-between">
                <p className="label-micro">Before / After</p>
                <p className="text-mono-value text-caption text-muted-foreground">
                  {comparison}%
                </p>
              </div>
              <div className="relative h-24 overflow-hidden rounded-md border border-border bg-secondary">
                <div className="absolute inset-0 bg-[linear-gradient(120deg,hsl(var(--secondary)),hsl(var(--accent)/0.55))]" />
                <div
                  className="absolute inset-y-0 left-0 border-r border-primary bg-card/45"
                  style={{ width: `${comparison}%` }}
                />
                <div className="absolute inset-0 flex items-center justify-between px-4">
                  <span className="label-micro">Before</span>
                  <span className="label-micro">After</span>
                </div>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={comparison}
                onChange={(event) => setComparison(Number(event.target.value))}
                aria-label="Before and after comparison position"
                className="mt-4 w-full accent-primary"
              />
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
