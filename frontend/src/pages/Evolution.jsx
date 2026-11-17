import React, { useState } from "react";
import { useLoad } from "../hooks.js";
import { Async, Badge, Card, Notice, Table, time } from "../components/ui.jsx";

export default function Evolution({ c, user }) {
  const imp = useLoad(() => c.get("/impacts"), [c]);
  const hyp = useLoad(() => c.get("/hypotheses"), [c]);
  const fnd = useLoad(() => c.get("/findings", { include_outdated: "true" }), [c]);
  const [msg, setMsg] = useState(null), [busy, setBusy] = useState(false);
  const refresh = () => { imp.reload(); hyp.reload(); fnd.reload(); };
  const recompute = async () => {
    setBusy(true); setMsg(null);
    try { const r = await c.post("/findings/recompute"); setMsg({ ok: true, text: `${r.outcomes.length} finding(s) processed. ${r.message}` }); refresh(); }
    catch (x) { setMsg({ ok: false, text: x.message }); } finally { setBusy(false); }
  };
  const clear = async (ref) => { try { await c.post(`/hypotheses/${ref}/clear-review`); hyp.reload(); } catch (x) { setMsg({ ok: false, text: x.message }); } };
  return (
    <>
      <Card title="Findings waiting for recompute" aside={<button className="primary" disabled={busy} onClick={recompute}>Recompute now</button>}>
        <Notice>When evidence changes, dependent findings are flagged rather than silently rewritten. Recompute creates a new finding version or records that support is gone; earlier versions stay available.</Notice>
        {msg && <div className={`state ${msg.ok ? "" : "error"}`} role="status">{msg.text}</div>}
        <Async state={imp} empty={Object.assign((d) => !d.open_impacts.length, { message: "Nothing is waiting. All findings reflect current evidence." })}>
          {(d) => <Table rows={d.open_impacts} cols={[{ label: "Finding", key: "statement" }, { label: "Evidence now", render: (r) => <Badge kind={r.evidence_new_status} /> }, { label: "Reason", key: "reason_code" }, { label: "Flagged", render: (r) => time(r.logged_at) }]} />}
        </Async>
      </Card>
      <Card title="Hypotheses (not recorded facts)">
        <Async state={hyp} empty={Object.assign((d) => !d.hypotheses.length, { message: "No hypotheses." })}>
          {(d) => d.hypotheses.map((h) => (
            <div key={h.ref} className="finding"><b>{h.ref}</b> {h.title} <Badge kind={h.status} />
              {h.needs_review && <><Badge kind="needs review" /> <button onClick={() => clear(h.ref)}>I have reviewed this</button></>}
              <div className="small muted">Evidence: {h.evidence.map((e) => `${e.ref} (${e.validity_status})`).join(", ") || "—"}</div></div>))}
        </Async>
      </Card>
      <Card title="Finding versions">
        <Async state={fnd}>{(d) => <Table rows={d.findings} cols={[{ label: "Key", key: "finding_key" }, { label: "v", key: "version" }, { label: "Status", render: (r) => <Badge kind={r.status} /> }, { label: "Class", render: (r) => <Badge kind={r.classification} /> }, { label: "Statement", key: "statement" }]} />}</Async>
      </Card>
    </>);
}
