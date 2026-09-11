import { useState, useMemo, useEffect } from "react";
import { ChevronRight, Layers3, Pause, Play, Search, X, Satellite, Radio, Crosshair, Globe as GlobeIcon, Activity } from "lucide-react";
import { useQuery } from '@tanstack/react-query';
import { cn } from "@/lib/utils";
import { useGlobe } from "@/lib/globe-context";
import { parseTLECatalog } from "@/lib/satellite-service";
import { SatelliteInfoPanel } from "@/components/globe/SatelliteInfoPanel";

export default function Globe() {
  const {
    satellites,
    setSatellites,
    selectedSat,
    selectedPos,
    setSelectedSat,
    flyToSatellite,
    flyToView,
    isPlaying,
    setIsPlaying,
    catalogSource,
    setCatalogSource,
    error,
    setError,
  } = useGlobe();

  const [layersVisible, setLayersVisible] = useState(true);
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const [constellation, setConstellation] = useState<
    'active' | 'starlink' | 'stations' | 'gps' | 'weather' | 'resource' | 'science' | 'cubesat'
  >('active');

  const { data: tleData, isLoading, error: queryError } = useQuery({
    queryKey: ['satellite-tles', constellation],
    queryFn: async () => {
      const res = await fetch(`/api/satellites/${constellation}`);
      if (!res.ok) throw new Error('Network response failed');
      return res.text();
    },
    staleTime: 1000 * 60 * 60
  });

  useEffect(() => {
    if (tleData) {
      setSatellites(parseTLECatalog(tleData));
      setCatalogSource(`Live: ${constellation}`);
      setError(null);
    }
    if (queryError) {
      setError(queryError.message);
    }
  }, [tleData, queryError, constellation, setSatellites, setCatalogSource, setError]);


  // Automatically open inspector drawer when a satellite is selected (e.g. clicked on globe or searched)
  useEffect(() => {
    if (selectedSat) {
      setIsInspectorOpen(true);
    }
  }, [selectedSat]);

  // Filtered satellites for search bar dropdown
  const filteredSatellites = useMemo(() => {
    if (!searchQuery.trim()) return satellites.slice(0, 8);
    const q = searchQuery.toLowerCase().trim();
    return satellites
      .filter((s) => s.name.toLowerCase().includes(q) || s.noradId.includes(q))
      .slice(0, 10);
  }, [satellites, searchQuery]);

  // Handle selecting satellite from search or inspector
  const handleSelectSatellite = (sat: typeof satellites[0]) => {
    flyToSatellite(sat);
    setIsInspectorOpen(true);
  };

  // Handle closing inspector drawer and resetting camera to default globe view
  const handleCloseInspector = () => {
    setIsInspectorOpen(false);
    setSelectedSat(null);
    flyToView("globe");
  };

  // Dynamic Inspector Fields formatting
  const inspectorData = useMemo(() => {
    const name = selectedSat?.name || "Awaiting selection";
    const noradId = selectedSat?.noradId || "—";
    const altitude = selectedPos ? `${selectedPos.altitude.toFixed(1)} km` : "—";
    const velocity = selectedPos ? `${selectedPos.velocity.toFixed(2)} km/s` : "—";
    const typeLabel = selectedSat ? selectedSat.type.toUpperCase() : "—";
    const country = selectedSat ? (selectedSat.isISRO ? "India (ISRO)" : "International") : "—";

    return [
      ["Satellite Name", name],
      ["NORAD ID", noradId],
      ["Sensor Type", typeLabel],
      ["Operator", country],
      ["Altitude", altitude],
      ["Velocity", velocity],
    ];
  }, [selectedSat, selectedPos]);

  const constellationLabels: Record<string, string> = {
    active: 'All Active (16k+)',
    starlink: 'Starlink (~11k)',
    stations: 'Space Stations',
    gps: 'GPS Constellation',
    weather: 'Weather',
    resource: 'Earth Resource',
    science: 'Science',
    cubesat: 'CubeSats',
  };

  return (
    <div className="pointer-events-none relative h-[calc(100vh-4rem)] overflow-hidden">
      {/* Top HUD: Constellation Picker */}
      <div className="pointer-events-auto absolute top-4 left-4 z-30 flex gap-2 bg-zinc-950/80 backdrop-blur-md p-1.5 rounded-lg border border-zinc-800">
        <div className="flex flex-wrap gap-2">
          {(['active', 'starlink', 'stations', 'gps', 'weather', 'resource', 'science', 'cubesat'] as const).map((group) => (
            <button
              key={group}
              onClick={() => setConstellation(group)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium tracking-wider transition ${
                constellation === group
                  ? 'bg-cyan-500 text-black shadow-sm font-semibold'
                  : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
              }`}
            >
              {constellationLabels[group] || group}
            </button>
          ))}
        </div>
      </div>

      {/* Status & Loader Indicator */}
      <div className="pointer-events-auto absolute bottom-4 left-1/2 -translate-x-1/2 md:left-4 md:-translate-x-0 md:bottom-28 z-30 flex items-center gap-3 bg-zinc-950/80 backdrop-blur-md px-3 py-2 rounded-lg border border-zinc-800 text-xs text-zinc-300">
        <Activity className={`w-4 h-4 ${isLoading ? 'animate-spin text-cyan-400' : 'text-emerald-400'}`} />
        <span>{isLoading ? 'Streaming Ephemeris...' : error ? 'Error loading data' : 'Orbital Pulse Live'}</span>
      </div>
      {error && (
        <div className="pointer-events-auto absolute top-4 left-1/2 z-50 -translate-x-1/2 rounded-md bg-destructive/90 px-4 py-2 text-sm font-medium text-destructive-foreground backdrop-blur shadow-lg border border-destructive/50 flex items-center gap-2">
          <span>{error}</span>
        </div>
      )}

      {/* Top Bar: Search Bar with Autocomplete & Active Status */}
      <div className="pointer-events-auto absolute left-1/2 top-24 z-20 -translate-x-1/2 flex flex-col items-center gap-2">
        <div className="relative">
          <label className="group flex h-11 w-[calc(100vw-32px)] max-w-[320px] sm:max-w-[380px] sm:w-[380px] items-center overflow-hidden rounded-md border border-border bg-card/90 backdrop-blur-md transition-all duration-200 focus-within:border-accent">
            <Search aria-hidden="true" className="ml-3 h-4 w-4 shrink-0 text-muted-foreground" />
            <input
              type="search"
              placeholder="Find a satellite (e.g. ISS, Starlink, GOES)"
              aria-label="Find a satellite"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onFocus={() => setIsSearchFocused(true)}
              onBlur={() => setTimeout(() => setIsSearchFocused(false), 200)}
              className="h-full min-w-0 flex-1 bg-transparent px-3 text-body text-foreground outline-none placeholder:text-muted-foreground"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="mr-2 p-1 text-muted-foreground hover:text-foreground"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </label>

          {/* Search Dropdown */}
          {isSearchFocused && filteredSatellites.length > 0 && (
            <div className="absolute left-0 right-0 top-12 z-30 max-h-64 overflow-y-auto rounded-md border border-border bg-card/95 p-1 shadow-2xl backdrop-blur-xl">
              <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Matching Satellites ({satellites.length.toLocaleString()} total)
              </div>
              {filteredSatellites.map((sat) => (
                <button
                  key={sat.noradId}
                  type="button"
                  onMouseDown={() => handleSelectSatellite(sat)}
                  className="flex w-full items-center justify-between rounded px-3 py-2 text-left text-xs transition-colors hover:bg-accent/40"
                >
                  <div className="flex items-center gap-2">
                    <Satellite className="h-3.5 w-3.5 text-primary" />
                    <span className="font-medium text-foreground">{sat.name}</span>
                  </div>
                  <span className="font-mono text-[11px] text-muted-foreground">
                    #{sat.noradId}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Catalog Status pill */}
        <div className="flex items-center gap-2 rounded-full border border-border/60 bg-card/70 px-3 py-1 text-[11px] text-muted-foreground backdrop-blur-md">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500"></span>
          </span>
          <span>{satellites.length.toLocaleString()} satellites live ({catalogSource})</span>
        </div>
      </div>

      {/* Satellite Classification Legend */}
      {layersVisible && constellation !== "starlink" && (
        <div className="pointer-events-auto absolute bottom-24 left-4 md:bottom-auto md:top-24 md:left-6 z-20 flex flex-col gap-2 rounded-lg border border-border/80 bg-card/85 p-3 text-xs backdrop-blur-md shadow-xl w-44">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Classification
          </div>
          <div className="flex items-center justify-between text-[11px]">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-blue-500"></span>
              <span className="text-foreground">Optical</span>
            </div>
            <span className="font-mono text-[10px] text-muted-foreground">
              {satellites.filter((s) => s.type === "optical" && !s.isISRO).length}
            </span>
          </div>
          <div className="flex items-center justify-between text-[11px]">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500"></span>
              <span className="text-foreground">SAR Radar</span>
            </div>
            <span className="font-mono text-[10px] text-muted-foreground">
              {satellites.filter((s) => s.type === "sar" && !s.isISRO).length}
            </span>
          </div>
          <div className="flex items-center justify-between text-[11px]">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-amber-500"></span>
              <span className="text-foreground">Weather</span>
            </div>
            <span className="font-mono text-[10px] text-muted-foreground">
              {satellites.filter((s) => s.type === "weather" && !s.isISRO).length}
            </span>
          </div>
          <div className="flex items-center justify-between text-[11px]">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-gray-400"></span>
              <span className="text-foreground">Comms / ISS</span>
            </div>
            <span className="font-mono text-[10px] text-muted-foreground">
              {satellites.filter((s) => s.type === "comms" && !s.isISRO).length}
            </span>
          </div>
        </div>
      )}

      {/* Starlink Shells Legend */}
      {layersVisible && constellation === "starlink" && (
        <div className="pointer-events-auto absolute bottom-24 right-4 md:bottom-auto md:top-24 md:right-6 z-20 flex flex-col gap-2 rounded-lg border border-border/80 bg-zinc-950/90 p-3 text-xs backdrop-blur-md shadow-xl w-48 text-zinc-300">
          <div className="text-[11px] font-bold text-white mb-1">
            Starlink Shells
          </div>
          <div className="flex items-center justify-between text-[11px]">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded bg-blue-500"></span>
              <span>Gen1</span>
            </div>
            <span className="font-mono text-[10px] text-zinc-500">
              {satellites.filter((s) => s.subType === "Gen1").length}
            </span>
          </div>
          <div className="flex items-center justify-between text-[11px]">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded bg-emerald-500"></span>
              <span>Gen2-Transit</span>
            </div>
            <span className="font-mono text-[10px] text-zinc-500">
              {satellites.filter((s) => s.subType === "Gen2-Transit").length}
            </span>
          </div>
          <div className="flex items-center justify-between text-[11px]">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded bg-orange-500"></span>
              <span>v2-mini</span>
            </div>
            <span className="font-mono text-[10px] text-zinc-500">
              {satellites.filter((s) => s.subType === "v2-mini").length}
            </span>
          </div>
          <div className="mt-2 pt-2 border-t border-zinc-800 text-[10px] text-zinc-500">
            Distribution ({satellites.length} satellites)
          </div>
        </div>
      )}

      {/* AI Satellite Info Panel */}
      {selectedSat && (
        <SatelliteInfoPanel 
          satellite={selectedSat} 
          onClose={() => setSelectedSat(null)} 
        />
      )}

      {/* Bottom Control Toolbar */}
      <div className="pointer-events-auto absolute bottom-8 left-6 z-20 flex items-center gap-2">
        <button
          type="button"
          onClick={() => setIsPlaying((playing) => !playing)}
          aria-label={isPlaying ? "Pause time" : "Play time"}
          className="flex h-11 w-11 items-center justify-center rounded-md border border-border bg-card/90 text-foreground backdrop-blur-md transition-colors hover:border-accent hover:bg-popover"
          title={isPlaying ? "Pause tracking propagation" : "Resume tracking propagation"}
        >
          {isPlaying ? <Pause aria-hidden="true" className="h-4 w-4" /> : <Play aria-hidden="true" className="h-4 w-4" />}
        </button>
        <button
          type="button"
          onClick={() => {
            setSelectedSat(null);
            flyToView("globe");
          }}
          aria-label="Reset to default globe view"
          className="flex h-11 items-center gap-1.5 px-3 rounded-md border border-border bg-card/90 text-foreground text-xs font-medium backdrop-blur-md transition-colors hover:border-accent hover:bg-popover"
          title="Recenter camera to default Earth view"
        >
          <GlobeIcon aria-hidden="true" className="h-4 w-4 text-primary" />
          <span>Reset View</span>
        </button>
        <button
          type="button"
          onClick={() => setLayersVisible((visible) => !visible)}
          aria-label="Toggle layers"
          aria-pressed={layersVisible}
          className={cn(
            "flex h-11 w-11 items-center justify-center rounded-md border bg-card/90 backdrop-blur-md transition-colors hover:border-accent hover:bg-popover",
            layersVisible ? "border-primary text-foreground" : "border-border text-muted-foreground",
          )}
        >
          <Layers3 aria-hidden="true" className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => setIsInspectorOpen((open) => !open)}
          aria-label="Toggle satellite inspector"
          aria-pressed={isInspectorOpen}
          className={cn(
            "flex h-11 w-11 items-center justify-center rounded-md border bg-card/90 backdrop-blur-md transition-colors hover:border-accent hover:bg-popover",
            isInspectorOpen ? "border-primary text-foreground" : "border-border text-muted-foreground",
          )}
        >
          <ChevronRight aria-hidden="true" className="h-4 w-4" />
        </button>
      </div>

      {/* Satellite Inspector Panel */}
      <aside
        className={cn(
          "pointer-events-auto absolute bottom-0 right-0 top-16 z-30 w-full max-w-sm border-l border-border bg-popover/95 p-6 backdrop-blur-xl transition-transform duration-300 sm:w-[380px]",
          isInspectorOpen ? "translate-x-0" : "translate-x-full",
        )}
        aria-hidden={!isInspectorOpen}
      >
        <div className="flex items-start justify-between">
          <div>
            <p className="label-micro mb-1 text-primary flex items-center gap-1.5 font-medium">
              <Radio className="h-3 w-3 animate-pulse" /> Live Telemetry
            </p>
            <h2 className="text-subhead font-semibold text-foreground">Satellite Inspector</h2>
          </div>
          <button
            type="button"
            onClick={handleCloseInspector}
            aria-label="Close satellite inspector and reset view"
            className="flex h-11 w-11 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-card hover:text-foreground"
          >
            <X aria-hidden="true" className="h-4 w-4" />
          </button>
        </div>

        {/* Selected Satellite Card */}
        {selectedSat ? (
          <div className="mt-4 rounded-lg border border-border/80 bg-card/80 p-3.5 backdrop-blur-md">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-md bg-accent/30 text-accent">
                  <Satellite className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground text-sm">{selectedSat.name}</h3>
                  <p className="text-[11px] text-muted-foreground">NORAD ID: {selectedSat.noradId}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => handleSelectSatellite(selectedSat)}
                className="flex items-center gap-1 rounded border border-border bg-popover px-2.5 py-1 text-xs text-primary hover:bg-accent/30 transition-colors"
                title="Fly camera to satellite"
              >
                <Crosshair className="h-3 w-3" />
                <span>Track</span>
              </button>
            </div>
          </div>
        ) : (
          <div className="mt-4 rounded-lg border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
            Click any satellite point on the globe or use search to select object.
          </div>
        )}

        {/* Inspector Fields Table */}
        <div className="mt-6 divide-y divide-border border-y border-border">
          {inspectorData.map(([label, value]) => (
            <div key={label} className="flex items-center justify-between gap-4 py-3.5">
              <span className="label-micro text-muted-foreground">{label}</span>
              <span className="text-caption font-mono font-medium text-foreground text-right">{value}</span>
            </div>
          ))}
        </div>

        {/* Coordinates readout if satellite is selected */}
        {selectedPos && (
          <div className="mt-6 rounded-md bg-card/60 p-3 text-[11px] font-mono text-muted-foreground space-y-1">
            <div className="flex justify-between">
              <span>LATITUDE:</span>
              <span className="text-foreground">{selectedPos.latitude.toFixed(4)}°</span>
            </div>
            <div className="flex justify-between">
              <span>LONGITUDE:</span>
              <span className="text-foreground">{selectedPos.longitude.toFixed(4)}°</span>
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}
