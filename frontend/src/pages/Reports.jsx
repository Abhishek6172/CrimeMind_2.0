import React, { useState } from "react";
import { useLoad } from "../hooks.js";
import { Async, Card, Table, time } from "../components/ui.jsx";

export default function Reports({ c, caseRef }) {
  const st = useLoad(() => c.get("/reports"), [c]);
  const [err, setErr] = useState(null), [busy, setBusy] = useState(false);
  const gen = async () => { setBusy(true); setErr(null); try { await c.post("/reports"); st.reload(); } catch (x) { setErr(x); } finally { setBusy(false); } };
  const open = async (id) => {   // fetched with the auth header, then shown in a new tab as a blob
    const t = sessionStorage.getItem("cm_token");
    const r = await fetch(`/api/cases/${caseRef}/reports/${id}/html`, { headers: { Authorization: `Bearer ${t}` } });
    if (r.ok) window.open(URL.createObjectURL(new Blob([await r.text()], { type: "text/html" })), "_blank");
  };
  return (
    <Card title="Reports" aside={<button className="primary" disabled={busy} onClick={gen}>Generate report</button>}>
      <p className="muted small">A report is a point-in-time snapshot: it states evidence validity, classifications, uncertainties and the module versions used. It is a decision-support document, not a conclusion.</p>
      {err && <div className="state error" role="alert">{err.message}</div>}
      <Async state={st} empty={Object.assign((d) => !d.reports.length, { message: "No reports yet." })}>
        {(d) => <Table rows={d.reports} cols={[{ label: "Report", render: (r) => r.report_id.slice(0, 8) }, { label: "Generated", render: (r) => time(r.generated_at) }, { label: "By", key: "generated_by" },
          { label: "SHA-256", render: (r) => <code>{r.content_sha256.slice(0, 12)}…</code> }, { label: "", render: (r) => <button onClick={() => open(r.report_id)}>Open</button> }]} />}
      </Async>
    </Card>);
}
