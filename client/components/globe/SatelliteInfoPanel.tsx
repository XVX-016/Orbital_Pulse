import React, { useState, useEffect, useMemo } from "react";
import { 
  SatelliteData, 
  propagateSatellite, 
  getSatelliteHardwareInfo 
} from "@/lib/satellite-service";
import { 
  X, 
  ChevronDown, 
  ChevronUp, 
  ChevronLeft, 
  ChevronRight, 
  Copy, 
  Check, 
  ExternalLink, 
  Radio, 
  Crosshair, 
  Cpu, 
  Sparkles 
} from "lucide-react";
import { cn } from "@/lib/utils";

interface SatelliteInfoPanelProps {
  satellite: SatelliteData;
  onClose: () => void;
  onTrack?: () => void;
}

export function SatelliteInfoPanel({ satellite, onClose, onTrack }: SatelliteInfoPanelProps) {
  const [copied, setCopied] = useState(false);
  const [currentPicIndex, setCurrentPicIndex] = useState(0);

  // Accordion open/close state matching satellitemap.space
  const [openSections, setOpenSections] = useState({
    position: true,
    hardware: true,
    pictures: true,
    launch: false,
    ai: false,
  });

  const [aiInfo, setAiInfo] = useState<string | null>(null);
  const [isLoadingAi, setIsLoadingAi] = useState(false);

  const [telemetry, setTelemetry] = useState({
    altitude: 0,
    velocity: 0,
    lat: 0,
    lng: 0,
  });

  const hardwareInfo = useMemo(() => {
    return getSatelliteHardwareInfo(satellite);
  }, [satellite]);

  // Live telemetry update loop (1s interval)
  useEffect(() => {
    const updateTelemetry = () => {
      const pos = propagateSatellite(satellite.satrec, new Date());
      if (pos) {
        setTelemetry({
          altitude: pos.altitude,
          velocity: pos.velocity,
          lat: pos.latitude,
          lng: pos.longitude,
        });
      }
    };

    updateTelemetry();
    const interval = setInterval(updateTelemetry, 1000);
    return () => clearInterval(interval);
  }, [satellite]);

  // Copy full 2-line or 3-line TLE to clipboard
  const handleCopyTLE = () => {
    const tleText = `${satellite.name}\n${satellite.line1}\n${satellite.line2}`;
    navigator.clipboard.writeText(tleText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const toggleSection = (section: keyof typeof openSections) => {
    setOpenSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  const nextPicture = () => {
    if (hardwareInfo.pictures.length > 1) {
      setCurrentPicIndex((prev) => (prev + 1) % hardwareInfo.pictures.length);
    }
  };

  const prevPicture = () => {
    if (hardwareInfo.pictures.length > 1) {
      setCurrentPicIndex((prev) => (prev - 1 + hardwareInfo.pictures.length) % hardwareInfo.pictures.length);
    }
  };

  // On-demand AI remote sensing telemetry summary
  const fetchAIInfo = async () => {
    if (aiInfo || isLoadingAi) return;
    setIsLoadingAi(true);
    try {
      const res = await fetch("/api/ai/satellite-info", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: satellite.name, type: satellite.type }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.info) setAiInfo(data.info);
      }
    } catch (e) {
      console.warn("AI Info fetch failed:", e);
    } finally {
      setIsLoadingAi(false);
    }
  };

  const activePicture = hardwareInfo.pictures[currentPicIndex] || hardwareInfo.pictures[0];

  return (
    <aside className="pointer-events-auto absolute top-16 right-0 bottom-0 z-30 w-full sm:w-[380px] max-w-[390px] border-l border-zinc-800 bg-[#0b0f17]/95 backdrop-blur-xl shadow-2xl text-zinc-100 flex flex-col overflow-hidden animate-in slide-in-from-right duration-200">
      
      {/* Top Header */}
      <div className="p-4 border-b border-zinc-800/80 bg-zinc-950/60 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
            <Radio className="h-4 w-4 animate-pulse" />
          </div>
          <div className="min-w-0">
            <h2 className="font-semibold text-sm tracking-tight text-white truncate">
              {satellite.name}
            </h2>
            <p className="text-[11px] font-mono text-zinc-400 truncate">
              NORAD #{satellite.noradId} &bull; {satellite.subType || satellite.type.toUpperCase()}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1">
          {onTrack && (
            <button
              type="button"
              onClick={onTrack}
              title="Track satellite with camera"
              className="flex items-center gap-1 px-2 py-1 rounded bg-zinc-800/80 hover:bg-zinc-700 text-xs text-zinc-300 transition"
            >
              <Crosshair className="h-3 w-3 text-cyan-400" />
              <span>Track</span>
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close inspector"
            className="rounded p-1 text-zinc-400 hover:bg-zinc-800 hover:text-white transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Top Action Pills (Copy TLE / TLE Details) */}
      <div className="px-4 py-2.5 bg-zinc-950/40 border-b border-zinc-800/60 flex items-center gap-2">
        <button
          type="button"
          onClick={handleCopyTLE}
          className="flex-1 flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-md bg-zinc-900 border border-zinc-700/80 hover:border-cyan-500/50 hover:bg-zinc-800/80 text-xs font-medium text-zinc-200 transition"
        >
          {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5 text-zinc-400" />}
          <span>{copied ? "Copied TLE!" : "copy tle"}</span>
        </button>

        <a
          href={`https://celestrak.org/NORAD/elements/gp.php?CATNR=${satellite.noradId}&FORMAT=tle`}
          target="_blank"
          rel="noreferrer"
          className="flex-1 flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-md bg-zinc-900 border border-zinc-700/80 hover:border-cyan-500/50 hover:bg-zinc-800/80 text-xs font-medium text-zinc-200 transition"
        >
          <ExternalLink className="h-3.5 w-3.5 text-zinc-400" />
          <span>tle raw</span>
        </a>
      </div>

      {/* Scrollable Content Body */}
      <div className="flex-1 overflow-y-auto divide-y divide-zinc-800/70 text-xs">
        
        {/* Section 1: Current Position */}
        <div className="p-4 bg-zinc-950/20">
          <button
            type="button"
            onClick={() => toggleSection("position")}
            className="w-full flex items-center justify-between text-left font-semibold text-zinc-200 hover:text-white transition pb-2"
          >
            <span className="text-xs uppercase tracking-wider text-zinc-300">Current Position</span>
            {openSections.position ? <ChevronUp className="h-4 w-4 text-zinc-400" /> : <ChevronDown className="h-4 w-4 text-zinc-400" />}
          </button>

          {openSections.position && (
            <div className="mt-2 space-y-2 font-mono text-zinc-300">
              <div className="flex items-center justify-between py-1 border-b border-zinc-800/40">
                <span className="text-zinc-500">Latitude:</span>
                <span className="font-semibold text-white">{telemetry.lat.toFixed(4)}°</span>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-zinc-800/40">
                <span className="text-zinc-500">Longitude:</span>
                <span className="font-semibold text-white">{telemetry.lng.toFixed(4)}°</span>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-zinc-800/40">
                <span className="text-zinc-500">Altitude:</span>
                <span className="font-semibold text-cyan-400">{telemetry.altitude.toFixed(2)} km</span>
              </div>
              <div className="flex items-center justify-between py-1">
                <span className="text-zinc-500">Velocity:</span>
                <span className="font-semibold text-emerald-400">{telemetry.velocity.toFixed(2)} km/s</span>
              </div>
            </div>
          )}
        </div>

        {/* Section 2: Hardware */}
        <div className="p-4 bg-zinc-950/20">
          <button
            type="button"
            onClick={() => toggleSection("hardware")}
            className="w-full flex items-center justify-between text-left font-semibold text-zinc-200 hover:text-white transition pb-2"
          >
            <span className="text-xs uppercase tracking-wider text-zinc-300">Hardware</span>
            {openSections.hardware ? <ChevronUp className="h-4 w-4 text-zinc-400" /> : <ChevronDown className="h-4 w-4 text-zinc-400" />}
          </button>

          {openSections.hardware && (
            <div className="mt-2 space-y-2.5">
              <div className="flex items-center justify-between py-1 border-b border-zinc-800/40">
                <span className="text-zinc-500">Hardware:</span>
                <span className="font-medium text-white">{hardwareInfo.hardware}</span>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-zinc-800/40">
                <span className="text-zinc-500">Generation:</span>
                <span className="font-medium text-white">{hardwareInfo.generation}</span>
              </div>
              <div className="pt-1">
                <span className="text-zinc-500 block mb-1">Description:</span>
                <p className="text-zinc-300 leading-relaxed text-[11px] bg-zinc-900/60 p-2.5 rounded border border-zinc-800">
                  {hardwareInfo.description}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Section 3: Pictures */}
        <div className="p-4 bg-zinc-950/20">
          <button
            type="button"
            onClick={() => toggleSection("pictures")}
            className="w-full flex items-center justify-between text-left font-semibold text-zinc-200 hover:text-white transition pb-2"
          >
            <span className="text-xs uppercase tracking-wider text-zinc-300">Pictures</span>
            {openSections.pictures ? <ChevronUp className="h-4 w-4 text-zinc-400" /> : <ChevronDown className="h-4 w-4 text-zinc-400" />}
          </button>

          {openSections.pictures && (
            <div className="mt-2">
              <div className="relative rounded-lg overflow-hidden border border-zinc-800 bg-black aspect-video flex items-center justify-center group">
                <img
                  src={activePicture.url}
                  alt={activePicture.caption}
                  className="w-full h-full object-contain object-center transition-transform duration-300 group-hover:scale-105"
                  onError={(e) => {
                    // Fallback to placeholder if not found
                    (e.target as HTMLImageElement).src = "/hero-satellite.jpg";
                  }}
                />

                {/* Left/Right carousel navigation controls */}
                {hardwareInfo.pictures.length > 1 && (
                  <>
                    <button
                      type="button"
                      onClick={prevPicture}
                      aria-label="Previous picture"
                      className="absolute left-2 top-1/2 -translate-y-1/2 h-7 w-7 rounded-full bg-black/70 hover:bg-black text-white flex items-center justify-center transition border border-white/20"
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={nextPicture}
                      aria-label="Next picture"
                      className="absolute right-2 top-1/2 -translate-y-1/2 h-7 w-7 rounded-full bg-black/70 hover:bg-black text-white flex items-center justify-center transition border border-white/20"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </button>
                  </>
                )}

                {/* Caption Bar */}
                <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/90 via-black/60 to-transparent p-2 text-left">
                  <p className="text-[11px] font-medium text-zinc-200">
                    {activePicture.caption}
                  </p>
                </div>
              </div>

              {/* Carousel Pagination Dots */}
              {hardwareInfo.pictures.length > 1 && (
                <div className="flex items-center justify-center gap-1.5 mt-2.5">
                  {hardwareInfo.pictures.map((_, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => setCurrentPicIndex(idx)}
                      className={cn(
                        "h-1.5 rounded-full transition-all",
                        idx === currentPicIndex ? "w-4 bg-cyan-400" : "w-1.5 bg-zinc-600 hover:bg-zinc-400"
                      )}
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Section 4: Launch Specs */}
        {hardwareInfo.launch && (
          <div className="p-4 bg-zinc-950/20">
            <button
              type="button"
              onClick={() => toggleSection("launch")}
              className="w-full flex items-center justify-between text-left font-semibold text-zinc-200 hover:text-white transition pb-2"
            >
              <span className="text-xs uppercase tracking-wider text-zinc-300">Launch</span>
              {openSections.launch ? <ChevronUp className="h-4 w-4 text-zinc-400" /> : <ChevronDown className="h-4 w-4 text-zinc-400" />}
            </button>

            {openSections.launch && (
              <div className="mt-2 space-y-2 text-[11px]">
                <div className="flex items-center justify-between py-1 border-b border-zinc-800/40">
                  <span className="text-zinc-500">Vehicle:</span>
                  <span className="font-medium text-white">{hardwareInfo.launch.vehicle}</span>
                </div>
                <div className="flex items-center justify-between py-1 border-b border-zinc-800/40">
                  <span className="text-zinc-500">Site:</span>
                  <span className="font-medium text-white text-right">{hardwareInfo.launch.site}</span>
                </div>
                <div className="flex items-center justify-between py-1">
                  <span className="text-zinc-500">Orbit Target:</span>
                  <span className="font-medium text-cyan-400 text-right">{hardwareInfo.launch.orbit}</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Section 5: AI Intelligence / Insight */}
        <div className="p-4 bg-zinc-950/20">
          <button
            type="button"
            onClick={() => {
              toggleSection("ai");
              fetchAIInfo();
            }}
            className="w-full flex items-center justify-between text-left font-semibold text-zinc-200 hover:text-white transition pb-2"
          >
            <span className="text-xs uppercase tracking-wider text-zinc-300 flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-cyan-400" /> AI Mission Intel
            </span>
            {openSections.ai ? <ChevronUp className="h-4 w-4 text-zinc-400" /> : <ChevronDown className="h-4 w-4 text-zinc-400" />}
          </button>

          {openSections.ai && (
            <div className="mt-2">
              {isLoadingAi ? (
                <div className="space-y-1.5 animate-pulse py-2">
                  <div className="h-2.5 bg-zinc-800 rounded w-full"></div>
                  <div className="h-2.5 bg-zinc-800 rounded w-4/5"></div>
                  <div className="h-2.5 bg-zinc-800 rounded w-2/3"></div>
                </div>
              ) : aiInfo ? (
                <p className="text-zinc-300 leading-relaxed text-[11px] bg-cyan-950/20 p-2.5 rounded border border-cyan-800/40">
                  {aiInfo}
                </p>
              ) : (
                <button
                  type="button"
                  onClick={fetchAIInfo}
                  className="w-full py-2 px-3 rounded bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 text-xs text-cyan-400 font-medium transition"
                >
                  Generate AI Telemetry Insight
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* External Links Footer */}
      <div className="p-3.5 border-t border-zinc-800 bg-zinc-950/80 text-[11px] flex flex-wrap items-center justify-between gap-1 text-zinc-400">
        <span className="text-zinc-500 font-medium">External:</span>
        <div className="flex items-center gap-2">
          <a
            href={`https://www.n2yo.com/satellite/?s=${satellite.noradId}`}
            target="_blank"
            rel="noreferrer"
            className="text-cyan-400 hover:text-cyan-300 hover:underline"
          >
            N2YO
          </a>
          <span className="text-zinc-700">&bull;</span>
          <a
            href={`https://celestrak.org/satcat/records.php?CATNR=${satellite.noradId}`}
            target="_blank"
            rel="noreferrer"
            className="text-cyan-400 hover:text-cyan-300 hover:underline"
          >
            CelesTrak
          </a>
          <span className="text-zinc-700">&bull;</span>
          <a
            href={`https://www.heavens-above.com/satinfo.aspx?satid=${satellite.noradId}`}
            target="_blank"
            rel="noreferrer"
            className="text-cyan-400 hover:text-cyan-300 hover:underline"
          >
            Heavens-Above
          </a>
          <span className="text-zinc-700">&bull;</span>
          <a
            href={`https://planet4589.org/space/gcat/`}
            target="_blank"
            rel="noreferrer"
            className="text-cyan-400 hover:text-cyan-300 hover:underline"
          >
            SatCat
          </a>
        </div>
      </div>

    </aside>
  );
}

