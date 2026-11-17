"""Relationship graph generation (SRS Section 10): built at request time from authorized, current-belief data.
Nothing here is case-specific; classification (FACT / CORRELATED / INFERRED) comes from the correlation engine."""
from collections import defaultdict
from datetime import datetime, timezone

from .sql_engine import jsonable


def build_graph(conn, case: dict, run_id: int, scope: str = "relevant", include_evidence: bool = False,
                classes: set | None = None, focus: str | None = None) -> dict:
    cid = case["case_id"]
    ents = {r["entity_id"]: r for r in conn.execute("SELECT * FROM entities WHERE case_id=%s", (cid,)).fetchall()}
    corrs = conn.execute(
        """SELECT c.*, coalesce((SELECT array_agg(e.ref ORDER BY e.ref) FROM correlation_evidence ce JOIN evidence e
                                  ON e.evidence_id=ce.evidence_id AND e.case_id=ce.case_id WHERE ce.correlation_id=c.correlation_id), '{}') AS evidence_refs,
                  r.rule_name
           FROM correlations c JOIN correlation_rules r ON r.rule_id=c.rule_id AND r.version=c.rule_version
           WHERE c.case_id=%s AND c.run_id=%s""", (cid, run_id)).fetchall()
    if classes:
        corrs = [c for c in corrs if c["result_type"] in classes]
    roles = {}
    for r in conn.execute("SELECT ee.entity_id, ee.role, ev.ref AS event_ref FROM event_entities ee JOIN events ev ON ev.event_id=ee.event_id AND ev.case_id=ee.case_id "
                          "WHERE ee.case_id=%s AND ev.event_type='INCIDENT'", (cid,)).fetchall():
        roles[r["entity_id"]] = r["role"]
    incident_locs = {r["location_entity_id"] for r in conn.execute(
        "SELECT location_entity_id FROM events WHERE case_id=%s AND event_type='INCIDENT'", (cid,)).fetchall() if r["location_entity_id"]}

    edges = []
    for c in corrs:
        target = c["entity_b"] if c["entity_b"] else c["location_id"]
        if not target or target == c["entity_a"]:
            continue
        edges.append({
            "id": c["ref"], "source": ents[c["entity_a"]]["ref"], "target": ents[target]["ref"],
            "classification": c["result_type"], "rule_id": c["rule_id"], "rule_version": c["rule_version"], "rule_name": c["rule_name"],
            "summary": c["summary"], "thresholds": c["thresholds"], "confidence": c["confidence"],
            "uncertainties": c["uncertainties"], "source_records": c["source_records"], "evidence_refs": c["evidence_refs"],
            "window_start": c["window_start"], "window_end": c["window_end"],
        })
    adj = defaultdict(set)
    nonfact_nodes = set()
    for e in edges:
        adj[e["source"]].add(e["target"])
        adj[e["target"]].add(e["source"])
        if e["classification"] != "FACT":
            nonfact_nodes |= {e["source"], e["target"]}
    keep = None
    if focus:
        keep = {focus}
        for _ in range(2):
            keep |= {n for k in list(keep) for n in adj[k]}
    elif scope == "relevant":
        keep = set(nonfact_nodes)
        keep |= {ents[i]["ref"] for i in roles}
        keep |= {ents[i]["ref"] for i in incident_locs}
        keep |= {n for k in list(keep) for n in adj[k]}      # one FACT hop of context
    by_ref = {e["ref"]: e for e in ents.values()}
    if keep is not None:
        edges = [e for e in edges if e["source"] in keep and e["target"] in keep]
    used = {e["source"] for e in edges} | {e["target"] for e in edges}
    if keep is not None:
        used |= {k for k in keep if k in by_ref and (k in {ents[i]["ref"] for i in roles} or k in {ents[i]["ref"] for i in incident_locs})}
    nodes = []
    for ref in sorted(used):
        en = by_ref[ref]
        a = en["attributes"] or {}
        nodes.append({"id": ref, "type": en["entity_type"], "label": en["display_name"],
                      "incident_role": roles.get(en["entity_id"]), "kind": a.get("kind"),
                      "lat": a.get("lat"), "lon": a.get("lon"), "attributes": {k: v for k, v in a.items() if k not in ("lat", "lon", "synthetic")}})
    if include_evidence:
        evs = conn.execute("SELECT e.ref, e.evidence_type, e.validity_status::text AS st, ee.entity_id FROM evidence e JOIN evidence_entities ee "
                           "ON ee.evidence_id=e.evidence_id AND ee.case_id=e.case_id WHERE e.case_id=%s", (cid,)).fetchall()
        seen = set()
        for r in evs:
            tgt = ents[r["entity_id"]]["ref"]
            if tgt not in used or r["st"] != "SUPPORTED":
                continue
            if r["ref"] not in seen:
                nodes.append({"id": r["ref"], "type": "EVIDENCE", "label": f"{r['ref']} · {r['evidence_type']}", "incident_role": None,
                              "kind": r["evidence_type"], "attributes": {}})
                seen.add(r["ref"])
            edges.append({"id": f"EV-{r['ref']}-{tgt}", "source": r["ref"], "target": tgt, "classification": "FACT", "rule_id": "EVIDENCE_LINK",
                          "rule_version": 1, "rule_name": "Explicit evidence link", "summary": f"Evidence {r['ref']} is linked to {tgt}",
                          "thresholds": {}, "confidence": None, "uncertainties": [], "source_records": [{"type": "evidence", "ref": r["ref"]}],
                          "evidence_refs": [r["ref"]], "window_start": None, "window_end": None})
    counts = defaultdict(int)
    for e in edges:
        counts[e["classification"]] += 1
    return jsonable({
        "case_reference": case["case_ref"], "generated_at": datetime.now(timezone.utc).isoformat(), "run_id": run_id,
        "scope": "focus" if focus else scope, "nodes": nodes, "edges": edges, "edge_counts": dict(counts),
        "legend": {"FACT": "directly recorded", "CORRELATED": "approved deterministic rule", "INFERRED": "weaker pattern; needs review"},
        "notice": "The graph visualizes records and rule outputs. Visual proximity or a connecting line is not evidence of intent, cooperation or guilt.",
        "empty": len(nodes) == 0})
