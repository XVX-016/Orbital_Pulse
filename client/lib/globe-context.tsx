import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from "react";
import { Viewer as CesiumViewer, CustomDataSource, Cartesian3, HeadingPitchRange, Color, EasingFunction } from "cesium";
import { fetchSatelliteCatalog, parseTLECatalog, HARDCODED_TLE_STRING, propagateSatellite, SatelliteData, SatellitePosition } from "@/lib/satellite-service";

interface GlobeContextType {
  viewerRef: React.MutableRefObject<CesiumViewer | null>;
  dataSourceRef: React.MutableRefObject<CustomDataSource | null>;
  satellites: SatelliteData[];
  selectedSat: SatelliteData | null;
  selectedPos: SatellitePosition | null;
  setSelectedSat: React.Dispatch<React.SetStateAction<SatelliteData | null>>;
  flyToSatellite: (sat: SatelliteData) => void;
  flyToView: (preset: "home" | "globe") => void;
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
  const [showSatellitePoints, setShowSatellitePoints] = useState(false);
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

  // Create satellite point entities when catalog updates
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
          show: showSatellitePoints as any,
          pixelSize: 6,
          color: Color.fromCssColorString("#06b6d4"), // Cyan for active satellites
          outlineColor: Color.fromCssColorString("#0284c7"),
          outlineWidth: 1.5,
        },
        properties: {
          satelliteData: sat,
        },
      });
    });
  }, [satellites]);

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
        prevEntity.point.pixelSize = 6 as any;
        prevEntity.point.color = Color.fromCssColorString("#06b6d4") as any;
      }
    }

    // Highlight new selection
    if (currentId) {
      const newEntity = dataSource.entities.getById(currentId);
      if (newEntity && newEntity.point) {
        newEntity.point.pixelSize = 10 as any;
        newEntity.point.color = Color.fromCssColorString("#38bdf8") as any;
      }
    }

    prevSelectedIdRef.current = currentId || null;
  }, [selectedSat?.noradId]);

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

  // Fly to satellite helper
  const flyToSatellite = useCallback((sat: SatelliteData) => {
    setSelectedSat(sat);
    const viewer = viewerRef.current;
    const dataSource = dataSourceRef.current;

    if (!viewer || viewer.isDestroyed() || !dataSource) return;

    const entity = dataSource.entities.getById(sat.noradId);
    if (entity) {
      viewer.flyTo(entity, {
        duration: 2.0,
        offset: new HeadingPitchRange(0, -Math.PI / 4, 3000000), // 3,000 km distance
      });
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
