"""Investigation questions, correlation, common-link analysis and the relationship graph."""
import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from .. import audit
from ..correlation.common_link import common_links
from ..correlation.engine import CaseData, run_and_persist
from ..correlation.rules import RULES
from ..deps import WRITE_ROLES, case_dep, get_ctx, require_roles, Ctx
from ..errors import ApiError
from ..graph import build_graph
from ..sql_engine import execute_question, jsonable, list_questions, resolve_entity

router = APIRouter(prefix="/api", tags=["analysis"])


@router.get("/questions")
def questions(ctx: Ctx = Depends(get_ctx)):
    return {"questions": jsonable(list_questions(ctx.conn)),
            "notice": "Questions are case-independent; the registry, not the frontend, defines their logic."}


class RunQuery(BaseModel):
    question_id: str
    parameters: dict[str, Any] = {}


@router.post("/cases/{case_ref}/queries/run")
def run_query(body: RunQuery, dep=Depends(case_dep)):
    ctx, case = dep
    require_roles(ctx, WRITE_ROLES, "query.run")
    return execute_question(ctx.conn, ctx.user, case, body.question_id, body.parameters)


# ---- natural-language -> approved question (never executes by itself; SRS 8.8, 8.42) ----
KEYWORDS = [
    (r"communicat|call|message|contact", ["Q1", "Q2", "Q3"]), (r"gap|missing time", ["Q13"]),
    (r"before.*incident|prior to", ["Q14"]), (r"after.*incident", ["Q15"]), (r"around.*incident|near.*incident|active", ["Q16"]),
    (r"strongest|most associated|combined|overall", ["Q40"]), (r"vehicle|car|van", ["Q22", "Q23"]),
    (r"transaction|payment|money|transfer", ["Q26", "Q27"]), (r"evidence", ["Q31", "Q32"]),
    (r"path|indirect|connected through", ["Q19", "Q20"]), (r"relationship", ["Q17", "Q18"]),
    (r"location|where|visited", ["Q6", "Q7"]), (r"timeline", ["Q11"]), (r"present at|was at|near", ["Q5"])]


class Resolve(BaseModel):
    text: str


@router.post("/cases/{case_ref}/queries/resolve")
def resolve(body: Resolve, dep=Depends(case_dep)):
    ctx, case = dep
    text = body.text.lower()
    cands: list[str] = []
    for pat, qs in KEYWORDS:
        if re.search(pat, text):
            cands += [q for q in qs if q not in cands]
    qmap = {q["question_id"]: q for q in list_questions(ctx.conn)}
    refs = re.findall(r"\b[PVL]-[A-Z]?\d+\b", body.text, flags=re.I)
    found = []
    for r in refs:
        row = ctx.conn.execute("SELECT ref, display_name, entity_type FROM entities WHERE case_id=%s AND upper(ref)=upper(%s)", (case["case_id"], r)).fetchone()
        if row:
            found.append(row)
    audit.log_activity(ctx.user, case["case_id"], "QUESTION_RESOLVED", ctx.request_id, details={"candidates": cands[:5]})
    return jsonable({"candidates": [qmap[q] for q in cands[:5] if q in qmap], "entities_mentioned": found,
                     "needs_clarification": len(cands) != 1,
                     "message": ("Pick the question to run and confirm the parameters; nothing has been executed." if cands
                                 else "No approved question matches this request; rephrase or choose from the question list."),
                     "dynamic_sql": "not enabled"})


# ---- correlation ----
def fresh_run(conn, case: dict, user: str, force: bool = False) -> dict:
    """Latest correlation run, recomputed when evidence validity or evidence changed since (SRS 9.53)."""
    run = conn.execute("SELECT run_id, started_at, result_count FROM correlation_runs WHERE case_id=%s ORDER BY run_id DESC LIMIT 1", (case["case_id"],)).fetchone()
    stale = True
    if run and not force:
        newer = conn.execute(
            """SELECT (SELECT count(*) FROM evidence_validity_events WHERE case_id=%(c)s AND changed_at > %(t)s) +
                      (SELECT count(*) FROM evidence WHERE case_id=%(c)s AND created_at > %(t)s) +
                      (SELECT count(*) FROM case_data_log WHERE case_id=%(c)s AND changed_at > %(t)s) AS n""",
            {"c": case["case_id"], "t": run["started_at"]}).fetchone()["n"]
        stale = newer > 0
    if run and not stale:
        return {"run_id": run["run_id"], "recomputed": False}
    res = run_and_persist(conn, case, user)
    audit.log_activity(user, case["case_id"], "CORRELATION_RUN", None, "correlation_run", str(res["run_id"]),
                       details={"results": res["result_count"], "excluded_records": res["excluded_records"]})
    return {"run_id": res["run_id"], "recomputed": True, "excluded_records": res["excluded_records"]}


class CorrParams(BaseModel):
    force: bool = True


