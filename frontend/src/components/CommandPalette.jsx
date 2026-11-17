import React, { useEffect, useState, useRef } from "react";
import { cyberAudio } from "../utils/cyberAudio.js";

export function CommandPalette({ isOpen, onClose, onSelectAction, caseRef }) {
  const [query, setQuery] = useState("");
  const [selectedIdx, setSelectedIdx] = useState(0);
  const inputRef = useRef(null);

  const ACTIONS = [
    { id: "tab-dashboard", label: "Open Case Dashboard", category: "NAVIGATION", icon: "⌖", run: () => onSelectAction("tab", "Dashboard") },
    { id: "tab-ballistics", label: "Open Ballistics Trajectory & 3D Ray-Tracer", category: "FORENSICS", icon: "🎯", run: () => onSelectAction("tab", "Ballistics 3D") },
    { id: "tab-money-trail", label: "Open Financial Flow & Money Trail (Sankey)", category: "FINANCIAL", icon: "💸", run: () => onSelectAction("tab", "Money Trail") },
    { id: "tab-crime-board", label: "Open Virtual Detective 'Red String' Crime Board", category: "INVESTIGATION", icon: "📌", run: () => onSelectAction("tab", "Crime Board") },
    { id: "tab-evidence-vault", label: "Open Cryptographic Evidence Vault Ledger", category: "FORENSICS", icon: "🔐", run: () => onSelectAction("tab", "Evidence Vault") },
    { id: "tab-cctv", label: "Open CCTV Surveillance Workspace", category: "SURVEILLANCE", icon: "⌕", run: () => onSelectAction("tab", "CCTV Analysis") },
    { id: "tab-statement-nlp", label: "Open Statement Credibility & Cognitive Load NLP Analyzer", category: "PSYCHOLOGICAL FORENSICS", icon: "🧠", run: () => onSelectAction("tab", "Statement NLP") },
    { id: "action-voice-stress", label: "Start Live Microphone Voice Stress & Pitch Tremor Interrogation", category: "VOICE BIOMETRICS", icon: "🎙️", run: () => onSelectAction("tab", "Statement NLP") },
    { id: "tab-gnn", label: "Open Syndicate GNN Link Prediction (PyTorch GCN)", category: "MACHINE LEARNING", icon: "🕸️", run: () => onSelectAction("tab", "Syndicate GNN") },
    { id: "tab-financial-ml", label: "Open Financial Forensics & Smurfing Anomaly Detector (Isolation Forest)", category: "MACHINE LEARNING", icon: "💳", run: () => onSelectAction("tab", "Financial ML") },
    { id: "tab-geo-ml", label: "Open Geographic Profiling & Serial Offender Spatial Forecaster (Rossmo)", category: "MACHINE LEARNING", icon: "🗺️", run: () => onSelectAction("tab", "Geographic ML") },
    { id: "tab-graph", label: "Open Relationship Graph", category: "NETWORK", icon: "☍", run: () => onSelectAction("tab", "Graph") },
    { id: "tab-ai", label: "Open AI Intelligence Assistant", category: "INTELLIGENCE", icon: "✧", run: () => onSelectAction("tab", "AI analysis") },
    { id: "tab-evidence", label: "Open Evidence Register", category: "FORENSICS", icon: "☵", run: () => onSelectAction("tab", "Evidence") },
    { id: "tab-questions", label: "Open SQL Module Runner (40 Questions)", category: "DATABASE", icon: "⌘", run: () => onSelectAction("tab", "Questions") },
    { id: "tab-analysis", label: "Open Movement Plausibility & Alibi Checker", category: "ANALYSIS", icon: "⌬", run: () => onSelectAction("tab", "Analysis") },
    { id: "optics-cyber", label: "Switch Optics: Electric Cyan & Graphite", category: "TACTICAL OPTICS", icon: "🩵", run: () => onSelectAction("optics", "cyber") },
    { id: "optics-nvg", label: "Switch Optics: NVG Night Vision (Phosphor Green)", category: "TACTICAL OPTICS", icon: "🟢", run: () => onSelectAction("optics", "nvg") },
    { id: "optics-flir", label: "Switch Optics: FLIR Thermal Infrared", category: "TACTICAL OPTICS", icon: "🔴", run: () => onSelectAction("optics", "flir") },
    { id: "optics-blueprint", label: "Switch Optics: Blueprint Vector Schematic", category: "TACTICAL OPTICS", icon: "📐", run: () => onSelectAction("optics", "blueprint") },
    { id: "emp-trigger", label: "Trigger Manual EMP Diagnostic Shockwave", category: "DIAGNOSTICS", icon: "⚡", run: () => onSelectAction("emp") },
    { id: "toggle-audio", label: "Toggle Procedural Tactical Audio (SFX)", category: "AUDIO HUD", icon: "🔊", run: () => onSelectAction("audio") },
    { id: "open-research", label: "Switch to Scientific Research Lab", category: "RESEARCH", icon: "🔬", run: () => onSelectAction("research") },
  ];

  const filtered = ACTIONS.filter(
    (a) =>
      a.label.toLowerCase().includes(query.toLowerCase()) ||
      a.category.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setSelectedIdx(0);
      cyberAudio.playHoverBlip();
    } else {
      setQuery("");
    }
  }, [isOpen]);

  useEffect(() => {
    setSelectedIdx(0);
  }, [query]);

  const handleKeyDown = (e) => {
    if (e.key === "Escape") {
      onClose();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIdx((i) => (i + 1) % Math.max(1, filtered.length));
      cyberAudio.playHoverBlip();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIdx((i) => (i - 1 + filtered.length) % Math.max(1, filtered.length));
      cyberAudio.playHoverBlip();
    } else if (e.key === "Enter" && filtered[selectedIdx]) {
      e.preventDefault();
      cyberAudio.playClickChirp();
      filtered[selectedIdx].run();
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="cm-palette-backdrop" onClick={onClose}>
      <div className="cm-palette-window" onClick={(e) => e.stopPropagation()}>
        <div className="cm-palette-header">
          <span className="cm-palette-glyph font-mono text-cyan">CRIMEMIND:COMMAND_PALETTE&gt;</span>
          <input
            ref={inputRef}
            type="text"
            placeholder="Type a command, case ref, optics mode, or tab name…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="cm-palette-input"
          />
          <span className="cm-palette-esc font-mono text-muted small">ESC TO CLOSE</span>
        </div>

        <div className="cm-palette-results">
          {filtered.length === 0 ? (
            <div className="cm-palette-empty font-mono text-muted small">
              NO DIRECTIVES MATCH QUERY "{query}"
            </div>
          ) : (
            filtered.map((item, idx) => {
              const isSelected = idx === selectedIdx;
              return (
                <div
                  key={item.id}
                  className={`cm-palette-item ${isSelected ? "selected" : ""}`}
                  onClick={() => {
                    cyberAudio.playClickChirp();
                    item.run();
                    onClose();
                  }}
                  onPointerEnter={() => setSelectedIdx(idx)}
                >
                  <span className="cm-palette-item-icon">{item.icon}</span>
                  <div className="cm-palette-item-info">
                    <span className="cm-palette-item-label">{item.label}</span>
                    <span className="cm-palette-item-cat font-mono text-muted small">
                      {item.category}
                    </span>
                  </div>
                  {isSelected && <span className="cm-palette-enter-hint font-mono text-cyan small">↵ ENTER</span>}
                </div>
              );
            })
          )}
        </div>

        <div className="cm-palette-footer font-mono small text-muted">
          <span>NAVIGATION: ↑↓ ARROWS</span>
          <span>EXECUTE: ↵ ENTER</span>
          <span>DOCKET: {caseRef || "REGISTRY VIEW"}</span>
        </div>
      </div>
    </div>
  );
}
