import React, { useState, useMemo } from "react";
import { cyberAudio } from "../../utils/cyberAudio.js";

const METRIC_KEYS = [
  { key: "ndcg@5", label: "NDCG@5", max: 1.0 },
  { key: "mrr", label: "MRR", max: 1.0 },
  { key: "ap", label: "MAP (AP)", max: 1.0 },
  { key: "p@1", label: "P@1", max: 1.0 },
  { key: "p@3", label: "P@3", max: 1.0 },
  { key: "r@5", label: "Recall@5", max: 1.0 },
];

const MODEL_CONFIGS = {
  "RAEER:A1_full": {
    label: "RAEER (Full Model)",
    color: "#FFB52E",
    glow: "rgba(255, 181, 46, 0.4)",
    fill: "rgba(255, 181, 46, 0.2)",
  },
  q40: {
    label: "Q40 Baseline",
    color: "#00E5FF",
    glow: "rgba(0, 229, 255, 0.4)",
    fill: "rgba(0, 229, 255, 0.15)",
  },
  pagerank: {
    label: "PageRank",
    color: "#A855F7",
    glow: "rgba(168, 85, 247, 0.4)",
    fill: "rgba(168, 85, 247, 0.12)",
  },
  proximity: {
    label: "Proximity",
    color: "#00E6A0",
    glow: "rgba(0, 230, 160, 0.4)",
    fill: "rgba(0, 230, 160, 0.12)",
  },
};

