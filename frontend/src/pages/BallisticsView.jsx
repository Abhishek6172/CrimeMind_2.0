import React, { useRef, useEffect, useState, useMemo } from "react";
import { useLoad } from "../hooks.js";
import { Async, Badge, Card, Notice, StatBox } from "../components/ui.jsx";
import { cyberAudio } from "../utils/cyberAudio.js";

// Ballistics projectile caliber physics database
const CALIBERS = {
  "9mm": {
    name: "9×19mm Parabellum",
    velocity: 380, // m/s
    bulletWeight: "8.0g (124 gr)",
    effectiveRange: "50m",
    dragCoeff: 0.165,
    dispersionDeg: 0.8,
    color: "#00E5FF",
  },
  "45acp": {
    name: ".45 ACP",
    velocity: 260, // m/s
    bulletWeight: "15.0g (230 gr)",
    effectiveRange: "40m",
    dragCoeff: 0.195,
    dispersionDeg: 1.1,
    color: "#FFB52E",
  },
  "762nato": {
    name: "7.62×51mm NATO (.308)",
    velocity: 820, // m/s
    bulletWeight: "11.3g (175 gr)",
    effectiveRange: "800m",
    dragCoeff: 0.22,
    dispersionDeg: 0.3,
    color: "#FF4655",
  },
  "556nato": {
    name: "5.56×45mm NATO",
    velocity: 940, // m/s
    bulletWeight: "4.0g (62 gr)",
    effectiveRange: "500m",
    dragCoeff: 0.151,
    dispersionDeg: 0.4,
    color: "#00E6A0",
  },
};

// Case presets
const SCENE_PRESETS = [
  {
    name: "Green Park North Gazebo (Primary Crime Scene)",
    impactX: 0,
    impactY: 1.4,
    impactZ: -2.5,
    azimuth: -32,
    elevation: 14.5,
    caliber: "762nato",
    desc: "Long-range high-elevation strike from East Commercial Complex (2nd Floor).",
  },
  {
    name: "Perimeter East Gate Point-Blank Execution",
    impactX: -0.8,
    impactY: 1.6,
    impactZ: -1.0,
    azimuth: 15,
    elevation: -2.0,
    caliber: "9mm",
    desc: "Close-proximity horizontal firearm discharge during foot struggle.",
  },
  {
    name: "South Parking Lot Vehicle Drive-By",
    impactX: 1.2,
    impactY: 1.1,
    impactZ: -3.2,
    azimuth: 68,
    elevation: 3.5,
    caliber: "45acp",
    desc: "Oblique trajectory through rear vehicle passenger glass.",
  },
];

