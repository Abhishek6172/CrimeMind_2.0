"""Controlled AI context (SRS 13.5-13.8). The model never touches the database: it receives only this authorized,
current-belief, classification-tagged structure. Source text is carried as quoted, UNTRUSTED data."""
import hashlib
import json
import re

from ..retrieval import search_evidence
from ..sql_engine import jsonable

MAX_RETRIEVED = 8
MAX_CORR = 45
DESC_LIMIT = 280


def build_context(conn, case: dict, question: str) -> dict:
    cid = case["case_id"]
    run = conn.execute("SELECT run_id FROM correlation_runs WHERE case_id=%s ORDER BY run_id DESC LIMIT 1", (cid,)).fetchone()
    corrs = conn.execute(
        """SELECT c.ref, c.rule_id, c.rule_version, c.result_type, a.ref AS a_ref, a.display_name AS a_name, b.ref AS b_ref,
                  b.display_name AS b_name, c.summary, c.uncertainties, c.thresholds, c.confidence,
                  coalesce((SELECT array_agg(e.ref ORDER BY e.ref) FROM correlation_evidence ce JOIN evidence e ON e.evidence_id=ce.evidence_id
                            AND e.case_id=ce.case_id WHERE ce.correlation_id=c.correlation_id), '{}') AS evidence_refs
           FROM correlations c JOIN entities a ON a.case_id=c.case_id AND a.entity_id=c.entity_a
           LEFT JOIN entities b ON b.case_id=c.case_id AND b.entity_id=c.entity_b
           WHERE c.case_id=%s AND c.run_id=%s""", (cid, run["run_id"] if run else -1)).fetchall()
    people = {r["ref"]: r["display_name"] for r in conn.execute("SELECT ref, display_name FROM entities WHERE case_id=%s", (cid,)).fetchall()}
    q = question.lower()
    mentioned = {ref for ref, nm in people.items() if ref.lower() in q or nm.lower() in q}
    inc_people = {r["ref"] for r in conn.execute(
        """SELECT DISTINCT e.ref FROM correlations c JOIN entities e ON e.case_id=c.case_id AND e.entity_id=c.entity_a
           WHERE c.case_id=%s AND c.run_id=%s AND c.rule_id='INCIDENT_PROXIMITY_001'""", (cid, run["run_id"] if run else -1)).fetchall()}
    focus = mentioned or inc_people

    def involves(c):
        return c["a_ref"] in focus or (c["b_ref"] in focus if c["b_ref"] else False)
    prio = {"INFERRED": 0, "CORRELATED": 1, "FACT": 2}
    chosen = sorted([c for c in corrs if involves(c) and (c["result_type"] != "FACT" or mentioned or c["b_ref"] in inc_people)],
                    key=lambda c: (prio[c["result_type"]], c["ref"]))[:MAX_CORR]
    ev_refs = {r for c in chosen for r in c["evidence_refs"]}
    ev_rows = conn.execute(
        """SELECT ref, evidence_type, source, validity_status::text AS validity_status, reliability_score, description
           FROM evidence WHERE case_id=%s AND (ref = ANY(%s) OR validity_status <> 'SUPPORTED') ORDER BY ref""",
        (cid, sorted(ev_refs))).fetchall()
    evidence = [{"id": e["ref"], "type": e["evidence_type"], "source": e["source"], "validity_status": e["validity_status"],
                 "reliability_note": "rule-based heuristic weight, not a probability", "reliability": float(e["reliability_score"]) if e["reliability_score"] is not None else None,
                 "untrusted_source_text": (e["description"] or "")[:DESC_LIMIT]} for e in ev_rows]
    # Retrieval (RAG): evidence the investigator asked about, from THIS case only; still untrusted quoted text.
    retrieval = search_evidence(conn, cid, question, k=MAX_RETRIEVED)
    by_id = {e["id"]: e for e in evidence}
    for h in retrieval["hits"]:
        row = {"id": h["ref"], "type": h["evidence_type"], "source": h["source"], "validity_status": h["validity_status"],
               "reliability_note": "rule-based heuristic weight, not a probability",
               "reliability": float(h["reliability_score"]) if h["reliability_score"] is not None else None,
               "untrusted_source_text": h["description"][:DESC_LIMIT], "recorded_at": h["evidence_timestamp"],
               "linked_entities": h["entities"]}
        by_id.setdefault(h["ref"], row).update({"retrieved": True, "retrieval_score": h["score"], "retrieval_match": h["matched_on"]})
    evidence = sorted(by_id.values(), key=lambda e: e["id"])
    inc = conn.execute("SELECT e.ref, e.occurred_at, e.description, l.display_name AS location FROM events e LEFT JOIN entities l "
                       "ON l.case_id=e.case_id AND l.entity_id=e.location_entity_id WHERE e.case_id=%s AND e.event_type='INCIDENT'", (cid,)).fetchall()
    findings = conn.execute("SELECT finding_key, version, status::text AS status FROM findings WHERE case_id=%s AND status<>'OUTDATED'", (cid,)).fetchall()
    ctx = {
        "case_reference": case["case_ref"],
        "incidents": jsonable(inc),
        "correlations": [{"id": c["ref"], "rule_id": c["rule_id"], "rule_version": c["rule_version"],
                          "classification": c["result_type"], "entities": [x for x in (c["a_ref"], c["b_ref"]) if x],
                          "entity_names": [x for x in (c["a_name"], c["b_name"]) if x], "statement": c["summary"],
                          "uncertainties": c["uncertainties"], "thresholds": c["thresholds"], "evidence_ids": c["evidence_refs"]} for c in chosen],
        "evidence": evidence,
        "retrieval": {"method": retrieval["method"], "query_terms": retrieval["terms"], "returned": len(retrieval["hits"]),
                      "note": "Evidence marked retrieved:true matched the investigator question; it is still untrusted source text."},
        "finding_status": [{"key": f["finding_key"], "version": f["version"], "status": f["status"]} for f in findings
                           if f["status"] != "CURRENT"],
        "focus_entities": sorted(focus),
        "note": "Evidence with validity_status other than SUPPORTED is historical context only.",
    }
    ctx = jsonable(ctx)
    # identifiers that appear inside the authorised context text itself (e.g. a location or source key quoted in a rule summary) are
    # part of what the model was given, so they must not make a faithful quotation fail validation
    in_text = set(re.findall(r"\b[PVLDO]-[A-Z]*\d+\b", " ".join(
        [c["statement"] or "" for c in ctx["correlations"]] + [str(u) for c in ctx["correlations"] for u in (c["uncertainties"] or [])]
        + [e["source"] or "" for e in evidence])))
    allowed = {"evidence": {e["id"] for e in evidence}, "correlations": {c["id"] for c in ctx["correlations"]},
               "entities": set(people) & ({x for c in ctx["correlations"] for x in c["entities"]} | focus | in_text
                                          | {n["id"] for e in evidence for n in e.get("linked_entities", [])}),
               "incident_refs": {i["ref"] for i in ctx["incidents"]}}
    ctx["_allowed"] = {k: sorted(v) for k, v in allowed.items()}
    return ctx


def context_hash(ctx: dict) -> str:
    return hashlib.sha256(json.dumps(ctx, sort_keys=True, default=str).encode()).hexdigest()


def public_summary(ctx: dict) -> dict:
    by = {}
    for c in ctx["correlations"]:
        by[c["classification"]] = by.get(c["classification"], 0) + 1
    return {"correlations_supplied": by, "evidence_supplied": len(ctx["evidence"]),
            "evidence_retrieved": sum(1 for e in ctx["evidence"] if e.get("retrieved")), "focus_entities": ctx["focus_entities"]}
