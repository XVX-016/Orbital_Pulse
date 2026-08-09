import { ReactNode } from "react";
import { useLocation } from "react-router-dom";
import Navbar from "./Navbar";

export default function Layout({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const isGlobeRoute = pathname === "/globe";

  return (
    <div className="min-h-screen bg-background">
      <Navbar />
      <main>{children}</main>
      {!isGlobeRoute && (
        <footer className="border-t border-border px-6 py-8">
          <div className="mx-auto flex max-w-[1400px] flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
            <p className="label-micro">
              ORBITAL MISSION CONTROL &mdash; TRACKING NETWORK
            </p>
            <p className="text-caption text-muted-foreground">
              Data simulated for demonstration purposes.
            </p>
          </div>
        </footer>
      )}
    </div>
  );
}
