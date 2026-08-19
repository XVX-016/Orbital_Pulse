import { ArrowUpRight, ChevronLeft, ChevronRight, Cpu, Crosshair, Flame, Globe2, Radio, ScanSearch, Satellite, Thermometer, Waves, Wind } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useState, useEffect, useMemo } from "react";

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

interface EonetEventItem {
  title: string;
  category: string;
  date: string;
  id: string;
  coordinates?: [number, number]; // [lng, lat]
}

function getCategoryIcon(category: string) {
  const c = category.toLowerCase();
  if (c.includes("fire") || c.includes("wildfire")) return Flame;
  if (c.includes("storm") || c.includes("cyclone") || c.includes("typhoon") || c.includes("hurricane")) return Wind;
  if (c.includes("flood") || c.includes("water") || c.includes("sea")) return Waves;
  if (c.includes("temp") || c.includes("heat") || c.includes("volcano")) return Thermometer;
  return Globe2;
}

export default function Index() {
  const navigate = useNavigate();
  const [events, setEvents] = useState<EonetEventItem[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isLive, setIsLive] = useState(false);

  useEffect(() => {
    fetch("https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=6")
      .then((res) => {
        if (!res.ok) throw new Error("Network response was not ok");
        return res.json();
      })
      .then((data) => {
        if (data && data.events && data.events.length > 0) {
          const parsed: EonetEventItem[] = data.events.map((ev: any) => {
            const title = ev.title || "Unknown Event";
            const category = ev.categories?.[0]?.title || "Natural Event";
            const dateStr = ev.geometry?.[0]?.date;
            let date = "Recent";
            if (dateStr) {
              const d = new Date(dateStr);
              date = `${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}.${String(
                d.getFullYear()
              ).slice(2)}`;
            }

            let coordinates: [number, number] | undefined = undefined;
            const geom = ev.geometry?.[0];
            if (geom && geom.coordinates) {
              if (typeof geom.coordinates[0] === "number" && typeof geom.coordinates[1] === "number") {
                coordinates = [geom.coordinates[0], geom.coordinates[1]];
              } else if (Array.isArray(geom.coordinates[0])) {
                const first = Array.isArray(geom.coordinates[0][0]) ? geom.coordinates[0][0] : geom.coordinates[0];
                if (typeof first[0] === "number" && typeof first[1] === "number") {
                  coordinates = [first[0], first[1]];
                }
              }
            }

            return { title, category, date, id: ev.id || title, coordinates };
          });
          setEvents(parsed);
          setIsLive(true);
        }
      })
      .catch((err) => {
        console.error("Failed to fetch EONET events:", err);
      });
  }, []);

  const fallbackEvents: EonetEventItem[] = useMemo(
    () => [
      {
        title: "Pacific Atmospheric River & Cyclone Track",
        category: "Severe Storms",
        date: "03.18.25",
        id: "fallback-1",
        coordinates: [-140.0, 35.0],
      },
      {
        title: "Sub-Saharan Thermal Anomaly Cluster",
        category: "Wildfires",
        date: "03.15.25",
        id: "fallback-2",
        coordinates: [15.0, 10.0],
      },
      {
        title: "North Atlantic Sea Surface Temperature Drift",
        category: "Sea and Lake Ice",
        date: "03.10.25",
        id: "fallback-3",
        coordinates: [-30.0, 50.0],
      },
    ],
    []
  );

  const activeEvents = events.length > 0 ? events : fallbackEvents;
  const currentEvent = activeEvents[currentIndex % activeEvents.length];
  const CategoryIcon = getCategoryIcon(currentEvent.category);

  const handlePrev = () => {
    setCurrentIndex((prev) => (prev === 0 ? activeEvents.length - 1 : prev - 1));
  };

  const handleNext = () => {
    setCurrentIndex((prev) => (prev + 1) % activeEvents.length);
  };

  const handleViewOnGlobe = () => {
    if (currentEvent.coordinates) {
      navigate(
        `/globe?lat=${currentEvent.coordinates[1]}&lng=${currentEvent.coordinates[0]}&title=${encodeURIComponent(currentEvent.title)}`
      );
    } else {
      navigate("/globe");
    }
  };

  return (
    <div className="overflow-hidden">
      {/* Hero Section: Centered text with subtle lower-half vignette overlay */}
      <section className="pointer-events-none relative flex min-h-[calc(100vh-64px)] items-end justify-center px-6 pb-24 sm:pb-28 pt-16">
        {/* Subtle full-width vignette overlay across lower half for background contrast */}
        <div
          className="absolute inset-0 pointer-events-none z-0"
          style={{
            background: "linear-gradient(to top, rgba(10,10,10,0.6) 0%, transparent 55%)",
          }}
        />

        <div className="relative z-10 w-full max-w-[1400px] mx-auto flex justify-center">
          <div className="pointer-events-auto max-w-2xl text-center flex flex-col items-center">
            <p className="label-micro mb-4 text-primary-foreground/90 font-semibold tracking-wider drop-shadow-sm">
              Earth observation, reimagined
            </p>
            <h1
              className="text-hero font-bold leading-[1.04] text-foreground sm:text-[56px]"
              style={{ textShadow: "0 2px 16px rgba(0,0,0,0.7)" }}
            >
              Track Earth from orbit.
            </h1>
            <p className="mt-5 max-w-lg text-body text-muted-foreground font-medium leading-relaxed drop-shadow">
              One living view of our planet, powered by the satellites and AI that watch over it.
            </p>
            <div className="mt-8 flex justify-center">
              <Button asChild size="lg" className="shadow-lg hover:shadow-primary/20">
                <Link to="/globe">
                  Launch Globe
                  <ArrowUpRight aria-hidden="true" />
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Cards Grid: Fully Opaque Solid Background */}
      <section className="pointer-events-auto relative z-10 border-y border-border bg-background px-6 py-12">
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

      {/* Featured Event Section: Clean Card with Category Icon & Functional Prev/Next Navigation */}
      <section className="pointer-events-auto relative z-10 bg-background px-6 py-16">
        <div className="mx-auto max-w-[1400px]">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <p className="label-micro">Featured Earth Event</p>
            </div>

            {/* Functional Prev / Next Controls & Index Counter */}
            <div className="flex items-center gap-2">
              <span className="label-micro mr-2 font-mono">
                {String(currentIndex + 1).padStart(2, "0")} / {String(activeEvents.length).padStart(2, "0")}
              </span>
              <button
                type="button"
                onClick={handlePrev}
                aria-label="Previous event"
                className="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-[#121212] text-foreground transition-colors hover:border-primary hover:bg-[#181818]"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={handleNext}
                aria-label="Next event"
                className="flex h-8 w-8 items-center justify-center rounded-md border border-border bg-[#121212] text-foreground transition-colors hover:border-primary hover:bg-[#181818]"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Clean Card Layout without placeholder shapes */}
          <div className="relative overflow-hidden rounded-xl border border-border bg-[#121212] p-6 sm:p-8 shadow-xl">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6">
              <div className="max-w-3xl space-y-3">
                <div className="flex items-center gap-2 text-accent">
                  <div className="flex h-8 w-8 items-center justify-center rounded-md bg-accent/15 border border-accent/30 text-accent">
                    <CategoryIcon className="h-4 w-4" />
                  </div>
                  <span className="label-micro !mb-0 text-accent font-semibold tracking-wider">
                    {currentEvent.category} &bull; {currentEvent.date}
                  </span>
                </div>
                <h2 className="text-title font-semibold text-foreground text-xl sm:text-2xl tracking-tight">
                  {currentEvent.title}
                </h2>
                <p className="text-caption text-muted-foreground leading-relaxed max-w-2xl">
                  Monitored in real-time by NASA’s Earth Observatory Natural Event Tracker (EONET) telemetry network.
                </p>
              </div>

              <div className="flex sm:flex-col items-center sm:items-end justify-between border-t sm:border-t-0 border-border/50 pt-4 sm:pt-0 gap-3">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleViewOnGlobe}
                  className="bg-[#181818] border-border hover:border-primary"
                >
                  View on Globe
                  <ArrowUpRight className="ml-1.5 h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
