"""Activity audit. Written on a SEPARATE transaction so a failed or denied request is still
recorded even though its own transaction rolls back (SRS 20.2: security-relevant access failures)."""
import json
import logging

from . import config
from .db import pool

log = logging.getLogger("crimemind")


def log_activity(user: str | None, case_id: int | None, action: str, request_id: str | None = None,
                 object_type: str | None = None, object_id: str | None = None, status: str = "SUCCESS",
                 details: dict | None = None, version_meta: dict | None = None) -> None:
    try:
        meta = {"app_version": config.APP_VERSION, **(version_meta or {})}
        with pool().connection() as conn:
            conn.execute(
                "SELECT log_activity(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)",
                (user, case_id, action, request_id, object_type, object_id, status,
                 json.dumps(details or {}, default=str), json.dumps(meta)))
    except Exception as exc:  # auditing must never take the request down; the failure itself is logged
        log.error("audit write failed action=%s class=%s", action, type(exc).__name__)
