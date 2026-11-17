"""Deterministic SQL Investigation Engine (SRS Section 8).

Question -> module -> case-scoped bind-parameter execution -> structured result -> query audit.
The case_id always comes from the authorized case context, never from request parameters.
"""
import json
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from . import config
from .db import pool
from .errors import ApiError
from .registry import load_modules

ID_PARAMS = {"entity_id", "entity_id_1", "entity_id_2", "location_id", "vehicle_id", "event_id"}
TIME_PARAMS = {"start_time", "end_time"}
INT_RANGES = {"result_limit": (1, 1000), "min_count": (1, 1000), "window_minutes": (0, 1440),
              "gap_minutes": (1, 10080), "max_hops": (1, 4)}
ALL_PARAMS = ID_PARAMS | TIME_PARAMS | set(INT_RANGES) | {"minimum_strength", "include_historical"}


def jsonable(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    if isinstance(v, dict):
        return {k: jsonable(x) for k, x in v.items()}
    return v


def parse_time(name: str, value) -> datetime:
    try:
        dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{name} must be an ISO-8601 timestamp")
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _safe_ref(value, name: str):
    """Identifier strings are bounded and must not contain NUL (PostgreSQL text cannot, and the driver would raise an unhandled DataError)."""
    if isinstance(value, str) and ("\x00" in value or len(value) > 200):
        raise ValueError(f"{name} is not a valid identifier")
    return value


def resolve_entity(conn, case_id: int, value, expect: str | None, name: str) -> int:
    """Accepts a numeric id or a case-local ref (e.g. 'P-001'); the record must belong to THIS case."""
    if isinstance(value, bool):
        raise ValueError(f"{name} is not a valid identifier")
    _safe_ref(value, name)
    if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
        row = conn.execute("SELECT entity_id, entity_type FROM entities WHERE case_id=%s AND entity_id=%s",
                           (case_id, int(value))).fetchone()
    else:
        row = conn.execute("SELECT entity_id, entity_type FROM entities WHERE case_id=%s AND ref=%s",
                           (case_id, str(value))).fetchone()
    if not row:
        raise ValueError(f"{name}: no such record in this case")
    if expect and row["entity_type"] != expect:
        raise ValueError(f"{name} must be a {expect}")
    return row["entity_id"]


def resolve_event(conn, case_id: int, value, name: str) -> int:
    _safe_ref(value, name)
    if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
        row = conn.execute("SELECT event_id FROM events WHERE case_id=%s AND event_id=%s", (case_id, int(value))).fetchone()
    else:
        row = conn.execute("SELECT event_id FROM events WHERE case_id=%s AND ref=%s", (case_id, str(value))).fetchone()
    if not row:
        raise ValueError(f"{name}: no such event in this case")
    return row["event_id"]


def validate_params(conn, case_id: int, question: dict, raw: dict) -> dict:
    """SRS 8.26 / 8.27: only registry-defined names, presence, type, range, existence, temporal consistency."""
    raw = dict(raw or {})
    allowed = set(question["required_params"]) | set(question["optional_params"])
    problems: dict[str, str] = {}
    for k in raw:
        if k not in allowed:
            problems[k] = "parameter is not defined for this question"
    for k in question["required_params"]:
        if raw.get(k) in (None, ""):
            problems[k] = "required parameter is missing"
    if problems:
        raise ApiError(422, "INVALID_PARAMETERS", "The question parameters are invalid.", problems)

    out = {p: None for p in ALL_PARAMS}
    out["include_historical"] = False
    out.update(question.get("fixed_params") or {})
    for k, v in raw.items():
        if v in (None, ""):
            continue
        try:
            if k in ID_PARAMS:
                if k == "event_id":
                    out[k] = resolve_event(conn, case_id, v, k)
                elif k == "location_id":
                    out[k] = resolve_entity(conn, case_id, v, "LOCATION", k)
                elif k == "vehicle_id":
                    out[k] = resolve_entity(conn, case_id, v, "VEHICLE", k)
                else:
                    out[k] = resolve_entity(conn, case_id, v, None, k)
            elif k in TIME_PARAMS:
                out[k] = parse_time(k, v)
            elif k in INT_RANGES:
                lo, hi = INT_RANGES[k]
                n = int(v)
                if not lo <= n <= hi:
                    raise ValueError(f"{k} must be between {lo} and {hi}")
                out[k] = n
            elif k == "minimum_strength":
                f = float(v)
                if not 0 <= f <= 1:
                    raise ValueError("minimum_strength must be between 0 and 1")
                out[k] = f
            elif k == "include_historical":
                out[k] = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes")
        except (TypeError, ValueError) as exc:
            problems[k] = str(exc)
    if out["start_time"] and out["end_time"] and out["start_time"] > out["end_time"]:
        problems["start_time"] = "start_time must not be after end_time"
    if problems:
        raise ApiError(422, "INVALID_PARAMETERS", "The question parameters are invalid.", problems)
    out["case_id"] = case_id
    return out


def list_questions(conn) -> list[dict]:
    return conn.execute(
        """SELECT q.question_id, q.display_text, q.category, q.module_id, q.variant, q.required_params,
                  q.optional_params, q.version, m.version AS module_version, m.file_name
           FROM investigation_questions q JOIN sql_modules m USING (module_id)
           WHERE q.status='APPROVED' AND m.status='APPROVED'
           ORDER BY (regexp_replace(q.question_id,'\\D','','g'))::int""").fetchall()


def _audit(user, case_id, q, module_version, params, status, count, ms, error=None) -> str | None:
    safe = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in params.items() if k != "case_id" and v is not None}
    try:
        with pool().connection() as c2:   # separate transaction: audited even when the request fails
            row = c2.execute(
                """INSERT INTO query_audit(user_name, case_id, question_id, module_id, module_version, params,
                                           status, result_count, duration_ms, error)
                   VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s) RETURNING query_exec_id""",
                (user, case_id, q["question_id"] if q else None, q["module_id"] if q else None, module_version,
                 json.dumps(safe, default=str), status, count, ms, error)).fetchone()
            return str(row["query_exec_id"])
    except Exception:
        return None


