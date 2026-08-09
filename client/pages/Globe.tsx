import { useState, useCallback } from "react";
import { ChevronRight, Layers3, Pause, Play, Search, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Viewer } from "resium";
import { Ion, Color, Viewer as CesiumViewer } from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";

if (import.meta.env.VITE_CESIUM_ION_TOKEN) {
  Ion.defaultAccessToken = import.meta.env.VITE_CESIUM_ION_TOKEN;
}

const INSPECTOR_FIELDS = [
  ["Satellite Name", "Awaiting selection"],
  ["NORAD ID", "—"],
  ["Altitude", "—"],
  ["Velocity", "—"],
  ["Country", "—"],
];

export default function Globe() {
  const [isPlaying, setIsPlaying] = useState(true);
  const [layersVisible, setLayersVisible] = useState(true);
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);

  const handleViewerReady = useCallback((viewer: CesiumViewer) => {
    if (!viewer || viewer.isDestroyed()) return;
    const scene = viewer.scene;

    // Match --background (hsl(0, 0%, 4%))
    scene.backgroundColor = Color.fromCssColorString("hsl(0, 0%, 4%)");
    if (scene.skyBox) {
      scene.skyBox.show = false;
    }

    // Match --secondary / --accent dark navy (hsl(221, 47%, 20%))
    scene.globe.baseColor = Color.fromCssColorString("hsl(221, 47%, 20%)");
    scene.globe.showGroundAtmosphere = true;
    scene.globe.enableLighting = true;

    if (scene.skyAtmosphere) {
      scene.skyAtmosphere.show = true;
    }
  }, []);

  return (
    <div className="relative min-h-screen overflow-hidden bg-background">
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

      <div className="absolute left-1/2 top-20 z-20 -translate-x-1/2">
        <label className="group flex h-11 w-11 items-center overflow-hidden rounded-md border border-border bg-card/90 backdrop-blur-md transition-all duration-200 focus-within:w-[min(310px,calc(100vw-48px))]">
          <Search aria-hidden="true" className="ml-3 h-4 w-4 shrink-0 text-muted-foreground" />
          <input
            type="search"
            placeholder="Find a satellite"
            aria-label="Find a satellite"
            className="h-full min-w-0 flex-1 bg-transparent px-3 text-body text-foreground outline-none placeholder:text-muted-foreground"
          />
        </label>
      </div>

      <div className="absolute bottom-8 left-6 z-20 flex items-center gap-2">
        <button
          type="button"
          onClick={() => setIsPlaying((playing) => !playing)}
          aria-label={isPlaying ? "Pause time" : "Play time"}
          className="flex h-11 w-11 items-center justify-center rounded-md border border-border bg-card/90 text-foreground backdrop-blur-md transition-colors hover:border-accent hover:bg-popover"
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

      <aside
        className={cn(
          "absolute bottom-0 right-0 top-16 z-30 w-full max-w-sm border-l border-border bg-popover/95 p-6 backdrop-blur-xl transition-transform duration-300 sm:w-[380px]",
          isInspectorOpen ? "translate-x-0" : "translate-x-full",
        )}
        aria-hidden={!isInspectorOpen}
      >
        <div className="flex items-start justify-between">
          <div>
            <p className="label-micro mb-3">Satellite Inspector</p>
            <h2 className="text-subhead font-semibold text-foreground">Object details</h2>
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
        <div className="mt-8 divide-y divide-border border-y border-border">
          {INSPECTOR_FIELDS.map(([label, value]) => (
            <div key={label} className="flex items-center justify-between gap-4 py-4">
              <span className="label-micro">{label}</span>
              <span className="text-caption text-muted-foreground text-right">{value}</span>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}