@router.post("/cases/{case_ref}/correlations")
def run_correlation(body: CorrParams = CorrParams(), dep=Depends(case_dep)):
    ctx, case = dep
    require_roles(ctx, WRITE_ROLES, "correlation.run")
    r = fresh_run(ctx.conn, case, ctx.user, force=body.force)
    return jsonable({**r, **list_correlations(entity=None, result_type=None, rule_id=None, limit=100, dep=dep)})


@router.get("/cases/{case_ref}/correlations")
def list_correlations(entity: Optional[str] = None, result_type: Optional[str] = None, rule_id: Optional[str] = None,
                      limit: int = Query(200, ge=1, le=1000), dep=Depends(case_dep)):
    ctx, case = dep
    r = fresh_run(ctx.conn, case, ctx.user)
    eid = resolve_entity(ctx.conn, case["case_id"], entity, None, "entity") if entity else None
    rows = ctx.conn.execute(
        """SELECT c.ref AS correlation_id, c.rule_id, c.rule_version, c.result_type, a.ref AS entity_a, b.ref AS entity_b, l.ref AS location,
                  c.thresholds, c.window_start, c.window_end, c.confidence, c.summary, c.uncertainties, c.source_records,
                  coalesce((SELECT array_agg(e.ref ORDER BY e.ref) FROM correlation_evidence ce JOIN evidence e ON e.evidence_id=ce.evidence_id
                            AND e.case_id=ce.case_id WHERE ce.correlation_id=c.correlation_id), '{}') AS supporting_evidence_ids
           FROM correlations c JOIN entities a ON a.case_id=c.case_id AND a.entity_id=c.entity_a
           LEFT JOIN entities b ON b.case_id=c.case_id AND b.entity_id=c.entity_b
           LEFT JOIN entities l ON l.case_id=c.case_id AND l.entity_id=c.location_id
           WHERE c.case_id=%s AND c.run_id=%s AND (%s::text IS NULL OR c.result_type=%s) AND (%s::text IS NULL OR c.rule_id=%s)
             AND (%s::bigint IS NULL OR c.entity_a=%s OR c.entity_b=%s)
           ORDER BY (c.result_type='FACT'), c.result_type DESC, c.ref LIMIT %s""",
        (case["case_id"], r["run_id"], result_type, result_type, rule_id, rule_id, eid, eid, eid, limit)).fetchall()
    run = ctx.conn.execute("SELECT run_id, started_at, rule_versions, result_count FROM correlation_runs WHERE run_id=%s", (r["run_id"],)).fetchone()
    return jsonable({"case_reference": case["case_ref"], "run": run, "results": rows, "returned": len(rows),
                     "notice": "A correlation is not a conclusion: it never establishes intent, guilt or responsibility.",
                     "rules": [{k: v for k, v in x.items()} for x in RULES]})


@router.get("/cases/{case_ref}/common-link")
def common_link(a: str, b: str, window_minutes: int = Query(30, ge=0, le=1440), dep=Depends(case_dep)):
    ctx, case = dep
    ia = resolve_entity(ctx.conn, case["case_id"], a, "PERSON", "a")
    ib = resolve_entity(ctx.conn, case["case_id"], b, "PERSON", "b")
    if ia == ib:
        raise ApiError(422, "VALIDATION_ERROR", "Choose two different persons.", {"b": "must differ from a"})
    res = common_links(CaseData(ctx.conn, case["case_id"]), ia, ib, window_minutes)
    audit.log_activity(ctx.user, case["case_id"], "COMMON_LINK", ctx.request_id, details={"a": a, "b": b})
    return jsonable(res)


# ---- graph ----
def _graph(case_ref_dep, scope, include_evidence, classification, focus):
    ctx, case = case_ref_dep
    r = fresh_run(ctx.conn, case, ctx.user)
    classes = {c.strip().upper() for c in classification.split(",")} if classification else None
    if classes and not classes <= {"FACT", "CORRELATED", "INFERRED"}:
        raise ApiError(422, "VALIDATION_ERROR", "Unknown classification.", {"classification": "FACT, CORRELATED, INFERRED"})
    if focus:
        resolve_entity(ctx.conn, case["case_id"], focus, None, "focus")
    g = build_graph(ctx.conn, case, r["run_id"], scope, include_evidence, classes, focus)
    audit.log_activity(ctx.user, case["case_id"], "GRAPH_GENERATED", ctx.request_id, details={"nodes": len(g["nodes"]), "edges": len(g["edges"])})
    return g


@router.get("/cases/{case_ref}/relationship-graph")
def relationship_graph(scope: str = Query("relevant", pattern="^(relevant|all)$"), include_evidence: bool = False,
                       classification: Optional[str] = None, focus: Optional[str] = None, dep=Depends(case_dep)):
    return _graph(dep, scope, include_evidence, classification, focus)


@router.get("/cases/{case_ref}/relationships")      # Appendix D item 3: both paths retained, same implementation
def relationships_alias(scope: str = Query("relevant", pattern="^(relevant|all)$"), include_evidence: bool = False,
                        classification: Optional[str] = None, focus: Optional[str] = None, dep=Depends(case_dep)):
    return _graph(dep, scope, include_evidence, classification, focus)