def execute_question(conn, user: str, case: dict, question_id: str, raw_params: dict) -> dict:
    q = conn.execute(
        """SELECT q.*, m.version AS module_version, m.file_name, m.status AS module_status
           FROM investigation_questions q JOIN sql_modules m USING (module_id) WHERE q.question_id=%s""",
        (question_id,)).fetchone()
    if not q or q["status"] != "APPROVED" or q["module_status"] != "APPROVED":
        raise ApiError(404, "UNKNOWN_QUESTION", "No approved investigation question with that identifier.")
    module = load_modules().get(q["module_id"])
    if not module or module["version"] != q["module_version"] or q["variant"] not in module["variants"]:
        raise ApiError(500, "MODULE_MISMATCH", "The approved module registry and module files are out of sync.")
    try:
        params = validate_params(conn, case["case_id"], q, raw_params)
    except ApiError as exc:
        _audit(user, case["case_id"], q, q["module_version"], dict(raw_params or {}), "INVALID", None, None, exc.message)
        raise
    sql = module["variants"][q["variant"]]
    started = time.perf_counter()
    try:
        with conn.transaction():
            conn.execute(f"SET LOCAL statement_timeout = {int(config.QUERY_TIMEOUT_MS)}")
            cur = conn.execute(sql, params)
            columns = [d.name for d in cur.description]
            rows = cur.fetchall()
    except Exception as exc:
        ms = int((time.perf_counter() - started) * 1000)
        _audit(user, case["case_id"], q, q["module_version"], params, "ERROR", None, ms, type(exc).__name__)
        raise ApiError(503, "QUERY_FAILED", "The investigation query failed. No result was produced.")
    ms = int((time.perf_counter() - started) * 1000)
    rows = [jsonable(dict(r)) for r in rows]
    status = "OK" if rows else "EMPTY"
    exec_id = _audit(user, case["case_id"], q, q["module_version"], params, status, len(rows), ms)

    evidence_refs, record_refs = set(), set()
    for r in rows:
        for key, val in r.items():
            if key.startswith("evidence_ref") and val:
                evidence_refs.update(val if isinstance(val, list) else [val])
            if key in ("record_ref", "record_refs", "communication_ref", "transaction_ref", "relationship_ref") and val:
                record_refs.update(val if isinstance(val, list) else [val])
    limit = params.get("result_limit")
    warnings = []
    if not rows:
        warnings.append("No matching recorded information was found under these conditions. "
                        "This does not establish that the event did not occur.")
    if limit and len(rows) >= limit:
        warnings.append(f"Result limited to {limit} rows; more matching records may exist.")
    return {
        "question_id": q["question_id"], "question": q["display_text"], "module_id": q["module_id"],
        "module_version": q["module_version"], "module_file": q["file_name"], "variant": q["variant"],
        "case_reference": case["case_ref"], "query_exec_id": exec_id, "status": status,
        "executed_at": datetime.now(timezone.utc).isoformat(), "duration_ms": ms,
        "parameters": {k: jsonable(v) for k, v in params.items() if k != "case_id" and v is not None},
        "columns": columns, "rows": rows, "result_count": len(rows),
        "evidence_refs": sorted(evidence_refs), "record_refs": sorted(record_refs), "warnings": warnings,
        "classification": "RECORDED_FACT" if q["category"] != "Cross-domain" else "CORRELATED",
    }
