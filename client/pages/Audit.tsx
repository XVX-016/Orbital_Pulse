import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Terminal, ArrowLeft, Trash2, AlertTriangle, FileSearch } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  AuditRecord,
  clearAuditTrail,
  getAuditTrail,
  onAuditChange,
} from "@/lib/audit-store";

/**
 * Auditable Execution Trace — PS-26167 compliance surface.
 *
 * Relocated here from the Analyze results panel so the analysis view stays
 * focused on findings.  The trace is a compliance artefact, not a result, and
 * PS-26167 requires it to remain inspectable — hence a dedicated route rather
 * than deletion.  Analyze links here via a badge after every run.
 */
export default function Audit() {
  const [records, setRecords] = useState<AuditRecord[]>([]);
  const [selected, setSelected] = useState(0);

  useEffect(() => {
    const refresh = () => setRecords(getAuditTrail());
    refresh();
    return onAuditChange(refresh);
  }, []);

  const active = records[selected] ?? null;

  const handleClear = () => {
    clearAuditTrail();
    setSelected(0);
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="mb-2 flex items-center gap-2.5">
              <Terminal className="h-5 w-5 shrink-0 text-accent" />
              <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">
                Auditable Execution Trace
              </h1>
              <span className="rounded border border-accent/25 bg-accent/10 px-1.5 py-0.5 font-mono text-[10px] text-accent">
                PS-COMPLIANT
              </span>
            </div>
            <p className="max-w-2xl text-sm text-muted-foreground">
              Every analysis records which task the controller classified, which
              specialist executed it, and the exact parameters used. This log is
              per-browser-tab and clears when the tab closes.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button asChild variant="outline" size="sm">
              <Link to="/analyze">
                <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
                Back to Analyze
              </Link>
            </Button>
            {records.length > 0 && (
              <Button variant="ghost" size="sm" onClick={handleClear}>
                <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                Clear
              </Button>
            )}
          </div>
        </div>

        {records.length === 0 ? (
          <div className="rounded-xl border border-border bg-[#0E0E0E] px-6 py-16 text-center">
            <FileSearch className="mx-auto mb-3 h-8 w-8 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">
              No execution traces recorded in this session yet.
            </p>
            <p className="mt-1 text-xs text-muted-foreground/60">
              Run an analysis and its trace will appear here automatically.
            </p>
            <Button asChild variant="outline" size="sm" className="mt-5">
              <Link to="/analyze">Go to Analyze</Link>
            </Button>
          </div>
        ) : (
          <div className="grid gap-5 lg:grid-cols-[260px_1fr]">
            {/* Run list */}
            <div className="space-y-1.5">
              <p className="label-micro mb-2 px-1 text-muted-foreground">
                SESSION RUNS ({records.length})
              </p>
              {records.map((rec, idx) => (
                <button
                  key={rec.timestamp}
                  type="button"
                  onClick={() => setSelected(idx)}
                  className={cn(
                    "w-full rounded-lg border px-3 py-2.5 text-left transition-colors",
                    idx === selected
                      ? "border-primary/40 bg-primary/10"
                      : "border-border/60 bg-[#0E0E0E] hover:bg-white/[0.02]",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-[11px] font-bold text-primary">
                      {rec.task}
                    </span>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {new Date(rec.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="mt-1 truncate text-[11px] text-muted-foreground">
                    {rec.query || "(no query text)"}
                  </p>
                </button>
              ))}
            </div>

            {/* Detail */}
            {active && (
              <div className="space-y-4">
                {active.dataWarnings && active.dataWarnings.length > 0 && (
                  <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
                    <div className="mb-1.5 flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
                      <span className="label-micro text-amber-400">DATA WARNINGS</span>
                    </div>
                    <ul className="list-inside list-disc space-y-1">
                      {active.dataWarnings.map((w, i) => (
                        <li key={i} className="text-[12px] text-amber-200/80">{w}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="overflow-hidden rounded-xl border border-border bg-[#0E0E0E] shadow-xl">
                  <div className="border-b border-border/50 px-5 py-4">
                    <span className="label-micro text-muted-foreground">QUERY</span>
                    <p className="mt-1 text-sm text-foreground">
                      {active.query || "(no query text)"}
                    </p>
                  </div>

                  <div className="space-y-3 p-5 font-mono text-xs">
                    <div className="space-y-2 rounded-lg border border-border/60 bg-[#141414] p-3">
                      <div className="flex justify-between gap-3">
                        <span className="text-muted-foreground">Task Classified:</span>
                        <span className="font-bold text-primary">{active.task}</span>
                      </div>
                      <div className="flex justify-between gap-3">
                        <span className="text-muted-foreground">Specialist Used:</span>
                        <span className="text-foreground">{active.specialistUsed}</span>
                      </div>
                      <div className="flex justify-between gap-3">
                        <span className="text-muted-foreground">Executed At:</span>
                        <span className="text-foreground">
                          {new Date(active.timestamp).toLocaleString()}
                        </span>
                      </div>
                      {active.dataSource && (
                        <div className="flex justify-between gap-3">
                          <span className="text-muted-foreground">Data Origin:</span>
                          <span
                            className={cn(
                              "font-semibold",
                              active.dataSource === "cached_catalog"
                                ? "text-primary"
                                : "text-sky-400",
                            )}
                          >
                            {active.dataSource}
                          </span>
                        </div>
                      )}
                    </div>

                    <div className="rounded-lg border border-border/60 bg-[#141414] p-3">
                      <p className="mb-1.5 text-muted-foreground">Parameters:</p>
                      <pre className="overflow-x-auto text-[11px] text-accent/90">
                        {JSON.stringify(active.parameters ?? {}, null, 2)}
                      </pre>
                    </div>
                  </div>
                </div>

                {active.narrative && (
                  <div className="rounded-xl border border-border bg-[#0E0E0E] p-5 shadow-xl">
                    <span className="label-micro text-muted-foreground">
                      COMPOSED NARRATIVE (DETERMINISTIC)
                    </span>
                    <p className="mt-2 text-[13px] leading-relaxed text-foreground/90">
                      {active.narrative}
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
