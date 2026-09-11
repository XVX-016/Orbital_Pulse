import React, { useState, useEffect } from "react";
import { SatelliteData, propagateSatellite } from "@/lib/satellite-service";
import { X, Cpu, Info, Activity, Radio, Map } from "lucide-react";
import { cn } from "@/lib/utils";

interface SatelliteInfoPanelProps {
  satellite: SatelliteData;
  onClose: () => void;
}

export function SatelliteInfoPanel({ satellite, onClose }: SatelliteInfoPanelProps) {
  const [aiInfo, setAiInfo] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [telemetry, setTelemetry] = useState({
    altitude: 0,
    velocity: 0,
    lat: 0,
    lng: 0,
  });

  // Live telemetry update loop
  useEffect(() => {
    const updateTelemetry = () => {
      const pos = propagateSatellite(satellite.satrec, new Date());
      if (pos) {
        setTelemetry({
          altitude: pos.altitude,
          velocity: pos.velocity,
          lat: pos.latitude,
          lng: pos.longitude,
        });
      }
    };
    
    updateTelemetry();
    const interval = setInterval(updateTelemetry, 1000);
    return () => clearInterval(interval);
  }, [satellite]);

  // Fetch AI info
  useEffect(() => {
    const fetchAIInfo = async () => {
      setIsLoading(true);
      setError(null);
      setAiInfo(null);
      try {
        const res = await fetch("/api/ai/satellite-info", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: satellite.name, type: satellite.type })
        });
        
        if (!res.ok) {
          throw new Error("Failed to fetch AI data");
        }
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        setAiInfo(data.info);
      } catch (err: any) {
        setError(err.message || "An error occurred");
      } finally {
        setIsLoading(false);
      }
    };

    fetchAIInfo();
  }, [satellite.name, satellite.type]);

  return (
    <div className="absolute top-24 right-6 z-20 w-80 rounded-xl border border-border/80 bg-zinc-950/90 backdrop-blur-md shadow-2xl text-zinc-100 overflow-hidden flex flex-col pointer-events-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 bg-white/5 p-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/20 text-blue-400">
            <Radio className="h-5 w-5" />
          </div>
          <div>
            <h3 className="font-semibold tracking-tight">{satellite.name.replace('STARLINK-', 'Starlink ')}</h3>
            <p className="text-xs text-zinc-400 uppercase tracking-wider">{satellite.subType || satellite.type}</p>
          </div>
        </div>
        <button 
          onClick={onClose}
          className="rounded-md p-1 text-zinc-400 hover:bg-white/10 hover:text-white transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Telemetry */}
      <div className="grid grid-cols-2 gap-px bg-white/10">
        <div className="bg-zinc-950/80 p-3 flex flex-col gap-1">
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider flex items-center gap-1">
            <Activity className="h-3 w-3" /> Altitude
          </span>
          <span className="font-mono text-sm">{telemetry.altitude.toFixed(1)} km</span>
        </div>
        <div className="bg-zinc-950/80 p-3 flex flex-col gap-1">
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider flex items-center gap-1">
            <Activity className="h-3 w-3" /> Velocity
          </span>
          <span className="font-mono text-sm">{telemetry.velocity.toFixed(2)} km/s</span>
        </div>
        <div className="bg-zinc-950/80 p-3 flex flex-col gap-1 col-span-2">
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider flex items-center gap-1">
            <Map className="h-3 w-3" /> Sub-satellite Point
          </span>
          <span className="font-mono text-sm">
            {telemetry.lat.toFixed(4)}°, {telemetry.lng.toFixed(4)}°
          </span>
        </div>
      </div>

      {/* AI Summary */}
      <div className="p-4 border-t border-white/10 flex flex-col gap-3 relative">
        <div className="flex items-center gap-2 text-blue-400">
          <Cpu className="h-4 w-4" />
          <span className="text-xs font-semibold uppercase tracking-wider">AI Intelligence</span>
        </div>
        
        <div className="text-sm leading-relaxed text-zinc-300 min-h-[80px]">
          {isLoading ? (
            <div className="flex flex-col gap-2 animate-pulse mt-1">
              <div className="h-3 bg-zinc-800 rounded w-full"></div>
              <div className="h-3 bg-zinc-800 rounded w-5/6"></div>
              <div className="h-3 bg-zinc-800 rounded w-4/6"></div>
            </div>
          ) : error ? (
            <div className="text-red-400 flex items-start gap-2 bg-red-500/10 p-2 rounded border border-red-500/20">
              <Info className="h-4 w-4 mt-0.5 shrink-0" />
              <span className="text-xs">{error}</span>
            </div>
          ) : (
            <p className="animate-in fade-in slide-in-from-bottom-2 duration-500">{aiInfo}</p>
          )}
        </div>
      </div>
    </div>
  );
}
