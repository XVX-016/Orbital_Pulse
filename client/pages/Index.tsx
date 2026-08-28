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

interface PlanetaryEventItem {
  title: string;
  category: string;
  date: string;
  id: string;
  coordinates?: [number, number]; // [lng, lat]
  image: string;
  description: string;
}

const PLANETARY_EVENTS: PlanetaryEventItem[] = [
  {
    title: "Tropospheric Aerosol & Smog Dispersion Plume",
    category: "Air Pollution",
    date: "03.20.25",
    id: "event-air-pollution",
    coordinates: [77.20, 28.61],
    image: "/air_pollution.jpg",
    description: "Multispectral Sentinel-5P TROPOMI & MODIS aerosol optical depth analysis tracking particulate matter concentration and transboundary smog plumes.",
  },
  {
    title: "Urban Heat Island & Thermal Emission Corridor",
    category: "Urban Thermal",
    date: "03.18.25",
    id: "event-delhi",
    coordinates: [77.10, 28.70],
    image: "/delhi.jpeg",
    description: "High-resolution thermal infrared radiometric tracking of surface temperature anomalies, land cover shifts, and urban microclimates in Delhi NCR.",
  },
  {
    title: "Volcanic Caldera & High-Temperature Thermal Anomaly",
    category: "Volcanic Activity",
    date: "03.16.25",
    id: "event-fire",
    coordinates: [14.99, 37.75],
    image: "/fire.jpg",
    description: "Shortwave infrared (SWIR) radiometric sensors monitoring active lava effusion, pyroclastic plumes, and ground thermal deformation.",
  },
  {
    title: "River Basin Monsoon Inundation & Hydrological Surge",
    category: "Flood Inundation",
    date: "03.14.25",
    id: "event-ganga",
    coordinates: [85.13, 25.61],
    image: "/ganga.jpg",
    description: "Synthetic Aperture Radar (SAR) C-band water penetration quantifying flooded acreage, delta sediment transport, and river bank expansion.",
  },
  {
    title: "Severe Tropical Cyclone Vortex & Convective Wall",
    category: "Severe Storms",
    date: "03.12.25",
    id: "event-tropical-storm",
    coordinates: [-138.50, 22.10],
    image: "/tropical_storm.jpg",
    description: "Geostationary and low-Earth orbit scatterometer wind vector telemetry capturing rapid intensification, eye wall structure, and storm surge.",
  },
  {
    title: "Boreal Canopy Wildfire & Extreme Thermal Front",
    category: "Wildfires",
    date: "03.10.25",
    id: "event-wildfire",
    coordinates: [-119.50, 49.80],
    image: "/wildfire.jpg",
    description: "Mid-wave infrared active fire perimeter tracing, pyrocumulonimbus cloud formation, and burn severity index mapping.",
  },
];

function getCategoryIcon(category: string) {
  const c = category.toLowerCase();
  if (c.includes("wildfire") || c.includes("fire") || c.includes("volcano") || c.includes("thermal")) return Flame;
  if (c.includes("storm") || c.includes("cyclone") || c.includes("typhoon") || c.includes("hurricane")) return Wind;
  if (c.includes("flood") || c.includes("water") || c.includes("sea") || c.includes("river") || c.includes("ganga")) return Waves;
  if (c.includes("pollution") || c.includes("air") || c.includes("smoke") || c.includes("haze")) return Wind;
  if (c.includes("temp") || c.includes("heat") || c.includes("urban") || c.includes("delhi")) return Thermometer;
  return Globe2;
}

export default function Index() {
  const navigate = useNavigate();
  const [events] = useState<PlanetaryEventItem[]>(PLANETARY_EVENTS);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [imgLoaded, setImgLoaded] = useState(false);
  const [imgError, setImgError] = useState(false);

  const activeEvents = events;
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
              className="group flex items-start gap-4 border-l border-border pl-4 transition-colors hover:border-accent"
            >
              <Icon
                aria-hidden="true"
                className="mt-0.5 h-5 w-5 shrink-0 text-accent transition-colors group-hover:text-primary"
                strokeWidth={1.5}
              />
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

          {/* Event Card with Fixed Dimensions & Uniform Layout */}
          <div className="relative overflow-hidden rounded-xl border border-border bg-[#121212] shadow-xl md:h-[280px]">
            <div className="flex flex-col md:flex-row items-stretch h-full">
              {/* Event Image Thumbnail Container - Fixed Size */}
              <div className="relative w-full md:w-80 lg:w-[380px] shrink-0 h-60 md:h-full overflow-hidden bg-neutral-950">
                {!imgLoaded && !imgError && (
                  <div className="absolute inset-0 animate-pulse bg-neutral-800/80 flex items-center justify-center">
                    <Globe2 className="h-8 w-8 text-neutral-600 animate-spin" />
                  </div>
                )}
                <img
                  src={currentEvent.image}
                  alt={currentEvent.title}
                  onLoad={() => setImgLoaded(true)}
                  onError={() => {
                    setImgError(true);
                    setImgLoaded(true);
                  }}
                  className={`h-full w-full object-cover object-center transition-opacity duration-300 ${
                    imgLoaded ? "opacity-100" : "opacity-0"
                  }`}
                  loading="eager"
                />
                {/* Gradient overlay for smooth transition */}
                <div className="absolute inset-0 pointer-events-none bg-gradient-to-t md:bg-gradient-to-r from-transparent via-[#121212]/30 to-[#121212]" />
              </div>

              {/* Event Card Content - Fixed Structure */}
              <div className="flex-1 p-6 sm:p-8 flex flex-col justify-between gap-4 z-10 min-w-0">
                <div className="space-y-2.5">
                  <div className="flex items-center gap-2 text-accent">
                    <div className="flex h-7 w-7 items-center justify-center rounded-md bg-accent/15 border border-accent/30 text-accent shrink-0">
                      <CategoryIcon className="h-4 w-4" />
                    </div>
                    <span className="label-micro !mb-0 text-accent font-semibold tracking-wider truncate">
                      {currentEvent.category} &bull; {currentEvent.date}
                    </span>
                  </div>
                  <h2 className="text-title font-semibold text-foreground text-lg sm:text-xl md:text-2xl tracking-tight line-clamp-1">
                    {currentEvent.title}
                  </h2>
                  <p className="text-caption text-muted-foreground leading-relaxed line-clamp-2">
                    {currentEvent.description}
                  </p>
                </div>

                <div className="flex items-center justify-between border-t border-border/50 pt-4 mt-auto">
                  {currentEvent.coordinates ? (
                    <span className="text-xs font-mono text-muted-foreground">
                      LAT: {currentEvent.coordinates[1].toFixed(2)}&deg; &bull; LON: {currentEvent.coordinates[0].toFixed(2)}&deg;
                    </span>
                  ) : (
                    <span className="text-xs font-mono text-muted-foreground">GLOBAL SATELLITE TELEMETRY</span>
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
