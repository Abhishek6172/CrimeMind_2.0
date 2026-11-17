import React, { useEffect, useMemo, useRef, useState } from "react";
import { useLoad } from "../hooks.js";
import { Async, Badge, Card, Notice, time } from "../components/ui.jsx";

const W = 940, H = 640;
const COLOR = {
  PERSON: "#00E5FF",      // Electric Cyan
  LOCATION: "#00E6A0",    // Emerald
  VEHICLE: "#FFB52E",     // Amber
  DEVICE: "#A855F7",      // Violet
  EVIDENCE: "#94A3B8",    // Slate
  ORGANIZATION: "#FF4655",// Crimson
  ACCOUNT: "#38BDF8",     // Sky
};
const STYLE = {
  FACT: { dash: "", w: 2.2, color: "#00E5FF" },
  CORRELATED: { dash: "8 4", w: 2.4, color: "#FFB52E" },
  INFERRED: { dash: "3 4", w: 2.2, color: "#A855F7" },
};

function layout(nodes, edges) {
  const pos = new Map(
    nodes.map((n, i) => {
      const a = (i / Math.max(1, nodes.length)) * Math.PI * 2;
      return [
        n.id,
        {
          x: W / 2 + Math.cos(a) * 270,
          y: H / 2 + Math.sin(a) * 230,
          vx: 0,
          vy: 0,
        },
      ];
    })
  );
  const seen = new Set(), links = [];
  for (const e of edges) {
    const k = e.source < e.target ? `${e.source}|${e.target}` : `${e.target}|${e.source}`;
    if (!seen.has(k) && pos.has(e.source) && pos.has(e.target)) {
      seen.add(k);
      links.push([e.source, e.target]);
    }
  }
  const ids = nodes.map((n) => n.id);
  for (let t = 0; t < 220; t++) {
    const cool = 1 - t / 220;
    for (let i = 0; i < ids.length; i++) {
      for (let j = i + 1; j < ids.length; j++) {
        const a = pos.get(ids[i]), b = pos.get(ids[j]);
        let dx = a.x - b.x, dy = a.y - b.y;
        const d2 = Math.max(dx * dx + dy * dy, 60), f = 2800 / d2, d = Math.sqrt(d2);
        dx /= d; dy /= d;
        a.vx += dx * f; a.vy += dy * f;
        b.vx -= dx * f; b.vy -= dy * f;
      }
    }
    for (const [s, tg] of links) {
      const a = pos.get(s), b = pos.get(tg);
      const dx = b.x - a.x, dy = b.y - a.y;
      const d = Math.sqrt(dx * dx + dy * dy) || 1, f = (d - 100) * 0.022;
      a.vx += (dx / d) * f; a.vy += (dy / d) * f;
      b.vx -= (dx / d) * f; b.vy -= (dy / d) * f;
    }
    for (const p of pos.values()) {
      p.vx += (W / 2 - p.x) * 0.004;
      p.vy += (H / 2 - p.y) * 0.004;
      p.x = Math.min(W - 25, Math.max(25, p.x + p.vx * cool));
      p.y = Math.min(H - 25, Math.max(25, p.y + p.vy * cool));
      p.vx *= 0.6; p.vy *= 0.6;
    }
  }
  return pos;
}

