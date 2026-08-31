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

    const pointerEventsValue = isGlobe ? "auto" : "none";

    // Disable pointer events on canvas itself
    if (viewer.canvas) {
      viewer.canvas.style.pointerEvents = pointerEventsValue;
    }
    // Also disable on the viewer container so internal Cesium widget divs
    // don't intercept clicks on non-globe page content
    if (viewer.container) {
      (viewer.container as HTMLElement).style.pointerEvents = pointerEventsValue;
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
    const initialPointerEvents = isGlobeRoute ? "auto" : "none";
    if (viewer.canvas) {
      viewer.canvas.style.pointerEvents = initialPointerEvents;
    }
    // Also disable on viewer container so Cesium's internal widget divs
    // don't intercept clicks on non-globe page content
    if (viewer.container) {
      (viewer.container as HTMLElement).style.pointerEvents = initialPointerEvents;
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
    scene.backgroundColor = Color.fromCssColorString("hsl(220, 20%, 4%)");
    if (scene.skyBox) {
      scene.skyBox.show = true;
    }

    scene.globe.baseColor = Color.fromCssColorString("hsl(220, 20%, 6%)");
    scene.globe.showGroundAtmosphere = true;
    scene.globe.enableLighting = true;
    scene.globe.lightingFadeOutDistance = 10000000.0;
    scene.globe.lightingFadeInDistance = 20000000.0;

    if (scene.skyAtmosphere) {
      scene.skyAtmosphere.show = true;
      scene.skyAtmosphere.brightnessShift = 0.0;
      scene.skyAtmosphere.hueShift = 0.0;
      scene.skyAtmosphere.saturationShift = 0.1;
    }

    // Setup NASA GIBS WMTS high-resolution Earth satellite imagery layer
    const setupImagery = async () => {
      try {
        viewer.imageryLayers.removeAll();

        // 1. Try NASA GIBS BlueMarble / VIIRS TrueColor WMTS
        const gibsProvider = new WebMapTileServiceImageryProvider({
          url: "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{TileMatrix}/{TileRow}/{TileCol}.jpeg",
          layer: "BlueMarble_ShadedRelief_Bathymetry",
          style: "default",
          format: "image/jpeg",
          tileMatrixSetID: "GoogleMapsCompatible_Level8",
          maximumLevel: 8,
          credit: "NASA GIBS / Earthdata",
        });

        viewer.imageryLayers.addImageryProvider(gibsProvider);
      } catch (err) {
        console.warn("NASA GIBS tile fetch error — using World Imagery fallback:", err);
        try {
          const fallbackProvider = await createWorldImageryAsync();
          viewer.imageryLayers.removeAll();
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
