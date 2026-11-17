"""Cases, entities, evidence, EVLM transitions, findings and hypotheses."""
import json
from datetime import datetime
from typing import Optional

import psycopg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from .. import audit
from ..correlation.engine import recompute_pending
from ..deps import SUPERVISOR_ROLES, WRITE_ROLES, case_dep, get_ctx, require_roles, Ctx
from ..errors import ApiError
from ..retrieval import search_evidence
from ..sql_engine import jsonable

router = APIRouter(prefix="/api", tags=["cases"])


@router.get("/cases")
def list_cases(ctx: Ctx = Depends(get_ctx)):
    rows = ctx.conn.execute(
        """SELECT c.case_ref, c.title, c.status, c.created_at FROM cases c
           JOIN user_case_access a ON a.case_id=c.case_id WHERE a.user_id=%s ORDER BY c.case_ref""", (ctx.user_id,)).fetchall()
    audit.log_activity(ctx.user, None, "CASES_LISTED", ctx.request_id, details={"count": len(rows)})
    return {"cases": jsonable(rows)}


@router.get("/cases/{case_ref}")
def case_detail(dep=Depends(case_dep)):
    ctx, case = dep
    cid, q = case["case_id"], ctx.conn.execute
    ev = {r["validity_status"]: r["n"] for r in q("SELECT validity_status::text, count(*) n FROM evidence WHERE case_id=%s GROUP BY 1", (cid,))}
    fs = {r["status"]: r["n"] for r in q("SELECT status::text, count(*) n FROM findings WHERE case_id=%s AND status<>'OUTDATED' GROUP BY 1", (cid,))}
    counts = q("""SELECT (SELECT count(*) FROM entities WHERE case_id=%(c)s AND entity_type='PERSON') persons,
                         (SELECT count(*) FROM entities WHERE case_id=%(c)s AND entity_type='VEHICLE') vehicles,
                         (SELECT count(*) FROM entities WHERE case_id=%(c)s AND entity_type='LOCATION') locations,
                         (SELECT count(*) FROM communications WHERE case_id=%(c)s) communications,
                         (SELECT count(*) FROM transactions WHERE case_id=%(c)s) transactions,
                         (SELECT count(*) FROM location_observations WHERE case_id=%(c)s) observations,
                         (SELECT count(*) FROM evidence WHERE case_id=%(c)s) evidence""", {"c": cid}).fetchone()
    incidents = q("""SELECT e.ref, e.occurred_at, e.description, l.ref AS location_ref, l.display_name AS location_name
                     FROM events e LEFT JOIN entities l ON l.case_id=e.case_id AND l.entity_id=e.location_entity_id
                     WHERE e.case_id=%s AND e.event_type='INCIDENT' ORDER BY e.occurred_at""", (cid,)).fetchall()
    state = q("""SELECT (SELECT count(*) FROM finding_impact_log WHERE case_id=%(c)s AND recomputed_at IS NULL) open_impacts,
                        (SELECT count(*) FROM hypotheses WHERE case_id=%(c)s AND needs_review) hypotheses_needing_review,
                        (SELECT count(*) FROM hypotheses WHERE case_id=%(c)s AND status='OPEN') open_hypotheses,
                        (SELECT count(*) FROM query_audit WHERE case_id=%(c)s AND status IN ('OK','EMPTY')) queries_run,
                        (SELECT count(*) FROM reviews WHERE case_id=%(c)s) reviews""", {"c": cid}).fetchone()
    audit.log_activity(ctx.user, cid, "CASE_OPENED", ctx.request_id, "case", case["case_ref"])
    return jsonable({"case": case, "counts": counts, "evidence_by_validity": ev, "findings_by_status": fs,
                     "incidents": incidents, "investigation_state": state,
                     "notice": "Synthetic data. CrimeMind is decision support: findings require investigator review."})


@router.get("/cases/{case_ref}/entities")
def entities(type: Optional[str] = None, q: Optional[str] = None, limit: int = Query(300, ge=1, le=1000), dep=Depends(case_dep)):
    ctx, case = dep
    rows = ctx.conn.execute(
        """SELECT entity_id, entity_type, ref, display_name, attributes FROM entities
           WHERE case_id=%s AND (%s::text IS NULL OR entity_type=%s) AND (%s::text IS NULL OR display_name ILIKE %s OR ref ILIKE %s)
           ORDER BY entity_type, ref LIMIT %s""",
        (case["case_id"], type, type, q, f"%{q}%" if q else None, f"%{q}%" if q else None, limit)).fetchall()
    return jsonable({"case_reference": case["case_ref"], "entities": rows})


