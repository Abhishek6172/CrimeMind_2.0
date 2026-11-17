import React, { useRef, useEffect, useState, useMemo } from "react";
import { cyberAudio } from "../../utils/cyberAudio.js";

const SPLIT_COLORS = {
  all: { bg: "#00E5FF", glow: "rgba(0, 229, 255, 0.6)", label: "All" },
  dev: { bg: "#FFB52E", glow: "rgba(255, 181, 46, 0.6)", label: "Dev" },
  test: { bg: "#A855F7", glow: "rgba(168, 85, 247, 0.6)", label: "Test" },
};

export default function SeedScatterCanvas({ seeds = [], activeSeed, onSelectSeed }) {
  const canvasRef = useRef(null);
  const [hoveredSeed, setHoveredSeed] = useState(null);
  const [filterSplit, setFilterSplit] = useState("all_splits");
  const [zoom, setZoom] = useState(1.0);
  const [searchTerm, setSearchTerm] = useState("");

  const filteredSeeds = useMemo(() => {
    return seeds.filter((s) => {
      const matchSplit = filterSplit === "all_splits" || s.split.toLowerCase() === filterSplit.toLowerCase();
      const matchSearch = !searchTerm.trim() || String(s.seed).includes(searchTerm.trim());
      return matchSplit && matchSearch;
    });
  }, [seeds, filterSplit, searchTerm]);

  // Canvas bounds calculation
  const stats = useMemo(() => {
    if (!seeds.length) return { minX: 80, maxX: 150, minY: 400, maxY: 650 };
    const xs = seeds.map((s) => Number(s.n_entities || 100));
    const ys = seeds.map((s) => Number(s.n_evidence || 500));
    return {
      minX: Math.min(...xs) - 10,
      maxX: Math.max(...xs) + 10,
      minY: Math.min(...ys) - 30,
      maxY: Math.max(...ys) + 30,
    };
  }, [seeds]);

  const mousePos = useRef({ x: -1000, y: -1000 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let animId;

    const render = () => {
      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);

      // Draw subtle background grid
      ctx.strokeStyle = "rgba(0, 229, 255, 0.05)";
      ctx.lineWidth = 1;
      const gridSize = 40 * zoom;
      for (let x = 0; x < width; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      for (let y = 0; y < height; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      // Map seed data to canvas coordinates
      const padding = 50;
      const renderNodes = filteredSeeds.map((s) => {
        const ent = Number(s.n_entities || 100);
        const evi = Number(s.n_evidence || 500);

        const normX = (ent - stats.minX) / (stats.maxX - stats.minX || 1);
        const normY = (evi - stats.minY) / (stats.maxY - stats.minY || 1);

        // Center with zoom
        const cx = padding + normX * (width - padding * 2);
        const cy = height - (padding + normY * (height - padding * 2));
        const leads = Number(s.n_relevant_leads || 3);
        const radius = Math.max(5, leads * 2.2);

        return {
          seed: s,
          x: cx,
          y: cy,
          radius,
          isSelected: Number(s.seed) === Number(activeSeed),
        };
      });

      // Draw mouse gravitational tether lines to nearby seeds
      const mx = mousePos.current.x;
      const my = mousePos.current.y;
      const tetherThreshold = 140;

      if (mx > 0 && my > 0) {
        ctx.beginPath();
        ctx.arc(mx, my, tetherThreshold, 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(0, 229, 255, 0.08)";
        ctx.stroke();

        renderNodes.forEach((node) => {
          const dx = node.x - mx;
          const dy = node.y - my;
          const dist = Math.hypot(dx, dy);
          if (dist < tetherThreshold) {
            ctx.beginPath();
            ctx.moveTo(mx, my);
            ctx.lineTo(node.x, node.y);
            ctx.strokeStyle = `rgba(0, 229, 255, ${(1 - dist / tetherThreshold) * 0.4})`;
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        });
      }

      // Render Seeds
      renderNodes.forEach((node) => {
        const splitKey = node.seed.split.toLowerCase();
        const colCfg = SPLIT_COLORS[splitKey] || SPLIT_COLORS.all;

        // Hover or selected glow
        if (node.isSelected || (hoveredSeed && hoveredSeed.seed === node.seed.seed)) {
          ctx.beginPath();
          ctx.arc(node.x, node.y, node.radius + 8, 0, Math.PI * 2);
          ctx.fillStyle = colCfg.glow;
          ctx.fill();

          ctx.beginPath();
          ctx.arc(node.x, node.y, node.radius + 4, 0, Math.PI * 2);
          ctx.strokeStyle = "#FFFFFF";
          ctx.lineWidth = 2;
          ctx.stroke();
        }

        // Inner circle
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
        ctx.fillStyle = colCfg.bg;
        ctx.fill();

        // Node label
        ctx.fillStyle = "#FFFFFF";
        ctx.font = "9px monospace";
        ctx.textAlign = "center";
        ctx.fillText(node.seed.seed, node.x, node.y - node.radius - 4);
      });

      animId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animId);
  }, [filteredSeeds, stats, activeSeed, hoveredSeed, zoom]);

  // Handle Mouse Hover / Proximity
  const handleMouseMove = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left) * (canvas.width / rect.width);
    const my = (e.clientY - rect.top) * (canvas.height / rect.height);
    mousePos.current = { x: mx, y: my };

    // Find nearest seed
    const padding = 50;
    let found = null;
    for (const s of filteredSeeds) {
      const ent = Number(s.n_entities || 100);
      const evi = Number(s.n_evidence || 500);
      const normX = (ent - stats.minX) / (stats.maxX - stats.minX || 1);
      const normY = (evi - stats.minY) / (stats.maxY - stats.minY || 1);
      const cx = padding + normX * (canvas.width - padding * 2);
      const cy = canvas.height - (padding + normY * (canvas.height - padding * 2));

      if (Math.hypot(mx - cx, my - cy) < 18) {
        found = s;
        break;
      }
    }

    if (found && (!hoveredSeed || hoveredSeed.seed !== found.seed)) {
      cyberAudio.playHoverBlip();
      setHoveredSeed(found);
    } else if (!found && hoveredSeed) {
      setHoveredSeed(null);
    }
  };

  const handleMouseLeave = () => {
    mousePos.current = { x: -1000, y: -1000 };
    setHoveredSeed(null);
  };

  const handleClick = () => {
    if (hoveredSeed) {
      cyberAudio.playAccessGranted();
      onSelectSeed(hoveredSeed.seed);
    }
  };

  return (
    <div className="cm-scatter-widget">
      {/* Top Controls Bar */}
      <div className="cm-scatter-controls">
        <div className="row items-center gap-3">
          <span className="cm-pulse-cyan" />
          <h3 className="font-mono" style={{ margin: 0, fontSize: 13 }}>
            TOPOLOGICAL SEED FEATURE SPACE ({filteredSeeds.length} SEEDS LOADED)
          </h3>
        </div>

        <div className="row items-center gap-2">
          {/* Split Filter Buttons */}
          <button
            className={`cm-filter-pill ${filterSplit === "all_splits" ? "active" : ""}`}
            onClick={() => setFilterSplit("all_splits")}
          >
            ALL SPLITS
          </button>
          <button
            className={`cm-filter-pill ${filterSplit === "all" ? "active" : ""}`}
            onClick={() => setFilterSplit("all")}
          >
            ALL
          </button>
          <button
            className={`cm-filter-pill ${filterSplit === "dev" ? "active" : ""}`}
            onClick={() => setFilterSplit("dev")}
          >
            DEV
          </button>
          <button
            className={`cm-filter-pill ${filterSplit === "test" ? "active" : ""}`}
            onClick={() => setFilterSplit("test")}
          >
            TEST
          </button>

          {/* Quick Search */}
          <input
            type="text"
            placeholder="Search Seed #"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="cm-cyber-input"
            style={{ width: 120, padding: "4px 8px", fontSize: 11 }}
          />

          {/* Zoom controls */}
          <button
            className="cm-filter-pill"
            onClick={() => setZoom((z) => Math.min(2.0, z + 0.2))}
            title="Zoom In"
          >
            ＋
          </button>
          <button
            className="cm-filter-pill"
            onClick={() => setZoom((z) => Math.max(0.6, z - 0.2))}
            title="Zoom Out"
          >
            －
          </button>
        </div>
      </div>

      {/* Main Canvas & HUD Overlay */}
      <div className="cm-scatter-canvas-wrap">
        <canvas
          ref={canvasRef}
          width={880}
          height={380}
          className="cm-scatter-canvas"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          onClick={handleClick}
        />

        {/* Axis Guides */}
        <div className="cm-axis-guide cm-axis-x font-mono text-muted small">
          AXIS X: LINKED ENTITY DENSITY →
        </div>
        <div className="cm-axis-guide cm-axis-y font-mono text-muted small">
          ↑ AXIS Y: EVIDENCE CORPUS COUNT
        </div>

        {/* Floating HUD Card for Hovered Seed */}
        {hoveredSeed && (
          <div className="cm-scatter-hud-card">
            <div className="row justify-between items-center" style={{ marginBottom: 4 }}>
              <strong className="text-cyan font-mono" style={{ fontSize: 13 }}>
                SEED #{hoveredSeed.seed}
              </strong>
              <span className={`cm-split-badge ${hoveredSeed.split.toLowerCase()}`}>
                {hoveredSeed.split.toUpperCase()}
              </span>
            </div>
            <div className="cm-hud-grid font-mono text-xs">
              <div>Entities: <span className="text-white">{hoveredSeed.n_entities}</span></div>
              <div>Evidence: <span className="text-white">{hoveredSeed.n_evidence}</span></div>
              <div>Leads: <span className="text-emerald">{hoveredSeed.n_relevant_leads}</span></div>
              <div>Herrings: <span className="text-crimson">{hoveredSeed.n_red_herrings}</span></div>
            </div>
            <div className="font-mono text-xs text-muted" style={{ marginTop: 6, wordBreak: "break-all" }}>
              SHA: {hoveredSeed.dataset_sha256 ? hoveredSeed.dataset_sha256.slice(0, 16) + "..." : "—"}
            </div>
            <div className="text-amber font-mono text-xs" style={{ marginTop: 6 }}>
              ▶ CLICK TO LOAD GROUND-TRUTH CASE
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
