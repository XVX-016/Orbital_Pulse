import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from "react";
import {
  Viewer as CesiumViewer,
  CustomDataSource,
  Cartesian3,
  HeadingPitchRange,
  BoundingSphere,
  Color,
  EasingFunction,
  PolylineGlowMaterialProperty,
} from "cesium";
import {
  fetchSatelliteCatalog,
  parseTLECatalog,
  HARDCODED_TLE_STRING,
  propagateSatellite,
  computePastOrbitPositions,
  SatelliteData,
  SatellitePosition,
} from "@/lib/satellite-service";

function getSatelliteColorStyle(sat: SatelliteData) {
  if (sat.isISRO) {
    return {
      color: Color.fromCssColorString("#f97316"), // Saffron / ISRO Orange
      outlineColor: Color.fromCssColorString("#ffedd5"),
      pixelSize: 9,
      outlineWidth: 2.5,
    };
  }

  switch (sat.type) {
    case "optical":
      return {
        color: Color.fromCssColorString("#3b82f6"), // Blue
        outlineColor: Color.fromCssColorString("#93c5fd"),
        pixelSize: 6,
        outlineWidth: 1.5,
      };
    case "sar":
      return {
        color: Color.fromCssColorString("#22c55e"), // Green
        outlineColor: Color.fromCssColorString("#86efac"),
        pixelSize: 6,
        outlineWidth: 1.5,
      };
    case "weather":
      return {
        color: Color.fromCssColorString("#f59e0b"), // Amber
        outlineColor: Color.fromCssColorString("#fde68a"),
        pixelSize: 6,
        outlineWidth: 1.5,
      };
    case "comms":
    default:
      return {
        color: Color.fromCssColorString("#9ca3af"), // Grey
        outlineColor: Color.fromCssColorString("#e5e7eb"),
        pixelSize: 6,
        outlineWidth: 1.5,
      };
  }
}

interface GlobeContextType {
  viewerRef: React.MutableRefObject<CesiumViewer | null>;
  dataSourceRef: React.MutableRefObject<CustomDataSource | null>;
  satellites: SatelliteData[];
  selectedSat: SatelliteData | null;
  selectedPos: SatellitePosition | null;
  setSelectedSat: React.Dispatch<React.SetStateAction<SatelliteData | null>>;
  flyToSatellite: (sat: SatelliteData) => void;
  flyToView: (preset: "home" | "globe") => void;
  flyToLocation: (lat: number, lng: number, altitude?: number) => void;
  showSatellitePoints: boolean;
  setShowSatellitePoints: React.Dispatch<React.SetStateAction<boolean>>;
  isPlaying: boolean;
  setIsPlaying: React.Dispatch<React.SetStateAction<boolean>>;
  catalogSource: string;
  error: string | null;
}

const GlobeContext = createContext<GlobeContextType | null>(null);

