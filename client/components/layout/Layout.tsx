import { ReactNode } from "react";
import { useLocation } from "react-router-dom";
import Navbar from "./Navbar";
import Footer from "./Footer";
import GlobeCanvas from "@/components/globe/GlobeCanvas";

export default function Layout({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const isGlobe = pathname === "/globe";
  const isMap = pathname === "/map";

  return (
    <div className="relative min-h-screen flex flex-col justify-between">
      <GlobeCanvas />
      <Navbar />
      <main className="flex-1">{children}</main>
      {!isGlobe && !isMap && <Footer />}
    </div>
  );
}
