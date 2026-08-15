import { ArrowUpRight, Cpu, Crosshair, ScanSearch, Satellite } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useState, useEffect } from "react";

const FEATURES = [
  {
    icon: Satellite,
    label: "Live Satellite Tracking",
    detail: "Follow every orbit in real time.",
    to: "/globe",
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
    to: "/globe",
  },
  {
    icon: Cpu,
    label: "Edge AI Pipeline",
    detail: "Process insights at the edge.",
    to: "/about",
  },
];

export default function Index() {
  const [eventData, setEventData] = useState<{ title: string; category: string; date: string } | null>(null);

  useEffect(() => {
    fetch("https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=1")
      .then((res) => {
        if (!res.ok) throw new Error("Network response was not ok");
        return res.json();
      })
      .then((data) => {
        if (data && data.events && data.events.length > 0) {
          const ev = data.events[0];
          const title = ev.title || "Unknown Event";
          const category = ev.categories?.[0]?.title || "Event";
          const dateStr = ev.geometry?.[0]?.date;

          let date = "Recent";
          if (dateStr) {
            const d = new Date(dateStr);
            date = `${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}.${String(
              d.getFullYear()
            ).slice(2)}`;
          }

          setEventData({ title, category, date });
        }
      })
      .catch((err) => {
        console.error("Failed to fetch EONET event:", err);
      });
  }, []);

  const displayEvent = eventData || {
    title: "A storm seen from above",
    category: "Pacific",
    date: "03.18.25",
  };

  const displayDesc = eventData
    ? `An active ${displayEvent.category.toLowerCase()} event monitored by the Earth observation network.`
    : "A wide atmospheric river crossing the Pacific, captured by the Orbital observation network.";

  return (
    <div className="overflow-hidden">
      {/* Hero Section: Pointer-events-none on section container, pointer-events-auto on interactive content */}
      <section className="pointer-events-none relative flex min-h-[calc(100vh-64px)] items-center px-6 pt-16">
        <div className="relative z-10 mx-auto w-full max-w-[1400px]">
          <div className="pointer-events-auto max-w-xl">
            <p className="label-micro mb-6">Earth observation, reimagined</p>
            <h1 className="max-w-2xl text-hero font-semibold leading-[1.04] text-foreground sm:text-[56px]">
              Track Earth
              <br />
              from orbit.
            </h1>
            <p className="mt-6 max-w-md text-body text-muted-foreground">
              One living view of our planet, powered by the satellites and AI that watch over it.
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

        <p className="pointer-events-auto absolute bottom-8 left-6 label-micro">Orbital / 01</p>
        <p className="pointer-events-auto absolute bottom-8 right-6 label-micro">Live planetary view</p>
      </section>

      {/* Feature Cards Grid: Fully Opaque Solid Background */}
      <section className="relative z-10 border-y border-border bg-background px-6 py-12">
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
                <span className="block text-body text-foreground">{label}</span>
                <span className="mt-1 block text-caption text-muted-foreground">{detail}</span>
              </span>
            </Link>
          ))}
        </div>
      </section>

      {/* Featured Event Section: Fully Opaque Solid Background */}
      <section className="relative z-10 bg-background px-6 py-16">
        <div className="mx-auto max-w-[1400px]">
          <div className="mb-6 flex items-center justify-between">
            <p className="label-micro">Featured Earth Event</p>
            <p className="label-micro">02 / 04</p>
          </div>
          <div className="relative min-h-[280px] overflow-hidden rounded-lg border border-border bg-card sm:min-h-[360px]">
            <div className="absolute inset-0 bg-[linear-gradient(135deg,hsl(var(--card))_0%,hsl(var(--secondary))_50%,hsl(var(--accent)/0.3)_100%)] opacity-90" />
            <div className="absolute inset-0 opacity-20 [background-image:linear-gradient(hsl(var(--border))_1px,transparent_1px),linear-gradient(90deg,hsl(var(--border))_1px,transparent_1px)] [background-size:48px_48px]" />
            <div className="absolute right-[10%] top-1/2 h-48 w-48 -translate-y-1/2 rounded-full border border-accent/40 bg-[radial-gradient(circle_at_35%_30%,hsl(var(--accent)/0.6),hsl(var(--secondary))_50%,hsl(var(--background))_80%)] shadow-2xl sm:h-64 sm:w-64" />
            <div className="absolute inset-x-0 bottom-0 border-t border-border bg-card/95 p-6 backdrop-blur-md sm:p-8">
              <p className="label-micro mb-2">
                {displayEvent.category} / {displayEvent.date}
              </p>
              <h2 className="text-title font-semibold text-foreground">{displayEvent.title}</h2>
              <p className="mt-2 max-w-xl text-caption text-muted-foreground">{displayDesc}</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
