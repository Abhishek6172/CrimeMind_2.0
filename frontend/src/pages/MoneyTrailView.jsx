import React, { useMemo, useState } from "react";
import { useLoad } from "../hooks.js";
import { Async, Badge, Card, Notice, StatBox, time } from "../components/ui.jsx";
import { cyberAudio } from "../utils/cyberAudio.js";

function safeText(val, fallback = "") {
  if (val === null || val === undefined) return fallback;
  if (typeof val === "object") {
    return val.display_name || val.name || val.ref || "";
  }
  return String(val);
}

export default function MoneyTrailView({ c, caseRef }) {
  const [entity, setEntity] = useState("P-002");
  const [direction, setDirection] = useState("forward");
  const [minAmount, setMinAmount] = useState(0);
  const [maxHops, setMaxHops] = useState(4);
  const [selectedTxn, setSelectedTxn] = useState(null);

  // Load entities to populate selector
  const entState = useLoad(() => c.get("/entities?limit=100"), [c]);

  // Load money trail for the selected entity
  const trailState = useLoad(
    () => c.get("/insights/money-trail", { entity, direction, min_amount: minAmount, max_hops: maxHops }),
    [c, entity, direction, minAmount, maxHops]
  );

  const paths = trailState.data?.paths || [];
  const passThroughs = trailState.data?.pass_through || [];

  // Flatten unique transactions and nodes for Sankey / Flow diagram
  const flowGraph = useMemo(() => {
    const nodes = new Map();
    const links = [];
    const seenLinks = new Set();

    // Add start node
    if (trailState.data?.start) {
      const startObj = trailState.data.start;
      const startName = typeof startObj === "object" ? (startObj.name || startObj.ref || entity) : String(startObj);
      nodes.set(entity, {
        id: entity,
        name: startName,
        type: "START",
        level: 0,
        inflow: 0,
        outflow: 0,
      });
    }

    paths.forEach((p) => {
      let currentLevel = 0;
      (p.steps || []).forEach((step) => {
        const fromId = step.from;
        const toId = step.to;
        const linkKey = `${fromId}->${toId}-${step.txn}`;

        if (!nodes.has(fromId)) {
          nodes.set(fromId, { id: fromId, name: fromId, type: "ACCOUNT", level: currentLevel, inflow: 0, outflow: 0 });
        }
        if (!nodes.has(toId)) {
          const endObj = p.end;
          const endName = typeof endObj === "object" ? (endObj.ref === toId ? endObj.name : toId) : toId;
          nodes.set(toId, { id: toId, name: endName || toId, type: "ACCOUNT", level: currentLevel + 1, inflow: 0, outflow: 0 });
        }

        const fromNode = nodes.get(fromId);
        const toNode = nodes.get(toId);
        fromNode.outflow += Number(step.amount || 0);
        toNode.inflow += Number(step.amount || 0);

        if (!seenLinks.has(linkKey)) {
          seenLinks.add(linkKey);
          links.push({
            id: step.txn,
            source: fromId,
            target: toId,
            amount: Number(step.amount || 0),
            currency: step.currency || "INR",
            time: step.at,
            evidenceRef: step.evidence_ref,
          });
        }
        currentLevel++;
      });
    });

    return {
      nodes: Array.from(nodes.values()),
      links: links.sort((a, b) => b.amount - a.amount),
    };
  }, [paths, trailState.data, entity]);

  const totalVolume = useMemo(() => {
    return flowGraph.links.reduce((acc, l) => acc + l.amount, 0);
  }, [flowGraph.links]);

  return (
    <div className="cm-money-trail-workspace">
      {/* Top Banner Ribbon */}
      <div className="cm-cctv-banner">
        <div className="cm-cctv-banner-left">
          <span className="cm-pulse-emerald" />
          <strong className="font-mono">FINANCIAL FORENSICS & MONEY LAUNDERING SANKEY FLOW</strong>
          <span className="cm-pipeline-badge offline">
            PASS-THROUGH DETECTION ENGINE ACTIVE
          </span>
        </div>
        <div className="cm-cctv-banner-right font-mono text-muted small">
          CASE: {caseRef} · {flowGraph.links.length} TRACED TRANSACTIONS
        </div>
      </div>

      {/* Metrics HUD */}
      <div className="cm-metrics-hud">
        <StatBox
          label="TOTAL VOLUME TRACKED"
          value={`₹${totalVolume.toLocaleString("en-IN")}`}
          sub={`${flowGraph.links.length} transactions across ${flowGraph.nodes.length} accounts`}
          icon="₹"
          accent="amber"
        />
        <StatBox
          label="PASS-THROUGH NODES"
          value={passThroughs.length}
          sub={passThroughs.length > 0 ? "Potential shell/mule funnel accounts detected" : "No rapid pass-throughs"}
          icon="⚠️"
          accent={passThroughs.length > 0 ? "crimson" : "emerald"}
        />
        <StatBox
          label="MAX FLOW HOPS"
          value={maxHops}
          sub={`Traced direction: ${direction.toUpperCase()}`}
          icon="⌬"
          accent="cyan"
        />
        <StatBox
          label="RELEVANT PATHS"
          value={paths.length}
          sub={`Starting from ${entity}`}
          icon="☍"
          accent="purple"
        />
      </div>

      <Notice level="info">
        Money Trail Analysis maps transactional dissipation and funnel networks. Transfers that arrive and leave an account
        within hours are flagged as pass-through shell accounts.
      </Notice>

      {/* Controls Bar */}
      <div className="cm-money-controls-card">
        <div className="row items-center gap-3">
          <label className="font-mono small">
            TARGET ENTITY
            <select
              value={entity}
              onChange={(e) => {
                cyberAudio.playClickChirp();
                setEntity(e.target.value);
              }}
              className="cm-cyber-input"
            >
              {(entState.data?.entities || []).map((ent) => {
                const label = typeof ent.display_name === "string" ? ent.display_name : typeof ent.name === "string" ? ent.name : ent.ref;
                return (
                  <option key={ent.ref} value={ent.ref}>
                    {ent.ref} — {label}
                  </option>
                );
              })}
            </select>
          </label>

          <label className="font-mono small">
            FLOW DIRECTION
            <select
              value={direction}
              onChange={(e) => {
                cyberAudio.playClickChirp();
                setDirection(e.target.value);
              }}
              className="cm-cyber-input"
            >
              <option value="forward">Forward (Where did money go?)</option>
              <option value="backward">Backward (Where did money come from?)</option>
            </select>
          </label>

          <label className="font-mono small">
            MIN AMOUNT (₹)
            <input
              type="number"
              value={minAmount}
              onChange={(e) => setMinAmount(+e.target.value || 0)}
              style={{ width: 100 }}
              className="cm-cyber-input"
            />
          </label>

          <label className="font-mono small">
            MAX HOPS
            <select
              value={maxHops}
              onChange={(e) => setMaxHops(+e.target.value)}
              className="cm-cyber-input"
              style={{ width: 80 }}
            >
              <option value={2}>2</option>
              <option value={3}>3</option>
              <option value={4}>4</option>
              <option value={5}>5</option>
              <option value={6}>6</option>
            </select>
          </label>
        </div>
      </div>

      <div className="cm-sankey-layout">
        {/* Main Interactive Flow Visualization */}
        <div className="cm-sankey-main">
          <Card
            title={`Money Trail Flow: ${entity} (${direction.toUpperCase()})`}
            aside={<span className="font-mono small text-cyan">{paths.length} Flow Paths</span>}
          >
            <Async
              state={trailState}
              empty={Object.assign(() => !paths.length, {
                message: `No transactional fund transfers located for ${entity} with min amount ₹${minAmount}.`,
              })}
            >
              {() => (
                <div className="cm-flow-viewport">
                  {/* Interactive SVG Flow Diagram */}
                  <svg
                    viewBox="0 0 920 460"
                    className="cm-sankey-svg"
                    role="img"
                    aria-label="Interactive Financial Flow Diagram"
                  >
                    <defs>
                      <linearGradient id="flow-grad" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="#00E5FF" stopOpacity="0.8" />
                        <stop offset="100%" stopColor="#FFB52E" stopOpacity="0.8" />
                      </linearGradient>
                      <filter id="flow-glow">
                        <feGaussianBlur stdDeviation="3" result="blur" />
                        <feMerge>
                          <feMergeNode in="blur" />
                          <feMergeNode in="SourceGraphic" />
                        </feMerge>
                      </filter>
                    </defs>

                    {/* Nodes Columns */}
                    {flowGraph.nodes.map((node, idx) => {
                      const colX = 80 + node.level * 220;
                      const rowY = 80 + (idx % 5) * 75;
                      const isStart = node.id === entity;

                      return (
                        <g
                          key={node.id}
                          transform={`translate(${colX}, ${rowY})`}
                          className="cm-flow-node-group"
                        >
                          <rect
                            x="-15"
                            y="-25"
                            width="160"
                            height="50"
                            rx="8"
                            fill={isStart ? "rgba(0, 229, 255, 0.16)" : "rgba(14, 22, 38, 0.85)"}
                            stroke={isStart ? "#00E5FF" : "#FFB52E"}
                            strokeWidth={isStart ? 2.5 : 1.5}
                            filter="url(#flow-glow)"
                          />
                          <text x="6" y="-6" fill="#FFF" className="font-mono" fontSize="12" fontWeight="bold">
                            {node.id}
                          </text>
                          <text x="6" y="12" fill="#8292b0" fontSize="10">
                            {safeText(node.name).length > 18 ? safeText(node.name).slice(0, 16) + "…" : safeText(node.name)}
                          </text>
                        </g>
                      );
                    })}

                    {/* Flow Streams */}
                    {flowGraph.links.map((link, i) => {
                      const fromIdx = flowGraph.nodes.findIndex((n) => n.id === link.source);
                      const toIdx = flowGraph.nodes.findIndex((n) => n.id === link.target);

                      const x1 = 80 + (fromIdx >= 0 ? flowGraph.nodes[fromIdx].level : 0) * 220 + 145;
                      const y1 = 80 + (fromIdx % 5) * 75;
                      const x2 = 80 + (toIdx >= 0 ? flowGraph.nodes[toIdx].level : 1) * 220 - 15;
                      const y2 = 80 + (toIdx % 5) * 75;

                      const isSelected = selectedTxn?.id === link.id;
                      const strokeW = Math.max(3, Math.min(18, (link.amount / (totalVolume || 1)) * 25));

                      const pathD = `M ${x1} ${y1} C ${x1 + 60} ${y1}, ${x2 - 60} ${y2}, ${x2} ${y2}`;

                      return (
                        <g
                          key={link.id || i}
                          onClick={() => {
                            cyberAudio.playHoverBlip();
                            setSelectedTxn(link);
                          }}
                          className={`cm-flow-stream ${isSelected ? "selected" : ""}`}
                          style={{ cursor: "pointer" }}
                        >
                          <path
                            d={pathD}
                            fill="none"
                            stroke="transparent"
                            strokeWidth={strokeW + 14}
                          />
                          <path
                            d={pathD}
                            fill="none"
                            stroke={isSelected ? "#FFF" : "url(#flow-grad)"}
                            strokeWidth={isSelected ? strokeW + 3 : strokeW}
                            opacity={isSelected ? 1 : 0.75}
                            strokeDasharray={isSelected ? "8 4" : undefined}
                          />
                          <text
                            x={(x1 + x2) / 2}
                            y={(y1 + y2) / 2 - 8}
                            fill="#FFB52E"
                            fontSize="10"
                            textAnchor="middle"
                            className="font-mono"
                          >
                            ₹{link.amount.toLocaleString("en-IN")}
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                </div>
              )}
            </Async>
          </Card>
        </div>

        {/* Transaction Telemetry Drawer */}
        <div className="cm-sankey-side">
          <Card
            title={selectedTxn ? "Selected Transaction Exhibit" : "Pass-Through Funnels"}
            aside={selectedTxn && <button className="small" onClick={() => setSelectedTxn(null)}>Clear</button>}
          >
            {selectedTxn ? (
              <div className="stack font-mono small">
                <div className="row items-center justify-between">
                  <span className="text-cyan text-base"><b>{selectedTxn.id}</b></span>
                  <Badge kind="TRANSACTION" />
                </div>
                <div className="cm-amount-callout">
                  <span className="small text-muted">TRANSFER VALUE</span>
                  <strong className="text-amber text-xl">
                    ₹{selectedTxn.amount.toLocaleString("en-IN")} {selectedTxn.currency}
                  </strong>
                </div>
                <div className="kv"><span>From Account</span><b>{selectedTxn.source}</b></div>
                <div className="kv"><span>To Beneficiary</span><b>{selectedTxn.target}</b></div>
                <div className="kv"><span>Execution Time</span><span>{time(selectedTxn.time)}</span></div>
                <div className="kv"><span>Evidence Link</span><span className="text-cyan">{selectedTxn.evidenceRef || "—"}</span></div>
              </div>
            ) : (
              <div className="stack">
                {passThroughs.length === 0 ? (
                  <p className="muted small">
                    No immediate pass-through shell accounts detected. Funds were retained or routed through normal commercial cadences.
                  </p>
                ) : (
                  passThroughs.map((pt, i) => {
                    const entityRef = typeof pt.entity === "object" ? pt.entity?.ref : String(pt.entity || "N/A");
                    const entityName = typeof pt.entity === "object" ? (typeof pt.entity?.name === "string" ? pt.entity.name : "") : "";
                    const receivedAmount = pt.received?.amount ?? pt.inflow ?? 0;
                    const forwardedAmount = pt.forwarded_within_48h ?? pt.outflow ?? 0;
                    const txnId = pt.received?.txn || "";

                    return (
                      <div key={i} className="cm-passthrough-card">
                        <div className="cm-passthrough-badge">FLAGGED PASS-THROUGH</div>
                        <div style={{ marginTop: 6 }}>
                          <strong className="text-amber">
                            {entityRef}
                          </strong>
                          {entityName && (
                            <span className="small text-muted" style={{ marginLeft: 6 }}>
                              ({entityName})
                            </span>
                          )}
                        </div>
                        <div className="small text-muted" style={{ marginTop: 6, lineHeight: 1.5 }}>
                          Inflow: <span className="text-cyan">₹{Number(receivedAmount).toLocaleString("en-IN")}</span>
                          {txnId ? ` (${txnId})` : ""}
                          <br />
                          Forwarded within 48h: <span className="text-amber">₹{Number(forwardedAmount).toLocaleString("en-IN")}</span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
