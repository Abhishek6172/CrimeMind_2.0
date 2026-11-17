import React, { useState } from "react";
import { ApiError } from "../api.js";
import { useLoad } from "../hooks.js";
import { Async, Badge, Card, Notice, Table, fmt, time } from "../components/ui.jsx";

// Guidance only: the server's EVLM rules are authoritative and re-check every request.
const RULES = {
  SUPPORTED: [["CHALLENGED", "DOCUMENTED_CONTRADICTION"], ["INVALIDATED", "CONFIRMED_INVALIDITY"], ["SUPERSEDED", "REPLACEMENT_RECORD"]],
  CHALLENGED: [["INVALIDATED", "CONFIRMED_INVALIDITY"], ["SUPPORTED", "CORROBORATION"], ["SUPERSEDED", "REPLACEMENT_RECORD"]],
  INVALIDATED: [["SUPERSEDED", "REPLACEMENT_RECORD"]],
  SUPERSEDED: [],
};
const REASONS = ["TIMESTAMP_ERROR", "DEVICE_FAULT", "SOURCE_RETRACTION", "CONTRADICTED_BY_STRONGER_SOURCE", "CORRECTED_RECORD", "OWNERSHIP_TRANSFER", "MANUAL_REVIEW", "CORROBORATED"];

function ChangePanel({ c, ev, role, onDone }) {
  const opts = [...(RULES[ev.validity_status] || []), ...(["SUPERVISOR", "ADMINISTRATOR"].includes(role) && ev.validity_status !== "SUPERSEDED"
    ? ["SUPPORTED", "CHALLENGED", "INVALIDATED"].filter((s) => s !== ev.validity_status).map((s) => [s, "MANUAL_OVERRIDE"]) : [])];
  const [pick, setPick] = useState(0), [reason, setReason] = useState("MANUAL_REVIEW"), [just, setJust] = useState(""), [trig, setTrig] = useState("");
  const [busy, setBusy] = useState(false), [msg, setMsg] = useState(null);
  if (!opts.length) return <p className="muted">This evidence is {ev.validity_status} and cannot change state.</p>;
  const [newStatus, trigger] = opts[pick] || opts[0];
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setMsg(null);
    try {
      const r = await c.post(`/evidence/${ev.ref}/validity`, { new_status: newStatus, trigger, reason, justification: just || null, triggering_evidence_ref: trig || null });
      setMsg({ ok: true, text: `${r.message} ${r.findings_marked_recompute_required.length} finding(s) flagged; ${r.hypotheses_needing_review.length} hypothesis(es) need review.` });
      onDone();
    } catch (x) { setMsg({ ok: false, text: x instanceof ApiError ? `${x.message}${x.fields ? " " + JSON.stringify(x.fields) : ""}` : String(x) }); }
    finally { setBusy(false); }
  };
  return (
    <form onSubmit={submit} className="stack">
      <h4>Change validity</h4>
      <label>Transition<select value={pick} onChange={(e) => setPick(+e.target.value)}>{opts.map(([s, t], i) => <option key={i} value={i}>→ {s} (via {t})</option>)}</select></label>
      <label>Reason<select value={reason} onChange={(e) => setReason(e.target.value)}>{REASONS.map((r) => <option key={r}>{r}</option>)}</select></label>
      <label>Triggering evidence ref (if required)<input value={trig} onChange={(e) => setTrig(e.target.value)} placeholder="e.g. E-D001" /></label>
      <label>Justification{trigger === "MANUAL_OVERRIDE" && " (required, min 10 characters)"}<textarea value={just} onChange={(e) => setJust(e.target.value)} rows={3} /></label>
      <button className="primary" disabled={busy}>Record change</button>
      {msg && <div className={`state ${msg.ok ? "" : "error"}`} role="status">{msg.text}</div>}
      <p className="small muted">Changes are recorded, audited and propagate to dependent findings, which are flagged — never silently rewritten.</p>
    </form>);
}

