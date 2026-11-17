import React, { useState, useEffect, useRef } from "react";
import { api } from "../../api.js";
import { cyberAudio } from "../../utils/cyberAudio.js";

const DEFAULT_HYPERPARAMS = {
  algorithm: "raeer",
  seeds: [2026, 2027, 2028],
  caseFilter: "all",
  metrics: ["nDCG@5", "P@5", "R@5", "MRR", "AP"],
  weights: {
    spatial: 0.35,
    temporal: 0.10,
    communication: 0.15,
    financial: 0.15,
    relational: 0.10,
    corroboration: 0.15,
  },
  contradiction: {
    gamma: 0.50,
    distance_m: 1000,
  },
  temporal_tau_minutes: 30,
  scene_radius_m: 150,
  challenged_factor: 0.50,
  features: {
    reliability: true,
    temporal: true,
    relational: true,
    independence: true,
    contradiction: true,
    lifecycle: true,
    corroboration: true,
  },
};

export default function HyperparameterTuner() {
  // 1. Hyperparameter & Config State
  const [config, setConfig] = useState(DEFAULT_HYPERPARAMS);
  const [isConfigModified, setIsConfigModified] = useState(false);

  // 2. Execution & Polling State
  const [activeJobId, setActiveJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [logs, setLogs] = useState([]);
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionError, setExecutionError] = useState("");

  // 3. Genuine Results State (from Backend ONLY)
  const [activeExperiment, setActiveExperiment] = useState(null);
  const [expandedSeed, setExpandedSeed] = useState(null);

  // 4. Comparative Study State
  const [isComparing, setIsComparing] = useState(false);
  const [comparisonResults, setComparisonResults] = useState(null);

  // 5. Experiment History
  const [recentExperiments, setRecentExperiments] = useState([]);
  const logsEndRef = useRef(null);

  // Load recent experiments on mount
  useEffect(() => {
    fetchRecentExperiments();
  }, []);

  const fetchRecentExperiments = async () => {
    try {
      const data = await api("/research/experiments?limit=5");
      if (Array.isArray(data)) {
        setRecentExperiments(data);
      }
    } catch {}
  };

  // Poll active experiment job
  useEffect(() => {
    if (!activeJobId) return;
    let failCount = 0;

    const interval = setInterval(async () => {
      try {
        const status = await api(`/research/experiments/${activeJobId}/status`);
        setJobStatus(status);

        // Fetch logs
        try {
          const lData = await api(`/research/experiments/${activeJobId}/logs?limit=100`);
          if (Array.isArray(lData)) setLogs(lData);
        } catch {}

        if (status.status === "COMPLETED") {
          clearInterval(interval);
          setActiveJobId(null);
          setIsExecuting(false);
          setIsConfigModified(false);
          cyberAudio.playSuccess();
          // Fetch full results
          const fullExp = await api(`/research/experiments/${activeJobId}`);
          setActiveExperiment(fullExp);
          fetchRecentExperiments();
        } else if (status.status === "FAILED" || status.status === "CANCELLED") {
          clearInterval(interval);
          setActiveJobId(null);
          setIsExecuting(false);
          cyberAudio.playGlitch();
          setExecutionError(status.error_message || `Experiment ${status.status.toLowerCase()}`);
        }
      } catch (err) {
        failCount += 1;
        if (failCount >= 6) {
          clearInterval(interval);
          setActiveJobId(null);
          setIsExecuting(false);
        }
      }
    }, 1200);

    return () => clearInterval(interval);
  }, [activeJobId]);

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // Handlers for parameters
  const updateWeight = (domain, val) => {
    setIsConfigModified(true);
    setConfig((prev) => ({
      ...prev,
      weights: { ...prev.weights, [domain]: parseFloat(val) },
    }));
  };

  const updateContradiction = (key, val) => {
    setIsConfigModified(true);
    setConfig((prev) => ({
      ...prev,
      contradiction: { ...prev.contradiction, [key]: parseFloat(val) },
    }));
  };

  const updateFeature = (key) => {
    setIsConfigModified(true);
    setConfig((prev) => ({
      ...prev,
      features: { ...prev.features, [key]: !prev.features[key] },
    }));
  };

  const setSeedsQuick = (count) => {
    setIsConfigModified(true);
    const startSeed = 2026;
    const newSeeds = Array.from({ length: count }, (_, i) => startSeed + i);
    setConfig((prev) => ({ ...prev, seeds: newSeeds }));
  };

  const resetDefaults = () => {
    cyberAudio.playSuccess();
    setConfig(DEFAULT_HYPERPARAMS);
    setIsConfigModified(false);
    setExecutionError("");
  };

  // Launch Live Backend Experiment
  const handleRunExperiment = async () => {
    try {
      setIsExecuting(true);
      setExecutionError("");
      setLogs([]);
      cyberAudio.playScan();

      const payload = {
        name: `RAEER Tuning · ${config.seeds.length} Seeds · γ=${config.contradiction.gamma.toFixed(2)}`,
        algorithm: config.algorithm,
        dataset_id: "synthetic_seeds",
        seeds: config.seeds,
        cases: config.caseFilter === "all" ? null : [config.caseFilter],
        parameters: {
          weights: config.weights,
          contradiction: config.contradiction,
          temporal_tau_minutes: config.temporal_tau_minutes,
          scene_radius_m: config.scene_radius_m,
          features: config.features,
          status_factor: {
            SUPPORTED: 1.0,
            CHALLENGED: config.challenged_factor,
            INVALIDATED: 0.0,
            SUPERSEDED: 0.0,
          },
        },
        metrics: config.metrics,
      };

      const res = await api("/research/experiments/run", {
        method: "POST",
        body: payload,
      });

      setActiveJobId(res.experiment_id);
      setJobStatus({
        status: "QUEUED",
        progress_pct: 0,
        current_step: "Queued for worker execution",
      });
    } catch (err) {
      setIsExecuting(false);
      setExecutionError(err.message || "Failed to dispatch experiment");
      cyberAudio.playGlitch();
    }
  };

  // Cancel experiment
  const handleCancelExperiment = async () => {
    if (!activeJobId) return;
    try {
      await api(`/research/experiments/${activeJobId}/cancel`, { method: "POST" });
      cyberAudio.playClickChirp();
    } catch {}
  };

  // Run Comparative Benchmark (Q40, Q40-R, RAEER)
  const handleRunComparison = async () => {
    try {
      setIsComparing(true);
      cyberAudio.playScan();
      const payload = {
        name: `Benchmark Study (${config.seeds.length} Seeds)`,
        algorithms: ["q40_py", "q40_r", "raeer"],
        seeds: config.seeds,
        cases: config.caseFilter === "all" ? null : [config.caseFilter],
        raeer_parameters: {
          weights: config.weights,
          contradiction: config.contradiction,
          temporal_tau_minutes: config.temporal_tau_minutes,
        },
        metrics: config.metrics,
      };

      // We run the benchmark directly via backend service or run endpoint
      const res = await api("/research/experiments/compare", {
        method: "POST",
        body: payload,
      });
      cyberAudio.playSuccess();
      // Poll recent experiments after a short wait
      setTimeout(() => {
        setIsComparing(false);
        fetchRecentExperiments();
      }, 3000);
    } catch (err) {
      setIsComparing(false);
      cyberAudio.playGlitch();
    }
  };

  // Load a completed experiment from history
  const loadHistoricalExperiment = async (expId) => {
    try {
      cyberAudio.playClickChirp();
      const exp = await api(`/research/experiments/${expId}`);
      setActiveExperiment(exp);
      setIsConfigModified(false);
    } catch {}
  };

  return (
    <div className="cm-tuner-widget" style={{ padding: 20 }}>
      {/* Header Banner */}
      <div className="cm-tuner-header row justify-between items-center" style={{ marginBottom: 16 }}>
        <div>
          <div className="row items-center gap-2">
            <span className="cm-pulse-cyan" />
            <h3 className="font-mono text-cyan" style={{ margin: 0, fontSize: 15, letterSpacing: "0.08em" }}>
              GENUINE RESEARCH EXPERIMENT PLATFORM · RAEER HYPERPARAMETER TUNER
            </h3>
            <span className="cm-badge-tag" style={{ background: "rgba(0, 229, 255, 0.15)", color: "#00e5ff", fontSize: "0.7rem", padding: "2px 8px" }}>
              POSTGRESQL PERSISTED · REAL COMPUTATION
            </span>
          </div>
          <p className="font-mono text-xs text-muted" style={{ margin: "4px 0 0 0" }}>
            Executes real mathematical ranking algorithms against synthetic ground truth datasets. Zero simulated or projected values.
          </p>
        </div>

        <div className="row items-center gap-2">
          <button
            className="cm-filter-pill"
            onClick={resetDefaults}
            disabled={isExecuting}
            title="Restore default Phase 4 frozen RAEER parameters"
          >
            ⟲ RESTORE RAEER DEFAULTS
          </button>
          <button
            className="cm-filter-pill"
            style={{ borderColor: "var(--cm-amber, #f59e0b)", color: "#f59e0b" }}
            onClick={handleRunComparison}
            disabled={isExecuting || isComparing}
            title="Execute head-to-head evaluation of Q40, Q40-R, and RAEER"
          >
            {isComparing ? "⚡ RUNNING BENCHMARK..." : "⚡ BENCHMARK VS BASELINES"}
          </button>
        </div>
      </div>

      {/* Main Grid: Parameters on Left, Execution & Results on Right */}
      <div className="row gap-4" style={{ alignItems: "flex-start" }}>
        {/* LEFT COLUMN: Controls & Hyperparameters */}
        <div style={{ flex: "1 1 520px", display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Card 1: Target Algorithm & Dataset Seed Selection */}
          <div className="cm-cyber-panel" style={{ padding: 14 }}>
            <div className="row justify-between items-center" style={{ marginBottom: 10 }}>
              <span className="font-mono text-xs text-cyan" style={{ fontWeight: 700 }}>
                1. TARGET ALGORITHM & DATASET SEEDS
              </span>
              <span className="font-mono text-xs text-muted">50 Seeds Available</span>
            </div>

            <div className="row gap-3" style={{ marginBottom: 10 }}>
              <div style={{ flex: 1 }}>
                <label className="font-mono text-xs text-muted block" style={{ marginBottom: 4 }}>
                  ALGORITHM:
                </label>
                <select
                  className="cm-cyber-input font-mono small full-width"
                  value={config.algorithm}
                  onChange={(e) => {
                    setIsConfigModified(true);
                    setConfig((prev) => ({ ...prev, algorithm: e.target.value }));
                  }}
                  disabled={isExecuting}
                >
                  <option value="raeer">RAEER (Reliability-Aware Evidence Evolution Ranking)</option>
                  <option value="q40_r">Q40-R (Reliability-Weighted Baseline)</option>
                  <option value="q40_py">Q40 (Frozen Phase 3 Baseline)</option>
                  <option value="raeer-no_contradiction">RAEER Ablation: No Contradiction Penalty</option>
                  <option value="raeer-no_lifecycle">RAEER Ablation: No Lifecycle Awareness</option>
                  <option value="raeer-no_temporal">RAEER Ablation: No Temporal Decay</option>
                  <option value="raeer-no_independence">RAEER Ablation: No Source Independence</option>
                </select>
              </div>

              <div style={{ flex: 1 }}>
                <label className="font-mono text-xs text-muted block" style={{ marginBottom: 4 }}>
                  CASE SCOPE:
                </label>
                <select
                  className="cm-cyber-input font-mono small full-width"
                  value={config.caseFilter}
                  onChange={(e) => {
                    setIsConfigModified(true);
                    setConfig((prev) => ({ ...prev, caseFilter: e.target.value }));
                  }}
                  disabled={isExecuting}
                >
                  <option value="all">All Cases (CASE-001 & CASE-002)</option>
                  <option value="CASE-2026-001">CASE-2026-001 Only</option>
                  <option value="CASE-2026-002">CASE-2026-002 Only</option>
                </select>
              </div>
            </div>

            {/* Seed Quick Selectors */}
            <div>
              <div className="row justify-between items-center" style={{ marginBottom: 6 }}>
                <span className="font-mono text-xs text-muted">EVALUATION SEEDS ({config.seeds.length}):</span>
                <div className="row gap-1">
                  <button className="cm-badge-tag" onClick={() => setSeedsQuick(1)} style={{ cursor: "pointer" }}>1 Seed</button>
                  <button className="cm-badge-tag" onClick={() => setSeedsQuick(3)} style={{ cursor: "pointer" }}>3 Seeds</button>
                  <button className="cm-badge-tag" onClick={() => setSeedsQuick(5)} style={{ cursor: "pointer" }}>5 Seeds</button>
                  <button className="cm-badge-tag" onClick={() => setSeedsQuick(10)} style={{ cursor: "pointer" }}>10 Seeds</button>
                </div>
              </div>
              <div className="row gap-1 flex-wrap">
                {config.seeds.map((s) => (
                  <span key={s} className="cm-badge-tag" style={{ background: "rgba(0, 229, 255, 0.12)", color: "#00e5ff" }}>
                    seed_{s}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Card 2: RAEER Hyperparameter Controls */}
          {config.algorithm.startsWith("raeer") && (
            <div className="cm-cyber-panel" style={{ padding: 14 }}>
              <span className="font-mono text-xs text-cyan block" style={{ fontWeight: 700, marginBottom: 12 }}>
                2. GENUINE RAEER HYPERPARAMETERS
              </span>

              {/* Contradiction Penalty Gamma */}
              <div className="cm-tuner-row" style={{ marginBottom: 12 }}>
                <div className="row justify-between items-center">
                  <span className="font-mono small">CONTRADICTION PENALTY (γ):</span>
                  <strong className="text-amber font-mono small">{config.contradiction.gamma.toFixed(2)}</strong>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={config.contradiction.gamma}
                  onChange={(e) => updateContradiction("gamma", e.target.value)}
                  className="cm-cyber-range"
                  disabled={isExecuting}
                />
                <div className="small text-muted font-mono" style={{ fontSize: 10 }}>
                  Controls spatial score attenuation under conflicting alibi records. Default: 0.50.
                </div>
              </div>

              {/* Temporal Decay Tau */}
              <div className="cm-tuner-row" style={{ marginBottom: 12 }}>
                <div className="row justify-between items-center">
                  <span className="font-mono small">TEMPORAL HALF-LIFE DECAY (τ):</span>
                  <strong className="text-cyan font-mono small">{config.temporal_tau_minutes} Minutes</strong>
                </div>
                <input
                  type="range"
                  min="5"
                  max="120"
                  step="5"
                  value={config.temporal_tau_minutes}
                  onChange={(e) => {
                    setIsConfigModified(true);
                    setConfig((prev) => ({ ...prev, temporal_tau_minutes: parseFloat(e.target.value) }));
                  }}
                  className="cm-cyber-range"
                  disabled={isExecuting}
                />
                <div className="small text-muted font-mono" style={{ fontSize: 10 }}>
                  Exponential decay window toward incident time: exp(-gap / tau). Default: 30 min.
                </div>
              </div>

              {/* Challenged Evidence Lifecycle Weight */}
              <div className="cm-tuner-row" style={{ marginBottom: 12 }}>
                <div className="row justify-between items-center">
                  <span className="font-mono small">CHALLENGED EVIDENCE WEIGHT:</span>
                  <strong className="text-purple font-mono small">{config.challenged_factor.toFixed(2)}</strong>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={config.challenged_factor}
                  onChange={(e) => {
                    setIsConfigModified(true);
                    setConfig((prev) => ({ ...prev, challenged_factor: parseFloat(e.target.value) }));
                  }}
                  className="cm-cyber-range"
                  disabled={isExecuting}
                />
                <div className="small text-muted font-mono" style={{ fontSize: 10 }}>
                  Discount factor for evidence under active dispute (SUPPORTED=1.0, INVALIDATED=0.0). Default: 0.50.
                </div>
              </div>

              {/* Multi-Domain Weights Grid */}
              <div style={{ marginTop: 14 }}>
                <span className="font-mono text-xs text-muted block" style={{ marginBottom: 8 }}>
                  DOMAIN RELEVANCE WEIGHTS:
                </span>
                <div className="row gap-2 flex-wrap">
                  {Object.entries(config.weights).map(([domain, weight]) => (
                    <div
                      key={domain}
                      style={{
                        flex: "1 1 140px",
                        background: "rgba(0,0,0,0.3)",
                        padding: "6px 10px",
                        borderRadius: 4,
                        border: "1px solid rgba(255,255,255,0.06)",
                      }}
                    >
                      <div className="row justify-between items-center font-mono text-xs">
                        <span className="text-muted capitalize">{domain}:</span>
                        <strong className="text-cyan">{weight.toFixed(2)}</strong>
                      </div>
                      <input
                        type="range"
                        min="0.0"
                        max="0.60"
                        step="0.05"
                        value={weight}
                        onChange={(e) => updateWeight(domain, e.target.value)}
                        className="cm-cyber-range"
                        style={{ marginTop: 4 }}
                        disabled={isExecuting}
                      />
                    </div>
                  ))}
                </div>
              </div>

              {/* Feature Ablation Toggles */}
              <div style={{ marginTop: 14 }}>
                <span className="font-mono text-xs text-muted block" style={{ marginBottom: 8 }}>
                  FEATURE TIE & REASONING ENABLERS:
                </span>
                <div className="row gap-2 flex-wrap">
                  {Object.entries(config.features).map(([feat, enabled]) => (
                    <button
                      key={feat}
                      onClick={() => updateFeature(feat)}
                      className={`cm-badge-tag ${enabled ? "active" : ""}`}
                      style={{
                        cursor: "pointer",
                        background: enabled ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.1)",
                        color: enabled ? "#10b981" : "#ef4444",
                        border: `1px solid ${enabled ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.2)"}`,
                      }}
                      disabled={isExecuting}
                    >
                      {enabled ? "✓" : "✗"} {feat}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* RIGHT COLUMN: Execution Controls, Live Logs, and Genuine Results */}
        <div style={{ flex: "1 1 540px", display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Action & Status Deck */}
          <div className="cm-cyber-panel" style={{ padding: 16 }}>
            <div className="row justify-between items-center" style={{ marginBottom: 12 }}>
              <span className="font-mono text-xs text-cyan" style={{ fontWeight: 700 }}>
                EXECUTION CONTROL
              </span>
              {isConfigModified && !isExecuting && (
                <span className="cm-badge-tag" style={{ background: "rgba(245, 158, 11, 0.15)", color: "#f59e0b" }}>
                  CONFIGURATION MODIFIED · READY TO RUN
                </span>
              )}
            </div>

            {/* Error Message if any */}
            {executionError && (
              <div className="cm-error-box font-mono text-xs" style={{ marginBottom: 12 }}>
                ⚠️ {executionError}
              </div>
            )}

            {/* Main Run Button */}
            <div className="row gap-2 items-center">
              <button
                className="cm-courtroom-export-btn"
                style={{ flex: 1, padding: "12px 20px", fontSize: "0.9rem" }}
                onClick={handleRunExperiment}
                disabled={isExecuting}
              >
                {isExecuting ? "⚡ RUNNING REAL EXPERIMENT..." : "⚡ RUN BACKEND EXPERIMENT"}
              </button>

              {isExecuting && (
                <button
                  className="cm-filter-pill"
                  style={{ borderColor: "#ef4444", color: "#ef4444", height: 44 }}
                  onClick={handleCancelExperiment}
                >
                  ✕ CANCEL
                </button>
              )}

              {activeExperiment && (
                <a
                  href={`/api/research/experiments/${activeExperiment.experiment_id}/artifacts?format=csv`}
                  download
                  className="cm-filter-pill row items-center gap-1"
                  style={{ height: 44, textDecoration: "none" }}
                  title="Download Raw Results CSV"
                >
                  📥 EXPORT CSV
                </a>
              )}
            </div>

            {/* Progress Bar when running */}
            {isExecuting && jobStatus && (
              <div style={{ marginTop: 14 }}>
                <div className="row justify-between items-center font-mono text-xs" style={{ marginBottom: 6 }}>
                  <span className="text-cyan">
                    {jobStatus.current_step || "Processing experiment..."}
                  </span>
                  <span className="text-amber">
                    {jobStatus.progress_pct ? `${jobStatus.progress_pct}%` : "INITIALIZING..."}
                  </span>
                </div>
                <div className="cm-timeline-track-wrap">
                  <div
                    className="cm-timeline-progress"
                    style={{ width: `${jobStatus.progress_pct || 5}%` }}
                  />
                </div>
              </div>
            )}

            {/* Live Terminal Execution Logs */}
            {logs.length > 0 && (
              <div style={{ marginTop: 14 }}>
                <span className="font-mono text-xs text-muted block" style={{ marginBottom: 4 }}>
                  LIVE EXPERIMENTAL LOG STREAM:
                </span>
                <div
                  className="cm-terminal-box font-mono"
                  style={{
                    maxHeight: 140,
                    overflowY: "auto",
                    background: "rgba(0, 0, 0, 0.6)",
                    padding: 8,
                    borderRadius: 4,
                    fontSize: "0.75rem",
                    border: "1px solid rgba(255,255,255,0.06)",
                  }}
                >
                  {logs.map((l, i) => (
                    <div key={i} style={{ color: l.level === "ERROR" ? "#ef4444" : l.level === "WARNING" ? "#f59e0b" : "#00e5ff" }}>
                      <span className="text-muted">[{new Date(l.log_timestamp).toLocaleTimeString()}]</span> {l.message}
                    </div>
                  ))}
                  <div ref={logsEndRef} />
                </div>
              </div>
            )}
          </div>

          {/* Genuine Results Display Panel */}
          {activeExperiment ? (
            <div className="cm-cyber-panel" style={{ padding: 16 }}>
              <div className="row justify-between items-center" style={{ marginBottom: 12 }}>
                <div className="row items-center gap-2">
                  <span className="cm-pulse-emerald" />
                  <strong className="font-mono text-emerald" style={{ fontSize: "0.85rem" }}>
                    LIVE EXPERIMENT #{activeExperiment.experiment_id} RESULTS
                  </strong>
                  <span className="cm-badge-tag" style={{ background: "rgba(16, 185, 129, 0.15)", color: "#10b981", fontSize: "0.65rem" }}>
                    PROVENANCE VERIFIED
                  </span>
                </div>
                <span className="font-mono text-xs text-muted">
                  Duration: {activeExperiment.execution_time_sec}s · {activeExperiment.seed_results?.length} Case Runs
                </span>
              </div>

              {/* Metrics Grid */}
              <div className="cm-tuner-metrics-grid" style={{ marginBottom: 16 }}>
                {activeExperiment.metrics?.map((m) => (
                  <div key={m.metric_name} className="cm-gauge-box">
                    <span className="text-muted font-mono text-xs">{m.metric_name}</span>
                    <strong className="text-cyan font-mono text-xl">
                      {(m.mean_value * 100).toFixed(1)}%
                    </strong>
                    <div className="row justify-between text-muted font-mono" style={{ fontSize: "0.65rem", marginTop: 2 }}>
                      <span>±{(m.std_err * 100).toFixed(1)}% SE</span>
                      <span>95% CI: [{(m.ci_lower * 100).toFixed(0)}%, {(m.ci_upper * 100).toFixed(0)}%]</span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Per-Seed Case Breakdown */}
              <div>
                <span className="font-mono text-xs text-muted block" style={{ marginBottom: 6 }}>
                  PER-SEED CASE RANKING BREAKDOWN (CLICK TO INSPECT CANDIDATE SCORES):
                </span>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {activeExperiment.seed_results?.map((sr) => {
                    const isExp = expandedSeed === `${sr.seed}-${sr.case_ref}`;
                    return (
                      <div
                        key={`${sr.seed}-${sr.case_ref}`}
                        style={{
                          background: "rgba(0,0,0,0.25)",
                          border: "1px solid rgba(255,255,255,0.06)",
                          borderRadius: 4,
                          padding: "6px 10px",
                        }}
                      >
                        <div
                          className="row justify-between items-center font-mono text-xs"
                          style={{ cursor: "pointer" }}
                          onClick={() => setExpandedSeed(isExp ? null : `${sr.seed}-${sr.case_ref}`)}
                        >
                          <div className="row items-center gap-2">
                            <span className="text-cyan font-bold">Seed {sr.seed}</span>
                            <span className="text-muted">| {sr.case_ref}</span>
                            <span className="cm-badge-tag" style={{ fontSize: "0.65rem" }}>
                              {sr.n_candidates} candidates ({sr.n_relevant} relevant)
                            </span>
                          </div>
                          <div className="row items-center gap-3">
                            <span>nDCG@5: <strong className="text-cyan">{sr.metrics?.["nDCG@5"]?.toFixed(3)}</strong></span>
                            <span>P@5: <strong className="text-amber">{sr.metrics?.["P@5"]?.toFixed(3)}</strong></span>
                            <span>MRR: <strong className="text-emerald">{sr.metrics?.["MRR"]?.toFixed(3)}</strong></span>
                            <span>{isExp ? "▲" : "▼"}</span>
                          </div>
                        </div>

                        {/* Expanded Top 5 Candidates */}
                        {isExp && (
                          <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                            <div className="font-mono text-xs text-muted" style={{ marginBottom: 4 }}>
                              TOP RANKED CANDIDATES FROM ALGORITHM INFERENCE:
                            </div>
                            <table className="cm-cyber-table font-mono text-xs" style={{ width: "100%" }}>
                              <thead>
                                <tr>
                                  <th>Rank</th>
                                  <th>Candidate</th>
                                  <th>Score</th>
                                  <th>Ground Truth</th>
                                  <th>Mathematical Explanation</th>
                                </tr>
                              </thead>
                              <tbody>
                                {sr.top_ranked?.slice(0, 5).map((cand) => (
                                  <tr key={cand.rank}>
                                    <td className="text-cyan">#{cand.rank}</td>
                                    <td><strong>{cand.lead_id}</strong></td>
                                    <td>{cand.raw_score}</td>
                                    <td>
                                      <span style={{ color: cand.is_relevant ? "#10b981" : "#a0aec0" }}>
                                        {cand.is_relevant ? `★ Relevant (Grade ${cand.relevance_grade})` : "Irrelevant"}
                                      </span>
                                    </td>
                                    <td className="text-muted" style={{ fontSize: "0.7rem" }}>
                                      {cand.explanation}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          ) : (
            /* Empty State */
            <div
              className="cm-cyber-panel"
              style={{
                padding: 24,
                textAlign: "center",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                minHeight: 200,
              }}
            >
              <span style={{ fontSize: 28, marginBottom: 8 }}>🔬</span>
              <span className="font-mono text-muted text-sm" style={{ maxWidth: 360 }}>
                Adjust hyperparameters on the left and click <strong>RUN BACKEND EXPERIMENT</strong> to compute real metrics.
              </span>
            </div>
          )}

          {/* Historical Experiments Drawer */}
          {recentExperiments.length > 0 && (
            <div className="cm-cyber-panel" style={{ padding: 12 }}>
              <span className="font-mono text-xs text-muted block" style={{ marginBottom: 6 }}>
                RECENT EXECUTED EXPERIMENTS (REPRODUCIBILITY ARCHIVE):
              </span>
              <div className="row gap-2 flex-wrap">
                {recentExperiments.map((exp) => (
                  <button
                    key={exp.experiment_id}
                    onClick={() => loadHistoricalExperiment(exp.experiment_id)}
                    className="cm-badge-tag"
                    style={{
                      cursor: "pointer",
                      padding: "4px 8px",
                      background: activeExperiment?.experiment_id === exp.experiment_id ? "rgba(0, 229, 255, 0.2)" : "rgba(0,0,0,0.3)",
                      color: activeExperiment?.experiment_id === exp.experiment_id ? "#00e5ff" : "#cbd5e1",
                      border: "1px solid rgba(255,255,255,0.08)",
                    }}
                  >
                    #{exp.experiment_id} {exp.algorithm.toUpperCase()} ({exp.status})
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
