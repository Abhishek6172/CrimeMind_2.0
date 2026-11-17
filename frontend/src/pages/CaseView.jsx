import React, { useMemo, useState } from "react";
import { caseApi } from "../api.js";
import { useLoad } from "../hooks.js";
import { Async, Badge, Card, Notice, StatBox, CyberProgress, fmt, time } from "../components/ui.jsx";
import Entities from "./Entities.jsx";
import Evidence from "./Evidence.jsx";
import Graph from "./Graph.jsx";
import Questions from "./Questions.jsx";
import Correlations from "./Correlations.jsx";
import AiPanel from "./AiPanel.jsx";
import Evolution from "./Evolution.jsx";
import Reports from "./Reports.jsx";
import Audit from "./Audit.jsx";
import AddData from "./AddData.jsx";
import Analysis from "./Analysis.jsx";
import MapView from "./MapView.jsx";
import Notes from "./Notes.jsx";
import Access from "./Access.jsx";
import CctvAnalysis from "./CctvAnalysis.jsx";
import MoneyTrailView from "./MoneyTrailView.jsx";
import CrimeBoard from "./CrimeBoard.jsx";
import EvidenceVault from "./EvidenceVault.jsx";
import BallisticsView from "./BallisticsView.jsx";
import StatementNlpView from "./StatementNlpView.jsx";
import SyndicateGnnView from "./SyndicateGnnView.jsx";
import FinancialForensicsView from "./FinancialForensicsView.jsx";
import GeographicProfilingView from "./GeographicProfilingView.jsx";
import { ScrambleText } from "../components/ScrambleText.jsx";
import { exportCourtroomDossier } from "../utils/courtroomExport.js";
import { cyberAudio } from "../utils/cyberAudio.js";

const TABS = [
  ["Dashboard", Dashboard, "⌖"],
  ["Entities", Entities, "◈"],
  ["Evidence", Evidence, "☵"],
  ["Evidence Vault", EvidenceVault, "🔐"],
  ["Crime Board", CrimeBoard, "📌"],
  ["Ballistics 3D", BallisticsView, "🎯"],
  ["Money Trail", MoneyTrailView, "💸"],
  ["CCTV Analysis", CctvAnalysis, "⌕"],
  ["Statement NLP", StatementNlpView, "🧠"],
  ["Syndicate GNN", SyndicateGnnView, "🕸️"],
  ["Financial ML", FinancialForensicsView, "💳"],
  ["Geographic ML", GeographicProfilingView, "🗺️"],
  ["Add data", AddData, "＋"],
  ["Graph", Graph, "☍"],
  ["Map", MapView, "⊕"],
  ["Analysis", Analysis, "⌬"],
  ["Questions", Questions, "⌘"],
  ["Correlations", Correlations, "⋈"],
  ["AI analysis", AiPanel, "✧"],
  ["Evidence changes", Evolution, "◴"],
  ["Notes", Notes, "✎"],
  ["Reports", Reports, "📄"],
  ["Audit", Audit, "🛡"],
  ["Access", Access, "⚿"],
];

