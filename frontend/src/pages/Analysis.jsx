import React, { useState } from "react";
import { useLoad } from "../hooks.js";
import { Async, Badge, Card, Notice, Table, time } from "../components/ui.jsx";
import { EntityList, Field, toIso, useSubmit } from "../components/Forms.jsx";

const Result = ({ st }) => (<>
  {st.err && <div className="state error" role="alert">{st.err.message}{st.err.fields ? " " + Object.values(st.err.fields).join("; ") : ""}</div>}
  {st.busy && <div className="state">Working…</div>}
</>);

function Jumps({ c }) {
  const [speed, setSpeed] = useState(120);
  const st = useLoad(() => c.get("/insights/jumps", { max_speed_kmh: speed }), [c, speed]);
  return (
    <Card title="Movement plausibility" aside={<label className="inline small">Max plausible speed (km/h)<input type="number" value={speed} onChange={(e) => setSpeed(+e.target.value || 120)} style={{ width: 80 }} /></label>}>
      <Notice>Finds people recorded in two places that cannot both be right. A source that appears in many conflicts is a candidate for a device or timestamp check.</Notice>
      <Async state={st} empty={Object.assign((d) => !d.flags.length, { message: "No impossible movements found in the current, supported records." })}>
        {(d) => (<>
          {d.sources_in_conflicts.length > 0 && <div className="state warn">Sources involved: {d.sources_in_conflicts.map((s) => `${s.source} (${s.flagged_pairs})`).join(" · ")}</div>}
          <Table rows={d.flags} cols={[{ label: "Kind", render: (r) => <Badge kind={r.kind === "SIMULTANEOUS_PRESENCE" ? "correlated" : "inferred"}>{r.kind.replace("_", " ")}</Badge> },
            { label: "Person", render: (r) => `${r.subject.ref} ${r.subject.name}` }, { label: "Finding", key: "summary" },
            { label: "Records", render: (r) => `${r.from.obs}, ${r.to.obs}` }, { label: "Evidence", render: (r) => [r.from.evidence_ref, r.to.evidence_ref].filter(Boolean).join(", ") || "—" }]} />
          <p className="small muted">Possible explanations: {d.flags[0]?.possible_explanations.join("; ")}.</p></>)}
      </Async>
    </Card>);
}

function Alibi({ c }) {
  const [v, setV] = useState({ start: "2026-08-14T20:30", end: "2026-08-14T21:30" }), [st, run] = useSubmit();
  const go = (e) => { e.preventDefault(); run(() => c.get("/insights/alibi", { person: v.person, start: toIso(v.start), end: toIso(v.end), location: v.location, radius_m: v.radius || 150 })); };
  const d = st.ok;
  const tone = { PLACED_AT_LOCATION: "correlated", CONFLICTING: "invalid", RECORDED_ELSEWHERE: "ok", NO_DATA: "uncertain" };
  return (
    <Card title="Alibi checker">
      <form onSubmit={go} className="stack"><div className="grid">
        <Field spec={{ label: "Person", kind: "entity", required: true }} value={v.person} onChange={(x) => setV({ ...v, person: x })} />
        <Field spec={{ label: "Location (blank = incident location)", kind: "entity" }} value={v.location} onChange={(x) => setV({ ...v, location: x })} />
        <Field spec={{ label: "From (IST)", kind: "datetime", required: true }} value={v.start} onChange={(x) => setV({ ...v, start: x })} />
        <Field spec={{ label: "To (IST)", kind: "datetime", required: true }} value={v.end} onChange={(x) => setV({ ...v, end: x })} />
        <Field spec={{ label: "Radius (m)", kind: "number" }} value={v.radius} onChange={(x) => setV({ ...v, radius: x })} /></div>
        <button className="primary" disabled={!v.person || st.busy}>Check</button></form>
      <Result st={st} />
      {d && (<div className="stack">
        <div className="row"><Badge kind={tone[d.verdict]}>{d.verdict.replace(/_/g, " ")}</Badge><span className="muted small">{d.coverage_percent}% of the window covered · {d.independent_sources} independent source(s)</span></div>
        <p>{d.explanation}</p>
        <h4>At the location</h4><Table rows={d.at_location} empty="None." cols={[{ label: "Record", key: "obs" }, { label: "Place", key: "location_name" }, { label: "Source", key: "source" }, { label: "From", render: (r) => time(r.from) }, { label: "Evidence", key: "evidence_ref" }]} />
        <h4>Elsewhere</h4><Table rows={d.elsewhere} empty="None." cols={[{ label: "Record", key: "obs" }, { label: "Place", key: "location_name" }, { label: "Distance (m)", key: "distance_to_target_m" }, { label: "Source", key: "source" }, { label: "From", render: (r) => time(r.from) }, { label: "Evidence", key: "evidence_ref" }]} />
        <p className="small muted">{d.communications_in_window.length} communication(s) and {d.transactions_in_window.length} transaction(s) in the window. {d.excluded_unsupported_records} observation(s) are excluded because their evidence is no longer supported. {d.notice}</p></div>)}
    </Card>);
}

function Network({ c }) {
  const st = useLoad(() => c.get("/insights/network"), [c]);
  return (
    <Card title="Network structure">
      <Async state={st}>{(d) => (<>
        <Notice>{d.metrics_note}</Notice>
        <p className="small muted">{d.people_count} connected people in {d.communities.length} communities (sizes {d.communities.map((x) => x.size).join(", ")}).</p>
        <Table rows={d.people.slice(0, 40)} cols={[{ label: "Person", render: (r) => `${r.ref} ${r.name}` }, { label: "Links", key: "degree" }, { label: "Betweenness", key: "betweenness" }, { label: "PageRank", key: "pagerank" },
          { label: "Community", key: "community" }, { label: "Notes", render: (r) => [r.is_victim && "victim", r.connected_to_victim && "linked to victim", r.bridges_communities && "go-between"].filter(Boolean).join(", ") || "—" }]} /></>)}</Async>
    </Card>);
}

