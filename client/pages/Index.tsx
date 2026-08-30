import { ArrowUpRight, ChevronLeft, ChevronRight, Cpu, GitCompare, MessageSquareText, Radio, Flame, Wind, Waves, Thermometer, Globe2 } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useState, useEffect, useMemo } from "react";

const FEATURES = [
  {
    icon: MessageSquareText,
    label: "Visual Question Answering",
    detail: "Ask natural-language queries on optical & SAR satellite imagery.",
    to: "/analyze",
  },
  {
    icon: GitCompare,
    label: "Change Detection & Description",
    detail: "Quantify and describe surface alterations across bi-temporal pairs.",
    to: "/analyze",
  },
  {
    icon: Radio,
    label: "Optical–SAR Fusion",
    detail: "Combine cloud-penetrating radar with high-res optical channels.",
    to: "/analyze",
  },
  {
    icon: Cpu,
    label: "Agentic Task Routing",
    detail: "Automatic intent classification & auditable execution traces.",
    to: "/analyze",
  },
];

interface EonetEventItem {
  title: string;
  category: string;
  date: string;
  id: string;
  coordinates?: [number, number]; // [lng, lat]
}

const CATEGORY_IMAGES: Record<string, string> = {
  wildfire: "https://images.unsplash.com/photo-1542601906990-b4d3fb778b09?auto=format&fit=crop&w=800&q=80",
  storm: "https://images.unsplash.com/photo-1527482797697-8795b05a13fe?auto=format&fit=crop&w=800&q=80",
  flood: "https://images.unsplash.com/photo-1547683905-f686c993aae5?auto=format&fit=crop&w=800&q=80",
  ice: "https://images.unsplash.com/photo-1517783999520-f068d7431a60?auto=format&fit=crop&w=800&q=80",
  volcano: "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=800&q=80",
  default: "/hero-satellite.jpg",
};

function getCategoryIcon(category: string) {
  const c = category.toLowerCase();
  if (c.includes("fire") || c.includes("wildfire")) return Flame;
  if (c.includes("storm") || c.includes("cyclone") || c.includes("typhoon") || c.includes("hurricane")) return Wind;
  if (c.includes("flood") || c.includes("water") || c.includes("sea")) return Waves;
  if (c.includes("temp") || c.includes("heat") || c.includes("volcano")) return Thermometer;
  return Globe2;
}

function getEventImageUrl(item: EonetEventItem): string {
  const cat = item.category.toLowerCase();
  if (cat.includes("fire") || cat.includes("wildfire")) return CATEGORY_IMAGES.wildfire;
  if (cat.includes("storm") || cat.includes("cyclone") || cat.includes("hurricane") || cat.includes("typhoon")) return CATEGORY_IMAGES.storm;
  if (cat.includes("flood") || cat.includes("water") || cat.includes("sea")) return CATEGORY_IMAGES.flood;
  if (cat.includes("ice") || cat.includes("snow")) return CATEGORY_IMAGES.ice;
  if (cat.includes("volcano") || cat.includes("temp") || cat.includes("heat")) return CATEGORY_IMAGES.volcano;
  return CATEGORY_IMAGES.default;
}

