"""AI analysis, investigator review, reports and audit queries."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .. import audit, config
from ..ai.providers import get_provider
from ..ai.service import analyze
from ..deps import SUPERVISOR_ROLES, WRITE_ROLES, case_dep, get_ctx, require_roles, Ctx
from ..errors import ApiError
from ..reports import build_report, render_html
from ..sql_engine import jsonable

router = APIRouter(prefix="/api", tags=["oversight"])


@router.get("/ai/status")
def ai_status(ctx: Ctx = Depends(get_ctx)):
    p = get_provider()
    return {"provider": p.name, "is_llm": p.is_llm,
            "message": "A language model is configured." if p.is_llm else
            "No language model key is configured: the deterministic offline template provider is used and is labelled as such."}


class AiRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


@router.post("/cases/{case_ref}/ai/analyze")
def ai_analyze(body: AiRequest, dep=Depends(case_dep)):
    ctx, case = dep
    require_roles(ctx, WRITE_ROLES, "ai.analyze")
    from .analysis import fresh_run
    fresh_run(ctx.conn, case, ctx.user)           # AI context uses current belief only
    return analyze(ctx.conn, ctx.user, case, body.question, ctx.request_id)


@router.get("/cases/{case_ref}/ai/analyses")
def ai_history(dep=Depends(case_dep)):
    ctx, case = dep
    rows = ctx.conn.execute("SELECT analysis_id::text AS analysis_id, requested_by, question, provider, status, created_at "
                            "FROM ai_analyses WHERE case_id=%s ORDER BY created_at DESC LIMIT 50", (case["case_id"],)).fetchall()
    return jsonable({"analyses": rows})


class ReviewIn(BaseModel):
    target_type: str
    target_ref: str = Field(min_length=1, max_length=200)
    decision: str
    comment: Optional[str] = Field(None, max_length=4000)


@router.post("/cases/{case_ref}/reviews", status_code=201)
def create_review(body: ReviewIn, dep=Depends(case_dep)):
    ctx, case = dep
    require_roles(ctx, WRITE_ROLES, "review.create")
    if body.target_type not in ("FINDING", "CORRELATION", "AI_ANALYSIS", "HYPOTHESIS", "REPORT"):
        raise ApiError(422, "VALIDATION_ERROR", "Unknown target type.", {"target_type": "invalid"})
    if body.decision not in ("ACCEPTED", "REJECTED", "CORRECTED", "COMMENT"):
        raise ApiError(422, "VALIDATION_ERROR", "Unknown decision.", {"decision": "invalid"})
    cid, c = case["case_id"], ctx.conn.execute
    exists = {
        "FINDING": lambda: c("SELECT 1 FROM findings WHERE case_id=%s AND finding_key=%s", (cid, body.target_ref)).fetchone(),
        "HYPOTHESIS": lambda: c("SELECT 1 FROM hypotheses WHERE case_id=%s AND ref=%s", (cid, body.target_ref)).fetchone(),
        "CORRELATION": lambda: c("SELECT 1 FROM correlations WHERE case_id=%s AND ref=%s", (cid, body.target_ref)).fetchone(),
        "AI_ANALYSIS": lambda: c("SELECT 1 FROM ai_analyses WHERE case_id=%s AND analysis_id::text=%s", (cid, body.target_ref)).fetchone(),
        "REPORT": lambda: c("SELECT 1 FROM reports WHERE case_id=%s AND report_id::text=%s", (cid, body.target_ref)).fetchone(),
    }[body.target_type]()
    if not exists:
        raise ApiError(404, "TARGET_NOT_FOUND", "The review target does not exist in this case.")
    r = c("""INSERT INTO reviews(case_id, target_type, target_ref, decision, comment, reviewer) VALUES (%s,%s,%s,%s,%s,%s)
             RETURNING review_id, created_at""", (cid, body.target_type, body.target_ref, body.decision, body.comment, ctx.user)).fetchone()
    audit.log_activity(ctx.user, cid, "REVIEW_RECORDED", ctx.request_id, body.target_type, body.target_ref, details={"decision": body.decision})
    return jsonable({"review_id": r["review_id"], "created_at": r["created_at"],
                     "message": "Review recorded. Reviews never alter the underlying evidence."})


@router.get("/cases/{case_ref}/reviews")
def list_reviews(dep=Depends(case_dep)):
    ctx, case = dep
    rows = ctx.conn.execute("SELECT review_id, target_type, target_ref, decision, comment, reviewer, created_at FROM reviews WHERE case_id=%s ORDER BY created_at DESC",
                            (case["case_id"],)).fetchall()
    return jsonable({"reviews": rows})


@router.post("/cases/{case_ref}/reports", status_code=201)
def generate_report(dep=Depends(case_dep)):
    ctx, case = dep
    require_roles(ctx, WRITE_ROLES, "report.generate")
    rep = build_report(ctx.conn, case, ctx.user)
    audit.log_activity(ctx.user, case["case_id"], "REPORT_GENERATED", ctx.request_id, "report", rep["report_id"],
                       version_meta={"content_sha256": rep["content_sha256"]})
    return jsonable(rep)


@router.get("/cases/{case_ref}/reports")
def list_reports(dep=Depends(case_dep)):
    ctx, case = dep
    rows = ctx.conn.execute("SELECT report_id::text AS report_id, generated_by, generated_at, content_sha256 FROM reports WHERE case_id=%s ORDER BY generated_at DESC",
                            (case["case_id"],)).fetchall()
    return jsonable({"reports": rows})


def _load(ctx, case, report_id):
    r = ctx.conn.execute("SELECT report_id::text AS report_id, generated_at, content, content_sha256 FROM reports WHERE case_id=%s AND report_id::text=%s",
                         (case["case_id"], report_id)).fetchone()
    if not r:
        raise ApiError(404, "REPORT_NOT_FOUND", "No such report in this case.")
    return r


@router.get("/cases/{case_ref}/reports/{report_id}")
def get_report(report_id: str, dep=Depends(case_dep)):
    ctx, case = dep
    audit.log_activity(ctx.user, case["case_id"], "REPORT_VIEWED", ctx.request_id, "report", report_id)
    return jsonable(_load(ctx, case, report_id))


@router.get("/cases/{case_ref}/reports/{report_id}/html", response_class=HTMLResponse)
def get_report_html(report_id: str, dep=Depends(case_dep)):
    ctx, case = dep
    return HTMLResponse(render_html(jsonable(_load(ctx, case, report_id))))


@router.get("/cases/{case_ref}/audit")
def audit_view(limit: int = Query(100, ge=1, le=500), dep=Depends(case_dep)):
    """Investigators see their own entries; supervisors and administrators see the whole case."""
    ctx, case = dep
    own = None if ctx.role in SUPERVISOR_ROLES else ctx.user
    cid = case["case_id"]
    activity = ctx.conn.execute(
        """SELECT audit_id, occurred_at, user_name, action_type, object_type, object_id, status, details FROM activity_log
           WHERE case_id=%s AND (%s::text IS NULL OR user_name=%s) ORDER BY audit_id DESC LIMIT %s""", (cid, own, own, limit)).fetchall()
    queries = ctx.conn.execute(
        """SELECT query_exec_id::text AS query_exec_id, executed_at, user_name, question_id, module_id, module_version, status, result_count, params
           FROM query_audit WHERE case_id=%s AND (%s::text IS NULL OR user_name=%s) ORDER BY executed_at DESC LIMIT %s""", (cid, own, own, limit)).fetchall()
    changes = ctx.conn.execute(
        """SELECT audit_id, occurred_at, actor, action_type, object_type, object_id FROM audit_log WHERE case_id=%s
           AND object_type IN ('evidence_validity_events','findings','hypotheses','reviews') AND (%s::text IS NULL OR actor=%s)
           ORDER BY audit_id DESC LIMIT %s""", (cid, own, own, limit)).fetchall()
    return jsonable({"activity": activity, "queries": queries, "record_changes": changes,
                     "scope": "own entries" if own else "whole case"})
