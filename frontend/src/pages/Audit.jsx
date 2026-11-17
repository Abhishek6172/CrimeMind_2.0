import React from "react";
import { useLoad } from "../hooks.js";
import { Async, Card, Table, time } from "../components/ui.jsx";

export default function Audit({ c, user }) {
  const st = useLoad(() => c.get("/audit"), [c]);
  const rv = useLoad(() => c.get("/reviews"), [c]);
  return (
    <>
      <Async state={st}>{(d) => (<>
        <Card title="Activity"><Table rows={d.activity} cols={[{ label: "When", render: (r) => time(r.occurred_at) }, { label: "User", key: "user_name" }, { label: "Action", key: "action_type" }, { label: "Object", render: (r) => [r.object_type, r.object_id].filter(Boolean).join(" ") || "—" }, { label: "Status", key: "status" }]} /></Card>
        <Card title="Queries run"><Table rows={d.queries} cols={[{ label: "When", render: (r) => time(r.executed_at) }, { label: "User", key: "user_name" }, { label: "Question", key: "question_id" }, { label: "Module", render: (r) => `${r.module_id} v${r.module_version}` }, { label: "Status", key: "status" }, { label: "Rows", key: "result_count" }]} /></Card>
        <Card title="Record changes"><Table rows={d.record_changes} cols={[{ label: "When", render: (r) => time(r.occurred_at) }, { label: "Actor", key: "actor" }, { label: "Action", key: "action_type" }, { label: "Object", render: (r) => `${r.object_type} ${r.object_id}` }]} /></Card></>)}</Async>
      <Card title="Reviews"><Async state={rv} empty={Object.assign((d) => !d.reviews.length, { message: "No reviews recorded." })}>
        {(d) => <Table rows={d.reviews} cols={[{ label: "When", render: (r) => time(r.created_at) }, { label: "Reviewer", key: "reviewer" }, { label: "Target", render: (r) => `${r.target_type} ${r.target_ref}` }, { label: "Decision", key: "decision" }, { label: "Comment", key: "comment" }]} />}</Async></Card>
    </>);
}
