import React, { useState, useEffect, useMemo, useRef } from "react";
import { cyberAudio } from "../../utils/cyberAudio.js";

const STATUS_COLORS = {
  SUPPORTED: { bg: "rgba(0, 230, 160, 0.15)", border: "#00E6A0", text: "#00E6A0" },
  CHALLENGED: { bg: "rgba(255, 181, 46, 0.15)", border: "#FFB52E", text: "#FFB52E" },
  INVALIDATED: { bg: "rgba(255, 70, 85, 0.15)", border: "#FF4655", text: "#FF4655" },
  SUPERSEDED: { bg: "rgba(168, 85, 247, 0.15)", border: "#A855F7", text: "#A855F7" },
};

export default function EvolutionPlayhead({ evolutionSteps = [] }) {
  const [selectedScenario, setSelectedScenario] = useState("all");
  const [stepIndex, setStepIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1); // 1x, 2x, 5x
  const playTimer = useRef(null);

  // Extract unique scenarios
  const scenarios = useMemo(() => {
    const set = new Set();
    evolutionSteps.forEach((s) => {
      if (s.scenario) set.add(s.scenario);
    });
    return Array.from(set);
  }, [evolutionSteps]);

  // Filtered steps
  const activeSteps = useMemo(() => {
    if (selectedScenario === "all") return evolutionSteps.slice(0, 80);
    return evolutionSteps.filter((s) => s.scenario === selectedScenario);
  }, [evolutionSteps, selectedScenario]);

  // Clamp stepIndex
  useEffect(() => {
    setStepIndex(0);
    setIsPlaying(false);
  }, [selectedScenario]);

  const currentStep = activeSteps[stepIndex] || activeSteps[0] || {};
  const maxSteps = Math.max(1, activeSteps.length - 1);

  // Playback timer loop
  useEffect(() => {
    if (!isPlaying) {
      if (playTimer.current) clearInterval(playTimer.current);
      return;
    }

    const intervalMs = Math.max(120, 1000 / playbackSpeed);
    playTimer.current = setInterval(() => {
      setStepIndex((prev) => {
        if (prev >= maxSteps) {
          setIsPlaying(false);
          cyberAudio.playSuccess();
          return prev;
        }
        cyberAudio.playHoverBlip();
        return prev + 1;
      });
    }, intervalMs);

    return () => clearInterval(playTimer.current);
  }, [isPlaying, playbackSpeed, maxSteps]);

  const togglePlay = () => {
    if (stepIndex >= maxSteps) {
      setStepIndex(0);
    }
    cyberAudio.playClickChirp();
    setIsPlaying(!isPlaying);
  };

  const jumpTo = (idx) => {
    cyberAudio.playClickChirp();
    setStepIndex(Math.max(0, Math.min(maxSteps, idx)));
  };

  const statusStyle = STATUS_COLORS[currentStep.new_status] || STATUS_COLORS.CHALLENGED;

  // Recent sequence logs up to current step
  const recentLogs = useMemo(() => {
    return activeSteps.slice(Math.max(0, stepIndex - 4), stepIndex + 1);
  }, [activeSteps, stepIndex]);

  return (
    <div className="cm-evolution-playhead-widget">
      {/* Top Banner */}
      <div className="cm-playhead-header">
        <div className="row items-center gap-2">
          <span className="cm-pulse-emerald" />
          <h3 className="font-mono" style={{ margin: 0, fontSize: 13 }}>
            PHASE 4 DYNAMIC EVIDENCE EVOLUTION TIME-TRAVEL PLAYHEAD
          </h3>
        </div>

        {/* Scenario Filter */}
        <div className="row items-center gap-2">
          <span className="font-mono small text-muted">SCENARIO:</span>
          <select
            value={selectedScenario}
            onChange={(e) => {
              cyberAudio.playClickChirp();
              setSelectedScenario(e.target.value);
            }}
            className="cm-cyber-input font-mono text-xs"
            style={{ maxWidth: 220 }}
          >
            <option value="all">ALL SCENARIOS ({evolutionSteps.length} Steps)</option>
            {scenarios.map((sc) => (
              <option key={sc} value={sc}>
                {sc}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Main Scrubber Control Bar */}
      <div className="cm-scrubber-deck">
        <div className="row items-center gap-3">
          <button
            className={`cm-play-btn ${isPlaying ? "playing" : ""}`}
            onClick={togglePlay}
            title={isPlaying ? "Pause Simulation" : "Auto-Simulate Timeline"}
          >
            {isPlaying ? "⏸ PAUSE" : "▶ AUTO-SIMULATE"}
          </button>

          <button
            className="cm-filter-pill"
            onClick={() => jumpTo(stepIndex - 1)}
            disabled={stepIndex <= 0}
            title="Step Back"
          >
            ⏮
          </button>

          <button
            className="cm-filter-pill"
            onClick={() => jumpTo(stepIndex + 1)}
            disabled={stepIndex >= maxSteps}
            title="Step Forward"
          >
            ⏭
          </button>

          {/* Speed Selector */}
          <div className="row items-center gap-1 font-mono small text-muted">
            <span>SPEED:</span>
            {[1, 2, 5].map((sp) => (
              <button
                key={sp}
                className={`cm-filter-pill ${playbackSpeed === sp ? "active" : ""}`}
                onClick={() => {
                  cyberAudio.playClickChirp();
                  setPlaybackSpeed(sp);
                }}
              >
                {sp}x
              </button>
            ))}
          </div>

          <div className="grow" />

          {/* Step Progress readout */}
          <div className="font-mono small">
            TIMESTEP: <span className="text-cyan text-base font-bold">{stepIndex + 1}</span> / {maxSteps + 1}
          </div>
        </div>

        {/* Interactive Scrub Bar Range */}
        <div className="cm-timeline-track-wrap">
          <input
            type="range"
            min={0}
            max={maxSteps}
            value={stepIndex}
            onChange={(e) => jumpTo(Number(e.target.value))}
            className="cm-cyber-range"
          />
          <div
            className="cm-timeline-progress"
            style={{ width: `${(stepIndex / maxSteps) * 100}%` }}
          />
        </div>
      </div>

      {/* Real-time State & Telemetry Gauges */}
      <div className="cm-playhead-grid">
        {/* Left: Active Event Box */}
        <div className="cm-playhead-event-card">
          <div className="row justify-between items-center" style={{ marginBottom: 8 }}>
            <span className="font-mono small text-muted">TRANSITION TARGET:</span>
            <span
              className="cm-status-pill"
              style={{
                background: statusStyle.bg,
                borderColor: statusStyle.border,
                color: statusStyle.text,
              }}
            >
              {currentStep.new_status || "NORMAL"}
            </span>
          </div>

          <div className="font-mono text-xl text-cyan font-bold" style={{ marginBottom: 4 }}>
            {currentStep.evidence_ref || "E-0000"}
          </div>

          <div className="font-mono text-xs text-muted">
            CASE: <span className="text-white">{currentStep.case_ref || "CASE-2026-001"}</span> · SCENARIO: <span className="text-amber">{currentStep.scenario || "N/A"}</span>
          </div>

          <div className="cm-audit-trail-snippet font-mono text-xs" style={{ marginTop: 12 }}>
            <div className="text-muted" style={{ marginBottom: 4 }}>RECENT TIMELINE LOG:</div>
            {recentLogs.map((log, i) => (
              <div key={i} className="row justify-between" style={{ padding: "2px 0", borderBottom: "1px dashed rgba(0,229,255,0.1)" }}>
                <span>Step {log.step || i + 1} · {log.evidence_ref}</span>
                <span style={{ color: (STATUS_COLORS[log.new_status] || STATUS_COLORS.CHALLENGED).text }}>
                  → {log.new_status}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Real-time Metric Gauges */}
        <div className="cm-playhead-telemetry-card">
          <div className="font-mono small text-muted" style={{ marginBottom: 10 }}>
            INVESTIGATION DETECTIONS AT TIMESTEP T_{stepIndex + 1}
          </div>

          <div className="cm-gauge-grid">
            <div className="cm-gauge-box">
              <span className="text-muted font-mono text-xs">EXPECTED DETECTED</span>
              <strong className="text-emerald font-mono text-xl">{currentStep.detected_expected ?? 0}</strong>
              <small className="text-muted">Correctly flagged</small>
            </div>

            <div className="cm-gauge-box">
              <span className="text-muted font-mono text-xs">EXPECTED MISSED</span>
              <strong className="text-crimson font-mono text-xl">{currentStep.missed_expected ?? 0}</strong>
              <small className="text-muted">Evidentiary slips</small>
            </div>

            <div className="cm-gauge-box">
              <span className="text-muted font-mono text-xs">FALSE ALARMS</span>
              <strong className="text-amber font-mono text-xl">{currentStep.false_alarm_must_not ?? 0}</strong>
              <small className="text-muted">Protected alibis</small>
            </div>

            <div className="cm-gauge-box">
              <span className="text-muted font-mono text-xs">TOTAL FLAGGED</span>
              <strong className="text-cyan font-mono text-xl">{currentStep.flagged ?? 0}</strong>
              <small className="text-muted">Under investigation</small>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
