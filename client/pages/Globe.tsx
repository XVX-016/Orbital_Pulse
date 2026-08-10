import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import { ChevronRight, Layers3, Pause, Play, Search, X, Satellite, Radio, Crosshair, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { Viewer } from "resium";
import { Ion, Color, Viewer as CesiumViewer, Cartesian3, CustomDataSource, Entity, HeadingPitchRange, ScreenSpaceEventHandler, ScreenSpaceEventType, WebMapTileServiceImageryProvider, createWorldImageryAsync } from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import { fetchSatelliteCatalog, propagateSatellite, SatelliteData, SatellitePosition } from "@/lib/satellite-service";

if (import.meta.env.VITE_CESIUM_ION_TOKEN) {
  Ion.defaultAccessToken = import.meta.env.VITE_CESIUM_ION_TOKEN;
}

export default function Globe() {
  const [isPlaying, setIsPlaying] = useState(true);
  const [layersVisible, setLayersVisible] = useState(true);
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);
  const [satellites, setSatellites] = useState<SatelliteData[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const [selectedSat, setSelectedSat] = useState<SatelliteData | null>(null);
  const [selectedPos, setSelectedPos] = useState<SatellitePosition | null>(null);
  const [catalogSource, setCatalogSource] = useState<string>("Orbit Service");
  const [error, setError] = useState<string | null>(null);

  const viewerRef = useRef<CesiumViewer | null>(null);
  const dataSourceRef = useRef<CustomDataSource | null>(null);
  const isPlayingRef = useRef(isPlaying);
  isPlayingRef.current = isPlaying;

  // Load Satellite TLE catalog
  useEffect(() => {
    let isMounted = true;
    fetchSatelliteCatalog()
      .then((data) => {
        if (!isMounted) return;
        setSatellites(data);
        setError(null);
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(err.message);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  // Filtered satellites for search bar dropdown
  const filteredSatellites = useMemo(() => {
    if (!searchQuery.trim()) return satellites.slice(0, 8);
    const q = searchQuery.toLowerCase().trim();
    return satellites
      .filter((s) => s.name.toLowerCase().includes(q) || s.noradId.includes(q))
      .slice(0, 10);
  }, [satellites, searchQuery]);

  // Update selected satellite position periodically
  useEffect(() => {
    if (!selectedSat) return;

    const updateSelectedPos = () => {
      const pos = propagateSatellite(selectedSat.satrec, new Date());
      if (pos) {
        setSelectedPos(pos);
      }
    };

    updateSelectedPos();
    const interval = setInterval(updateSelectedPos, 1000);
    return () => clearInterval(interval);
  }, [selectedSat]);

  // Fly to satellite helper
  const flyToSatellite = useCallback((sat: SatelliteData) => {
    setSelectedSat(sat);
    setIsInspectorOpen(true);
    const viewer = viewerRef.current;
    const dataSource = dataSourceRef.current;

    if (!viewer || !dataSource) return;

    const entity = dataSource.entities.getById(sat.noradId);
    if (entity) {
      viewer.flyTo(entity, {
        duration: 2.0,
        offset: new HeadingPitchRange(0, -Math.PI / 4, 3000000), // 3,000 km distance
      });
    }
  }, []);

  const handleViewerReady = useCallback((viewer: CesiumViewer) => {
    if (!viewer || viewer.isDestroyed()) return;
    viewerRef.current = viewer;

    const scene = viewer.scene;

    // Default Globe Restyling (Stage B styling hook ready)
    scene.backgroundColor = Color.fromCssColorString("hsl(0, 0%, 4%)");
    if (scene.skyBox) {
      scene.skyBox.show = false;
    }

    scene.globe.baseColor = Color.fromCssColorString("hsl(0, 0%, 4%)");
    scene.globe.showGroundAtmosphere = true;
    scene.globe.enableLighting = true;

    if (scene.skyAtmosphere) {
      scene.skyAtmosphere.show = true;
      scene.skyAtmosphere.brightnessShift = -0.4; // Darken the atmosphere glow
      scene.skyAtmosphere.hueShift = -0.1; // Shift slightly towards navy
    }

    // Setup NASA GIBS Imagery Layer with fallback
    const setupImagery = async () => {
      try {
        const date = new Date();
        date.setDate(date.getDate() - 1); // Use yesterday to ensure data is available
        const dateStr = date.toISOString().split('T')[0];
        
        const gibsProvider = new WebMapTileServiceImageryProvider({
          url: `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_SNPP_CorrectedReflectance_TrueColor/default/${dateStr}/{TileMatrixSet}/{TileMatrix}/{TileRow}/{TileCol}.jpg`,
          layer: "VIIRS_SNPP_CorrectedReflectance_TrueColor",
          style: "default",
          format: "image/jpeg",
          tileMatrixSetID: "GoogleMapsCompatible_Level9",
          maximumLevel: 9,
          credit: "NASA GIBS",
        });
        
        viewer.imageryLayers.removeAll();
        viewer.imageryLayers.addImageryProvider(gibsProvider);
      } catch (err) {
        console.error("Failed to load NASA GIBS, falling back to World Imagery", err);
        try {
          const fallbackProvider = await createWorldImageryAsync();
          viewer.imageryLayers.addImageryProvider(fallbackProvider);
        } catch (e) {
          console.error("Fallback imagery failed", e);
        }
      }
    };
    setupImagery();

    // Setup CustomDataSource for satellite entities
    let dataSource = dataSourceRef.current;
    if (!dataSource) {
      dataSource = new CustomDataSource("satellite-tracker");
      viewer.dataSources.add(dataSource);
      dataSourceRef.current = dataSource;
    }

    // Screen click handler for selecting satellites
    const handler = new ScreenSpaceEventHandler(scene.canvas);
    handler.setInputAction((click: { position: Cartesian3 }) => {
      const pickedObject = scene.pick(click.position);
      if (pickedObject && pickedObject.id && pickedObject.id.properties) {
        const satData: SatelliteData | undefined = pickedObject.id.properties.satelliteData?.getValue();
        if (satData) {
          setSelectedSat(satData);
          setIsInspectorOpen(true);
          const pos = propagateSatellite(satData.satrec, new Date());
          if (pos) setSelectedPos(pos);
        }
      }
    }, ScreenSpaceEventType.LEFT_CLICK);

    return () => {
      handler.destroy();
    };
  }, []);

  // Update satellite point entities when catalog or time ticks
  useEffect(() => {
    const dataSource = dataSourceRef.current;
    if (!dataSource || satellites.length === 0) return;

    dataSource.entities.removeAll();

    const now = new Date();
    satellites.forEach((sat) => {
      const pos = propagateSatellite(sat.satrec, now);
      if (!pos) return;

      const positionCartesian = Cartesian3.fromDegrees(pos.longitude, pos.latitude, pos.altitude * 1000);

      dataSource.entities.add({
        id: sat.noradId,
        name: sat.name,
        position: positionCartesian as any,
        point: {
          pixelSize: selectedSat?.noradId === sat.noradId ? 10 : 6,
          color: selectedSat?.noradId === sat.noradId
            ? Color.fromCssColorString("#38bdf8") // Bright Sky Blue when selected
            : Color.fromCssColorString("#06b6d4"), // Cyan for active satellites
          outlineColor: Color.fromCssColorString("#0284c7"),
          outlineWidth: 1.5,
        },
        properties: {
          satelliteData: sat,
        },
      });
    });
  }, [satellites, selectedSat?.noradId]);

  // Throttled clock update loop (recomputes satellite positions every 1 second)
  useEffect(() => {
    const interval = setInterval(() => {
      if (!isPlayingRef.current) return;
      const dataSource = dataSourceRef.current;
      if (!dataSource || satellites.length === 0) return;

      const now = new Date();
      satellites.forEach((sat) => {
        const pos = propagateSatellite(sat.satrec, now);
        if (!pos) return;

        const entity = dataSource.entities.getById(sat.noradId);
        if (entity) {
          entity.position = Cartesian3.fromDegrees(pos.longitude, pos.latitude, pos.altitude * 1000) as any;
        }
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [satellites]);

  // Dynamic Inspector Fields formatting
  const inspectorData = useMemo(() => {
    const name = selectedSat?.name || "Awaiting selection";
    const noradId = selectedSat?.noradId || "—";
    const altitude = selectedPos ? `${selectedPos.altitude.toFixed(1)} km` : "—";
    const velocity = selectedPos ? `${selectedPos.velocity.toFixed(2)} km/s` : "—";
    const country = "—";

    return [
      ["Satellite Name", name],
      ["NORAD ID", noradId],
      ["Altitude", altitude],
      ["Velocity", velocity],
      ["Country", country],
    ];
  }, [selectedSat, selectedPos]);

  return (
    <div className="relative min-h-screen overflow-hidden bg-background">
      {/* Cesium Globe Canvas */}
      <div className="absolute inset-0 z-0 [&_.cesium-viewer-bottom]:hidden">
        <Viewer
          full
          animation={false}
          timeline={false}
          baseLayerPicker={false}
          fullscreenButton={false}
          geocoder={false}
          homeButton={false}
          infoBox={false}
          sceneModePicker={false}
          selectionIndicator={false}
          navigationHelpButton={false}
          navigationInstructionsInitiallyVisible={false}
          ref={(e) => {
            if (e?.cesiumElement) {
              handleViewerReady(e.cesiumElement);
            }
          }}
        />
      </div>

      {error && (
        <div className="absolute top-4 left-1/2 z-50 -translate-x-1/2 rounded-md bg-destructive/90 px-4 py-2 text-sm font-medium text-destructive-foreground backdrop-blur shadow-lg border border-destructive/50 flex items-center gap-2">
          <span>{error}</span>
        </div>
      )}

      {/* Top Bar: Search Bar with Autocomplete & Active Status */}
      <div className="absolute left-1/2 top-16 z-20 -translate-x-1/2 flex flex-col items-center gap-2">
        <div className="relative">
          <label className="group flex h-11 w-[320px] sm:w-[380px] items-center overflow-hidden rounded-md border border-border bg-card/90 backdrop-blur-md transition-all duration-200 focus-within:border-accent">
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
                Matching Satellites ({satellites.length} total)
              </div>
              {filteredSatellites.map((sat) => (
                <button
                  key={sat.noradId}
                  type="button"
                  onMouseDown={() => flyToSatellite(sat)}
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
          <span>{satellites.length} satellites loaded ({catalogSource})</span>
        </div>
      </div>

      {/* Bottom Control Toolbar */}
      <div className="absolute bottom-8 left-6 z-20 flex items-center gap-2">
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
          "absolute bottom-0 right-0 top-16 z-30 w-full max-w-sm border-l border-border bg-popover/95 p-6 backdrop-blur-xl transition-transform duration-300 sm:w-[380px]",
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
            onClick={() => setIsInspectorOpen(false)}
            aria-label="Close satellite inspector"
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
                onClick={() => flyToSatellite(selectedSat)}
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
