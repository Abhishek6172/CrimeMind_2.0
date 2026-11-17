import React, { useState } from "react";
import { useLoad } from "../hooks.js";

// Entity ref input with suggestions from the case's own entities (the server still validates every ref).
export function EntityList({ c }) {
  const st = useLoad(() => c.get("/entities", { limit: 1000 }), [c]);
  return <datalist id="entity-refs">{(st.data?.entities || []).map((e) => <option key={e.ref} value={e.ref}>{e.display_name} · {e.entity_type}</option>)}</datalist>;
}
export function EvidenceList({ c }) {
  const st = useLoad(() => c.get("/evidence"), [c]);
  return <datalist id="evidence-refs">{(st.data?.evidence || []).map((e) => <option key={e.ref} value={e.ref}>{e.evidence_type} · {e.source}</option>)}</datalist>;
}

// local date-time (entered in IST, the case timezone) -> ISO with offset
export const toIso = (v) => (!v ? null : v.length === 16 ? `${v}:00+05:30` : v);

export function Field({ spec, value, onChange, error }) {
  const common = { value: value ?? "", onChange: (e) => onChange(e.target.value), "aria-invalid": !!error };
  let input;
  if (spec.kind === "select") input = <select {...common}><option value="">—</option>{spec.options.map((o) => <option key={o}>{o}</option>)}</select>;
  else if (spec.kind === "textarea") input = <textarea rows={3} {...common} />;
  else if (spec.kind === "entity") input = <input list="entity-refs" placeholder="e.g. P-004" {...common} />;
  else if (spec.kind === "evidence") input = <input list="evidence-refs" placeholder="optional, e.g. E-0308" {...common} />;
  else if (spec.kind === "datetime") input = <input type="datetime-local" {...common} />;
  else if (spec.kind === "number") input = <input type="number" step="any" {...common} />;
  else input = <input {...common} placeholder={spec.placeholder} />;
  return <label>{spec.label}{spec.required && " *"}{spec.hint && <span className="small muted"> {spec.hint}</span>}{input}{error && <span className="fielderr">{error}</span>}</label>;
}

export function useSubmit() {
  const [state, set] = useState({ busy: false, ok: null, err: null });
  const run = async (fn) => {
    set({ busy: true, ok: null, err: null });
    try { const r = await fn(); set({ busy: false, ok: r, err: null }); return r; }
    catch (e) { set({ busy: false, ok: null, err: e }); return null; }
  };
  return [state, run];
}