function Anomalies({ c }) {
  const st = useLoad(() => c.get("/insights/anomalies"), [c]);
  return (
    <Card title="Anomaly flags">
      <Async state={st} empty={Object.assign((d) => !d.flags.length, { message: "Nothing unusual found under the current rules." })}>{(d) => (<>
        <Notice>{d.notice}</Notice>
        <p className="small muted">{Object.entries(d.by_rule).map(([k, v]) => `${k}: ${v}`).join(" · ")}</p>
        <Table rows={d.flags} cols={[{ label: "Rule", key: "rule" }, { label: "Level", render: (r) => <Badge kind={r.severity === "MEDIUM" ? "challenged" : "supported"}>{r.severity}</Badge> }, { label: "Who", render: (r) => Array.isArray(r.subjects) ? r.subjects.map(s => typeof s === "object" ? `${s.ref || ""} ${s.name || ""}`.trim() : s).join(", ") : String(r.subjects || "") },
          { label: "Finding", key: "summary" }, { label: "Records", render: (r) => r.records.join(", ") || "—" }]} />
        <details><summary className="small muted">How each rule works</summary>{Object.entries(d.rules).map(([k, v]) => <div key={k} className="kv small"><span>{k}</span><span>{v}</span></div>)}</details></>)}</Async>
    </Card>);
}

function MoneyTrail({ c }) {
  const [v, setV] = useState({ direction: "forward", max_hops: 4 }), [st, run] = useSubmit();
  const go = (e) => { e.preventDefault(); run(() => c.get("/insights/money-trail", { entity: v.entity, direction: v.direction, max_hops: v.max_hops, min_amount: v.min_amount })); };
  const d = st.ok;
  return (
    <Card title="Money trail">
      <form onSubmit={go} className="stack"><div className="grid">
        <Field spec={{ label: "Start from", kind: "entity", required: true }} value={v.entity} onChange={(x) => setV({ ...v, entity: x })} />
        <Field spec={{ label: "Direction", kind: "select", options: ["forward", "backward"] }} value={v.direction} onChange={(x) => setV({ ...v, direction: x || "forward" })} />
        <Field spec={{ label: "Max hops", kind: "number" }} value={v.max_hops} onChange={(x) => setV({ ...v, max_hops: x })} />
        <Field spec={{ label: "Min amount", kind: "number" }} value={v.min_amount} onChange={(x) => setV({ ...v, min_amount: x })} /></div>
        <button className="primary" disabled={!v.entity || st.busy}>Trace</button></form>
      <Result st={st} />
      {d && (<><Notice>{d.notice}</Notice>
        {d.paths.length === 0 ? <div className="state">No time-ordered transaction path found from {d.start?.ref || "start entity"}.</div> :
          d.paths.slice(0, 20).map((p, i) => (<div key={i} className="finding"><b>{p.hops} hop(s)</b> → {p.end?.ref} {p.end?.name} · {p.total_moved.toLocaleString()} moved
            <div className="small muted">{p.steps.map((s) => `${s.from} → ${s.to} ${s.amount.toLocaleString()} (${s.txn}, ${time(s.at)})`).join("  ›  ")}</div></div>))}
        {d.pass_through.length > 0 && <><h4>Pass-through accounts (received, then forwarded ≥ 80% within 48 h)</h4>
          {d.pass_through.map((p, i) => {
            const eRef = typeof p.entity === "object" ? p.entity?.ref : p.entity;
            const eName = typeof p.entity === "object" ? p.entity?.name : "";
            return (
              <div key={i} className="kv small">
                <span>{eRef} {eName}</span>
                <span>received {p.received?.amount ?? 0} ({p.received?.txn || ""}), forwarded {p.forwarded_within_48h}</span>
              </div>
            );
          })}</>}</>)}
    </Card>);
}

function Meetings({ c }) {
  const st = useLoad(() => c.get("/insights/meetings"), [c]);
  return (
    <Card title="Possible meetings">
      <Async state={st} empty={Object.assign((d) => !d.meetings.length, { message: "No repeated co-presence or contact-then-meeting pattern found." })}>{(d) => (<>
        <Notice>{d.notice}</Notice>
        <Table rows={d.meetings} cols={[{ label: "People", render: (r) => r.people.map((p) => `${p.ref} ${p.name}`).join(" & ") }, { label: "Pattern", render: (r) => <Badge kind="correlated">{r.pattern.replace(/_/g, " ")}</Badge> },
          { label: "Occasions", key: "occasions" }, { label: "Place", key: "first_place" }, { label: "Linked contacts", render: (r) => r.linked_communications.join(", ") || "—" }]} /></>)}</Async>
    </Card>);
}

const SUBS = [["Movement", Jumps], ["Alibi", Alibi], ["Network", Network], ["Anomalies", Anomalies], ["Money trail", MoneyTrail], ["Meetings", Meetings]];
export default function Analysis({ c }) {
  const [sub, setSub] = useState("Movement");
  const P = SUBS.find(([n]) => n === sub)[1];
  return (<>
    <EntityList c={c} />
    <div className="row" style={{ marginBottom: 12 }}>{SUBS.map(([n]) => <button key={n} className={sub === n ? "primary" : ""} onClick={() => setSub(n)}>{n}</button>)}</div>
    <P key={sub} c={c} /></>);
}
