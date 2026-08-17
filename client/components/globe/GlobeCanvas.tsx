import { useCallback, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { Viewer } from "resium";
import {
  Ion,
  Color,
  Viewer as CesiumViewer,
  Cartesian2,
  Cartesian3,
  CustomDataSource,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  WebMapTileServiceImageryProvider,
  createWorldImageryAsync,
} from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import { useGlobe } from "@/lib/globe-context";
import { SatelliteData } from "@/lib/satellite-service";
import { cn } from "@/lib/utils";

if (import.meta.env.VITE_CESIUM_ION_TOKEN) {
  Ion.defaultAccessToken = import.meta.env.VITE_CESIUM_ION_TOKEN;
}

export default function GlobeCanvas() {
  const { viewerRef, dataSourceRef, flyToSatellite } = useGlobe();
  const { pathname } = useLocation();
  const isGlobe = pathname === "/globe";
  const isCanvasVisible = pathname === "/" || pathname === "/globe";

  // Control camera interactivity & DOM pointer-events based on active route (/globe vs homepage/other routes)
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    if (viewer.canvas) {
      viewer.canvas.style.pointerEvents = isGlobe ? "auto" : "none";
    }

    const controller = viewer.scene.screenSpaceCameraController;
    controller.enableRotate = isGlobe;
    controller.enableZoom = isGlobe;
    controller.enableTranslate = isGlobe;
    controller.enableTilt = isGlobe;
    controller.enableLook = isGlobe;
    controller.enableInputs = isGlobe;
  }, [pathname, viewerRef, isGlobe]);

  const handleViewerReady = useCallback((viewer: CesiumViewer) => {
    if (viewerRef.current === viewer) return;
    if (!viewer || viewer.isDestroyed()) return;
    viewerRef.current = viewer;

    const scene = viewer.scene;
    const isGlobeRoute = window.location.pathname === "/globe";

    // Set initial canvas DOM pointer-events & controller interactivity
    if (viewer.canvas) {
      viewer.canvas.style.pointerEvents = isGlobeRoute ? "auto" : "none";
    }

    scene.screenSpaceCameraController.enableRotate = isGlobeRoute;
    scene.screenSpaceCameraController.enableZoom = isGlobeRoute;
    scene.screenSpaceCameraController.enableTranslate = isGlobeRoute;
    scene.screenSpaceCameraController.enableTilt = isGlobeRoute;
    scene.screenSpaceCameraController.enableLook = isGlobeRoute;
    scene.screenSpaceCameraController.enableInputs = isGlobeRoute;

    // Initial camera setup per route — distinct altitudes give flyToView() real delta to animate
    if (isGlobeRoute) {
      viewer.camera.setView({
        destination: Cartesian3.fromDegrees(0.0, 20.0, 12500000),
        orientation: {
          heading: 0.0,
          pitch: -Math.PI / 2,
          roll: 0.0,
        },
      });
    } else {
      viewer.camera.setView({
        destination: Cartesian3.fromDegrees(0.0, 20.0, 18000000),
        orientation: {
          heading: 0.0,
          pitch: -Math.PI / 2,
          roll: 0.0,
        },
      });
    }

    // Default Globe Restyling
    scene.backgroundColor = Color.fromCssColorString("hsl(0, 0%, 4%)");
    if (scene.skyBox) {
      scene.skyBox.show = false;
    }

    scene.globe.baseColor = Color.fromCssColorString("hsl(0, 0%, 4%)");
    scene.globe.showGroundAtmosphere = true;
    scene.globe.enableLighting = false;

    if (scene.skyAtmosphere) {
      scene.skyAtmosphere.show = true;
      scene.skyAtmosphere.brightnessShift = -0.4;
      scene.skyAtmosphere.hueShift = -0.1;
    }

    // Setup NASA GIBS Imagery Layer with fallback
    const setupImagery = async () => {
      try {
        const date = new Date();
        date.setDate(date.getDate() - 1);
        const dateStr = date.toISOString().split("T")[0];

        const gibsProvider = new WebMapTileServiceImageryProvider({
          url: `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_SNPP_CorrectedReflectance_TrueColor/default/${dateStr}/{TileMatrixSet}/{TileMatrix}/{TileRow}/{TileCol}.jpg`,
          layer: "VIIRS_SNPP_CorrectedReflectance_TrueColor",
          style: "default",
          format: "image/jpeg",
          tileMatrixSetID: "GoogleMapsCompatible_Level9",
          maximumLevel: 9,
          credit: "NASA GIBS",
        });

        // Track tile errors — only fall back on sustained failures, not per-tile noise
        let hasFallenBack = false;
        let tileErrorCount = 0;
        let errorWindowStart = Date.now();
        const ERROR_THRESHOLD = 5;
        const ERROR_WINDOW_MS = 30_000; // 30 seconds

        gibsProvider.errorEvent.addEventListener(async (error: unknown) => {
          if (hasFallenBack) return;

          // Log every error so we can diagnose what GIBS is actually returning
          console.warn("[GIBS tile error]", {
            message: error instanceof Error ? error.message : String(error),
            error,
            timestamp: new Date().toISOString(),
          });

          // Reset counter if outside the rolling window
          const now = Date.now();
          if (now - errorWindowStart > ERROR_WINDOW_MS) {
            tileErrorCount = 0;
            errorWindowStart = now;
          }

          tileErrorCount++;

          if (tileErrorCount >= ERROR_THRESHOLD) {
            hasFallenBack = true;
            console.warn(
              `NASA GIBS hit ${ERROR_THRESHOLD} tile errors within ${ERROR_WINDOW_MS / 1000}s — falling back to Cesium World Imagery`
            );
            try {
              viewer.imageryLayers.removeAll();
              const fallbackProvider = await createWorldImageryAsync();
              viewer.imageryLayers.addImageryProvider(fallbackProvider);
            } catch (fallbackErr) {
              console.error("Cesium World Imagery fallback failed:", fallbackErr);
            }
          }
        });

        viewer.imageryLayers.removeAll();
        viewer.imageryLayers.addImageryProvider(gibsProvider);
      } catch (err) {
        console.error("Failed to load NASA GIBS, falling back to World Imagery", err);
        try {
          viewer.imageryLayers.removeAll();
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
    handler.setInputAction((click: { position: Cartesian2 }) => {
      const pickedObject = scene.pick(click.position);
      if (pickedObject && pickedObject.id && pickedObject.id.properties) {
        const satData: SatelliteData | undefined = pickedObject.id.properties.satelliteData?.getValue();
        if (satData) {
          flyToSatellite(satData);
        }
      }
    }, ScreenSpaceEventType.LEFT_CLICK);
  }, [viewerRef, dataSourceRef, flyToSatellite]);

  return (
    <div
      className={cn(
        "fixed inset-0 z-0 [&_.cesium-viewer-bottom]:hidden",
        isGlobe ? "pointer-events-auto" : "pointer-events-none"
      )}
      style={{ display: isCanvasVisible ? undefined : "none" }}
    >
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
  );
}