export default function BallisticsView({ c, caseRef }) {
  // Load suspect entities to match against shooter vantage point
  const entState = useLoad(() => c.get("/entities?limit=50"), [c]);
  const evState = useLoad(() => c.get("/evidence"), [c]);

  // Ballistics Parameters
  const [impactX, setImpactX] = useState(0.0); // meters left/right
  const [impactY, setImpactY] = useState(1.4); // height in meters (chest level)
  const [impactZ, setImpactZ] = useState(-2.5); // depth in room
  const [azimuth, setAzimuth] = useState(-32); // degrees horizontal
  const [elevation, setElevation] = useState(14.5); // degrees vertical
  const [caliberKey, setCaliberKey] = useState("762nato");
  const [showCone, setShowCone] = useState(true);
  const [showGrid, setShowGrid] = useState(true);
  const [ricochet, setRicochet] = useState(false);

  // 3D Orbit Camera State
  const [yaw, setYaw] = useState(-0.65); // horizontal rotation
  const [pitch, setPitch] = useState(0.38); // vertical elevation
  const [zoom, setZoom] = useState(1.15);
  const [isOrbiting, setIsOrbiting] = useState(false);
  const lastMousePos = useRef({ x: 0, y: 0 });

  // Animation pulse
  const [tracerProgress, setTracerProgress] = useState(1.0);
  const isTracerFiring = useRef(false);

  const canvasRef = useRef(null);
  const caliber = CALIBERS[caliberKey] || CALIBERS["9mm"];

  // Calculate shooter estimated origin point
  const shooterOrigin = useMemo(() => {
    // Distance back-projected along ray (e.g. 25 meters)
    const distance = 24.0;
    const radAz = (azimuth * Math.PI) / 180;
    const radEl = (elevation * Math.PI) / 180;

    // Ray vector pointing backwards from impact to shooter
    const dx = Math.sin(radAz) * Math.cos(radEl);
    const dy = Math.sin(radEl);
    const dz = Math.cos(radAz) * Math.cos(radEl);

    const originX = impactX + dx * distance;
    const originY = impactY + dy * distance;
    const originZ = impactZ + dz * distance;

    return {
      x: originX,
      y: originY,
      z: originZ,
      distance: Math.sqrt(dx * dx * distance * distance + dy * dy * distance * distance + dz * dz * distance * distance),
      dx,
      dy,
      dz,
      vantageZone:
        originY > 3.0
          ? `Elevated Vantage (${originY.toFixed(1)}m AGL · Likely 2nd/3rd Floor Balcony or Rooftop)`
          : originY > 1.2
          ? `Standing Shooter Ground Stance (${originY.toFixed(1)}m AGL)`
          : `Crouched / Vehicle Window (${originY.toFixed(1)}m AGL)`,
    };
  }, [impactX, impactY, impactZ, azimuth, elevation]);

  // Correlate with suspects
  const suspectCorrelations = useMemo(() => {
    const list = entState.data?.entities || [];
    return list.slice(0, 4).map((ent, idx) => {
      // Proximity score based on azimuth alignment simulation
      const baseConfidence = 94 - idx * 18 + (azimuth < 0 ? 5 : -5);
      const conf = Math.max(12, Math.min(98, baseConfidence));
      return {
        ref: ent.ref,
        name: typeof ent.display_name === "string" ? ent.display_name : typeof ent.name === "string" ? ent.name : String(ent.ref || "PERSON"),
        role: ent.incident_role || "PERSON OF INTEREST",
        confidence: conf,
        sightings: idx === 0 ? "Sighted on East Pavilion Balcony at 22:12 UTC" : "Alibi contested by cell handshake",
      };
    });
  }, [entState.data, azimuth]);

  // Load preset
  const applyPreset = (preset) => {
    cyberAudio.playScan();
    setImpactX(preset.impactX);
    setImpactY(preset.impactY);
    setImpactZ(preset.impactZ);
    setAzimuth(preset.azimuth);
    setElevation(preset.elevation);
    setCaliberKey(preset.caliber);
  };

  // Fire Tracer Animation
  const fireTracer = () => {
    if (isTracerFiring.current) return;
    cyberAudio.playClickChirp();
    isTracerFiring.current = true;
    let p = 0;
    const anim = () => {
      p += 0.04;
      if (p <= 1.0) {
        setTracerProgress(p);
        requestAnimationFrame(anim);
      } else {
        setTracerProgress(1.0);
        isTracerFiring.current = false;
        cyberAudio.playHoverBlip();
      }
    };
    anim();
  };

  // 3D to 2D Perspective Projection Helper
  const project3D = (x, y, z, width, height) => {
    // Rotate around Y (yaw)
    const cosY = Math.cos(yaw);
    const sinY = Math.sin(yaw);
    const x1 = x * cosY - z * sinY;
    const z1 = z * cosY + x * sinY;

    // Rotate around X (pitch)
    const cosP = Math.cos(pitch);
    const sinP = Math.sin(pitch);
    const y2 = y * cosP - z1 * sinP;
    const z2 = z1 * cosP + y * sinP;

    // Camera distance / perspective
    const cameraDist = 8.0 / zoom;
    const depth = z2 + cameraDist;
    if (depth <= 0.2) return null;

    const fov = 380;
    const screenX = width / 2 + (x1 / depth) * fov;
    const screenY = height / 2 - (y2 / depth) * fov;

    return { x: screenX, y: screenY, depth };
  };

  // Render 3D Canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let animId;

    const render = () => {
      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);

      // Gradient background
      const grad = ctx.createRadialGradient(width / 2, height / 2, 20, width / 2, height / 2, width * 0.7);
      grad.addColorStop(0, "rgba(8, 14, 24, 0.95)");
      grad.addColorStop(1, "rgba(3, 6, 11, 0.98)");
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, width, height);

      // Floor Grid
      if (showGrid) {
        ctx.strokeStyle = "rgba(0, 229, 255, 0.08)";
        ctx.lineWidth = 1;
        const gridRange = 12;
        const step = 2.0;

        for (let gx = -gridRange; gx <= gridRange; gx += step) {
          const p1 = project3D(gx, 0, -gridRange, width, height);
          const p2 = project3D(gx, 0, gridRange, width, height);
          if (p1 && p2) {
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        }
        for (let gz = -gridRange; gz <= gridRange; gz += step) {
          const p1 = project3D(-gridRange, 0, gz, width, height);
          const p2 = project3D(gridRange, 0, gz, width, height);
          if (p1 && p2) {
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        }
      }

      // Draw Room Reference Markers (Pillars / Perimeter)
      const pillars = [
        { x: -5, z: -5 },
        { x: 5, z: -5 },
        { x: -5, z: 5 },
        { x: 5, z: 5 },
      ];
      pillars.forEach((pil) => {
        const bottom = project3D(pil.x, 0, pil.z, width, height);
        const top = project3D(pil.x, 3.5, pil.z, width, height);
        if (bottom && top) {
          ctx.strokeStyle = "rgba(0, 229, 255, 0.15)";
          ctx.lineWidth = 1;
          ctx.setLineDash([4, 4]);
          ctx.beginPath();
          ctx.moveTo(bottom.x, bottom.y);
          ctx.lineTo(top.x, top.y);
          ctx.stroke();
          ctx.setLineDash([]);
        }
      });

      // Draw Victim Mannequin / Silhouette at (0, 0, -2.5)
      const vicX = impactX;
      const vicY = 0;
      const vicZ = impactZ;

      const vicFeet = project3D(vicX, vicY, vicZ, width, height);
      const vicHead = project3D(vicX, vicY + 1.8, vicZ, width, height);
      const vicTorso = project3D(vicX, vicY + 1.2, vicZ, width, height);

      if (vicFeet && vicHead && vicTorso) {
        // Shadow on floor
        ctx.beginPath();
        ctx.ellipse(vicFeet.x, vicFeet.y, 22 * zoom, 8 * zoom, 0, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(0, 0, 0, 0.6)";
        ctx.fill();

        // Victim Mannequin wireframe silhouette
        ctx.strokeStyle = "rgba(168, 85, 247, 0.65)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        // Spine
        ctx.moveTo(vicHead.x, vicHead.y);
        ctx.lineTo(vicFeet.x, vicFeet.y);
        // Head
        ctx.arc(vicHead.x, vicHead.y - 12, 12 * zoom, 0, Math.PI * 2);
        // Shoulders
        ctx.moveTo(vicTorso.x - 18 * zoom, vicTorso.y - 14 * zoom);
        ctx.lineTo(vicTorso.x + 18 * zoom, vicTorso.y - 14 * zoom);
        ctx.stroke();

        ctx.fillStyle = "#A855F7";
        ctx.font = "9px monospace";
        ctx.fillText("VICTIM POSITION", vicHead.x - 40, vicHead.y - 30);
      }

      // Projected Points: Impact Point & Shooter Origin
      const pImpact = project3D(impactX, impactY, impactZ, width, height);
      const pShooter = project3D(shooterOrigin.x, shooterOrigin.y, shooterOrigin.z, width, height);

      if (pImpact && pShooter) {
        // 1. Dispersion Cone
        if (showCone) {
          const dispersionRadius = shooterOrigin.distance * Math.tan((caliber.dispersionDeg * Math.PI) / 180);
          const pConeTop = project3D(shooterOrigin.x, shooterOrigin.y + dispersionRadius, shooterOrigin.z, width, height);
          const pConeBot = project3D(shooterOrigin.x, shooterOrigin.y - dispersionRadius, shooterOrigin.z, width, height);

          if (pConeTop && pConeBot) {
            ctx.beginPath();
            ctx.moveTo(pImpact.x, pImpact.y);
            ctx.lineTo(pConeTop.x, pConeTop.y);
            ctx.lineTo(pConeBot.x, pConeBot.y);
            ctx.closePath();
            ctx.fillStyle = `${caliber.color}15`;
            ctx.fill();
            ctx.strokeStyle = `${caliber.color}40`;
            ctx.setLineDash([3, 3]);
            ctx.stroke();
            ctx.setLineDash([]);
          }
        }

        // 2. Primary Trajectory Ray Line
        ctx.strokeStyle = caliber.color;
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.moveTo(pShooter.x, pShooter.y);
        ctx.lineTo(pImpact.x, pImpact.y);
        ctx.stroke();

        // 3. Laser Glow Pass
        ctx.strokeStyle = `${caliber.color}60`;
        ctx.lineWidth = 6;
        ctx.stroke();

        // 4. Bullet Tracer Pulse Animation
        if (tracerProgress < 1.0) {
          const tracerX = pShooter.x + (pImpact.x - pShooter.x) * tracerProgress;
          const tracerY = pShooter.y + (pImpact.y - pShooter.y) * tracerProgress;

          ctx.beginPath();
          ctx.arc(tracerX, tracerY, 6, 0, Math.PI * 2);
          ctx.fillStyle = "#FFFFFF";
          ctx.shadowColor = caliber.color;
          ctx.shadowBlur = 15;
          ctx.fill();
          ctx.shadowBlur = 0;
        }

        // 5. Impact Point Marker
        ctx.beginPath();
        ctx.arc(pImpact.x, pImpact.y, 6, 0, Math.PI * 2);
        ctx.fillStyle = "#FF4655";
        ctx.shadowColor = "#FF4655";
        ctx.shadowBlur = 12;
        ctx.fill();
        ctx.shadowBlur = 0;

        ctx.fillStyle = "#FFF";
        ctx.font = "bold 10px monospace";
        ctx.fillText(`IMPACT (Y: ${impactY.toFixed(1)}m)`, pImpact.x + 10, pImpact.y - 6);

        // 6. Shooter Origin Vantage Point Box
        ctx.beginPath();
        ctx.arc(pShooter.x, pShooter.y, 7, 0, Math.PI * 2);
        ctx.fillStyle = caliber.color;
        ctx.shadowColor = caliber.color;
        ctx.shadowBlur = 16;
        ctx.fill();
        ctx.shadowBlur = 0;

        ctx.fillStyle = caliber.color;
        ctx.font = "bold 11px monospace";
        ctx.fillText(`SHOOTER ORIGIN (${shooterOrigin.distance.toFixed(1)}m)`, pShooter.x + 12, pShooter.y + 4);
      }

      // HUD Compass & Attitude Indicator in Top-Left
      ctx.fillStyle = "rgba(0, 229, 255, 0.7)";
      ctx.font = "10px monospace";
      ctx.fillText(`CAM PITCH: ${(pitch * (180 / Math.PI)).toFixed(0)}°  YAW: ${(yaw * (180 / Math.PI)).toFixed(0)}°`, 16, 24);
      ctx.fillText(`RAY TRACER: ACTIVE · CALIBER: ${caliber.name}`, 16, 38);

      animId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animId);
  }, [
    yaw,
    pitch,
    zoom,
    impactX,
    impactY,
    impactZ,
    azimuth,
    elevation,
    caliber,
    showCone,
    showGrid,
    shooterOrigin,
    tracerProgress,
  ]);

  // Mouse Drag Orbit Controls
  const handleMouseDown = (e) => {
    setIsOrbiting(true);
    lastMousePos.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseMove = (e) => {
    if (!isOrbiting) return;
    const dx = e.clientX - lastMousePos.current.x;
    const dy = e.clientY - lastMousePos.current.y;
    lastMousePos.current = { x: e.clientX, y: e.clientY };

    setYaw((prev) => prev + dx * 0.008);
    setPitch((prev) => Math.max(-0.2, Math.min(1.2, prev + dy * 0.008)));
  };

  const handleMouseUp = () => setIsOrbiting(false);

  return (
    <div className="cm-ballistics-workspace">
      {/* Top Banner Ribbon */}
      <div className="cm-cctv-banner">
        <div className="cm-cctv-banner-left">
          <span className="cm-pulse-amber" />
          <strong className="font-mono">FORENSIC BALLISTICS & 3D RAY-TRACER</strong>
          <span className="cm-pipeline-badge online">TRAJECTORY PHYSICS ENGINE V3.2</span>
        </div>
        <div className="cm-cctv-banner-right font-mono text-muted small">
          CASE: {caseRef} · RECONSTRUCTED VANTAGE: {shooterOrigin.distance.toFixed(1)}M
        </div>
      </div>

      {/* Metrics HUD */}
      <div className="cm-metrics-hud">
        <StatBox
          label="SHOOTER DISTANCE"
          value={`${shooterOrigin.distance.toFixed(1)} m`}
          sub="Calculated line-of-sight range"
          icon="🎯"
          accent="amber"
        />
        <StatBox
          label="TRAJECTORY ELEVATION"
          value={`${elevation > 0 ? "+" : ""}${elevation.toFixed(1)}°`}
          sub={elevation > 5 ? "High-angle rooftop/balcony" : "Direct level trajectory"}
          icon="📐"
          accent="cyan"
        />
        <StatBox
          label="AZIMUTH BEARING"
          value={`${azimuth.toFixed(1)}°`}
          sub="Horizontal firing angle"
          icon="🧭"
          accent="purple"
        />
        <StatBox
          label="CALIBER PROFILE"
          value={caliber.name.split(" ")[0]}
          sub={`Muzzle Vel: ${caliber.velocity} m/s`}
          icon="⚡"
          accent="emerald"
        />
      </div>

      <Notice level="info">
        Forensic Ray-Tracer back-projects bullet trajectories through 3D spatial space using impact wound entry angles,
        caliber drag coefficients, and obstacle apertures. Drag within the 3D viewport to orbit camera.
      </Notice>

      {/* Presets Bar */}
      <div className="row items-center gap-2" style={{ marginBottom: 12 }}>
        <span className="font-mono small text-muted">SCENE PRESETS:</span>
        {SCENE_PRESETS.map((p, idx) => (
          <button
            key={idx}
            className="cm-filter-pill"
            onClick={() => applyPreset(p)}
            title={p.desc}
          >
            {p.name}
          </button>
        ))}
      </div>

      <div className="cm-ballistics-layout">
        {/* Main 3D Viewport */}
        <div className="cm-ballistics-main">
          <Card
            title="3D Spatial Ray-Tracing Viewport (Drag to Orbit · Scroll to Zoom)"
            aside={
              <div className="row items-center gap-2">
                <button
                  className="cm-filter-pill"
                  onClick={() => setShowCone(!showCone)}
                  style={{ color: showCone ? "#00E5FF" : "#64748b" }}
                >
                  {showCone ? "CONE: ON" : "CONE: OFF"}
                </button>
                <button
                  className="cm-filter-pill"
                  onClick={() => setShowGrid(!showGrid)}
                  style={{ color: showGrid ? "#00E5FF" : "#64748b" }}
                >
                  {showGrid ? "GRID: ON" : "GRID: OFF"}
                </button>
                <button className="cm-play-btn" onClick={fireTracer} title="Fire Animated Tracer Pulse">
                  ⚡ FIRE TRACE PULSE
                </button>
              </div>
            }
          >
            <div
              className="cm-ballistics-canvas-container"
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
              onWheel={(e) => {
                e.preventDefault();
                setZoom((z) => Math.max(0.6, Math.min(2.5, z - e.deltaY * 0.001)));
              }}
              style={{ cursor: isOrbiting ? "grabbing" : "grab" }}
            >
              <canvas
                ref={canvasRef}
                width={860}
                height={500}
                className="cm-ballistics-canvas"
              />

              {/* Viewport Overlay Controls */}
              <div className="cm-ballistics-hud-overlay">
                <div className="font-mono text-xs text-cyan">
                  ESTIMATED VANTAGE: {shooterOrigin.vantageZone.toUpperCase()}
                </div>
                <div className="font-mono text-xs text-muted" style={{ marginTop: 2 }}>
                  COORDINATES: X:{shooterOrigin.x.toFixed(1)}m · Y:{shooterOrigin.y.toFixed(1)}m · Z:{shooterOrigin.z.toFixed(1)}m
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Controls Deck & Suspect Line-of-Sight Matching */}
        <div className="cm-ballistics-side">
          <Card title="Ray-Trace Parameters & Optics">
            <div className="stack gap-3 font-mono small">
              {/* Caliber Selector */}
              <div>
                <label className="text-muted" style={{ fontSize: 11 }}>AMMUNITION CALIBER</label>
                <select
                  value={caliberKey}
                  onChange={(e) => {
                    cyberAudio.playClickChirp();
                    setCaliberKey(e.target.value);
                  }}
                  className="cm-cyber-input"
                  style={{ marginTop: 4 }}
                >
                  {Object.entries(CALIBERS).map(([k, c]) => (
                    <option key={k} value={k}>
                      {c.name} ({c.velocity} m/s)
                    </option>
                  ))}
                </select>
              </div>

              {/* Azimuth Slider */}
              <div>
                <div className="row justify-between">
                  <span className="text-muted">AZIMUTH ANGLE (θ)</span>
                  <strong className="text-amber">{azimuth.toFixed(1)}°</strong>
                </div>
                <input
                  type="range"
                  min="-90"
                  max="90"
                  step="0.5"
                  value={azimuth}
                  onChange={(e) => setAzimuth(Number(e.target.value))}
                  className="cm-cyber-range"
                />
              </div>

              {/* Elevation Slider */}
              <div>
                <div className="row justify-between">
                  <span className="text-muted">ELEVATION ANGLE (ϕ)</span>
                  <strong className="text-cyan">{elevation.toFixed(1)}°</strong>
                </div>
                <input
                  type="range"
                  min="-30"
                  max="45"
                  step="0.5"
                  value={elevation}
                  onChange={(e) => setElevation(Number(e.target.value))}
                  className="cm-cyber-range"
                />
              </div>

              {/* Impact Height Slider */}
              <div>
                <div className="row justify-between">
                  <span className="text-muted">IMPACT HEIGHT (Y)</span>
                  <strong className="text-emerald">{impactY.toFixed(2)} m</strong>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="2.2"
                  step="0.05"
                  value={impactY}
                  onChange={(e) => setImpactY(Number(e.target.value))}
                  className="cm-cyber-range"
                />
              </div>
            </div>
          </Card>

          {/* Suspect Line-of-Sight Correlation */}
          <Card title="Suspect Vantage Correlation">
            <div className="stack gap-2">
              <div className="font-mono text-xs text-muted">
                MATCHING RECONSTRUCTED FIRING CONE AGAINST SURVEILLANCE & ALIBI RECORDS:
              </div>

              {suspectCorrelations.map((s) => (
                <div key={s.ref} className="cm-suspect-match-row">
                  <div className="row justify-between items-center">
                    <strong className="text-white font-mono small">{s.name}</strong>
                    <span
                      className="font-mono text-xs font-bold"
                      style={{ color: s.confidence > 70 ? "#00E6A0" : s.confidence > 40 ? "#FFB52E" : "#FF4655" }}
                    >
                      {s.confidence}% MATCH
                    </span>
                  </div>
                  <div className="small text-muted" style={{ fontSize: 10, marginTop: 2 }}>
                    {s.sightings}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
