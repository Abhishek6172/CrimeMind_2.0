import React, { useState, useEffect, useRef, useMemo } from "react";
import { useLoad } from "../hooks.js";
import { api } from "../api.js";
import { Async, Badge, Card, Notice, StatBox } from "../components/ui.jsx";
import { cyberAudio } from "../utils/cyberAudio.js";
import { VoiceStressMonitor } from "../components/VoiceStressMonitor.jsx";

export default function StatementNlpView({ c, caseRef }) {
  const [refreshKey, setRefreshKey] = useState(0);

  // Load stored statements for this case
  const statementsState = useLoad(
    () => c.get("/nlp/statements"),
    [c, caseRef, refreshKey]
  );

  const [selectedStatementId, setSelectedStatementId] = useState(null);
  const [activeSentenceIdx, setActiveSentenceIdx] = useState(1);
  const [showIngestModal, setShowIngestModal] = useState(false);
  const [showVoiceStress, setShowVoiceStress] = useState(false);
  const [isFlagging, setIsFlagging] = useState(false);
  const [flagFeedback, setFlagFeedback] = useState(null);

  // Form for custom statement ingestion
  const [formSubject, setFormSubject] = useState("");
  const [formRole, setFormRole] = useState("SUSPECT");
  const [formTitle, setFormTitle] = useState("");
  const [formInterviewer, setFormInterviewer] = useState("Lead Investigator");
  const [formTranscript, setFormTranscript] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [ingestError, setIngestError] = useState("");

  const canvasRef = useRef(null);

  // Select active statement
  const activeStatement = useMemo(() => {
    const list = statementsState.data || [];
    if (!list.length) return null;
    return list.find((s) => s.statement_id === selectedStatementId) || list[0];
  }, [statementsState.data, selectedStatementId]);

  // Radar Spider Canvas Drawing
  useEffect(() => {
    if (!activeStatement || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(centerX, centerY) - 35;

    const dimensions = [
      { key: "sensory_density", label: "Sensory Density" },
      { key: "self_ownership", label: "Self Ownership" },
      { key: "temporal_spontaneity", label: "Temporal Spontaneity" },
      { key: "hedging_filter", label: "Hedging Filter" },
      { key: "memory_grounding", label: "Memory Grounding" },
      { key: "evidence_concordance", label: "Evidence Concordance" },
    ];

    const numAxes = dimensions.length;
    const angleStep = (Math.PI * 2) / numAxes;

    // Draw concentric polygon webs
    const levels = [0.25, 0.5, 0.75, 1.0];
    levels.forEach((lvl) => {
      ctx.beginPath();
      for (let i = 0; i < numAxes; i++) {
        const a = i * angleStep - Math.PI / 2;
        const r = radius * lvl;
        const x = centerX + Math.cos(a) * r;
        const y = centerY + Math.sin(a) * r;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.strokeStyle = "rgba(0, 229, 255, 0.12)";
      ctx.lineWidth = 1;
      ctx.stroke();
    });

    // Draw axis lines and labels
    ctx.font = "bold 9px monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    dimensions.forEach((dim, i) => {
      const a = i * angleStep - Math.PI / 2;
      const x = centerX + Math.cos(a) * radius;
      const y = centerY + Math.sin(a) * radius;

      // Axis ray
      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      ctx.lineTo(x, y);
      ctx.strokeStyle = "rgba(0, 229, 255, 0.25)";
      ctx.stroke();

      // Axis label
      const lx = centerX + Math.cos(a) * (radius + 20);
      const ly = centerY + Math.sin(a) * (radius + 20);
      ctx.fillStyle = "#94a3b8";
      ctx.fillText(dim.label, lx, ly);
    });

    // Draw data polygon
    const metrics = activeStatement.metrics || {};
    const credBand = activeStatement.credibility_band;
    const radarData = [
      Math.min(100, (metrics.sensory_density_pct || 0) * 18),
      Math.max(10, Math.min(100, 100 - (metrics.depersonalization_ratio || 0) * 25)),
      Math.max(10, Math.min(100, 85 - (metrics.temporal_skips_count || 0) * 20 + (metrics.spontaneous_corrections_count || 0) * 10)),
      Math.max(10, Math.min(100, 95 - ((metrics.equivocation_hedges_count || 0) * 25 + (metrics.soft_hedges_count || 0) * 3.5))),
      Math.min(100, 30 + (metrics.spontaneous_corrections_count || 0) * 20 + (metrics.memory_limitation_admissions || 0) * 18 + (metrics.sensory_words_count || 0) * 2),
      activeStatement.credibility_score > 60 ? 90 : 35,
    ];

    const polyCol = credBand === "HIGH_VERACITY" ? "#00E6A0" : credBand === "AMBIGUOUS" ? "#FFB020" : "#FF2A3D";

    ctx.beginPath();
    radarData.forEach((val, i) => {
      const normVal = Math.max(0.05, Math.min(1.0, val / 100.0));
      const a = i * angleStep - Math.PI / 2;
      const r = radius * normVal;
      const x = centerX + Math.cos(a) * r;
      const y = centerY + Math.sin(a) * r;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.closePath();

    ctx.fillStyle = polyCol === "#00E6A0" ? "rgba(0, 230, 160, 0.25)" : polyCol === "#FFB020" ? "rgba(255, 176, 32, 0.25)" : "rgba(255, 42, 61, 0.25)";
    ctx.fill();
    ctx.strokeStyle = polyCol;
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // Data vertices
    radarData.forEach((val, i) => {
      const normVal = Math.max(0.05, Math.min(1.0, val / 100.0));
      const a = i * angleStep - Math.PI / 2;
      const r = radius * normVal;
      const x = centerX + Math.cos(a) * r;
      const y = centerY + Math.sin(a) * r;

      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = "#FFFFFF";
      ctx.fill();
      ctx.strokeStyle = polyCol;
      ctx.lineWidth = 2;
      ctx.stroke();
    });
  }, [activeStatement]);

  // Handle Custom Statement Ingestion
  const handleIngestSubmit = async (e) => {
    e.preventDefault();
    if (!formTranscript.trim() || !formSubject.trim()) return;

    try {
      setIsSubmitting(true);
      setIngestError("");
      try { cyberAudio?.playScan?.(); } catch {}

      const res = await c.post("/nlp/statements", {
        transcript_text: formTranscript,
        subject_name: formSubject,
        subject_role: formRole,
        statement_title: formTitle || `Interrogation: ${formSubject}`,
        interviewer_name: formInterviewer,
      });

      try { cyberAudio?.playAccessGranted?.(); } catch {}
      setShowIngestModal(false);
      setFormTranscript("");
      setFormSubject("");
      setFormTitle("");
      setRefreshKey((k) => k + 1);
      if (res?.statement_id) {
        setSelectedStatementId(res.statement_id);
      }
    } catch (err) {
      setIngestError(err.message || "Failed to analyze and save statement");
      try { cyberAudio?.playGlitch?.(); } catch {}
    } finally {
      setIsSubmitting(false);
    }
  };

  // Convert Statement Contradiction into EVLM Finding
  const handleFlagContradiction = async (conflict) => {
    if (!activeStatement || !conflict) return;
    try {
      setIsFlagging(true);
      try { cyberAudio?.playClickChirp?.(); } catch {}

      const res = await c.post("/nlp/flag-contradiction", {
        statement_id: activeStatement.statement_id,
        subject_name: activeStatement.subject_name,
        evidence_ref: conflict.evidence_ref,
        contradiction_text: conflict.reason,
        action: "CHALLENGE_EVIDENCE",
      });

      try { cyberAudio?.playSuccess?.(); } catch {}
      setFlagFeedback(res.message || "Recorded finding in EVLM ledger.");
      setTimeout(() => setFlagFeedback(null), 4000);
    } catch (err) {
      setFlagFeedback(`Error: ${err.message}`);
    } finally {
      setIsFlagging(false);
    }
  };

  const sentences = activeStatement?.sentence_analyses || [];
  const activeSentence = sentences.find((s) => s.sentence_idx === activeSentenceIdx) || sentences[0];
  const questions = activeStatement?.tactical_questions || [];

  return (
    <div className="cm-nlp-workspace stack gap-4">
      {/* Top Banner */}
      <div className="cm-cctv-banner">
        <div className="cm-cctv-banner-left">
          <span className="cm-pulse-amber" />
          <strong className="font-mono">STATEMENT CREDIBILITY & COGNITIVE LOAD NLP ANALYZER</strong>
          <span className="cm-pipeline-badge active">
            CRITERIA-BASED CONTENT ANALYSIS (CBCA) & SVA ENGINE
          </span>
        </div>
        <div className="cm-cctv-banner-right font-mono text-muted small">
          CASE: {caseRef} · FORENSIC LINGUISTIC INTELLIGENCE ACTIVE
        </div>
      </div>

      <Notice level="info">
        Forensic Statement Validity Assessment (SVA): Evaluates criteria-based memory grounding, spontaneous self-corrections,
        pronoun depersonalization, and hedging frequency. Cross-checks statements against physical case exhibits to expose factual contradictions.
      </Notice>

      {/* Transcript Selector Deck */}
      <div className="row justify-between items-center" style={{ flexWrap: "wrap", gap: 10 }}>
        <div className="row items-center gap-2" style={{ overflowX: "auto" }}>
          {(statementsState.data || []).map((s) => {
            const isSelected = activeStatement?.statement_id === s.statement_id;
            return (
              <button
                key={s.statement_id}
                className={`cm-filter-pill ${isSelected ? "active" : ""}`}
                onClick={() => {
                  try { cyberAudio?.playClickChirp?.(); } catch {}
                  setSelectedStatementId(s.statement_id);
                  setActiveSentenceIdx(1);
                }}
              >
                <b>[{s.subject_role}]</b> {s.subject_name} · {s.statement_title.slice(0, 24)}…
              </button>
            );
          })}
        </div>

        <div className="row items-center gap-2" style={{ flexWrap: "wrap" }}>
          <button
            className={`small font-mono ${showVoiceStress ? "danger" : "primary"}`}
            style={{
              background: showVoiceStress ? "rgba(244, 63, 94, 0.2)" : "rgba(6, 182, 212, 0.15)",
              borderColor: showVoiceStress ? "#F43F5E" : "#06B6D4",
              color: showVoiceStress ? "#FCA5A5" : "#38BDF8",
              fontWeight: 700,
            }}
            onClick={() => {
              try { cyberAudio?.playClickChirp?.(); } catch {}
              setShowVoiceStress(!showVoiceStress);
            }}
            title="Open real-time microphone Voice Stress & Pitch Tremor analyzer"
          >
            🎙️ {showVoiceStress ? "HIDE VOICE STRESS SENSOR" : "START LIVE AUDIO INTERROGATION"}
          </button>

          <button
            className="primary small font-mono"
            onClick={() => {
              try { cyberAudio?.playClickChirp?.(); } catch {}
              setShowIngestModal(true);
            }}
          >
            + Ingest New Interrogation Transcript
          </button>
        </div>
      </div>

      {/* Real-Time Live Microphone Voice Stress & Pitch Tremor Monitor */}
      {showVoiceStress && (
        <div className="mt-2 mb-4">
          <VoiceStressMonitor
            caseRef={caseRef}
            onLogToCase={() => setRefreshKey((k) => k + 1)}
            onClose={() => setShowVoiceStress(false)}
          />
        </div>
      )}

      {activeStatement && (
        <>
          {/* Executive Forensic Scorecard Deck */}
          <div className="grid grid-4 gap-3">
            <StatBox
              label="CREDIBILITY INDEX"
              val={`${activeStatement.credibility_score}%`}
              aside={
                <Badge
                  kind={
                    activeStatement.credibility_band === "HIGH_VERACITY"
                      ? "SUPPORTED"
                      : activeStatement.credibility_band === "AMBIGUOUS"
                      ? "CHALLENGED"
                      : "DISPUTED"
                  }
                >
                  {activeStatement.credibility_band.replace(/_/g, " ")}
                </Badge>
              }
            />

            <StatBox
              label="COGNITIVE LOAD LEVEL"
              val={`${activeStatement.cognitive_load_score}%`}
              aside={
                <span className="font-mono text-xs text-muted">
                  {activeStatement.cognitive_load_score > 65 ? "ELEVATED STRAIN" : "BASELINE"}
                </span>
              }
            />

            <StatBox
              label="SENSORY GROUNDING"
              val={`${activeStatement.metrics?.sensory_density_pct ?? 0}%`}
              aside={
                <span className="font-mono text-xs text-muted">
                  {activeStatement.metrics?.sensory_words_count ?? 0} perceptual cues
                </span>
              }
            />

            <StatBox
              label="DEPERSONALIZATION RATIO"
              val={activeStatement.metrics?.depersonalization_ratio ?? 0}
              aside={
                <span className="font-mono text-xs text-muted">
                  {activeStatement.metrics?.depersonalization_ratio > 1.5 ? "AVOIDANCE FLAGGED" : "NORMAL OWNERSHIP"}
                </span>
              }
            />
          </div>

          {/* Main Intelligence Grid */}
          <div className="cm-cctv-workspace-grid">
            {/* Left Column: Interactive Transcript & Sentence Heatmap */}
            <div className="cm-cctv-main-column stack gap-3">
              <Card
                title={`TRANSCRIPT: ${activeStatement.statement_title.toUpperCase()}`}
                aside={
                  <div className="row items-center gap-2 font-mono text-xs text-muted">
                    <span>SUBJECT: <b>{activeStatement.subject_name}</b> ({activeStatement.subject_role})</span>
                    <span>·</span>
                    <span>INTERVIEWER: {activeStatement.interviewer_name}</span>
                  </div>
                }
              >
                <div className="stack gap-2" style={{ maxHeight: 420, overflowY: "auto", paddingRight: 6 }}>
                  {sentences.map((sent) => {
                    const isSelected = sent.sentence_idx === activeSentenceIdx;
                    const hasConflict = sent.evidence_conflicts && sent.evidence_conflicts.length > 0;

                    let borderCol = "rgba(255, 255, 255, 0.1)";
                    let bgCol = "rgba(14, 22, 38, 0.4)";
                    if (hasConflict) {
                      borderCol = "#FF2A3D";
                      bgCol = "rgba(255, 42, 61, 0.12)";
                    } else if (sent.status === "VERACIOUS") {
                      borderCol = "#00E6A0";
                      bgCol = "rgba(0, 230, 160, 0.08)";
                    } else if (sent.status === "STRAINED") {
                      borderCol = "#FFB020";
                      bgCol = "rgba(255, 176, 32, 0.08)";
                    }

                    return (
                      <div
                        key={sent.sentence_idx}
                        className={`cm-sentence-card ${isSelected ? "active" : ""}`}
                        style={{
                          borderLeft: `4px solid ${borderCol}`,
                          background: bgCol,
                          padding: "10px 14px",
                          borderRadius: 4,
                          cursor: "pointer",
                          transition: "all 0.15s ease",
                        }}
                        onClick={() => {
                          try { cyberAudio?.playHoverBlip?.(); } catch {}
                          setActiveSentenceIdx(sent.sentence_idx);
                        }}
                      >
                        <div className="row justify-between items-center" style={{ marginBottom: 4 }}>
                          <span className="font-mono text-cyan text-xs">
                            SENTENCE #{sent.sentence_idx} · {sent.word_count} words
                          </span>
                          <div className="row items-center gap-2 font-mono text-xs">
                            <span className={sent.credibility_score >= 70 ? "text-emerald" : sent.credibility_score >= 45 ? "text-amber" : "text-crimson"}>
                              VERACITY: {sent.credibility_score}%
                            </span>
                            <span className="text-muted">|</span>
                            <span className="text-muted">LOAD: {sent.cognitive_load_score}%</span>
                          </div>
                        </div>

                        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.5, color: "#f8fafc" }}>
                          {sent.text}
                        </p>

                        {sent.flags && sent.flags.length > 0 && (
                          <div className="row items-center gap-2" style={{ marginTop: 6, flexWrap: "wrap" }}>
                            {sent.flags.map((fl, fi) => (
                              <span
                                key={fi}
                                className="font-mono text-xs"
                                style={{
                                  background: fl.includes("CONTRADICTION") ? "rgba(255, 42, 61, 0.25)" : fl.includes("Sensory") ? "rgba(0, 230, 160, 0.18)" : "rgba(255, 176, 32, 0.2)",
                                  color: fl.includes("CONTRADICTION") ? "#FF2A3D" : fl.includes("Sensory") ? "#00E6A0" : "#FFB020",
                                  padding: "2px 6px",
                                  borderRadius: 3,
                                }}
                              >
                                {fl}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </Card>

              {/* Active Sentence Micro-Inspection Deck */}
              {activeSentence && (
                <Card title={`MICROSCOPIC LINGUISTIC INSPECTION (SENTENCE #${activeSentence.sentence_idx})`}>
                  <div className="stack gap-3 font-mono small">
                    <div style={{ background: "rgba(0,0,0,0.3)", padding: "10px 14px", borderRadius: 4, fontStyle: "italic", color: "#e2e8f0" }}>
                      "{activeSentence.text}"
                    </div>

                    <div className="row justify-between" style={{ flexWrap: "wrap", gap: 8 }}>
                      <div>
                        <span className="text-muted">Sensory Anchors: </span>
                        {activeSentence.sensory_words?.length ? (
                          <span className="text-emerald">{activeSentence.sensory_words.join(", ")}</span>
                        ) : (
                          <span className="text-muted">None detected</span>
                        )}
                      </div>

                      <div>
                        <span className="text-muted">Hedging Phrases: </span>
                        {activeSentence.hedges?.length ? (
                          <span className="text-amber">{activeSentence.hedges.join(", ")}</span>
                        ) : (
                          <span className="text-muted">None detected</span>
                        )}
                      </div>
                    </div>

                    {/* Evidence Conflicts Box */}
                    {activeSentence.evidence_conflicts && activeSentence.evidence_conflicts.length > 0 && (
                      <div className="cm-conflict-banner stack gap-2" style={{ background: "rgba(255, 42, 61, 0.1)", border: "1px solid rgba(255, 42, 61, 0.4)", padding: 12, borderRadius: 6 }}>
                        <div className="row items-center gap-2 text-crimson font-bold">
                          <span>⚠️</span>
                          <span>PHYSICAL EVIDENCE COLLISION DETECTED</span>
                        </div>

                        {activeSentence.evidence_conflicts.map((conf, ci) => (
                          <div key={ci} className="stack gap-1">
                            <div className="row justify-between items-center">
                              <span className="text-cyan">CONFLICTING EXHIBIT: <b>{conf.evidence_ref}</b></span>
                              <Badge kind="CHALLENGED">{conf.conflict_type}</Badge>
                            </div>
                            <p style={{ margin: "4px 0", color: "#f87171" }}>{conf.reason}</p>
                            <p className="text-muted text-xs">EXHIBIT RECORD: {conf.evidence_summary}</p>

                            <div className="row justify-end" style={{ marginTop: 6 }}>
                              <button
                                className="cm-filter-pill active"
                                disabled={isFlagging}
                                onClick={() => handleFlagContradiction(conf)}
                              >
                                {isFlagging ? "Recording..." : `⚖️ Flag Contradiction & Challenge ${conf.evidence_ref}`}
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {flagFeedback && (
                      <div className="text-emerald font-mono small">
                        ✓ {flagFeedback}
                      </div>
                    )}
                  </div>
                </Card>
              )}
            </div>

            {/* Right Column: Holographic Radar Spider & Tactical Question Engine */}
            <div className="cm-cctv-side-column stack gap-4">
              {/* 6-Axis Cognitive Spider Radar */}
              <Card title="6-AXIS COGNITIVE VALIDITY RADAR">
                <div style={{ display: "flex", justifyContent: "center", alignItems: "center", padding: "10px 0" }}>
                  <canvas ref={canvasRef} width={340} height={280} />
                </div>
                <div className="row justify-between font-mono text-xs text-muted" style={{ marginTop: 6 }}>
                  <span>Spontaneity vs Scripting</span>
                  <span>Sensory vs Abstract</span>
                </div>
              </Card>

              {/* Tactical Interrogation Strategic Assistant */}
              <Card title="P.E.A.C.E. STRATEGIC INTERROGATION PROBES">
                <div className="stack gap-3" style={{ maxHeight: 440, overflowY: "auto" }}>
                  {questions.map((q, qi) => (
                    <div
                      key={qi}
                      className="cm-cctv-event-card stack gap-2"
                      style={{ padding: 12, borderLeft: "3px solid #00E5FF" }}
                    >
                      <div className="row justify-between items-center font-mono text-xs">
                        <span className="text-cyan font-bold">{q.category.replace(/_/g, " ")}</span>
                        {q.relevant_evidence_ref && (
                          <Badge kind="SUPPORTED">EXHIBIT {q.relevant_evidence_ref}</Badge>
                        )}
                      </div>

                      <div style={{ fontWeight: "bold", fontSize: 13, color: "#FFFFFF" }}>
                        "{q.question}"
                      </div>

                      <p className="text-muted text-xs" style={{ margin: 0, fontStyle: "italic" }}>
                        <b>Strategic Rationale:</b> {q.rationale}
                      </p>

                      <div className="stack gap-1 font-mono text-xs" style={{ background: "rgba(0,0,0,0.25)", padding: 8, borderRadius: 4 }}>
                        <span className="text-emerald">✓ Truthful: {q.expected_truthful_response}</span>
                        <span className="text-crimson">✕ Deceptive: {q.expected_deceptive_reaction}</span>
                      </div>
                    </div>
                  ))}

                  {questions.length === 0 && (
                    <p className="text-muted font-mono small">No tactical probes generated.</p>
                  )}
                </div>
              </Card>
            </div>
          </div>
        </>
      )}

      {/* Ingest New Statement Modal */}
      {showIngestModal && (
        <div className="cm-upload-modal-overlay">
          <div className="cm-upload-modal-box" style={{ maxWidth: 640 }}>
            <div className="row justify-between items-center" style={{ marginBottom: 16 }}>
              <div className="row items-center gap-2">
                <span className="cm-pulse-emerald" />
                <h3 className="font-mono" style={{ margin: 0, fontSize: 14 }}>
                  INGEST NEW INTERROGATION / WITNESS STATEMENT
                </h3>
              </div>
              <button className="cm-filter-pill" onClick={() => setShowIngestModal(false)}>
                ✕ Close
              </button>
            </div>

            <form onSubmit={handleIngestSubmit} className="stack gap-3 font-mono small">
              <div className="row gap-3">
                <div style={{ flex: 1 }}>
                  <label className="text-muted">SUBJECT NAME:</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Karan Bhatt"
                    value={formSubject}
                    onChange={(e) => setFormSubject(e.target.value)}
                    className="cm-cyber-input"
                    style={{ marginTop: 4 }}
                  />
                </div>

                <div style={{ flex: 1 }}>
                  <label className="text-muted">SUBJECT ROLE:</label>
                  <select
                    value={formRole}
                    onChange={(e) => setFormRole(e.target.value)}
                    className="cm-cyber-input"
                    style={{ marginTop: 4 }}
                  >
                    <option value="SUSPECT">SUSPECT</option>
                    <option value="WITNESS">WITNESS</option>
                    <option value="VICTIM">VICTIM</option>
                    <option value="PERSON_OF_INTEREST">PERSON OF INTEREST</option>
                  </select>
                </div>
              </div>

              <div className="row gap-3">
                <div style={{ flex: 1 }}>
                  <label className="text-muted">STATEMENT TITLE:</label>
                  <input
                    type="text"
                    placeholder="e.g. Alibi Deposition #2"
                    value={formTitle}
                    onChange={(e) => setFormTitle(e.target.value)}
                    className="cm-cyber-input"
                    style={{ marginTop: 4 }}
                  />
                </div>

                <div style={{ flex: 1 }}>
                  <label className="text-muted">INTERVIEWING DETECTIVE:</label>
                  <input
                    type="text"
                    value={formInterviewer}
                    onChange={(e) => setFormInterviewer(e.target.value)}
                    className="cm-cyber-input"
                    style={{ marginTop: 4 }}
                  />
                </div>
              </div>

              <div>
                <label className="text-muted">INTERVIEW TRANSCRIPT / DEPOSITION TEXT:</label>
                <textarea
                  rows={6}
                  required
                  placeholder="Paste verbatim transcript or witness deposition text here…"
                  value={formTranscript}
                  onChange={(e) => setFormTranscript(e.target.value)}
                  className="cm-cyber-input"
                  style={{ marginTop: 4, width: "100%", fontFamily: "inherit" }}
                />
              </div>

              {ingestError && (
                <div className="text-crimson font-mono small">⚠️ {ingestError}</div>
              )}

              <div className="row justify-end gap-2" style={{ marginTop: 8 }}>
                <button
                  type="button"
                  className="cm-filter-pill"
                  onClick={() => setShowIngestModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="cm-play-btn"
                  disabled={isSubmitting || !formTranscript.trim() || !formSubject.trim()}
                >
                  {isSubmitting ? "ANALYZING LINGUISTIC COGNITION..." : "EXECUTE FORENSIC CBCA ANALYSIS"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