function Canvas({ g, classes, sel, setSel, filterText }) {
  const [scale, setScale] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const [hoveredNode, setHoveredNode] = useState(null);

  const edges = useMemo(() => g.edges.filter((e) => classes.has(e.classification)), [g, classes]);
  const nodes = useMemo(() => {
    const used = new Set(edges.flatMap((e) => [e.source, e.target]));
    let nList = g.nodes.filter((n) => used.has(n.id) || n.incident_role);
    if (filterText?.trim()) {
      const q = filterText.toLowerCase();
      nList = nList.filter((n) => n.label.toLowerCase().includes(q) || n.id.toLowerCase().includes(q) || (n.type || "").toLowerCase().includes(q));
    }
    return nList;
  }, [g, edges, filterText]);

  const pos = useMemo(() => layout(nodes, edges), [nodes, edges]);
  const hot = useMemo(() => {
    const s = new Set();
    if (sel?.kind === "edge") {
      s.add(sel.item.source);
      s.add(sel.item.target);
    }
    if (sel?.kind === "node") s.add(sel.item.id);
    if (hoveredNode) s.add(hoveredNode.id);
    return s;
  }, [sel, hoveredNode]);

  // Handle Pan
  const onPointerDown = (e) => {
    if (e.target.closest(".node") || e.target.closest(".edge")) return;
    setIsDragging(true);
    dragStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };

  const onPointerMove = (e) => {
    if (!isDragging) return;
    setPan({ x: e.clientX - dragStart.current.x, y: e.clientY - dragStart.current.y });
  };

  const onPointerUp = () => setIsDragging(false);

  const resetView = () => {
    setScale(1);
    setPan({ x: 0, y: 0 });
  };

  return (
    <div className="cm-graph-container">
      {/* Interactive Controls Overlay */}
      <div className="cm-graph-toolbar">
        <button onClick={() => setScale((s) => Math.min(2.4, s + 0.2))} title="Zoom In">＋</button>
        <button onClick={() => setScale((s) => Math.max(0.4, s - 0.2))} title="Zoom Out">−</button>
        <button onClick={resetView} title="Reset Scale & Pan">⌖ Fit</button>
        <span className="cm-graph-zoom-label font-mono small text-cyan">{Math.round(scale * 100)}%</span>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="graph cm-cyber-graph"
        role="img"
        aria-label="Interactive Relationship Graph"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        style={{ cursor: isDragging ? "grabbing" : "grab" }}
      >
        <defs>
          <radialGradient id="cyber-bg-glow" cx="50%" cy="50%" r="60%">
            <stop offset="0%" stopColor="#00E5FF" stopOpacity="0.06" />
            <stop offset="100%" stopColor="#05090F" stopOpacity="0" />
          </radialGradient>
          <filter id="neon-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <rect width={W} height={H} fill="url(#cyber-bg-glow)" />

        <g transform={`translate(${pan.x}, ${pan.y}) scale(${scale})`}>
          {/* Edges */}
          {edges.map((e) => {
            const a = pos.get(e.source), b = pos.get(e.target);
            if (!a || !b) return null;
            const st = STYLE[e.classification] || { dash: "", w: 2, color: "#00E5FF" };
            const isSelected = sel?.item?.id === e.id;
            const isConnectedToHot = hot.has(e.source) && hot.has(e.target);

            return (
              <g key={e.id} onClick={() => setSel({ kind: "edge", item: e })} className="edge">
                {/* Wider invisible stroke for easy clicking */}
                <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="transparent" strokeWidth="12" />
                {/* Visual line */}
                <line
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={isSelected ? "#FFF" : isConnectedToHot ? st.color : st.color}
                  strokeWidth={isSelected ? st.w + 2 : isConnectedToHot ? st.w + 1 : st.w}
                  strokeDasharray={st.dash}
                  opacity={isSelected ? 1 : isConnectedToHot ? 0.9 : 0.45}
                  filter={isSelected ? "url(#neon-glow)" : undefined}
                />
              </g>
            );
          })}

          {/* Nodes */}
          {nodes.map((n) => {
            const p = pos.get(n.id);
            if (!p) return null;
            const isHot = hot.has(n.id);
            const isSelected = sel?.kind === "node" && sel.item.id === n.id;
            const nodeColor = COLOR[n.type] || "#94A3B8";

            return (
              <g
                key={n.id}
                transform={`translate(${p.x},${p.y})`}
                onClick={() => setSel({ kind: "node", item: n })}
                onPointerEnter={() => setHoveredNode(n)}
                onPointerLeave={() => setHoveredNode(null)}
                className={`node ${isSelected ? "selected" : ""}`}
                tabIndex={0}
              >
                {/* Outer halo when active or hovered */}
                {(isHot || isSelected) && (
                  <circle
                    r={n.incident_role ? 19 : 15}
                    fill="none"
                    stroke={nodeColor}
                    strokeWidth="1.5"
                    strokeDasharray="3 3"
                    className="cm-node-halo-pulse"
                  />
                )}
                {/* Main Node Circle */}
                <circle
                  r={n.incident_role ? 12 : 9}
                  fill={nodeColor}
                  stroke={isSelected ? "#FFF" : n.incident_role ? "#FF4655" : "#05090F"}
                  strokeWidth={isSelected ? 3.5 : n.incident_role ? 2.5 : 2}
                  filter="url(#neon-glow)"
                />
                {/* Node Label */}
                <text
                  y={-15}
                  textAnchor="middle"
                  className="cm-graph-label"
                  style={{
                    fontWeight: isHot ? 700 : 500,
                    fill: isHot ? "#FFF" : "#C8D4F0",
                  }}
                >
                  {n.label.split(" ")[0]}
                </text>
              </g>
            );
          })}
        </g>
      </svg>

      {/* Floating Hover Card */}
      {hoveredNode && (
        <div className="cm-graph-hover-card">
          <div className="font-mono text-cyan">{hoveredNode.id}</div>
          <strong>{hoveredNode.label}</strong>
          <div className="row">
            <Badge kind={hoveredNode.type} />
            {hoveredNode.incident_role && <Badge kind={hoveredNode.incident_role} />}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Graph({ c }) {
  const [scope, setScope] = useState("relevant");
  const [withEv, setWithEv] = useState(false);
  const [focus, setFocus] = useState("");
  const [appliedFocus, setAF] = useState("");
  const [filterQuery, setFilterQuery] = useState("");
  const [classes, setClasses] = useState(new Set(["CORRELATED", "INFERRED"]));
  const [sel, setSel] = useState(null);

  const st = useLoad(
    () => c.get("/relationship-graph", { scope, include_evidence: withEv ? "true" : "", focus: appliedFocus }),
    [c, scope, withEv, appliedFocus]
  );

  const toggle = (k) =>
    setClasses((s) => {
      const n = new Set(s);
      n.has(k) ? n.delete(k) : n.add(k);
      return n;
    });

  return (
    <div className="split cm-graph-page-split">
      <Card
        title="Investigation Relationship Graph"
        aside={
          <div className="row">
            <select value={scope} onChange={(e) => setScope(e.target.value)} aria-label="Scope">
              <option value="relevant">Relevant to the case</option>
              <option value="all">Full Network (Everything)</option>
            </select>
            <label className="inline small text-muted">
              <input type="checkbox" checked={withEv} onChange={(e) => setWithEv(e.target.checked)} />
              Evidence nodes
            </label>
            <form
              className="row"
              onSubmit={(e) => {
                e.preventDefault();
                setAF(focus.trim());
              }}
            >
              <input
                placeholder="Focus ref (e.g. P-004)"
                value={focus}
                onChange={(e) => setFocus(e.target.value)}
                style={{ width: 140 }}
              />
              <button className="primary small">Focus</button>
            </form>
          </div>
        }
      >
        {/* Graph Legend & Quick Filter */}
        <div className="cm-graph-subbar">
          <div className="legend cm-cyber-legend">
            {["FACT", "CORRELATED", "INFERRED"].map((k) => (
              <label key={k} className="inline cm-legend-label">
                <input type="checkbox" checked={classes.has(k)} onChange={() => toggle(k)} />
                <svg width="30" height="8">
                  <line
                    x1="0"
                    y1="4"
                    x2="30"
                    y2="4"
                    stroke={STYLE[k].color}
                    strokeWidth="2.5"
                    strokeDasharray={STYLE[k].dash}
                  />
                </svg>
                <span>{k}</span>
                {st.data && <span className="muted font-mono">({st.data.edge_counts?.[k] ?? 0})</span>}
              </label>
            ))}
          </div>
          <input
            type="text"
            placeholder="Filter entities in graph…"
            value={filterQuery}
            onChange={(e) => setFilterQuery(e.target.value)}
            className="cm-graph-search"
          />
        </div>

        <Async
          state={st}
          empty={Object.assign(
            (d) => d.empty || !d.nodes.length,
            { message: "No relationships to show for this scope. Try switching scope to “Full Network”." }
          )}
        >
          {(d) => (
            <>
              <Notice level="info">{d.notice}</Notice>
              <Canvas g={d} classes={classes} sel={sel} setSel={setSel} filterText={filterQuery} />
              <p className="small muted font-mono" style={{ marginTop: 10 }}>
                {classes.has("FACT") ? "" : "Recorded-fact edges hidden by default for clarity · Tick FACT to display. "}
                Solid = Recorded Fact · Dashed = Correlation Rule · Dotted = Inferred Pattern. Generated {time(d.generated_at)} from run {d.run_id}.
              </p>
            </>
          )}
        </Async>
      </Card>

      {/* Holographic Inspector Drawer */}
      <Card title="Entity & Link Inspector" aside={sel && <button className="small" onClick={() => setSel(null)}>Clear</button>}>
        {!sel && (
          <div className="cm-empty-inspector">
            <span className="cm-reticle-icon">⌖</span>
            <p className="muted">Click on any graph node or relationship line to inspect forensic telemetry.</p>
          </div>
        )}

        {sel?.kind === "node" && (
          <div className="stack cm-inspector-pane">
            <div className="cm-inspector-header">
              <span className="font-mono text-cyan text-lg"><b>{sel.item.id}</b></span>
              <Badge kind={sel.item.type} />
            </div>
            <h3>{sel.item.label}</h3>

            {sel.item.incident_role && (
              <div className="cm-role-callout">
                <span>INCIDENT ROLE</span>
                <strong className="text-amber">{sel.item.incident_role}</strong>
              </div>
            )}

            <div className="row" style={{ marginTop: 8 }}>
              <button
                className="primary small"
                onClick={() => {
                  setFocus(sel.item.id);
                  setAF(sel.item.id);
                }}
              >
                Focus Graph on {sel.item.id}
              </button>
            </div>
          </div>
        )}

        {sel?.kind === "edge" &&
          (() => {
            const e = sel.item;
            return (
              <div className="stack cm-inspector-pane">
                <div className="row">
                  <Badge kind={e.classification} />
                  <span className="muted font-mono small">
                    {e.rule_id} v{e.rule_version}
                  </span>
                </div>
                <h4 style={{ margin: "4px 0" }}>{e.rule_name}</h4>
                <p className="cm-edge-summary">{e.summary}</p>
                <div className="kv">
                  <span>Endpoints</span>
                  <span className="font-mono text-cyan">
                    {e.source} ↔ {e.target}
                  </span>
                </div>
                <div className="kv">
                  <span>Confidence</span>
                  <span className="font-mono text-amber">
                    {e.confidence != null ? Number(e.confidence).toFixed(2) : "—"}
                  </span>
                </div>
                <div className="kv">
                  <span>Evidence Links</span>
                  <span className="font-mono small">
                    {(e.evidence_refs || []).join(", ") || "—"}
                  </span>
                </div>
                {e.uncertainties?.length > 0 && (
                  <div className="cm-uncertainties-box">
                    <h4>Uncertainties / Limitations</h4>
                    <ul>
                      {e.uncertainties.map((u, i) => (
                        <li key={i}>{u}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            );
          })()}
      </Card>
    </div>
  );
}
