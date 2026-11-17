import React, { useMemo, useState } from "react";
import { ApiError } from "../api.js";
import { useLoad } from "../hooks.js";
import { api } from "../api.js";
import { Async, Badge, Card, Notice, Table, fmt } from "../components/ui.jsx";

const LABEL = { entity_id: "Entity (ref, e.g. P-002)", entity_a: "Entity A", entity_b: "Entity B", location_id: "Location (ref, e.g. L-GP1)", event_id: "Incident (ref, e.g. EVT-001)",
  start_time: "Start (ISO time)", end_time: "End (ISO time)", window_minutes: "Window (minutes)", result_limit: "Max rows", vehicle_id: "Vehicle ref", include_historical: "Include non-SUPPORTED evidence" };

export default function Questions({ c }) {
  const qs = useLoad(() => api("/questions"), []);
  const [sel, setSel] = useState(null), [vals, setVals] = useState({}), [res, setRes] = useState(null), [err, setErr] = useState(null), [busy, setBusy] = useState(false), [text, setText] = useState(""), [cands, setCands] = useState(null);
  const groups = useMemo(() => { const g = {}; (qs.data?.questions || []).forEach((q) => (g[q.category] ||= []).push(q)); return g; }, [qs.data]);
  const pick = (q) => { setSel(q); setVals({}); setRes(null); setErr(null); };
  const run = async (e) => {
    e.preventDefault(); setBusy(true); setErr(null); setRes(null);
    const parameters = {}; Object.entries(vals).forEach(([k, v]) => { if (v !== "" && v !== undefined) parameters[k] = k === "include_historical" ? !!v : /^(window_minutes|result_limit)$/.test(k) ? Number(v) : v; });
    try { setRes(await c.post("/queries/run", { question_id: sel.question_id, parameters })); } catch (x) { setErr(x); } finally { setBusy(false); }
  };
  const resolve = async (e) => { e.preventDefault(); try { setCands(await c.post("/queries/resolve", { text })); } catch (x) { setErr(x); } };
  const params = sel ? [...sel.required_params.map((p) => [p, true]), ...sel.optional_params.map((p) => [p, false]), ["include_historical", false]] : [];
  return (
    <div className="split">
      <Card title="Investigation questions">
        <form className="row" onSubmit={resolve}><input placeholder="Describe what you want to know…" value={text} onChange={(e) => setText(e.target.value)} /><button>Suggest questions</button></form>
        {cands && <div className="state">{cands.candidates.length ? <>Suggested (nothing has been run): {cands.candidates.map((q) => <button key={q.question_id} onClick={() => pick(q)}>{q.question_id}</button>)}</> : "No matching question. Pick one from the list below."}</div>}
        <Async state={qs}>{() => Object.entries(groups).map(([cat, list]) => (
          <div key={cat}><h4>{cat}</h4>{list.map((q) => <button key={q.question_id} className={`qrow ${sel?.question_id === q.question_id ? "on" : ""}`} onClick={() => pick(q)}><b>{q.question_id}</b> {q.display_text}</button>)}</div>))}</Async>
      </Card>
      <Card title={sel ? `${sel.question_id} — ${sel.display_text}` : "Run a question"}>
        {!sel && <p className="muted">Choose a question. Parameters are validated on the server and bound to a fixed, reviewed SQL module — no free-form SQL.</p>}
        {sel && (<form onSubmit={run} className="stack">
          <p className="small muted">Module {sel.module_id} v{sel.module_version} · variant “{sel.variant}” · file {sel.file_name}</p>
          {params.map(([p, req]) => p === "include_historical"
            ? <label key={p} className="inline"><input type="checkbox" checked={!!vals[p]} onChange={(e) => setVals({ ...vals, [p]: e.target.checked })} /> {LABEL[p]}</label>
            : <label key={p}>{LABEL[p] || p}{req && " *"}<input value={vals[p] || ""} onChange={(e) => setVals({ ...vals, [p]: e.target.value })} aria-invalid={!!err?.fields?.[p]} />
                {err?.fields?.[p] && <span className="fielderr">{err.fields[p]}</span>}</label>)}
          <button className="primary" disabled={busy}>{busy ? "Running…" : "Run"}</button>
        </form>)}
        {err && <div className="state error" role="alert">{err.message}{err.fields && !params.length ? JSON.stringify(err.fields) : ""}</div>}
        {res && (<div className="stack">
          <div className="row"><Badge kind={res.classification} /><span className="muted small">{res.result_count} row(s) · {res.duration_ms} ms · exec {res.query_exec_id?.slice(0, 8)}</span></div>
          {res.warnings?.map((w, i) => <Notice key={i}>{w}</Notice>)}
          {res.result_count === 0
            ? <div className="state">No records matched. This is a valid result, not an error — it does not prove nothing happened.</div>
            : <Table rows={res.rows} cols={Object.keys(res.rows[0]).map((k) => ({ label: k, render: (r) => fmt(r[k]) }))} />}
        </div>)}
      </Card>
    </div>);
}
