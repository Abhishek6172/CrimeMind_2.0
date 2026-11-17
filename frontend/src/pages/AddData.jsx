import React, { useState } from "react";
import { Card, Notice } from "../components/ui.jsx";
import { EntityList, EvidenceList, Field, toIso, useSubmit } from "../components/Forms.jsx";

const EV_TYPES = ["DNA", "FINGERPRINT", "TRANSACTION_RECORD", "CDR", "DEVICE_DIAGNOSTIC", "ACCESS_LOG", "GPS", "CCTV", "WITNESS_STATEMENT", "DOCUMENT"];
const KINDS = {
  evidence: { path: "/evidence", title: "Evidence", fields: [
    { name: "evidence_type", label: "Type", kind: "select", options: EV_TYPES, required: true }, { name: "source", label: "Source", required: true, placeholder: "e.g. CAM-09" },
    { name: "description", label: "Description", kind: "textarea", required: true, hint: "(stored as untrusted source text)" },
    { name: "evidence_timestamp", label: "When it was recorded (IST)", kind: "datetime" },
    { name: "origin_root", label: "Origin (for source independence)", placeholder: "e.g. CCTV:CAM-09", hint: "same origin = counted once" },
    { name: "entity_refs", label: "Entities it concerns", placeholder: "P-004, L-GP2", hint: "comma-separated refs" }] },
  entity: { path: "/entities", title: "Entity", fields: [
    { name: "entity_type", label: "Type", kind: "select", options: ["PERSON", "VEHICLE", "LOCATION", "ACCOUNT", "DEVICE", "ORGANIZATION"], required: true },
    { name: "display_name", label: "Name", required: true }, { name: "lat", label: "Latitude (locations)", kind: "number" }, { name: "lon", label: "Longitude (locations)", kind: "number" },
    { name: "loc_kind", label: "Location kind", kind: "select", options: ["PUBLIC", "RESIDENCE", "WORKPLACE"] }] },
  observation: { path: "/observations", title: "Location sighting", fields: [
    { name: "subject", label: "Person or vehicle", kind: "entity", required: true }, { name: "location", label: "Location", kind: "entity", required: true },
    { name: "observed_from", label: "From (IST)", kind: "datetime", required: true }, { name: "observed_to", label: "To (IST)", kind: "datetime", required: true },
    { name: "source_kind", label: "Source kind", kind: "select", options: ["GPS", "CCTV", "ACCESS_LOG", "WITNESS", "OTHER"], required: true },
    { name: "source", label: "Source", required: true, placeholder: "e.g. GPS-17" }, { name: "evidence_ref", label: "Evidence", kind: "evidence" }] },
  communication: { path: "/communications", title: "Communication", fields: [
    { name: "sender", label: "Sender", kind: "entity", required: true }, { name: "receiver", label: "Receiver", kind: "entity", required: true },
    { name: "comm_type", label: "Type", kind: "select", options: ["CALL", "SMS", "EMAIL", "CHAT"], required: true },
    { name: "occurred_at", label: "When (IST)", kind: "datetime", required: true }, { name: "duration_sec", label: "Duration (seconds)", kind: "number" }, { name: "evidence_ref", label: "Evidence", kind: "evidence" }] },
  transaction: { path: "/transactions", title: "Transaction", fields: [
    { name: "from_entity", label: "From", kind: "entity", required: true }, { name: "to_entity", label: "To", kind: "entity", required: true },
    { name: "txn_type", label: "Type", kind: "select", options: ["TRANSFER", "PAYMENT", "WITHDRAWAL", "DEPOSIT", "PURCHASE"], required: true },
    { name: "amount", label: "Amount", kind: "number", required: true }, { name: "currency", label: "Currency", placeholder: "INR" },
    { name: "occurred_at", label: "When (IST)", kind: "datetime", required: true }, { name: "location", label: "Location", kind: "entity" }, { name: "evidence_ref", label: "Evidence", kind: "evidence" }] },
  relationship: { path: "/relationships", title: "Relationship", fields: [
    { name: "entity_a", label: "Entity A", kind: "entity", required: true }, { name: "entity_b", label: "Entity B", kind: "entity", required: true },
    { name: "rel_type", label: "Type", kind: "select", options: ["FAMILY", "FRIEND", "COLLEAGUE", "EMPLOYER", "OWNS", "USES", "ASSOCIATE", "ACCOUNT_OF"], required: true },
    { name: "strength", label: "Strength 0–1", kind: "number" }, { name: "evidence_ref", label: "Evidence", kind: "evidence" }] },
};

