import { ReactNode } from "react";
import Navbar from "./Navbar";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-screen">
      <Navbar />
      <main>{children}</main>
      <footer className="relative z-10 border-t border-border px-6 py-8 bg-background">
        <div className="mx-auto flex max-w-[1400px] flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
          <p className="label-micro">SATQUERY AI &mdash; REMOTE-SENSING VQA &amp; CHANGE ANALYSIS</p>
          <p className="text-caption text-muted-foreground">
            Multi-modal Earth Observation &amp; Agentic Intelligence
          </p>
        </div>
      </footer>
    </div>
  );
}
