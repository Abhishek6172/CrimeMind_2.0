import json

from .. import audit
from ..sql_engine import jsonable
from .context import build_context, context_hash, public_summary
from .providers import ProviderUnavailable, get_provider
from .validator import validate


def analyze(conn, user: str, case: dict, question: str, request_id: str, provider=None) -> dict:
    ctx = build_context(conn, case, question)
    chash = context_hash(ctx)
    provider = provider or get_provider()
    problems: list[str] = []
    output, status = None, "OK"
    try:
        output = provider.generate(ctx, question)
        problems = validate(output, ctx)
        if problems:
            status, output_for_ui = "INVALID", None
    except ProviderUnavailable:
        status, problems = "UNAVAILABLE", ["The AI service is unavailable."]
    except (ValueError, KeyError, TypeError) as exc:
        status, problems = "INVALID", [f"The AI response could not be parsed ({type(exc).__name__})."]
    stored = output if status == "OK" else None
    row = conn.execute(
        """INSERT INTO ai_analyses(case_id, requested_by, question, provider, status, context_sha256, output, problems)
           VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb) RETURNING analysis_id, created_at""",
        (case["case_id"], user, question[:2000], provider.name, status, chash, json.dumps(stored), json.dumps(problems))).fetchone()
    audit.log_activity(user, case["case_id"], "AI_ANALYSIS", request_id, "ai_analysis", str(row["analysis_id"]),
                       "SUCCESS" if status == "OK" else status, {"provider": provider.name, "problems": len(problems)},
                       {"context_sha256": chash, "prompt_rules": "v1"})
    msg = {"OK": "AI-assisted analysis. Findings are labelled by classification and require investigator review.",
           "UNAVAILABLE": "AI analysis is unavailable. SQL results, correlations, evidence and the graph remain available.",
           "INVALID": "The AI response failed validation and was withheld; it is never shown as trusted analysis."}[status]
    return jsonable({"analysis_id": row["analysis_id"], "status": status, "provider": provider.name,
                     "provider_is_llm": getattr(provider, "is_llm", False), "created_at": row["created_at"],
                     "context_summary": public_summary(ctx), "context_sha256": chash, "output": stored, "problems": problems,
                     "message": msg, "classification_legend": {
                         "RECORDED FACT": "directly recorded in source records", "CORRELATED": "result of an approved deterministic rule",
                         "AI-INFERRED": "model interpretation; requires review", "UNCERTAIN": "insufficient or conflicting support"}})
