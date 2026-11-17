import React, { useState } from "react";
import { useLoad } from "../hooks.js";
import { Async, Badge, Card, Notice, time } from "../components/ui.jsx";
import { api } from "../api.js";

const SUGGESTED_QUERIES = [
  "Summarise what the current evidence says about movements near the park around the incident.",
  "Which entities share anomalous communications or fund transfers with the victim?",
  "Are there conflicting alibis or impossible speed jumps detected for Karan Bhatt?",
  "List all corroborated CCTV sightings recorded within 1 hour of the incident.",
];

export default function AiPanel({ c }) {
  const status = useLoad(() => api("/ai/status"), []);
  const hist = useLoad(() => c.get("/ai/analyses"), [c]);
  const [q, setQ] = useState("");
  const [res, setRes] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const ask = async (questionText) => {
    const query = questionText || q;
    if (!query || query.trim().length < 3) return;
    setBusy(true);
    setErr(null);
    setRes(null);
    try {
      const data = await c.post("/ai/analyze", { question: query });
      setRes(data);
      hist.reload();
    } catch (x) {
      setErr(x);
    } finally {
      setBusy(false);
    }
  };

  const handleFormSubmit = (e) => {
    e.preventDefault();
    ask(q);
  };

  return (
    <div className="split cm-ai-split">
      <Card title="AI Intelligence Assistant // Controlled Context Engine">
        {/* Provider Status Terminal Ribbon */}
        <Async state={status}>
          {(s) => (
            <div className={`cm-ai-provider-pill ${s.is_llm ? "llm" : "offline"}`}>
              <div className="cm-ai-pulse" />
              <div className="cm-ai-pill-text">
                <strong>{s.is_llm ? `ACTIVE MODEL: ${s.provider.toUpperCase()}` : "OFFLINE DETERMINISTIC TEMPLATE"}</strong>
                <span> · {s.message}</span>
              </div>
            </div>
          )}
        </Async>

        <Notice level="info">
          Controlled Context Pipeline: The assistant only inspects evidence and records you are cleared to view.
          Outputs pass an automated hallucination and overreach validator. Every proposition is explicitly labelled.
          The AI never determines guilt.
        </Notice>

        {/* Suggested Queries */}
        <div className="cm-ai-suggestions">
          <span className="cm-ai-sugg-label font-mono small text-muted">SUGGESTED QUERIES:</span>
          <div className="cm-sugg-chips">
            {SUGGESTED_QUERIES.map((sq, i) => (
              <button
                key={i}
                type="button"
                className="cm-sugg-chip"
                onClick={() => {
                  setQ(sq);
                  ask(sq);
                }}
              >
                {sq}
              </button>
            ))}
          </div>
        </div>

        {/* Prompt Input Form */}
        <form onSubmit={handleFormSubmit} className="stack" style={{ marginTop: 12 }}>
          <div className="cm-prompt-box">
            <span className="cm-terminal-prompt font-mono text-cyan">CRIMEMIND:AI&gt;</span>
            <textarea
              rows={3}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Ask an investigative synthesis question (e.g. movement contradictions, financial paths, alibis)…"
              className="cm-prompt-input"
            />
          </div>
          <button className="primary" disabled={busy || q.trim().length < 3}>
            {busy ? (
              <span className="row items-center gap-2">
                <span className="cm-radar-spinner small" />
                <span>SYNTHESIZING VERIFIED EVIDENCE…</span>
              </span>
            ) : (
              "Run Intelligence Analysis ↗"
            )}
          </button>
        </form>

        {err && <div className="state error cm-cyber-error" role="alert">{err.message}</div>}

        {/* AI Synthesis Result Card */}
        {res && (
          <div className="cm-ai-result-pane">
            <div className="cm-ai-res-header">
              <div className="row">
                <Badge kind={res.status} />
                <Badge kind={res.provider_is_llm ? "AI model" : "offline template"} />
              </div>
              <span className="font-mono small text-muted">
                CONTEXT_SHA: {res.context_sha256?.slice(0, 14)}…
              </span>
            </div>

            <p className="cm-ai-status-msg">{res.message}</p>

            {res.problems?.length > 0 && (
              <div className="state error">
                <strong>Validator Warnings:</strong>
                <ul>
                  {res.problems.map((p, i) => (
                    <li key={i}>{p}</li>
                  ))}
                </ul>
              </div>
            )}

            {res.output && (
              <div className="cm-ai-synthesis-body">
                <div className="cm-ai-summary-callout">
                  <h4>SYNTHESIS EXECUTIVE SUMMARY</h4>
                  <p>{res.output.summary}</p>
                </div>

                <h4>VALIDATED STATEMENT BREAKDOWN</h4>
                <div className="cm-findings-list">
                  {res.output.findings.map((f, i) => (
                    <div className="cm-finding-card" key={i}>
                      <div className="cm-finding-top">
                        <Badge kind={f.classification} />
                        <span className="font-mono small text-cyan">STATEMENT #{i + 1}</span>
                      </div>
                      <p className="cm-finding-text">{f.statement}</p>
                      <div className="cm-finding-citations font-mono small text-muted">
                        CITATIONS: {[...(f.correlation_ids || []), ...(f.evidence_ids || [])].join(" · ") || "NONE"}
                      </div>
                    </div>
                  ))}
                </div>

                {res.output.uncertainties?.length > 0 && (
                  <div className="cm-uncertainties-panel">
                    <h4>STATED UNCERTAINTIES & LIMITATIONS</h4>
                    <ul>
                      {res.output.uncertainties.map((u, i) => (
                        <li key={i}>{u}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Audit History of Prior Inquiries */}
      <Card title="Prior Audited Syntheses">
        <Async
          state={hist}
          empty={Object.assign((d) => !d.analyses?.length, { message: "No previous analyses recorded for this case." })}
        >
          {(d) =>
            d.analyses.map((a) => (
              <div key={a.analysis_id} className="cm-history-item" onClick={() => setQ(a.question)}>
                <div className="cm-history-question">"{a.question}"</div>
                <div className="cm-history-meta font-mono small">
                  <Badge kind={a.status} />
                  <span>{time(a.created_at)}</span>
                </div>
              </div>
            ))
          }
        </Async>
      </Card>
    </div>
  );
}
