import React, { useState } from "react";
import { useLoad } from "../hooks.js";
import { Async, Badge, Card, Notice, Table, fmt } from "../components/ui.jsx";

function CommonLink({ c }) {
  const [a, setA] = useState(""), [b, setB] = useState(""), [res, setRes] = useState(null), [err, setErr] = useState(null);
  const go = async (e) => { e.preventDefault(); setErr(null); setRes(null); try { setRes(await c.get("/common-link", { a, b })); } catch (x) { setErr(x); } };
  return (
    <Card title="Common link between two people">
      <form className="row" onSubmit={go}><input placeholder="Person A (e.g. P-002)" value={a} onChange={(e) => setA(e.target.value)} /><input placeholder="Person B (e.g. P-003)" value={b} onChange={(e) => setB(e.target.value)} /><button disabled={!a || !b}>Find</button></form>
      {err && <div className="state error" role="alert">{err.message}</div>}
      {res && <pre className="json">{JSON.stringify(res, null, 2)}</pre>}
    </Card>);
}

export default function Correlations({ c }) {
  const [type, setType] = useState(""), [entity, setEntity] = useState(""), [applied, setApplied] = useState({ type: "", entity: "" });
  const st = useLoad(() => c.get("/correlations", { result_type: applied.type, entity: applied.entity, limit: 300 }), [c, applied]);
  return (
    <>
      <Card title="Correlations" aside={
        <form className="row" onSubmit={(e) => { e.preventDefault(); setApplied({ type, entity }); }}>
          <select value={type} onChange={(e) => setType(e.target.value)} aria-label="Class"><option value="">All classes</option><option>FACT</option><option>CORRELATED</option><option>INFERRED</option></select>
          <input placeholder="Entity ref" value={entity} onChange={(e) => setEntity(e.target.value)} /><button>Filter</button></form>}>
        <Async state={st} empty={Object.assign((d) => !d.results.length, { message: "No correlations match." })}>
          {(d) => (<><Notice>{d.notice}</Notice>
            <p className="small muted">{d.returned} shown · run {d.run.run_id} · started {fmt(d.run.started_at)}</p>
            <Table rows={d.results} cols={[
              { label: "ID", key: "correlation_id" }, { label: "Class", render: (r) => <Badge kind={r.result_type} /> }, { label: "Rule", render: (r) => `${r.rule_id} v${r.rule_version}` },
              { label: "Summary", key: "summary" }, { label: "Evidence", key: "supporting_evidence_ids" }, { label: "Conf.", key: "confidence" }]} /></>)}
        </Async>
      </Card>
      <CommonLink c={c} />
    </>);
}