@router.get("/cases/{case_ref}/evidence")
def evidence_list(status: Optional[str] = None, dep=Depends(case_dep)):
    ctx, case = dep
    if status and status not in ("SUPPORTED", "CHALLENGED", "INVALIDATED", "SUPERSEDED"):
        raise ApiError(422, "VALIDATION_ERROR", "Unknown validity status.", {"status": "must be a validity state"})
    rows = ctx.conn.execute(
        """SELECT e.ref, e.evidence_type, e.source, e.evidence_timestamp, e.description, e.reliability_score,
                  e.validity_status::text AS validity_status, e.provenance, r.ref AS replaced_by,
                  (SELECT count(*) FROM finding_evidence_links l JOIN findings f ON f.finding_id=l.finding_id
                    WHERE l.evidence_id=e.evidence_id AND f.status<>'OUTDATED') AS dependent_findings
           FROM evidence e LEFT JOIN evidence r ON r.case_id=e.case_id AND r.evidence_id=e.replaced_by_evidence_id
           WHERE e.case_id=%s AND (%s::text IS NULL OR e.validity_status=%s::validity_status)
           ORDER BY e.ref""", (case["case_id"], status, status)).fetchall()
    return jsonable({"case_reference": case["case_ref"], "evidence": rows,
                     "notice": "Reliability is a rule-based heuristic weight, distinct from validity status."})


@router.get("/cases/{case_ref}/evidence-search")
def evidence_search(q: str = Query(min_length=2, max_length=500), k: int = Query(8, ge=1, le=50), dep=Depends(case_dep)):
    """Ask for evidence in plain language ("CCTV near the lawn", "calls by Rohit Sethi", "E-0042"). Case-scoped and audited."""
    ctx, case = dep
    res = search_evidence(ctx.conn, case["case_id"], q, k)
    audit.log_activity(ctx.user, case["case_id"], "EVIDENCE_SEARCH", ctx.request_id, details={"results": len(res["hits"]), "query_chars": len(q)})
    return jsonable({"case_reference": case["case_ref"], "query": q, "method": res["method"], "terms": res["terms"],
                     "typo_corrections": res["typo_corrections"], "named_entities": res["named_entities"], "results": res["hits"],
                     "notice": "Ranked by keyword relevance, named people/places and exact references. A match is a lead to open, not a finding; "
                               "record text is source content, shown as data."})


@router.get("/cases/{case_ref}/evidence/{ref}")
def evidence_detail(ref: str, dep=Depends(case_dep)):
    ctx, case = dep
    cid = case["case_id"]
    ev = ctx.conn.execute("SELECT * FROM evidence WHERE case_id=%s AND ref=%s", (cid, ref)).fetchone()
    if not ev:
        raise ApiError(404, "EVIDENCE_NOT_FOUND", "No such evidence in this case.")
    hist = ctx.conn.execute(
        """SELECT v.event_id, v.previous_status::text previous_status, v.new_status::text new_status, v.trigger_code::text trigger_code,
                  v.reason_code::text reason_code, v.justification, v.changed_at, v.changed_by, t.ref AS triggering_evidence
           FROM evidence_validity_events v LEFT JOIN evidence t ON t.case_id=v.case_id AND t.evidence_id=v.triggering_evidence_id
           WHERE v.case_id=%s AND v.evidence_id=%s ORDER BY v.changed_at, v.event_id""", (cid, ev["evidence_id"])).fetchall()
    deps_ = ctx.conn.execute(
        """SELECT f.finding_key, f.version, f.status::text status, f.classification, f.statement FROM finding_evidence_links l
           JOIN findings f ON f.finding_id=l.finding_id AND f.case_id=l.case_id
           WHERE l.case_id=%s AND l.evidence_id=%s ORDER BY f.finding_key, f.version""", (cid, ev["evidence_id"])).fetchall()
    ents = ctx.conn.execute("""SELECT en.ref, en.display_name, en.entity_type FROM evidence_entities ee
           JOIN entities en ON en.case_id=ee.case_id AND en.entity_id=ee.entity_id WHERE ee.case_id=%s AND ee.evidence_id=%s ORDER BY en.ref""",
                            (cid, ev["evidence_id"])).fetchall()
    out = {k: ev[k] for k in ("ref", "evidence_type", "source", "evidence_timestamp", "description", "provenance",
                              "reliability_score", "processing_status")}
    out["validity_status"] = str(ev["validity_status"])
    return jsonable({"evidence": out, "validity_history": hist, "dependent_findings": deps_, "linked_entities": ents,
                     "untrusted_text_notice": "The description is source content, shown as data; it is never treated as an instruction."})


