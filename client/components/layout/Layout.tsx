import { ReactNode, useEffect } from "react";
import { useLocation } from "react-router-dom";
import Navbar from "./Navbar";
import { GlobeProvider, useGlobe } from "@/lib/globe-context";
import GlobeCanvas from "@/components/globe/GlobeCanvas";

function GlobeNavigationController() {
  const { pathname } = useLocation();
  const { flyToView, setShowSatellitePoints } = useGlobe();

  useEffect(() => {
    if (pathname === "/globe") {
      flyToView("globe");
      setShowSatellitePoints(true);
    } else {
      flyToView("home");
      setShowSatellitePoints(false);
    }
  }, [pathname, flyToView, setShowSatellitePoints]);

  return null;
}

export default function Layout({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const isGlobeRoute = pathname === "/globe";

  return (
    <GlobeProvider>
      <GlobeCanvas />
      <GlobeNavigationController />
      <div className="pointer-events-none relative z-10 min-h-screen">
        <Navbar />
        <main className="pointer-events-none">{children}</main>
        {!isGlobeRoute && (
          <footer className="pointer-events-auto relative z-10 border-t border-border px-6 py-8 bg-background">
            <div className="mx-auto flex max-w-[1400px] flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
              <p className="label-micro">
                ORBITAL PULSE MISSION CONTROL &mdash; TRACKING NETWORK
              </p>
              <p className="text-caption text-muted-foreground">
                Live data via NASA EONET &amp; CelesTrak
              </p>
            </div>
          </footer>
        )}
      </div>
    </GlobeProvider>
  );
}
