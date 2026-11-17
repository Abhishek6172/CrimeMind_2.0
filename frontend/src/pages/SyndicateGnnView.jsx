import React, { useState, useEffect, useRef } from "react";
import { api } from "../api.js";
import { Card, Badge, StatBox } from "../components/ui.jsx";
import { cyberAudio } from "../utils/cyberAudio.js";

export default function SyndicateGnnView({ caseRef }) {
  const [loading, setLoading] = useState(true);
  const [gnnData, setGnnData] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [filterThreshold, setFilterThreshold] = useState(0.65);
  const [isInferencing, setIsInferencing] = useState(false);
  const canvasRef = useRef(null);
  const animRef = useRef(null);

  // Fetch GNN Analysis
  const fetchGnn = async () => {
    setIsInferencing(true);
    cyberAudio.playScan?.();
    try {
      const res = await api("/ml/gnn/analyze", {
        method: "POST",
        body: { case_id: caseRef },
      });
      setGnnData(res);
      if (res.suspected_mastermind) {
        setSelectedNode(res.suspected_mastermind);
      }
    } catch (err) {
      console.error("GNN fetch failed", err);
    } finally {
      setLoading(false);
      setIsInferencing(false);
    }
  };

  useEffect(() => {
    fetchGnn();
  }, [caseRef]);

  // Interactive 60 FPS HTML5 Canvas Force-Directed Network Graph
  useEffect(() => {
    if (!gnnData || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Initialize node positions
    const nodes = gnnData.nodes.map((n, i) => {
      const angle = (i / gnnData.nodes.length) * Math.PI * 2;
      const r = n.is_mastermind ? 40 : 160 + (i % 3) * 35;
      return {
        ...n,
        x: width / 2 + Math.cos(angle) * r,
        y: height / 2 + Math.sin(angle) * r,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
      };
    });

    let phase = 0;

    const render = () => {
      ctx.clearRect(0, 0, width, height);
      phase += 0.03;

      // Draw Background Grid
      ctx.strokeStyle = "rgba(30, 58, 95, 0.25)";
      ctx.lineWidth = 1;
      const step = 40;
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

      // Draw Known Edges (Solid Cyan/Gray Lines)
      ctx.lineWidth = 1.5;
      gnnData.known_edges.forEach((edge) => {
        const u = nodes.find((n) => n.id === edge.source);
        const v = nodes.find((n) => n.id === edge.target);
        if (u && v) {
          ctx.beginPath();
          ctx.strokeStyle = "rgba(6, 182, 212, 0.4)";
          ctx.moveTo(u.x, u.y);
          ctx.lineTo(v.x, v.y);
          ctx.stroke();
        }
      });

      // Draw PyTorch GCN Predicted Hidden Links (Glowing Amber Dashed with Pulse)
      const visiblePredicted = gnnData.predicted_links.filter(
        (l) => l.probability >= filterThreshold
      );
      visiblePredicted.forEach((link, idx) => {
        const u = nodes.find((n) => n.id === link.source);
        const v = nodes.find((n) => n.id === link.target);
        if (u && v) {
          ctx.save();
          ctx.setLineDash([6, 6]);
          ctx.lineDashOffset = -phase * 20;
          ctx.lineWidth = 2.0;
          ctx.strokeStyle = `rgba(245, 158, 11, ${0.4 + Math.sin(phase + idx) * 0.3})`;
          ctx.beginPath();
          ctx.moveTo(u.x, u.y);
          ctx.lineTo(v.x, v.y);
          ctx.stroke();

          // Draw Probability Badge at midpoint
          const mx = (u.x + v.x) / 2;
          const my = (u.y + v.y) / 2;
          ctx.fillStyle = "#0B0F19";
          ctx.fillRect(mx - 24, my - 9, 48, 18);
          ctx.strokeStyle = "#F59E0B";
          ctx.lineWidth = 1;
          ctx.setLineDash([]);
          ctx.strokeRect(mx - 24, my - 9, 48, 18);
          ctx.fillStyle = "#F59E0B";
          ctx.font = "bold 9px monospace";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(`${link.confidence_percent}%`, mx, my);
          ctx.restore();
        }
      });

      // Draw Nodes
      nodes.forEach((node) => {
        const isMaster = node.is_mastermind;
        const isSel = selectedNode && selectedNode.id === node.id;
        const nodeRadius = isMaster ? 22 : 14;

        // Outer glow
        const glowGrad = ctx.createRadialGradient(node.x, node.y, 4, node.x, node.y, nodeRadius + 12);
        if (isMaster) {
          glowGrad.addColorStop(0, "rgba(244, 63, 94, 0.6)");
          glowGrad.addColorStop(1, "rgba(244, 63, 94, 0)");
        } else {
          glowGrad.addColorStop(0, "rgba(6, 182, 212, 0.4)");
          glowGrad.addColorStop(1, "rgba(6, 182, 212, 0)");
        }
        ctx.fillStyle = glowGrad;
        ctx.beginPath();
        ctx.arc(node.x, node.y, nodeRadius + 12, 0, Math.PI * 2);
        ctx.fill();

        // Node Body
        ctx.beginPath();
        ctx.arc(node.x, node.y, nodeRadius, 0, Math.PI * 2);
        ctx.fillStyle = isMaster ? "#7F1D1D" : isSel ? "#0E7490" : "#131D31";
        ctx.fill();
        ctx.lineWidth = isSel || isMaster ? 2.5 : 1.5;
        ctx.strokeStyle = isMaster ? "#F43F5E" : isSel ? "#38BDF8" : "#06B6D4";
        ctx.stroke();

        // Node Label
        ctx.font = isMaster ? "bold 11px sans-serif" : "10px sans-serif";
        ctx.fillStyle = isMaster ? "#FCA5A5" : "#E2E8F0";
        ctx.textAlign = "center";
        ctx.fillText(node.name.split(" ")[0], node.x, node.y + nodeRadius + 14);

        if (isMaster) {
          ctx.font = "bold 8px monospace";
          ctx.fillStyle = "#F43F5E";
          ctx.fillText("★ MASTERMIND", node.x, node.y - nodeRadius - 6);
        }
      });

      animRef.current = requestAnimationFrame(render);
    };

    render();

    // Handle canvas click to select node
    const handleClick = (e) => {
      const rect = canvas.getBoundingClientRect();
      const clickX = ((e.clientX - rect.left) / rect.width) * width;
      const clickY = ((e.clientY - rect.top) / rect.height) * height;

      for (let n of nodes) {
        const dist = Math.hypot(n.x - clickX, n.y - clickY);
        if (dist <= 26) {
          setSelectedNode(n);
          cyberAudio.playClick?.();
          break;
        }
      }
    };

    canvas.addEventListener("click", handleClick);

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
      canvas.removeEventListener("click", handleClick);
    };
  }, [gnnData, filterThreshold, selectedNode]);

  if (loading) {
    return (
      <div className="p-8 text-center font-mono text-cyan">
        <span className="cm-pulse-dot" /> EXECUTING PYTORCH GCN FORWARD PASS & TOPOLOGICAL EMBEDDING...
      </div>
    );
  }

  const mastermind = gnnData?.suspected_mastermind;

  return (
    <div className="space-y-6">
      {/* Top Banner Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border-subtle pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xl">🕸️</span>
            <h1 className="text-2xl font-bold tracking-wider text-white uppercase">
              Syndicate GNN Analysis
            </h1>
            <Badge tone="cyan">PyTorch Spectral GCN</Badge>
          </div>
          <p className="text-xs text-muted font-mono mt-1">
            2-Layer Graph Convolutional Network: Topological Latent Space & Hidden Syndicate Link Prediction
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            className="btn btn-outline border-cyan text-cyan hover:bg-cyan hover:text-black font-mono text-xs px-3 py-1.5"
            onClick={fetchGnn}
            disabled={isInferencing}
          >
            {isInferencing ? "🔄 COMPUTING..." : "⚡ RE-RUN GCN FORWARD PASS"}
          </button>
        </div>
      </div>

      {/* 4 Stat Metric KPI Boxes */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatBox
          label="NETWORK SUSPECTS"
          value={gnnData?.total_suspects || 0}
          caption="Graph Vertices"
          accent="cyan"
        />
        <StatBox
          label="OBSERVED EDGES"
          value={gnnData?.total_known_edges || 0}
          caption="Known Interactions"
          accent="gold"
        />
        <StatBox
          label="PREDICTED LINKS"
          value={gnnData?.total_predicted_links || 0}
          caption="Latent Connections"
          accent="magenta"
        />
        <StatBox
          label="SUSPECTED MASTERMIND"
          value={mastermind ? mastermind.name.split(" ")[0] : "UNDETERMINED"}
          caption={mastermind ? `Betweenness: ${mastermind.betweenness_centrality}` : "Computing"}
          accent="emerald"
        />
      </div>

      {/* Main Interactive Network Canvas + Inspector Split */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Interactive Graph Canvas */}
        <div className="lg:col-span-2 space-y-3">
          <Card className="p-4 bg-slate-900/60 border border-border-subtle relative overflow-hidden">
            <div className="flex items-center justify-between mb-3 text-xs font-mono">
              <span className="text-cyan font-bold">
                GRAPH TOPOLOGY VIEW // LATENT EMBEDDINGS (DIM=8)
              </span>
              <div className="flex items-center gap-2">
                <span className="text-muted">LINK CONFIDENCE:</span>
                <input
                  type="range"
                  min="0.5"
                  max="0.9"
                  step="0.05"
                  value={filterThreshold}
                  onChange={(e) => setFilterThreshold(parseFloat(e.target.value))}
                  className="w-24 accent-cyan"
                />
                <span className="text-gold font-bold">{Math.round(filterThreshold * 100)}%</span>
              </div>
            </div>

            <canvas
              ref={canvasRef}
              width={750}
              height={440}
              className="w-full h-[440px] rounded bg-[#070b14] border border-cyan/20 cursor-crosshair shadow-inner"
            />

            <div className="flex items-center justify-between mt-3 text-[11px] font-mono text-muted">
              <div className="flex items-center gap-4">
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-cyan inline-block" /> Known Edge
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-gold border border-dashed inline-block" /> Predicted GCN Link
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block" /> Mastermind / Broker
                </span>
              </div>
              <span>Click any suspect node to inspect latent vector</span>
            </div>
          </Card>

          {/* Predicted Hidden Links Table */}
          <Card className="p-4 border border-border-subtle bg-slate-900/40">
            <h3 className="text-sm font-bold tracking-wide text-gold uppercase mb-3 flex items-center gap-2">
              <span>⚡</span> Top Latent Link Predictions (GCN Link Probability)
            </h3>
            <div className="space-y-2">
              {gnnData?.predicted_links
                .filter((l) => l.probability >= filterThreshold)
                .map((link, idx) => (
                  <div
                    key={idx}
                    className="flex flex-wrap items-center justify-between p-2.5 rounded bg-slate-800/50 border border-slate-700/60 text-xs font-mono"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-cyan font-bold">{link.source_name}</span>
                      <span className="text-gold">⮂ [UNOBSERVED LINK] ⮂</span>
                      <span className="text-cyan font-bold">{link.target_name}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-muted">Cosine: {link.latent_cosine_sim}</span>
                      <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold border border-amber-500/40">
                        {link.confidence_percent}% PROBABILITY
                      </span>
                    </div>
                  </div>
                ))}
            </div>
          </Card>
        </div>

        {/* Right Col: Node Inspector & Mastermind Intelligence Dossier */}
        <div className="space-y-4">
          {/* Mastermind Card */}
          {mastermind && (
            <Card className="p-5 border-2 border-rose-500/50 bg-rose-950/20 shadow-lg">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono text-rose-400 font-bold">TOPOLOGICAL KINGPIN IDENTIFIED</span>
                <Badge tone="red">PRIMARY TARGET</Badge>
              </div>
              <h2 className="text-xl font-bold text-white mt-1">{mastermind.name}</h2>
              <div className="text-xs font-mono text-muted mb-3">ID: {mastermind.id} | {mastermind.community_cell}</div>

              <div className="space-y-2 text-xs font-mono border-t border-rose-500/30 pt-3">
                <div className="flex justify-between">
                  <span className="text-muted">Betweenness Centrality:</span>
                  <span className="text-rose-300 font-bold">{mastermind.betweenness_centrality}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted">Network PageRank:</span>
                  <span className="text-cyan font-bold">{mastermind.pagerank}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted">Syndicate Degree:</span>
                  <span className="text-gold font-bold">{mastermind.degree} Direct Connections</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted">Assessed Flight Risk:</span>
                  <span className="text-rose-400 font-bold">{mastermind.risk_score * 100}%</span>
                </div>
              </div>

              <p className="mt-3 text-xs text-slate-300 italic">
                Highest structural brokerage index across all cell nodes. Coordinates independent communication channels without direct contact with field operatives.
              </p>
            </Card>
          )}

          {/* Inspected Node Detail */}
          {selectedNode && (
            <Card className="p-4 border border-cyan/40 bg-slate-900/70">
              <span className="text-xs font-mono text-cyan font-bold">NODE EMBEDDING INSPECTOR</span>
              <h3 className="text-lg font-bold text-white mt-1">{selectedNode.name}</h3>
              <div className="text-xs font-mono text-gold mb-3">ROLE: {selectedNode.role}</div>

              <div className="space-y-2 text-xs font-mono">
                <div className="flex justify-between border-b border-slate-800 pb-1">
                  <span className="text-muted">Cell Cluster:</span>
                  <span className="text-cyan font-bold">{selectedNode.community_cell}</span>
                </div>
                <div className="flex justify-between border-b border-slate-800 pb-1">
                  <span className="text-muted">Betweenness Index:</span>
                  <span className="text-white">{selectedNode.betweenness_centrality}</span>
                </div>
                <div className="flex justify-between border-b border-slate-800 pb-1">
                  <span className="text-muted">PageRank Centrality:</span>
                  <span className="text-white">{selectedNode.pagerank}</span>
                </div>
              </div>

              <div className="mt-4">
                <span className="text-[10px] font-mono text-muted block mb-1">
                  PYTORCH GCN LATENT VECTOR (DIM 0..3):
                </span>
                <div className="grid grid-cols-4 gap-1 font-mono text-[10px] text-center">
                  {selectedNode.embedding_vector?.map((v, i) => (
                    <div key={i} className="p-1 rounded bg-cyan/10 border border-cyan/30 text-cyan">
                      z_{i}:{v}
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