class ValidityChange(BaseModel):
    new_status: str
    trigger: str
    reason: str
    justification: Optional[str] = None
    triggering_evidence_ref: Optional[str] = None


@router.post("/cases/{case_ref}/evidence/{ref}/validity")
def change_validity(ref: str, body: ValidityChange, dep=Depends(case_dep)):
    """The only route by which evidence validity changes: deterministic EVLM rules, recorded, with impact propagation."""
    ctx, case = dep
    require_roles(ctx, WRITE_ROLES, "evidence.validity")
    if body.trigger == "MANUAL_OVERRIDE":
        require_roles(ctx, SUPERVISOR_ROLES, "evidence.validity.manual_override")
    cid = case["case_id"]
    ev = ctx.conn.execute("SELECT evidence_id FROM evidence WHERE case_id=%s AND ref=%s", (cid, ref)).fetchone()
    if not ev:
        raise ApiError(404, "EVIDENCE_NOT_FOUND", "No such evidence in this case.")
    trig = None
    if body.triggering_evidence_ref:
        t = ctx.conn.execute("SELECT evidence_id FROM evidence WHERE case_id=%s AND ref=%s", (cid, body.triggering_evidence_ref)).fetchone()
        if not t:
            raise ApiError(422, "VALIDATION_ERROR", "Triggering evidence not found in this case.", {"triggering_evidence_ref": "unknown"})
        trig = t["evidence_id"]
    try:
        with ctx.conn.transaction():
            event_id = ctx.conn.execute(
                "SELECT change_validity(%s,%s,%s::validity_status,%s::validity_trigger,%s::validity_reason,%s,%s) AS id",
                (cid, ev["evidence_id"], body.new_status, body.trigger, body.reason, body.justification, trig)).fetchone()["id"]
    except (psycopg.errors.RaiseException, psycopg.errors.InvalidTextRepresentation) as exc:
        audit.log_activity(ctx.user, cid, "EVIDENCE_VALIDITY_REJECTED", ctx.request_id, "evidence", ref, "FAILURE",
                           {"requested": body.new_status, "trigger": body.trigger, "reason": body.reason})
        raise ApiError(409, "TRANSITION_NOT_PERMITTED", str(getattr(exc, "diag", None) and exc.diag.message_primary or "Transition not permitted."))
    impacted = ctx.conn.execute(
        """SELECT f.finding_key, f.version, f.statement FROM finding_impact_log i JOIN findings f ON f.finding_id=i.affected_finding_id
           WHERE i.validity_event_id=%s ORDER BY f.finding_key""", (event_id,)).fetchall()
    flagged = ctx.conn.execute(
        """SELECT h.ref, h.title FROM hypotheses h WHERE h.case_id=%s AND h.needs_review ORDER BY h.ref""", (cid,)).fetchall()
    audit.log_activity(ctx.user, cid, "EVIDENCE_VALIDITY_CHANGED", ctx.request_id, "evidence", ref, details={
        "to": body.new_status, "trigger": body.trigger, "reason": body.reason, "impacted_findings": len(impacted)})
    return jsonable({"validity_event_id": event_id, "evidence": ref, "new_status": body.new_status,
                     "findings_marked_recompute_required": impacted, "hypotheses_needing_review": flagged,
                     "message": "Dependent findings were marked RECOMPUTE_REQUIRED; they have not been silently rewritten."})