function Dashboard({ c, go }) {
  const st = useLoad(() => c.get(""), [c]);
  return (
    <Async state={st}>
      {(d) => {
        const totalEvidence = d.counts?.evidence ?? 0;
        const totalEntities = d.counts?.entities ?? 0;
        const supportedEv = d.evidence_by_validity?.SUPPORTED ?? 0;
        const challengedEv = d.evidence_by_validity?.CHALLENGED ?? 0;
        const invalidatedEv = d.evidence_by_validity?.INVALIDATED ?? 0;
        const supersededEv = d.evidence_by_validity?.SUPERSEDED ?? 0;
        const openImpacts = d.investigation_state?.open_impacts ?? 0;
        const hypothesesReview = d.investigation_state?.hypotheses_needing_review ?? 0;

        return (
          <div className="cm-dashboard-command">
            {/* Command Centre Metric HUD */}
            <div className="cm-metrics-hud">
              <StatBox
                label="TOTAL EVIDENCE"
                value={totalEvidence}
                sub={`${supportedEv} supported records`}
                icon="☵"
                accent="cyan"
              />
              <StatBox
                label="LINKED ENTITIES"
                value={totalEntities}
                sub={`${d.counts?.people ?? 0} persons identified`}
                icon="◈"
                accent="amber"
              />
              <StatBox
                label="OPEN ALERTS / IMPACTS"
                value={openImpacts}
                sub={openImpacts > 0 ? "Requires recomputation" : "All models synced"}
                icon="⚠️"
                accent={openImpacts > 0 ? "crimson" : "emerald"}
              />
              <StatBox
                label="HYPOTHESES"
                value={d.counts?.hypotheses ?? 0}
                sub={`${hypothesesReview} pending supervisor review`}
                icon="✧"
                accent="purple"
              />
            </div>

            <Notice level="info">{d.notice}</Notice>

            {/* Quick Action Holographic Matrix */}
            <div className="cm-command-shortcuts">
              <button className="cm-shortcut-btn" onClick={() => go("Graph")}>
                <span>☍</span>
                <div>
                  <strong>Relationship Graph</strong>
                  <small>Interactive entity connections & force layout</small>
                </div>
              </button>
              <button className="cm-shortcut-btn" onClick={() => go("CCTV Analysis")}>
                <span>⌕</span>
                <div>
                  <strong>CCTV Surveillance Workspace</strong>
                  <small>Camera feeds, sightings & clock audits</small>
                </div>
              </button>
              <button className="cm-shortcut-btn" onClick={() => go("Statement NLP")}>
                <span>🧠</span>
                <div>
                  <strong>Statement Credibility NLP</strong>
                  <small>CBCA criteria, cognitive load & SVA probes</small>
                </div>
              </button>
              <button className="cm-shortcut-btn" onClick={() => go("AI analysis")}>
                <span>✧</span>
                <div>
                  <strong>AI Investigation Assistant</strong>
                  <small>Controlled context & verified findings</small>
                </div>
              </button>
              <button className="cm-shortcut-btn" onClick={() => go("Questions")}>
                <span>⌘</span>
                <div>
                  <strong>SQL Module Runner</strong>
                  <small>40 registered investigative questions</small>
                </div>
              </button>
            </div>

            <div className="grid">
              {/* Evidence Validity Distribution */}
              <Card title="Evidence Validity Distribution (EVLM)">
                <div className="cm-validity-bars">
                  <div className="cm-val-bar-item">
                    <div className="row justify-between">
                      <span className="font-mono text-emerald">SUPPORTED</span>
                      <b>{supportedEv}</b>
                    </div>
                    <CyberProgress value={supportedEv} max={Math.max(1, totalEvidence)} color="emerald" />
                  </div>
                  <div className="cm-val-bar-item">
                    <div className="row justify-between">
                      <span className="font-mono text-amber">CHALLENGED</span>
                      <b>{challengedEv}</b>
                    </div>
                    <CyberProgress value={challengedEv} max={Math.max(1, totalEvidence)} color="amber" />
                  </div>
                  <div className="cm-val-bar-item">
                    <div className="row justify-between">
                      <span className="font-mono text-crimson">INVALIDATED</span>
                      <b>{invalidatedEv}</b>
                    </div>
                    <CyberProgress value={invalidatedEv} max={Math.max(1, totalEvidence)} color="crimson" />
                  </div>
                  <div className="cm-val-bar-item">
                    <div className="row justify-between">
                      <span className="font-mono text-muted">SUPERSEDED</span>
                      <b>{supersededEv}</b>
                    </div>
                    <CyberProgress value={supersededEv} max={Math.max(1, totalEvidence)} color="muted" />
                  </div>
                </div>
                <div style={{ marginTop: 14 }}>
                  <button className="small" onClick={() => go("Evidence")}>
                    Manage Evidence Register →
                  </button>
                </div>
              </Card>

              {/* Case Telemetry & Records */}
              <Card title="Case Telemetry & Records">
                {Object.entries(d.counts).map(([k, v]) => (
                  <div className="kv" key={k}>
                    <span>{k.replace(/_/g, " ")}</span>
                    <b className="font-mono">{v}</b>
                  </div>
                ))}
              </Card>

              {/* Investigation Integrity & Needs Attention */}
              <Card
                title="Integrity & Needs Attention"
                aside={
                  (openImpacts > 0 || hypothesesReview > 0) && (
                    <span className="cm-badge-pulse alert">ACTION REQUIRED</span>
                  )
                }
              >
                <div className="kv">
                  <span>Findings awaiting recompute</span>
                  <b className="font-mono text-amber">{openImpacts}</b>
                </div>
                <div className="kv">
                  <span>Hypotheses needing review</span>
                  <b className="font-mono text-purple">{hypothesesReview}</b>
                </div>
                <div className="kv">
                  <span>Audited reviews recorded</span>
                  <b className="font-mono text-cyan">{d.investigation_state.reviews}</b>
                </div>
                {(openImpacts > 0 || hypothesesReview > 0) && (
                  <div style={{ marginTop: 12 }}>
                    <button className="primary" onClick={() => go("Evidence changes")}>
                      Resolve Evidence Changes ↗
                    </button>
                  </div>
                )}
              </Card>

              {/* Findings Classification */}
              <Card title="Findings by Status">
                {Object.entries(d.findings_by_status).map(([k, v]) => (
                  <div className="kv" key={k}>
                    <Badge kind={k} />
                    <b className="font-mono">{v}</b>
                  </div>
                ))}
              </Card>
            </div>

            {/* Incidents Timeline */}
            <Card title="Primary Case Incidents">
              {d.incidents.map((i) => (
                <div key={i.ref} className="cm-incident-row">
                  <div className="cm-incident-dot" />
                  <div className="cm-incident-main">
                    <div className="row">
                      <span className="font-mono text-cyan"><b>{i.ref}</b></span>
                      <strong>{i.description}</strong>
                    </div>
                    <div className="muted small">
                      Location: {i.location_name} · Incident Time: {time(i.occurred_at)}
                    </div>
                  </div>
                </div>
              ))}
            </Card>
          </div>
        );
      }}
    </Async>
  );
}