export default function Index() {
  const navigate = useNavigate();
  const [events, setEvents] = useState<EonetEventItem[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [imgLoaded, setImgLoaded] = useState(false);
  const [imgError, setImgError] = useState(false);

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

  // Reset image state on index change
  useEffect(() => {
    setImgLoaded(false);
    setImgError(false);
  }, [currentIndex]);

  const handlePrev = () => {
    setCurrentIndex((prev) => (prev === 0 ? activeEvents.length - 1 : prev - 1));
  };

  const handleNext = () => {
    setCurrentIndex((prev) => (prev + 1) % activeEvents.length);
  };

  const handleAnalyzeEvent = () => {
    navigate(`/analyze?query=${encodeURIComponent(`Analyze ${currentEvent.title}`)}`);
  };

  const eventImgUrl = getEventImageUrl(currentEvent);
  const catKey = currentEvent.category.toLowerCase();
  const fallbackCatImg = catKey.includes("fire")
    ? CATEGORY_IMAGES.wildfire
    : catKey.includes("storm")
    ? CATEGORY_IMAGES.storm
    : catKey.includes("flood")
    ? CATEGORY_IMAGES.flood
    : catKey.includes("ice")
    ? CATEGORY_IMAGES.ice
    : CATEGORY_IMAGES.default;

  return (
    <div className="overflow-hidden">
      {/* Hero Section: Centered text over high-res Earth satellite background visual */}
      <section className="relative flex min-h-[calc(100vh-64px)] items-end justify-center px-6 pb-24 sm:pb-28 pt-16">
        {/* Background Satellite Visual */}
        <div className="absolute inset-0 z-0 overflow-hidden">
          <img
            src="/hero-satellite.jpg"
            alt="Optical Earth observation satellite imagery"
            className="h-full w-full object-cover object-center scale-105 filter brightness-90 contrast-105"
          />
          {/* Vignette gradients for text legibility */}
          <div className="absolute inset-0 bg-gradient-to-t from-[#0A0A0A] via-[#0A0A0A]/60 to-transparent" />
          <div className="absolute inset-0 bg-gradient-to-b from-[#0A0A0A]/80 via-transparent to-[#0A0A0A]/90" />
        </div>

        <div className="relative z-10 w-full max-w-[1400px] mx-auto flex justify-center">
          <div className="max-w-2xl text-center flex flex-col items-center">
            <p className="label-micro mb-4 text-primary-foreground/90 font-semibold tracking-wider drop-shadow-sm">
              Agentic Remote-Sensing Intelligence
            </p>
            <h1
              className="text-hero font-bold leading-[1.04] text-foreground sm:text-[56px]"
              style={{ textShadow: "0 2px 20px rgba(0,0,0,0.85)" }}
            >
              Ask Earth what changed.
            </h1>
            <p className="mt-5 max-w-xl text-body text-muted-foreground font-medium leading-relaxed drop-shadow-md">
              Natural-language querying of multi-temporal optical &amp; SAR satellite imagery, orchestrated by an agentic multimodal AI assistant.
            </p>
            <div className="mt-8 flex justify-center">
              <Button asChild size="lg" className="shadow-lg hover:shadow-primary/20">
                <Link to="/analyze">
                  Try SatQuery AI
                  <ArrowUpRight aria-hidden="true" className="ml-1 h-4 w-4" />
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Cards Grid */}
      <section className="relative z-10 border-y border-border bg-background px-6 py-12">
        <div className="mx-auto grid max-w-[1400px] grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4 lg:gap-6">
          {FEATURES.map(({ icon: Icon, label, detail, to }) => (
            <Link
              key={label}
              to={to}
              className="group flex items-start gap-4 rounded-lg border-l border-border pl-4 pr-3 py-3 transition-all duration-150 hover:border-accent hover:bg-card/60"
            >
              <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-accent/10 border border-accent/20 text-accent transition-colors group-hover:bg-primary/10 group-hover:border-primary/30 group-hover:text-primary">
                <Icon aria-hidden="true" className="h-4 w-4" strokeWidth={1.5} />
              </div>
              <span>
                <span className="block text-body font-semibold text-foreground">{label}</span>
                <span className="mt-1 block text-caption text-muted-foreground">{detail}</span>
              </span>
            </Link>
          ))}
        </div>
      </section>

      {/* Featured Earth Event Section */}
      <section className="relative z-10 bg-background px-6 py-16">
        <div className="mx-auto max-w-[1400px]">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <p className="label-micro">Active Planetary Telemetry</p>
            </div>

            {/* Prev / Next Controls & Index Counter */}
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

          {/* Event Card with Thumbnail Image & Gradient Overlay */}
          <div className="relative overflow-hidden rounded-xl border border-border bg-[#121212] shadow-xl">
            <div className="flex flex-col md:flex-row items-stretch">
              {/* Event Image Thumbnail Container */}
              <div className="relative w-full md:w-72 lg:w-80 shrink-0 h-52 bg-black/40 overflow-hidden">
                {!imgLoaded && !imgError && (
                  <div className="absolute inset-0 animate-pulse bg-neutral-800/80 flex items-center justify-center">
                    <Globe2 className="h-8 w-8 text-neutral-600 animate-spin" />
                  </div>
                )}
                <img
                  src={imgError ? fallbackCatImg : eventImgUrl}
                  alt={currentEvent.title}
                  onLoad={() => setImgLoaded(true)}
                  onError={() => {
                    setImgError(true);
                    setImgLoaded(true);
                  }}
                  className={`h-full w-full object-cover transition-opacity duration-300 ${
                    imgLoaded ? "opacity-100" : "opacity-0"
                  }`}
                />
                {/* Gradient overlay for smooth transition */}
                <div className="absolute inset-0 bg-gradient-to-t md:bg-gradient-to-r from-transparent via-[#121212]/40 to-[#121212]" />
              </div>

              {/* Event Card Content */}
              <div className="flex-1 p-6 sm:p-8 flex flex-col justify-between gap-6 z-10">
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-accent">
                    <CategoryIcon className="h-3.5 w-3.5 shrink-0" />
                    <span className="label-micro !mb-0 text-accent font-semibold tracking-wider">
                      {currentEvent.category} &bull; {currentEvent.date}
                    </span>
                  </div>
                  <h2 className="text-title font-semibold text-foreground text-xl sm:text-2xl tracking-tight">
                    {currentEvent.title}
                  </h2>
                  <p className="text-caption text-muted-foreground leading-relaxed max-w-2xl">
                    Real-time environmental event tracked by satellite sensors. SatQuery AI can query multi-modal imagery for active event zones.
                  </p>
                </div>

                <div className="flex items-center justify-between border-t border-border/50 pt-4">
                  {currentEvent.coordinates && (
                    <span className="text-xs font-mono text-muted-foreground">
                      LAT: {currentEvent.coordinates[1].toFixed(2)}&deg; &bull; LON: {currentEvent.coordinates[0].toFixed(2)}&deg;
                    </span>
                  )}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleAnalyzeEvent}
                    className="ml-auto bg-[#181818] border-border hover:border-primary"
                  >
                    Query Event
                    <ArrowUpRight className="ml-1.5 h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
