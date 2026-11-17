import React, { useState, useEffect, useRef } from "react";
import { api } from "../api.js";
import { Card, Badge, StatBox } from "../components/ui.jsx";
import { cyberAudio } from "../utils/cyberAudio.js";

export default function GeographicProfilingView({ caseRef }) {
  const [loading, setLoading] = useState(true);
  const [geoData, setGeoData] = useState(null);
  const [bufferRadius, setBufferRadius] = useState(1.2);
  const [decayExponent, setDecayExponent] = useState(1.3);
  const [isProfiling, setIsProfiling] = useState(false);
  const canvasRef = useRef(null);
  const animRef = useRef(null);

  const fetchProfile = async () => {
    setIsProfiling(true);
    cyberAudio.playScan?.();
    try {
      const res = await api("/ml/spatial/profile", {
        method: "POST",
        body: {
          case_id: caseRef,
          buffer_radius_km: bufferRadius,
          decay_exponent: decayExponent,
          grid_size: 26,
        },
      });
      setGeoData(res);
    } catch (err) {
      console.error("Geographic profile failed", err);
    } finally {
      setLoading(false);
      setIsProfiling(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, [caseRef, bufferRadius, decayExponent]);

  // Render Interactive Canvas 2D Jeopardy Surface & Incident Heatmap
  useEffect(() => {
    if (!geoData || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    const bbox = geoData.bounding_box;

    const toX = (lng) => {
      return ((lng - bbox.min_lng) / (bbox.max_lng - bbox.min_lng)) * (width - 100) + 50;
    };
    const toY = (lat) => {
      // Invert Y for screen coordinates
      return height - (((lat - bbox.min_lat) / (bbox.max_lat - bbox.min_lat)) * (height - 100) + 50);
    };

    let phase = 0;

    const render = () => {
      ctx.clearRect(0, 0, width, height);
      phase += 0.04;

      // Dark Tactical Radar Background
      ctx.fillStyle = "#070b14";
      ctx.fillRect(0, 0, width, height);

      // Coordinate Grid Lines
      ctx.strokeStyle = "rgba(30, 58, 95, 0.35)";
      ctx.lineWidth = 1;
      const step = 45;
      for (let x = 0; x < width; x += step) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      for (let y = 0; y < height; y += step) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      // Draw Rossmo's Jeopardy Probability Surface Cells
      geoData.jeopardy_surface_points?.forEach((pt) => {
        const px = toX(pt.lng);
        const py = toY(pt.lat);
        const radius = 14 + pt.intensity * 12;

        const grad = ctx.createRadialGradient(px, py, 2, px, py, radius);
        if (pt.probability > 75) {
          grad.addColorStop(0, `rgba(244, 63, 94, ${pt.intensity * 0.7})`);
          grad.addColorStop(1, "rgba(244, 63, 94, 0)");
        } else if (pt.probability > 45) {
          grad.addColorStop(0, `rgba(245, 158, 11, ${pt.intensity * 0.5})`);
          grad.addColorStop(1, "rgba(245, 158, 11, 0)");
        } else {
          grad.addColorStop(0, `rgba(6, 182, 212, ${pt.intensity * 0.35})`);
          grad.addColorStop(1, "rgba(6, 182, 212, 0)");
        }

        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(px, py, radius, 0, Math.PI * 2);
        ctx.fill();
      });

      // Draw Crime Scene Incident Markers
      geoData.crime_sites?.forEach((site, idx) => {
        const sx = toX(site.lng);
        const sy = toY(site.lat);

        // Incident Pin Outer Glow
        ctx.beginPath();
        ctx.arc(sx, sy, 8, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(56, 189, 248, 0.4)";
        ctx.fill();

        // Incident Pin Center
        ctx.beginPath();
        ctx.arc(sx, sy, 4, 0, Math.PI * 2);
        ctx.fillStyle = "#38BDF8";
        ctx.fill();
        ctx.strokeStyle = "#FFFFFF";
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Label
        ctx.font = "bold 9px monospace";
        ctx.fillStyle = "#E2E8F0";
        ctx.textAlign = "left";
        ctx.fillText(site.id, sx + 10, sy - 2);
        ctx.font = "8px sans-serif";
        ctx.fillStyle = "#94A3B8";
        ctx.fillText(site.name.split(" (")[0], sx + 10, sy + 8);
      });

      // Draw Predicted Offender Anchor Point Target Reticle
      const anchor = geoData.predicted_anchor_point;
      if (anchor) {
        const ax = toX(anchor.lng);
        const ay = toY(anchor.lat);
        const pulseR = 18 + Math.sin(phase * 2) * 4;

        // Animated Outer Pulse Circle
        ctx.beginPath();
        ctx.arc(ax, ay, pulseR + 8, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(244, 63, 94, ${0.4 + Math.sin(phase * 3) * 0.3})`;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 4]);
        ctx.stroke();
        ctx.setLineDash([]);

        // Crosshairs
        ctx.strokeStyle = "#F43F5E";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(ax - 28, ay);
        ctx.lineTo(ax - 8, ay);
        ctx.moveTo(ax + 8, ay);
        ctx.lineTo(ax + 28, ay);
        ctx.moveTo(ax, ay - 28);
        ctx.lineTo(ax, ay - 8);
        ctx.moveTo(ax, ay + 8);
        ctx.lineTo(ax, ay + 28);
        ctx.stroke();

        // Center Point
        ctx.beginPath();
        ctx.arc(ax, ay, 4, 0, Math.PI * 2);
        ctx.fillStyle = "#F43F5E";
        ctx.fill();

        // Anchor Badge Box
        ctx.fillStyle = "rgba(127, 29, 29, 0.9)";
        ctx.strokeStyle = "#F43F5E";
        ctx.lineWidth = 1;
        ctx.fillRect(ax + 24, ay - 22, 175, 42);
        ctx.strokeRect(ax + 24, ay - 22, 175, 42);

        ctx.font = "bold 9px monospace";
        ctx.fillStyle = "#FECDD3";
        ctx.textAlign = "left";
        ctx.fillText("★ PREDICTED ANCHOR POINT", ax + 30, ay - 9);
        ctx.font = "8.5px monospace";
        ctx.fillStyle = "#FDE047";
        ctx.fillText(`CONFIDENCE: ${anchor.probability_confidence}%`, ax + 30, ay + 3);
        ctx.font = "7.5px monospace";
        ctx.fillStyle = "#CBD5E1";
        ctx.fillText(`GEO: ${anchor.lat.toFixed(4)}°N, ${anchor.lng.toFixed(4)}°E`, ax + 30, ay + 14);
      }

      animRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [geoData]);

  if (loading) {
    return (
      <div className="p-8 text-center font-mono text-cyan">
        <span className="cm-pulse-dot" /> COMPUTING ROSSMO'S JEOPARDY SURFACE & SPATIAL DECAY MANIFOLD...
      </div>
    );
  }

  const anchor = geoData?.predicted_anchor_point;

  return (
    <div className="space-y-6">
      {/* Top Banner Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border-subtle pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xl">🗺️</span>
            <h1 className="text-2xl font-bold tracking-wider text-white uppercase">
              Geographic Profiling & Spatial Forecasting
            </h1>
            <Badge tone="cyan">Rossmo's Criminology Algorithm</Badge>
          </div>
          <p className="text-xs text-muted font-mono mt-1">
            Serial Offender Spatial Modeling + Buffer Zone Penalty + Distance Decay Probability Surface
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            className="btn btn-outline border-cyan text-cyan hover:bg-cyan hover:text-black font-mono text-xs px-3 py-1.5"
            onClick={fetchProfile}
            disabled={isProfiling}
          >
            {isProfiling ? "🔄 COMPUTING..." : "⚡ RECALCULATE JEOPARDY SURFACE"}
          </button>
        </div>
      </div>

      {/* 4 Stat Metric KPI Boxes */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatBox
          label="CRIME SITES LINKED"
          value={geoData?.incidents_count || 0}
          caption="Geocoded Locations"
          accent="cyan"
        />
        <StatBox
          label="BUFFER ZONE RADIUS"
          value={`${geoData?.buffer_radius_km || 1.2} km`}
          caption="Home Proximity Penalty"
          accent="gold"
        />
        <StatBox
          label="ANCHOR CONFIDENCE"
          value={`${anchor?.probability_confidence || 0}%`}
          caption="Probability Peak Mode"
          accent="magenta"
        />
        <StatBox
          label="SPATIAL DISPERSION"
          value={`${geoData?.spatial_center?.standard_dispersion_km || 0} km`}
          caption="Standard Distance"
          accent="emerald"
        />
      </div>

      {/* Main Grid: Interactive Canvas Map + Control Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Interactive Canvas Map */}
        <div className="lg:col-span-2 space-y-3">
          <Card className="p-4 bg-slate-900/60 border border-border-subtle relative overflow-hidden">
            <div className="flex items-center justify-between mb-3 text-xs font-mono">
              <span className="text-cyan font-bold">
                2D JEOPARDY SURFACE PROJECTION // ROSSMO PROBABILITY DENSITY
              </span>
              <span className="text-muted">GRID RESOLUTION: {geoData?.grid_resolution}</span>
            </div>

            <canvas
              ref={canvasRef}
              width={750}
              height={440}
              className="w-full h-[440px] rounded bg-[#070b14] border border-cyan/30 shadow-inner"
            />

            <div className="flex items-center justify-between mt-3 text-[11px] font-mono text-muted">
              <div className="flex items-center gap-4">
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-cyan inline-block" /> Geocoded Crime Site
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block" /> High Jeopardy Zone (&gt;75%)
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-gold inline-block" /> Moderate Jeopardy Zone (&gt;45%)
                </span>
              </div>
              <span className="text-rose-400 font-bold">🎯 Crosshair = Predicted Offender Hideout</span>
            </div>
          </Card>

          {/* Linked Crime Incident Coordinates Table */}
          <Card className="p-4 border border-border-subtle bg-slate-900/40">
            <h3 className="text-sm font-bold tracking-wide text-white uppercase mb-3 flex items-center gap-2">
              <span>📍</span> Geocoded Serial Incidents (Input Spatial Vector)
            </h3>
            <div className="space-y-2 font-mono text-xs">
              {geoData?.crime_sites?.map((site) => (
                <div
                  key={site.id}
                  className="flex flex-wrap items-center justify-between p-2.5 rounded bg-slate-800/40 border border-slate-700/50"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-cyan font-bold">{site.id}</span>
                    <span className="text-white font-medium">{site.name}</span>
                  </div>
                  <div className="flex items-center gap-3 text-muted">
                    <span>{site.incident_type}</span>
                    <span className="text-gold font-bold">
                      {site.lat.toFixed(4)}°N, {site.lng.toFixed(4)}°E
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Right Col: Offender Anchor Intelligence & Hyperparameters */}
        <div className="space-y-4">
          {/* Predicted Anchor Intelligence Card */}
          {anchor && (
            <Card className="p-5 border-2 border-rose-500/50 bg-rose-950/20 shadow-lg">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono text-rose-400 font-bold">TARGET LOCATION PREDICTED</span>
                <Badge tone="red">{anchor.probability_confidence}% CERTAINTY</Badge>
              </div>
              <h2 className="text-lg font-bold text-white mt-1">{anchor.estimated_location_type}</h2>
              <div className="text-xs font-mono text-gold mb-3">
                COORDINATES: {anchor.lat.toFixed(5)}°N, {anchor.lng.toFixed(5)}°E
              </div>

              <div className="space-y-2 text-xs font-mono border-t border-rose-500/30 pt-3">
                <div className="flex justify-between">
                  <span className="text-muted">Distance from Centroid:</span>
                  <span className="text-white font-bold">{anchor.distance_from_centroid_km} km</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted">Buffer Zone Penalty:</span>
                  <span className="text-cyan font-bold">{bufferRadius} km exclusion</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted">Algorithm Model:</span>
                  <span className="text-gold font-bold">Rossmo Manhattan Metric</span>
                </div>
              </div>

              <p className="mt-3 text-xs text-slate-300 italic">
                Highest probability intersection of offender travel decay curves. Recommended for immediate tactical surveillance team deployment and search warrant prioritization.
              </p>
            </Card>
          )}

          {/* Hyperparameter Tuning Sliders */}
          <Card className="p-4 border border-cyan/40 bg-slate-900/70 space-y-4">
            <span className="text-xs font-mono text-cyan font-bold block">
              ROSSMO'S HYPERPARAMETER TUNER
            </span>

            {/* Buffer Radius Slider */}
            <div>
              <div className="flex justify-between text-xs font-mono mb-1">
                <span className="text-muted">Buffer Radius B (Home Exclusion):</span>
                <span className="text-gold font-bold">{bufferRadius} km</span>
              </div>
              <input
                type="range"
                min="0.4"
                max="3.0"
                step="0.1"
                value={bufferRadius}
                onChange={(e) => setBufferRadius(parseFloat(e.target.value))}
                className="w-full accent-gold"
              />
              <span className="text-[10px] text-muted block mt-0.5">
                Criminological buffer zone where offender avoids committing crimes near home base.
              </span>
            </div>

            {/* Distance Decay Slider */}
            <div>
              <div className="flex justify-between text-xs font-mono mb-1">
                <span className="text-muted">Distance Decay Exponent f:</span>
                <span className="text-cyan font-bold">{decayExponent}</span>
              </div>
              <input
                type="range"
                min="0.8"
                max="2.5"
                step="0.1"
                value={decayExponent}
                onChange={(e) => setDecayExponent(parseFloat(e.target.value))}
                className="w-full accent-cyan"
              />
              <span className="text-[10px] text-muted block mt-0.5">
                Exponential decay coefficient governing offender travel friction.
              </span>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