class TabBoundary extends React.Component {
  state = { err: null };
  static getDerivedStateFromError(err) {
    return { err };
  }
  componentDidUpdate(prevProps) {
    if (prevProps.tabKey !== this.props.tabKey && this.state.err) {
      this.setState({ err: null });
    }
  }
  render() {
    if (!this.state.err) return this.props.children;
    return (
      <div className="state error cm-cyber-error cm-chromatic-glitch" role="alert" style={{ margin: 24 }}>
        <strong>PANEL DISPLAY EXCEPTION</strong>
        <div className="small font-mono">
          {String(this.state.err.message || this.state.err)}
        </div>
        <button className="primary" onClick={() => this.setState({ err: null })} style={{ marginTop: 10 }}>
          ↻ Retry Component
        </button>
      </div>
    );
  }
}

export default function CaseView({ caseRef, user, onBack }) {
  const c = useMemo(() => caseApi(caseRef), [caseRef]);
  const [tab, setTab] = useState("Dashboard");
  const [isExporting, setIsExporting] = useState(false);
  const activeTabDef = TABS.find(([n]) => n === tab) || TABS[0];
  const Page = activeTabDef[1];

  const handleExportDossier = async () => {
    try {
      setIsExporting(true);
      cyberAudio.playScan();
      const [caseInfo, evRes, entRes] = await Promise.all([
        c.get("").catch(() => ({})),
        c.get("/evidence").catch(() => ({ evidence: [] })),
        c.get("/entities?limit=50").catch(() => ({ entities: [] })),
      ]);
      exportCourtroomDossier({
        caseInfo: { ref: caseRef, ...(caseInfo || {}) },
        evidenceList: evRes.evidence || [],
        entitiesList: entRes.entities || [],
      });
      cyberAudio.playSuccess();
    } catch (err) {
      console.error("Courtroom dossier export failed", err);
      cyberAudio.playGlitch();
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="cm-caseview-wrap">
      {/* Case Header Breadcrumb Bar */}
      <div className="cm-case-crumbs">
        <button className="cm-back-btn" onClick={onBack}>
          ← Case Directory
        </button>
        <span className="cm-crumb-sep">/</span>
        <div className="cm-case-badge-title">
          <h2><ScrambleText text={caseRef} speed={35} /></h2>
          <span className="cm-live-indicator">ACTIVE INVESTIGATION</span>
        </div>
        <div className="grow" />
        <button
          className="cm-courtroom-export-btn"
          onClick={handleExportDossier}
          disabled={isExporting}
          title="Export self-contained judicial case dossier for courtroom presentation"
        >
          {isExporting ? "⏳ COMPILING DOSSIER..." : "⚖️ COURTROOM DOSSIER ↗"}
        </button>
        <div className="cm-case-meta font-mono small text-muted">
          OPERATOR: <span className="text-cyan">{user.username}</span> ({user.role})
        </div>
      </div>

      {/* Cyberpunk Navigation Tabs */}
      <nav className="tabs cm-cyber-tabs" role="tablist">
        {TABS.map(([n, _, icon]) => {
          const isActive = tab === n;
          return (
            <button
              key={n}
              role="tab"
              aria-selected={isActive}
              className={`cm-cyber-tab ${isActive ? "on" : ""}`}
              onClick={() => setTab(n)}
            >
              <span className="cm-tab-icon">{icon}</span>
              <span className="cm-tab-label">{n}</span>
              {isActive && <span className="cm-tab-laser" />}
            </button>
          );
        })}
      </nav>

      {/* Active Tab Page Content */}
      <div className="cm-tab-content-pane">
        <TabBoundary tabKey={caseRef + tab}>
          <Page key={caseRef + tab} c={c} caseRef={caseRef} user={user} go={setTab} />
        </TabBoundary>
      </div>
    </div>
  );
}
