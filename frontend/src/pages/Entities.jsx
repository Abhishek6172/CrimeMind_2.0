import React, { useState } from "react";
import { useLoad } from "../hooks.js";
import { Async, Badge, Card, Table } from "../components/ui.jsx";

const TYPES = ["", "PERSON", "LOCATION", "VEHICLE", "DEVICE", "ORGANIZATION", "ACCOUNT"];

export default function Entities({ c }) {
  const [type, setType] = useState(""), [q, setQ] = useState(""), [applied, setApplied] = useState({ type: "", q: "" });
  const st = useLoad(() => c.get("/entities", { type: applied.type, q: applied.q }), [c, applied]);
  return (
    <Card title="Entities" aside={
      <form className="row" onSubmit={(e) => { e.preventDefault(); setApplied({ type, q }); }}>
        <select value={type} onChange={(e) => setType(e.target.value)} aria-label="Entity type">{TYPES.map((t) => <option key={t} value={t}>{t || "All types"}</option>)}</select>
        <input placeholder="Search name or ref" value={q} onChange={(e) => setQ(e.target.value)} />
        <button>Search</button>
      </form>}>
      <Async state={st} empty={Object.assign((d) => !d.entities.length, { message: "No entities match." })}>
        {(d) => <Table rows={d.entities} cols={[
          { label: "Ref", key: "ref" }, { label: "Type", render: (r) => <Badge kind={r.entity_type} /> }, { label: "Name", key: "display_name" },
          { label: "Attributes", render: (r) => <span className="small muted">{Object.entries(r.attributes || {}).filter(([k]) => k !== "synthetic").map(([k, v]) => `${k}: ${v}`).join(" · ")}</span> },
        ]} />}
      </Async>
    </Card>);
}
