import "./global.css";

import { Toaster } from "@/components/ui/toaster";
import { createRoot } from "react-dom/client";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "@/components/layout/Layout";
import Index from "./pages/Index";
import Analyze from "./pages/Analyze";
import About from "./pages/About";
import Globe from "./pages/Globe";
import MapView from "./pages/MapView";
import NotFound from "./pages/NotFound";
import { GlobeProvider } from "@/lib/globe-context";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <GlobeProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <Layout>
            <Routes>
              <Route path="/" element={<Index />} />
              <Route path="/globe" element={<Globe />} />
              <Route path="/analyze" element={<Analyze />} />
              <Route path="/about" element={<About />} />
              <Route path="/map" element={<MapView />} />
              {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Layout>
        </BrowserRouter>
      </TooltipProvider>
    </GlobeProvider>
  </QueryClientProvider>
);

createRoot(document.getElementById("root")!).render(<App />);