export default function BenchmarkSpiderRadar({ ablationData }) {
  const [activeSplit, setActiveSplit] = useState("all");
  const [hoveredModel, setHoveredModel] = useState("RAEER:A1_full");
  const [hoveredMetric, setHoveredMetric] = useState(null);
  const [visibleModels, setVisibleModels] = useState({
    "RAEER:A1_full": true,
    q40: true,
    pagerank: true,
    proximity: true,
  });

  const splitData = useMemo(() => {
    if (!ablationData) return {};
    return ablationData[activeSplit] || ablationData.all || {};
  }, [ablationData, activeSplit]);

  // Center coordinates and radius
  const size = 440;
  const cx = size / 2;
  const cy = size / 2;
  const radius = 150;
  const numAxes = METRIC_KEYS.length;

  // Calculate polygon points for each model
  const modelPolygons = useMemo(() => {
    const polys = {};
    Object.keys(MODEL_CONFIGS).forEach((modelKey) => {
      const modelMetrics = splitData[modelKey];
      if (!modelMetrics) return;

      const points = METRIC_KEYS.map((m, i) => {
        const angle = (Math.PI * 2 / numAxes) * i - Math.PI / 2;
        const val = modelMetrics[m.key]?.mean ?? 0;
        const dist = (Math.min(val, m.max) / m.max) * radius;
        const x = cx + dist * Math.cos(angle);
        const y = cy + dist * Math.sin(angle);
        return { x, y, val, metricKey: m.key };
      });

      const polyString = points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
      polys[modelKey] = { points, polyString };
    });
    return polys;
  }, [splitData, cx, cy, radius, numAxes]);

  const toggleModel = (modelKey) => {
    cyberAudio.playClickChirp();
    setVisibleModels((prev) => ({ ...prev, [modelKey]: !prev[modelKey] }));
  };

  const raeerMetrics = splitData["RAEER:A1_full"] || {};
  const q40Metrics = splitData["q40"] || {};

  return (
    <div className="cm-radar-widget">
      {/* Header & Controls */}
      <div className="cm-radar-header">
        <div className="row items-center gap-2">
          <span className="cm-pulse-amber" />
          <h3 className="font-mono" style={{ margin: 0, fontSize: 14 }}>
            HOLOGRAPHIC BENCHMARK RADAR · MULTI-METRIC ABLATION
          </h3>
        </div>
        <div className="row items-center gap-2">
          <span className="font-mono small text-muted">DATA SPLIT:</span>
          {["all", "dev", "test"].map((s) => (
            <button
              key={s}
              className={`cm-filter-pill ${activeSplit === s ? "active" : ""}`}
              onClick={() => {
                cyberAudio.playClickChirp();
                setActiveSplit(s);
              }}
            >
              {s.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      <div className="cm-radar-body">
        {/* SVG Radar Chart */}
        <div className="cm-radar-svg-container">
          <svg viewBox={`0 0 ${size} ${size}`} className="cm-radar-svg">
            <defs>
              <filter id="radar-glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="4" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {/* Concentric Grid Rings */}
            {[0.25, 0.5, 0.75, 1.0].map((ring, idx) => {
              const r = radius * ring;
              return (
                <g key={idx}>
                  <circle
                    cx={cx}
                    cy={cy}
                    r={r}
                    fill="none"
                    stroke="rgba(0, 229, 255, 0.12)"
                    strokeDasharray={idx === 3 ? "none" : "3 3"}
                    strokeWidth="1"
                  />
                  <text
                    x={cx + 6}
                    y={cy - r + 12}
                    fill="rgba(0, 229, 255, 0.4)"
                    fontSize="9"
                    className="font-mono"
                  >
                    {(ring * 100).toFixed(0)}%
                  </text>
                </g>
              );
            })}

            {/* Axes Lines and Labels */}
            {METRIC_KEYS.map((m, i) => {
              const angle = (Math.PI * 2 / numAxes) * i - Math.PI / 2;
              const x2 = cx + radius * Math.cos(angle);
              const y2 = cy + radius * Math.sin(angle);
              const labelDist = radius + 28;
              const lx = cx + labelDist * Math.cos(angle);
              const ly = cy + labelDist * Math.sin(angle);

              return (
                <g
                  key={m.key}
                  onMouseEnter={() => {
                    cyberAudio.playHoverBlip();
                    setHoveredMetric(m.key);
                  }}
                  onMouseLeave={() => setHoveredMetric(null)}
                  style={{ cursor: "pointer" }}
                >
                  <line
                    x1={cx}
                    y1={cy}
                    x2={x2}
                    y2={y2}
                    stroke={hoveredMetric === m.key ? "#FFB52E" : "rgba(0, 229, 255, 0.25)"}
                    strokeWidth={hoveredMetric === m.key ? 2 : 1}
                  />
                  <text
                    x={lx}
                    y={ly}
                    textAnchor="middle"
                    dominantBaseline="central"
                    fill={hoveredMetric === m.key ? "#FFB52E" : "#8292b0"}
                    fontSize="11"
                    fontWeight={hoveredMetric === m.key ? "bold" : "normal"}
                    className="font-mono"
                  >
                    {m.label}
                  </text>
                </g>
              );
            })}

            {/* Render Model Polygons */}
            {Object.entries(MODEL_CONFIGS).map(([mKey, cfg]) => {
              if (!visibleModels[mKey] || !modelPolygons[mKey]) return null;
              const isHovered = hoveredModel === mKey;
              const poly = modelPolygons[mKey];

              return (
                <g key={mKey} className="cm-radar-polygon-group">
                  <polygon
                    points={poly.polyString}
                    fill={cfg.fill}
                    stroke={cfg.color}
                    strokeWidth={isHovered ? 3 : 1.75}
                    filter={isHovered ? "url(#radar-glow)" : undefined}
                    opacity={hoveredModel && !isHovered ? 0.4 : 1}
                    style={{ transition: "all 0.3s ease", cursor: "pointer" }}
                    onMouseEnter={() => {
                      cyberAudio.playHoverBlip();
                      setHoveredModel(mKey);
                    }}
                  />
                  {/* Vertex Points */}
                  {poly.points.map((pt, pIdx) => (
                    <circle
                      key={pIdx}
                      cx={pt.x}
                      cy={pt.y}
                      r={isHovered ? 5 : 3.5}
                      fill={cfg.color}
                      stroke="#05090F"
                      strokeWidth="1.5"
                    />
                  ))}
                </g>
              );
            })}

            {/* Center Core Pip */}
            <circle cx={cx} cy={cy} r="4" fill="#00E5FF" />
          </svg>
        </div>

        {/* Model Selector & Telemetry Panel */}
        <div className="cm-radar-telemetry">
          <div className="font-mono small text-muted" style={{ marginBottom: 8 }}>
            BENCHMARK MODELS (CLICK TO TOGGLE):
          </div>

          <div className="cm-radar-legend-list">
            {Object.entries(MODEL_CONFIGS).map(([mKey, cfg]) => {
              const isVisible = visibleModels[mKey];
              const isHovered = hoveredModel === mKey;
              const modelData = splitData[mKey] || {};
              const ndcgVal = modelData["ndcg@5"]?.mean;

              return (
                <div
                  key={mKey}
                  className={`cm-radar-legend-item ${isHovered ? "hovered" : ""} ${!isVisible ? "disabled" : ""}`}
                  onMouseEnter={() => setHoveredModel(mKey)}
                  onClick={() => toggleModel(mKey)}
                >
                  <div className="row items-center gap-2">
                    <span
                      className="cm-legend-swatch"
                      style={{
                        backgroundColor: isVisible ? cfg.color : "#475569",
                        boxShadow: isVisible && isHovered ? `0 0 10px ${cfg.color}` : "none",
                      }}
                    />
                    <strong className="font-mono small" style={{ color: isVisible ? cfg.color : "#64748b" }}>
                      {cfg.label}
                    </strong>
                  </div>
                  <span className="font-mono small text-cyan">
                    {ndcgVal !== undefined ? `${(ndcgVal * 100).toFixed(1)}%` : "—"}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Comparative Delta Inspector */}
          {hoveredModel && (
            <div className="cm-radar-delta-box">
              <div className="font-mono text-xs text-amber" style={{ marginBottom: 6 }}>
                INSPECTING: {MODEL_CONFIGS[hoveredModel]?.label.toUpperCase()}
              </div>
              <div className="cm-radar-metric-grid">
                {METRIC_KEYS.map((m) => {
                  const mData = splitData[hoveredModel]?.[m.key];
                  const meanVal = mData?.mean ?? 0;
                  const q40Val = q40Metrics[m.key]?.mean ?? 0;
                  const deltaVsQ40 = meanVal - q40Val;
                  const isPositive = deltaVsQ40 >= 0;

                  return (
                    <div key={m.key} className="cm-radar-metric-cell">
                      <span className="text-muted font-mono">{m.label}</span>
                      <strong className="font-mono text-cyan">
                        {(meanVal * 100).toFixed(1)}%
                      </strong>
                      {hoveredModel !== "q40" && (
                        <span className={`font-mono text-xs ${isPositive ? "text-emerald" : "text-crimson"}`}>
                          {isPositive ? "+" : ""}
                          {(deltaVsQ40 * 100).toFixed(1)}%
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
