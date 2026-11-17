import React, { useState } from "react";
import { useLoad } from "../hooks.js";
import { Async, Badge, Card, Notice, time } from "../components/ui.jsx";
import { EntityList, EvidenceList, Field, useSubmit } from "../components/Forms.jsx";

export default function Notes({ c, caseRef }) {
  const [filter, setFilter] = useState({ bookmarked: "", tag: "" });
  const list = useLoad(() => c.get("/notes", { bookmarked: filter.bookmarked, tag: filter.tag }), [c, filter]);
  const [v, setV] = useState({ target_type: "ENTITY", bookmarked: false }), [st, run] = useSubmit();
  const submit = async (e) => {
    e.preventDefault();
    const r = await run(() => c.post("/notes", { target_type: v.target_type, target_ref: v.target_type === "CASE" ? caseRef : v.target_ref, body: v.body,
      tags: (v.tags || "").split(",").map((x) => x.trim()).filter(Boolean), bookmarked: !!v.bookmarked }));
    if (r) { setV({ ...v, body: "", tags: "" }); list.reload(); }
  };
  return (
    <div className="split">
      <Card title="Case notes and bookmarks">
        <Notice>Notes are your working comments, not evidence. They cannot be edited; add a new note to correct one.</Notice>
        <div className="row" style={{ marginBottom: 8 }}>
          <label className="inline small"><input type="checkbox" checked={filter.bookmarked === "true"} onChange={(e) => setFilter({ ...filter, bookmarked: e.target.checked ? "true" : "" })} /> bookmarks only</label>
          <input placeholder="Filter by tag" value={filter.tag} onChange={(e) => setFilter({ ...filter, tag: e.target.value.toLowerCase() })} />
        </div>
        <Async state={list} empty={Object.assign((d) => !d.notes.length, { message: "No notes yet." })}>
          {(d) => d.notes.map((n) => (<div key={n.note_id} className="finding">
            <div className="row"><Badge kind="inferred">{n.target_type}</Badge><b>{n.target_ref}</b>{n.bookmarked && <Badge kind="correlated">bookmark</Badge>}{n.tags.map((t) => <Badge key={t} kind="open">{t}</Badge>)}</div>
            <div style={{ whiteSpace: "pre-wrap" }}>{n.body}</div><div className="small muted">{n.author} · {time(n.created_at)}</div></div>))}
        </Async>
      </Card>
      <Card title="Add a note">
        <EntityList c={c} /><EvidenceList c={c} />
        <form onSubmit={submit} className="stack">
          <Field spec={{ label: "About", kind: "select", options: ["CASE", "ENTITY", "EVIDENCE", "FINDING", "HYPOTHESIS"], required: true }} value={v.target_type} onChange={(x) => setV({ ...v, target_type: x || "CASE" })} />
          {v.target_type !== "CASE" && <Field spec={{ label: "Reference", kind: v.target_type === "EVIDENCE" ? "evidence" : v.target_type === "ENTITY" ? "entity" : "text", required: true,
            placeholder: v.target_type === "HYPOTHESIS" ? "H-001" : v.target_type === "FINDING" ? "finding key" : undefined }} value={v.target_ref} onChange={(x) => setV({ ...v, target_ref: x })} error={st.err?.fields?.target_ref} />}
          <Field spec={{ label: "Note", kind: "textarea", required: true }} value={v.body} onChange={(x) => setV({ ...v, body: x })} />
          <Field spec={{ label: "Tags", hint: "comma-separated" }} value={v.tags} onChange={(x) => setV({ ...v, tags: x })} />
          <label className="inline"><input type="checkbox" checked={!!v.bookmarked} onChange={(e) => setV({ ...v, bookmarked: e.target.checked })} /> bookmark this</label>
          <button className="primary" disabled={st.busy || !v.body}>Save note</button>
          {st.err && <div className="state error" role="alert">{st.err.message}</div>}
        </form>
      </Card>
    </div>);
}
