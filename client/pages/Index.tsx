import { ArrowUpRight, Cpu, Crosshair, ScanSearch, Satellite } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

const FEATURES = [
  {
    icon: Satellite,
    label: "Live Satellite Tracking",
    detail: "Follow every orbit in real time.",
    to: "/satellites",
  },
  {
    icon: ScanSearch,
    label: "Change Detection AI",
    detail: "See what changed on Earth.",
    to: "/change-detection",
  },
  {
    icon: Crosshair,
    label: "Satellite Inspector",
    detail: "Dive into every signal.",
    to: "/satellites",
  },
  {
    icon: Cpu,
    label: "Edge AI Pipeline",
    detail: "Process insights at the edge.",
    to: "/timeline",
  },
];

export default function Index() {
  return (
    <div className="overflow-hidden">
      <section className="relative flex min-h-[calc(100vh-64px)] items-center px-6 pt-16">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_72%_42%,hsl(var(--secondary)/0.28),transparent_34%)]" />
        <div className="absolute right-[-18vw] top-1/2 h-[min(78vw,820px)] w-[min(78vw,820px)] -translate-y-1/2 rounded-full bg-[radial-gradient(circle_at_34%_28%,hsl(var(--accent)/0.48),hsl(var(--secondary)/0.42)_30%,hsl(var(--background))_70%)] opacity-90" />
        <div className="absolute right-[8vw] top-1/2 h-[min(56vw,600px)] w-[min(56vw,600px)] -translate-y-1/2 rounded-full border border-accent/30 bg-[radial-gradient(circle_at_35%_30%,hsl(var(--accent)/0.3),transparent_44%),hsl(var(--background)/0.35)] shadow-[inset_-50px_-30px_100px_hsl(var(--background)/0.9)]" />
        <div className="pointer-events-none absolute right-[12vw] top-1/2 h-[min(56vw,600px)] w-[min(56vw,600px)] -translate-y-1/2 rounded-full border border-border/60" />

        <div className="relative z-10 mx-auto w-full max-w-[1400px]">
          <div className="max-w-xl">
            <p className="label-micro mb-6">Earth observation, reimagined</p>
            <h1 className="max-w-2xl text-hero font-semibold leading-[1.04] text-foreground sm:text-[56px]">
              Track Earth
              <br />
              from orbit.
            </h1>
            <p className="mt-6 max-w-md text-body text-muted-foreground">
              One living view of our planet, powered by the satellites and AI
              that watch over it.
            </p>
            <div className="mt-8">
              <Button asChild size="lg">
                <Link to="/globe">
                  Launch Globe
                  <ArrowUpRight aria-hidden="true" />
                </Link>
              </Button>
            </div>
          </div>
        </div>

        <p className="absolute bottom-8 left-6 label-micro">Orbital / 01</p>
        <p className="absolute bottom-8 right-6 label-micro">Live planetary view</p>
      </section>

      <section className="border-y border-border px-6 py-12">
        <div className="mx-auto grid max-w-[1400px] grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4 lg:gap-6">
          {FEATURES.map(({ icon: Icon, label, detail, to }) => (
            <Link
              key={label}
              to={to}
              className="group flex items-start gap-4 border-l border-border pl-4 transition-colors hover:border-accent"
            >
              <Icon
                aria-hidden="true"
                className="mt-0.5 h-5 w-5 shrink-0 text-accent transition-colors group-hover:text-primary"
                strokeWidth={1.5}
              />
              <span>
                <span className="block text-body text-foreground">
                  {label}
                </span>
                <span className="mt-1 block text-caption text-muted-foreground">
                  {detail}
                </span>
              </span>
            </Link>
          ))}
        </div>
      </section>

      <section className="px-6 py-16">
        <div className="mx-auto max-w-[1400px]">
          <div className="mb-6 flex items-center justify-between">
            <p className="label-micro">Featured Earth Event</p>
            <p className="label-micro">02 / 04</p>
          </div>
          <div className="relative min-h-[280px] overflow-hidden rounded-lg border border-border bg-card sm:min-h-[360px]">
            <div className="absolute inset-0 bg-[linear-gradient(120deg,hsl(var(--card)),hsl(var(--secondary)/0.7),hsl(var(--card)))]" />
            <div className="absolute inset-0 opacity-40 [background-image:linear-gradient(hsl(var(--border)/0.35)_1px,transparent_1px),linear-gradient(90deg,hsl(var(--border)/0.35)_1px,transparent_1px)] [background-size:48px_48px]" />
            <div className="absolute right-[12%] top-1/2 h-48 w-48 -translate-y-1/2 rounded-full border border-accent/40 bg-[radial-gradient(circle_at_35%_30%,hsl(var(--accent)/0.5),hsl(var(--secondary)/0.42)_48%,hsl(var(--background))_78%)] shadow-[inset_-28px_-18px_45px_hsl(var(--background)/0.8)] sm:h-64 sm:w-64" />
            <div className="absolute inset-x-0 bottom-0 bg-background/85 p-6 backdrop-blur-md sm:p-8">
              <p className="label-micro mb-2">Pacific / 03.18.25</p>
              <h2 className="text-title font-semibold text-foreground">
                A storm seen from above
              </h2>
              <p className="mt-2 max-w-xl text-caption text-muted-foreground">
                A wide atmospheric river crossing the Pacific, captured by the
                Orbital observation network.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