@router.get("/cases/{case_ref}/findings")
def findings(include_outdated: bool = False, dep=Depends(case_dep)):
    ctx, case = dep
    rows = ctx.conn.execute(
        """SELECT f.finding_key, f.version, f.statement, f.classification, f.status::text status, f.generated_by, f.method, f.generated_at,
                  coalesce((SELECT array_agg(e.ref ORDER BY e.ref) FROM finding_evidence_links l JOIN evidence e
                            ON e.evidence_id=l.evidence_id AND e.case_id=l.case_id WHERE l.finding_id=f.finding_id), '{}') AS evidence_refs,
                  coalesce((SELECT array_agg(e.ref || ':' || e.validity_status::text ORDER BY e.ref) FROM finding_evidence_links l JOIN evidence e
                            ON e.evidence_id=l.evidence_id AND e.case_id=l.case_id WHERE l.finding_id=f.finding_id), '{}') AS evidence_states
           FROM findings f WHERE f.case_id=%s AND (%s OR f.status<>'OUTDATED')
           ORDER BY f.status DESC, f.finding_key, f.version""", (case["case_id"], include_outdated)).fetchall()
    return jsonable({"case_reference": case["case_ref"], "findings": rows})


@router.get("/cases/{case_ref}/impacts")
def impacts(dep=Depends(case_dep)):
    ctx, case = dep
    rows = ctx.conn.execute("SELECT finding_key, statement, evidence_id, evidence_new_status::text AS evidence_new_status, reason_code::text AS reason_code, logged_at "
                            "FROM v_open_impacts WHERE case_id=%s ORDER BY logged_at", (case["case_id"],)).fetchall()
    return jsonable({"open_impacts": rows})


@router.post("/cases/{case_ref}/findings/recompute")
def recompute(dep=Depends(case_dep)):
    ctx, case = dep
    require_roles(ctx, WRITE_ROLES, "findings.recompute")
    out = recompute_pending(ctx.conn, case, ctx.user)
    audit.log_activity(ctx.user, case["case_id"], "FINDINGS_RECOMPUTED", ctx.request_id, "case", case["case_ref"], details={"outcomes": out})
    return jsonable({"outcomes": out, "message": "Each outcome is a new finding version or a recorded retirement; previous versions remain available."})


@router.get("/cases/{case_ref}/hypotheses")
def hypotheses(dep=Depends(case_dep)):
    ctx, case = dep
    cid = case["case_id"]
    rows = ctx.conn.execute("SELECT hypothesis_id, ref, title, status, needs_review, created_by, updated_at FROM hypotheses WHERE case_id=%s ORDER BY ref", (cid,)).fetchall()
    out = []
    for h in rows:
        fs = ctx.conn.execute("""SELECT f.finding_key, f.version, f.status::text status FROM hypothesis_findings hf JOIN findings f
                                ON f.finding_id=hf.finding_id AND f.case_id=hf.case_id WHERE hf.hypothesis_id=%s""", (h["hypothesis_id"],)).fetchall()
        es = ctx.conn.execute("""SELECT e.ref, e.validity_status::text AS validity_status, he.stance FROM hypothesis_evidence he JOIN evidence e
                                ON e.evidence_id=he.evidence_id AND e.case_id=he.case_id WHERE he.hypothesis_id=%s ORDER BY e.ref""", (h["hypothesis_id"],)).fetchall()
        d = {k: v for k, v in h.items() if k != "hypothesis_id"}
        out.append({**d, "findings": fs, "evidence": es, "label": "HYPOTHESIS (not a recorded fact)"})
    return jsonable({"hypotheses": out})


@router.post("/cases/{case_ref}/hypotheses/{ref}/clear-review")
def clear_review(ref: str, dep=Depends(case_dep)):
    ctx, case = dep
    require_roles(ctx, WRITE_ROLES, "hypothesis.review")
    h = ctx.conn.execute("SELECT hypothesis_id FROM hypotheses WHERE case_id=%s AND ref=%s", (case["case_id"], ref)).fetchone()
    if not h:
        raise ApiError(404, "NOT_FOUND", "No such hypothesis in this case.")
    ctx.conn.execute("SELECT clear_hypothesis_review(%s,%s)", (case["case_id"], h["hypothesis_id"]))
    audit.log_activity(ctx.user, case["case_id"], "HYPOTHESIS_REVIEW_CLEARED", ctx.request_id, "hypothesis", ref)
    return {"ref": ref, "needs_review": False}


@router.get("/cases/{case_ref}/belief")
def current_belief(as_of: Optional[datetime] = None, dep=Depends(case_dep)):
    ctx, case = dep
    rows = ctx.conn.execute("SELECT ref, evidence_type, source, validity_status::text AS validity_status, reliability_score, counts_as_support, last_changed_at "
                            "FROM get_current_belief(%s,%s)", (case["case_id"], as_of)).fetchall()
    return jsonable({"as_of": as_of or "now", "evidence": rows})