export function GlobeProvider({ children }: { children: React.ReactNode }) {
  const [isPlaying, setIsPlaying] = useState(true);
  const [showSatellitePoints, setShowSatellitePoints] = useState(true);
  const [satellites, setSatellites] = useState<SatelliteData[]>(() => parseTLECatalog(HARDCODED_TLE_STRING));
  const [selectedSat, setSelectedSat] = useState<SatelliteData | null>(null);
  const [selectedPos, setSelectedPos] = useState<SatellitePosition | null>(null);
  const [catalogSource, setCatalogSource] = useState<string>("Offline Catalog");
  const [error, setError] = useState<string | null>(null);

  const viewerRef = useRef<CesiumViewer | null>(null);
  const dataSourceRef = useRef<CustomDataSource | null>(null);
  const isPlayingRef = useRef(isPlaying);
  isPlayingRef.current = isPlaying;

  // Load Satellite TLE catalog
  useEffect(() => {
    let isMounted = true;
    fetchSatelliteCatalog()
      .then((result) => {
        if (!isMounted) return;
        setSatellites(result.satellites);
        setCatalogSource(result.source === "live" ? "Orbit Service" : "Offline Catalog");
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

  // Toggle satellite point visibility without removing entities
  useEffect(() => {
    const dataSource = dataSourceRef.current;
    if (!dataSource) return;

    const entities = dataSource.entities.values;
    for (let i = 0; i < entities.length; i++) {
      if (entities[i].point) {
        entities[i].point.show = showSatellitePoints as any;
      }
    }
  }, [showSatellitePoints]);

  // Create satellite point entities & orbit trails when catalog updates
  useEffect(() => {
    const dataSource = dataSourceRef.current;
    if (!dataSource || satellites.length === 0) return;

    dataSource.entities.removeAll();

    const now = new Date();
    satellites.forEach((sat) => {
      const pos = propagateSatellite(sat.satrec, now);
      if (!pos) return;

      const positionCartesian = Cartesian3.fromDegrees(pos.longitude, pos.latitude, pos.altitude * 1000);
      const style = getSatelliteColorStyle(sat);

      const pastPts = computePastOrbitPositions(sat.satrec, now, 18, 45);
      const trailCartesians = pastPts.map((p) => Cartesian3.fromDegrees(p.longitude, p.latitude, p.altitude * 1000));

      dataSource.entities.add({
        id: sat.noradId,
        name: sat.name,
        position: positionCartesian as any,
        point: {
          show: showSatellitePoints as any,
          pixelSize: style.pixelSize,
          color: style.color,
          outlineColor: style.outlineColor,
          outlineWidth: style.outlineWidth,
        },
        polyline: {
          positions: trailCartesians as any,
          width: sat.isISRO ? 2.0 : 1.5,
          material: new PolylineGlowMaterialProperty({
            glowPower: 0.15,
            taperPower: 0.7,
            color: style.color.withAlpha(sat.isISRO ? 0.6 : 0.35),
          }),
        },
        properties: {
          satelliteData: sat,
        },
      });
    });
  }, [satellites, showSatellitePoints]);

  // Update selection highlight without removing entities
  const prevSelectedIdRef = useRef<string | null>(null);

  useEffect(() => {
    const dataSource = dataSourceRef.current;
    if (!dataSource) return;

    const prevId = prevSelectedIdRef.current;
    const currentId = selectedSat?.noradId;

    if (prevId === currentId) return;

    // Revert previous selection
    if (prevId) {
      const prevEntity = dataSource.entities.getById(prevId);
      if (prevEntity && prevEntity.point) {
        const satData: SatelliteData | undefined = prevEntity.properties?.satelliteData?.getValue();
        if (satData) {
          const style = getSatelliteColorStyle(satData);
          prevEntity.point.pixelSize = style.pixelSize as any;
          prevEntity.point.color = style.color as any;
        } else {
          prevEntity.point.pixelSize = 6 as any;
          prevEntity.point.color = Color.fromCssColorString("#06b6d4") as any;
        }
      }
    }

    // Highlight new selection
    if (currentId) {
      const newEntity = dataSource.entities.getById(currentId);
      if (newEntity && newEntity.point) {
        newEntity.point.pixelSize = 12 as any;
        newEntity.point.color = Color.fromCssColorString("#38bdf8") as any;
      }
    }

    prevSelectedIdRef.current = currentId || null;
  }, [selectedSat?.noradId]);

  // Throttled clock update loop (recomputes satellite positions every 1 second and trails periodically)
  useEffect(() => {
    let tickCount = 0;
    const interval = setInterval(() => {
      if (!isPlayingRef.current) return;
      const dataSource = dataSourceRef.current;
      if (!dataSource || satellites.length === 0) return;

      const now = new Date();
      tickCount++;

      satellites.forEach((sat) => {
        const pos = propagateSatellite(sat.satrec, now);
        if (!pos) return;

        const entity = dataSource.entities.getById(sat.noradId);
        if (entity) {
          entity.position = Cartesian3.fromDegrees(pos.longitude, pos.latitude, pos.altitude * 1000) as any;
          // Update orbit trail every 4 seconds to maintain smooth trail movement
          if (tickCount % 4 === 0 && entity.polyline) {
            const pastPts = computePastOrbitPositions(sat.satrec, now, 18, 45);
            entity.polyline.positions = pastPts.map((p) =>
              Cartesian3.fromDegrees(p.longitude, p.latitude, p.altitude * 1000)
            ) as any;
          }
        }
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [satellites]);

  // Fly to satellite helper
  const flyToSatellite = useCallback((sat: SatelliteData) => {
    setSelectedSat(sat);
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    // Use flyToBoundingSphere centered on the satellite's exact Cartesian3 position.
    // This guarantees the satellite dot is centered on screen and camera orbits it at
    // the given range distance. We avoid viewer.flyTo(entity) because the entity now
    // includes a polyline trail spanning thousands of km, which blows out the bounding sphere.
    const pos = propagateSatellite(sat.satrec, new Date());
    if (pos) {
      const target = Cartesian3.fromDegrees(pos.longitude, pos.latitude, pos.altitude * 1000);
      // Tiny radius bounding sphere centered on the satellite so flyToBoundingSphere
      // centers the dot exactly in frame, orbiting at 3,000 km range.
      viewer.camera.flyToBoundingSphere(
        new BoundingSphere(target, 1),
        {
          duration: 2.0,
          offset: new HeadingPitchRange(0, -Math.PI / 5, 3000000),
        }
      );
    }
  }, []);

  // Fly to view preset helper
  const flyToView = useCallback((preset: "home" | "globe") => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    if (preset === "home") {
      viewer.camera.flyTo({
        destination: Cartesian3.fromDegrees(0.0, 20.0, 18000000),
        orientation: {
          heading: 0.0,
          pitch: -Math.PI / 2,
          roll: 0.0,
        },
        duration: 2.0,
        easingFunction: EasingFunction.QUADRATIC_IN_OUT,
      });
    } else if (preset === "globe") {
      viewer.camera.flyTo({
        destination: Cartesian3.fromDegrees(0.0, 20.0, 12500000),
        orientation: {
          heading: 0.0,
          pitch: -Math.PI / 2,
          roll: 0.0,
        },
        duration: 2.0,
        easingFunction: EasingFunction.QUADRATIC_IN_OUT,
      });
    }
  }, []);

  // Fly to specific coordinates helper (e.g. EONET Earth Event focus)
  const flyToLocation = useCallback((lat: number, lng: number, altitude: number = 2500000) => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(lng, lat, altitude),
      orientation: {
        heading: 0.0,
        pitch: -Math.PI / 3, // slightly angled top-down perspective
        roll: 0.0,
      },
      duration: 2.5,
      easingFunction: EasingFunction.QUADRATIC_IN_OUT,
    });
  }, []);

  return (
    <GlobeContext.Provider
      value={{
        viewerRef,
        dataSourceRef,
        satellites,
        selectedSat,
        selectedPos,
        setSelectedSat,
        flyToSatellite,
        flyToView,
        flyToLocation,
        showSatellitePoints,
        setShowSatellitePoints,
        isPlaying,
        setIsPlaying,
        catalogSource,
        error,
      }}
    >
      {children}
    </GlobeContext.Provider>
  );
}

export function useGlobe() {
  const context = useContext(GlobeContext);
  if (!context) {
    throw new Error("useGlobe must be used within a GlobeProvider");
  }
  return context;
}