function buildBody(kind, vals) {
  const b = {};
  for (const f of KINDS[kind].fields) {
    let v = vals[f.name];
    if (v === "" || v == null) continue;
    if (f.kind === "datetime") v = toIso(v);
    else if (f.kind === "number") v = Number(v);
    b[f.name] = v;
  }
  if (kind === "evidence" && b.entity_refs) b.entity_refs = b.entity_refs.split(",").map((x) => x.trim()).filter(Boolean);
  if (kind === "entity") {
    const attributes = {};
    ["lat", "lon"].forEach((k) => { if (b[k] !== undefined) { attributes[k] = b[k]; delete b[k]; } });
    if (b.loc_kind) { attributes.kind = b.loc_kind; delete b.loc_kind; }
    b.attributes = attributes;
  }
  return b;
}

function RecordForm({ c, kind, onAdded }) {
  const [vals, setVals] = useState({});
  const [st, run] = useSubmit();
  const fields = st.err?.fields || {};
  const submit = async (e) => {
    e.preventDefault();
    const r = await run(() => c.post(KINDS[kind].path, buildBody(kind, vals)));
    if (r) { setVals({}); onAdded?.(); }
  };
  return (
    <form onSubmit={submit} className="stack">
      {KINDS[kind].fields.map((f) => <Field key={f.name} spec={f} value={vals[f.name]} onChange={(v) => setVals({ ...vals, [f.name]: v })} error={fields[f.name]} />)}
      <button className="primary" disabled={st.busy}>{st.busy ? "Saving…" : `Add ${KINDS[kind].title.toLowerCase()}`}</button>
      {st.err && <div className="state error" role="alert">{st.err.message}</div>}
      {st.ok && <div className="state" role="status">Recorded as <b>{st.ok.ref}</b>. {st.ok.message}</div>}
    </form>);
}

const EXAMPLE = `{
  "dry_run": true,
  "entities": [{"entity_type": "PERSON", "display_name": "New Person", "ref": "P-301"}],
  "communications": [{"sender": "P-301", "receiver": "P-004", "comm_type": "CALL", "occurred_at": "2026-08-14T15:20:00+05:30"}]
}`;

function Importer({ c }) {
  const [text, setText] = useState(EXAMPLE), [parseErr, setParseErr] = useState(null), [res, setRes] = useState(null), [st, run] = useSubmit();
  const go = async (dry) => {
    setParseErr(null);
    let body;
    try { body = JSON.parse(text); } catch (e) { setParseErr("This is not valid JSON: " + e.message); return; }
    body.dry_run = dry;
    const r = await run(() => c.post("/import", body));
    if (r) setRes(r);
  };
  const r = res;
  return (
    <div className="stack">
      <p className="small muted">Paste JSON with any of: entities, evidence, relationships, communications, transactions, observations. Everything is applied together or not at all. Entities and evidence may bring their own refs so later rows can refer to them.</p>
      <textarea className="json" rows={12} value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} />
      <div className="row"><button onClick={() => go(true)} disabled={st.busy}>Dry run</button><button className="primary" onClick={() => go(false)} disabled={st.busy}>Import for real</button></div>
      {parseErr && <div className="state error" role="alert">{parseErr}</div>}
      {st.err && <div className="state error" role="alert">{st.err.message}{st.err.fields ? " " + JSON.stringify(st.err.fields) : ""}</div>}
      {r && (<div className={`state ${r.errors.length ? "error" : ""}`} role="status"><b>{r.message}</b>
        <div className="small">{JSON.stringify(r.created || r.would_create)}</div>
        {r.errors.map((e, i) => <div key={i} className="small">• {e.section}[{e.index}]: {e.message} {e.fields ? JSON.stringify(e.fields) : ""}</div>)}</div>)}
    </div>);
}

export default function AddData({ c }) {
  const [kind, setKind] = useState("evidence"), [tab, setTab] = useState("form");
  return (
    <>
      <EntityList c={c} /><EvidenceList c={c} />
      <Notice>New records are stored as SUPPORTED and used by all analyses the next time they are viewed. Evidence is never edited afterwards; its validity changes only through the evidence-change process.</Notice>
      <div className="row" style={{ marginBottom: 12 }}>
        <button className={tab === "form" ? "primary" : ""} onClick={() => setTab("form")}>Add one record</button>
        <button className={tab === "import" ? "primary" : ""} onClick={() => setTab("import")}>Bulk import (JSON)</button>
      </div>
      {tab === "form" ? (
        <Card title="Add a record" aside={<select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Record type">{Object.entries(KINDS).map(([k, v]) => <option key={k} value={k}>{v.title}</option>)}</select>}>
          <RecordForm key={kind} c={c} kind={kind} />
        </Card>) : <Card title="Bulk import"><Importer c={c} /></Card>}
    </>);
}
