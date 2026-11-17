import React, { useState } from "react";
import { api } from "../api.js";
import { useLoad } from "../hooks.js";
import { Async, Badge, Card, Notice, Table, time } from "../components/ui.jsx";
import { useSubmit } from "../components/Forms.jsx";

export default function Access({ c, user }) {
  const isSup = ["SUPERVISOR", "ADMINISTRATOR"].includes(user.role);
  const acc = useLoad(() => (isSup ? c.get("/access") : Promise.resolve({ access: [] })), [c, isSup]);
  const users = useLoad(() => (isSup ? api("/users") : Promise.resolve({ users: [] })), [isSup]);
  const [pick, setPick] = useState(""), [st, run] = useSubmit();
  if (!isSup) return <Card title="Case access"><p className="muted">Only a supervisor or administrator can manage who can open this case.</p></Card>;
  const grant = async (e) => { e.preventDefault(); if (await run(() => c.post("/access", { username: pick }))) { setPick(""); acc.reload(); } };
  const revoke = async (u) => { if (await run(() => api(`/cases/${c.ref}/access/${u}`, { method: "DELETE" }))) acc.reload(); };
  const have = new Set((acc.data?.access || []).map((a) => a.username));
  return (
    <Card title="Who can open this case">
      <Notice>Access is enforced by the server. Revoking takes effect on the user's next request.</Notice>
      <Async state={acc}>{(d) => <Table rows={d.access} cols={[{ label: "User", key: "username" }, { label: "Role", render: (r) => <Badge kind="inferred">{r.role}</Badge> }, { label: "Since", render: (r) => time(r.granted_at) },
        { label: "", render: (r) => r.username === user.username ? <span className="muted small">you</span> : <button onClick={() => revoke(r.username)}>Revoke</button> }]} />}</Async>
      <form className="row" onSubmit={grant} style={{ marginTop: 12 }}>
        <select value={pick} onChange={(e) => setPick(e.target.value)} aria-label="User to add"><option value="">Add a user…</option>
          {(users.data?.users || []).filter((u) => !have.has(u.username)).map((u) => <option key={u.username} value={u.username}>{u.username} ({u.role})</option>)}</select>
        <button className="primary" disabled={!pick || st.busy}>Grant access</button></form>
      {st.err && <div className="state error" role="alert">{st.err.message}</div>}
    </Card>);
}
