import React, { useEffect, useRef, useState } from "react";
import { cyberAudio } from "../utils/cyberAudio.js";

export function HoloGlobe({ width = 120, height = 120, interactive = false }) {
  const canvasRef = useRef(null);
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId = null;
    let rotation = 0;

    const w = canvas.width;
    const h = canvas.height;
    const cx = w / 2;
    const cy = h / 2;
    const radius = Math.min(cx, cy) - 10;

    const incidents = [
      { name: "Green Park", lat: 19.076, lon: 72.877, color: "#00E6A0" },
      { name: "Riverside Warehouse", lat: 19.112, lon: 72.890, color: "#FF2A3D" },
      { name: "Ferry Landing", lat: 19.095, lon: 72.845, color: "#FFB020" },
    ];

    const render = () => {
      ctx.clearRect(0, 0, w, h);
      rotation += 0.015;

      // Outer Glow Aura
      const grad = ctx.createRadialGradient(cx, cy, radius * 0.4, cx, cy, radius * 1.1);
      grad.addColorStop(0, "rgba(0, 229, 255, 0.08)");
      grad.addColorStop(0.8, "rgba(0, 229, 255, 0.02)");
      grad.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, cy, radius * 1.1, 0, Math.PI * 2);
      ctx.fill();

      // Outer Sphere Border
      ctx.strokeStyle = "rgba(0, 229, 255, 0.45)";
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.stroke();

      // Latitude Parallels
      const latSteps = [-0.65, -0.35, 0, 0.35, 0.65];
      latSteps.forEach((latFrac) => {
        const yOffset = latFrac * radius;
        const rAtY = Math.sqrt(Math.max(0, radius * radius - yOffset * yOffset));
        ctx.strokeStyle = latFrac === 0 ? "rgba(0, 230, 160, 0.5)" : "rgba(0, 229, 255, 0.18)";
        ctx.lineWidth = latFrac === 0 ? 1.4 : 0.8;
        ctx.beginPath();
        ctx.ellipse(cx, cy + yOffset, rAtY, rAtY * 0.28, 0, 0, Math.PI * 2);
        ctx.stroke();
      });

      // Rotating Longitude Meridians
      const numMeridians = 8;
      for (let i = 0; i < numMeridians; i++) {
        const baseAngle = (i * Math.PI) / numMeridians + rotation;
        const scaleX = Math.cos(baseAngle);
        const isFront = Math.sin(baseAngle) >= 0;

        ctx.strokeStyle = isFront ? "rgba(0, 229, 255, 0.28)" : "rgba(0, 229, 255, 0.07)";
        ctx.lineWidth = isFront ? 1 : 0.6;
        ctx.beginPath();
        ctx.ellipse(cx, cy, radius * Math.abs(scaleX), radius, 0, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Sweeping Circular Radar Scanner
      ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.clip();

      const scanAngle = (rotation * 2.2) % (Math.PI * 2);
      const sweepGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
      sweepGrad.addColorStop(0, "rgba(0, 229, 255, 0.2)");
      sweepGrad.addColorStop(1, "rgba(0, 229, 255, 0.0)");

      ctx.fillStyle = sweepGrad;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, radius, scanAngle - 0.4, scanAngle);
      ctx.lineTo(cx, cy);
      ctx.fill();
      ctx.restore();

      // Pulsing Crime Scene Beacon Points
      incidents.forEach((inc, idx) => {
        const phi = (inc.lat * Math.PI) / 180;
        const theta = ((inc.lon * 3) * Math.PI) / 180 + rotation;

        const x = cx + Math.cos(phi) * Math.sin(theta) * (radius * 0.92);
        const y = cy - Math.sin(phi) * (radius * 0.92);
        const z = Math.cos(phi) * Math.cos(theta);

        if (z > -0.2) {
          const pulse = (Math.sin(rotation * 6 + idx) + 1) / 2;
          ctx.beginPath();
          ctx.arc(x, y, 3 + pulse * 2.5, 0, Math.PI * 2);
          ctx.fillStyle = inc.color;
          ctx.fill();

          ctx.strokeStyle = inc.color;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.arc(x, y, 5 + pulse * 4, 0, Math.PI * 2);
          ctx.stroke();
        }
      });

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      if (animId) cancelAnimationFrame(animId);
    };
  }, [width, height, isExpanded]);

  const toggleExpand = () => {
    try { cyberAudio?.playClickChirp?.(); } catch {}
    setIsExpanded((prev) => !prev);
  };

  return (
    <div className={`cm-holo-globe-wrapper ${isExpanded ? "expanded-modal" : ""}`}>
      <div
        className="cm-holo-globe-container"
        onClick={toggleExpand}
        title="Click to inspect 3D Geospatial Surveillance Radar"
        style={{ width, height }}
      >
        <canvas ref={canvasRef} width={width} height={height} className="cm-holo-globe-canvas" />
        <div className="cm-holo-globe-hud font-mono text-xs">
          <span className="cm-pulse-emerald" />
          <span className="text-cyan">GEOINT 3D</span>
        </div>
      </div>

      {isExpanded && (
        <div className="cm-holo-globe-backdrop" onClick={toggleExpand}>
          <div className="cm-holo-globe-modal" onClick={(e) => e.stopPropagation()}>
            <div className="row justify-between items-center" style={{ marginBottom: 12 }}>
              <div className="row items-center gap-2 font-mono">
                <span className="cm-pulse-emerald" />
                <strong className="text-cyan">HOLOGRAPHIC 3D CRIME SCENE GEOLOCATION RADAR</strong>
              </div>
              <button className="cm-filter-pill" onClick={toggleExpand}>
                ✕ Close
              </button>
            </div>

            <div style={{ display: "flex", justifyContent: "center", padding: "16px 0" }}>
              <canvas
                ref={canvasRef}
                width={360}
                height={360}
                style={{ width: 360, height: 360, borderRadius: "50%", background: "radial-gradient(circle, rgba(0,229,255,0.06) 0%, rgba(5,8,17,0.9) 70%)" }}
              />
            </div>

            <div className="row justify-between font-mono text-xs text-muted" style={{ marginTop: 10 }}>
              <span>ACTIVE BEACONS: GREEN PARK (19.076° N) · RIVERSIDE (19.112° N)</span>
              <span>WGS-84 PROJECTION · 60 FPS ORBITAL SWEEP</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