function Detail({ c, refId, role, onChanged }) {
  const st = useLoad(() => c.get(`/evidence/${refId}`), [c, refId]);
  return (
    <Async state={st}>
      {(d) => (
        <div className="stack">
          <h3>{d.evidence.ref} <Badge kind={d.evidence.validity_status} /></h3>
          <div className="kv"><span>Type / source</span><span>{d.evidence.evidence_type} · {d.evidence.source}</span></div>
          <div className="kv"><span>Recorded</span><span>{time(d.evidence.evidence_timestamp)}</span></div>
          <div className="kv"><span>Reliability (heuristic)</span><span>{d.evidence.reliability_score}</span></div>
          <div className="kv"><span>Origin (independence)</span><span>{d.evidence.provenance?.origin_root || "—"}</span></div>
          <blockquote title="Source content is shown as data and never treated as an instruction">{d.evidence.description}</blockquote>
          <p className="small muted">{d.untrusted_text_notice}</p>
          <h4>Validity history</h4>
          <Table rows={d.validity_history} empty="No changes since it was recorded." cols={[
            { label: "When", render: (r) => time(r.changed_at) }, { label: "Change", render: (r) => `${r.previous_status} → ${r.new_status}` },
            { label: "Trigger", key: "trigger_code" }, { label: "Reason", key: "reason_code" }, { label: "By", key: "changed_by" }, { label: "Note", key: "justification" }]} />
          <h4>Dependent findings</h4>
          <Table rows={d.dependent_findings} empty="No findings depend on this evidence." cols={[
            { label: "Finding", key: "statement" }, { label: "Status", render: (r) => <Badge kind={r.status} /> }, { label: "Class", render: (r) => <Badge kind={r.classification} /> }]} />
          <ChangePanel c={c} ev={d.evidence} role={role} onDone={() => { st.reload(); onChanged(); }} />
        </div>)}
    </Async>);
}

function Search({ c, onPick }) {
  const [q, setQ] = useState(""), [res, setRes] = useState(null), [busy, setBusy] = useState(false), [err, setErr] = useState(null);
  const run = async (e) => {
    e.preventDefault();
    if (q.trim().length < 2) return;
    setBusy(true); setErr(null);
    try { setRes(await c.get("/evidence-search", { q: q.trim() })); }
    catch (x) { setErr(x instanceof ApiError ? x.message : String(x)); }
    finally { setBusy(false); }
  };
  return (
    <div className="stack">
      <form onSubmit={run} className="row">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder='Ask for evidence: "CCTV at Green Park lawn", "calls by Rohit Sethi", "E-0042"' aria-label="Ask for evidence" style={{ flex: 1 }} />
        <button className="primary" disabled={busy}>{busy ? "Searching…" : "Find"}</button>
        {res && <button type="button" onClick={() => { setRes(null); setQ(""); }}>Clear</button>}
      </form>
      {err && <div className="state error" role="alert">{err}</div>}
      {res && (<>
        <p className="small muted">{res.results.length} match(es). {res.named_entities.length ? `Recognised: ${res.named_entities.join(", ")}. ` : ""}
          {Object.keys(res.typo_corrections).length ? `Interpreted ${Object.entries(res.typo_corrections).map(([a, b]) => `“${a}” as “${b}”`).join(", ")}. ` : ""}{res.notice}</p>
        <Table rows={res.results} onRow={(r) => onPick(r.ref)} empty="No evidence in this case matches that request." cols={[
          { label: "Ref", key: "ref" }, { label: "Type", key: "evidence_type" }, { label: "Validity", render: (r) => <Badge kind={r.validity_status} /> },
          { label: "Why it matched", render: (r) => r.matched_on.join(" · ") }, { label: "Score", key: "score" }]} />
      </>)}
    </div>);
}

export default function Evidence({ c, user }) {
  const [status, setStatus] = useState(""), [sel, setSel] = useState(null);
  const st = useLoad(() => c.get("/evidence", { status }), [c, status]);
  return (
    <div className="split">
      <Card title="Evidence" aside={
        <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Validity filter">
          <option value="">All states</option>{Object.keys(RULES).map((s) => <option key={s}>{s}</option>)}</select>}>
        <Search c={c} onPick={setSel} />
        <Async state={st} empty={Object.assign((d) => !d.evidence.length, { message: "No evidence in this state." })}>
          {(d) => (<><Notice>{d.notice}</Notice>
            <Table rows={d.evidence} onRow={(r) => setSel(r.ref)} cols={[
              { label: "Ref", key: "ref" }, { label: "Type", key: "evidence_type" }, { label: "Source", key: "source" },
              { label: "Validity", render: (r) => <Badge kind={r.validity_status} /> }, { label: "Rel.", key: "reliability_score" }, { label: "Used by", key: "dependent_findings" }]} /></>)}
        </Async>
      </Card>
      <Card title="Detail">{sel ? <Detail key={sel} c={c} refId={sel} role={user.role} onChanged={st.reload} /> : <p className="muted">Select evidence to see provenance, validity history and dependents.</p>}</Card>
    </div>);
}
