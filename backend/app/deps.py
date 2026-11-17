"""Authentication, role and case-scope dependencies (SRS 15.5 request lifecycle, 17.3)."""
from dataclasses import dataclass

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import audit
from .db import pool
from .errors import ApiError
from .security import decode_token

bearer = HTTPBearer(auto_error=False)
WRITE_ROLES = {"INVESTIGATOR", "SUPERVISOR", "ADMINISTRATOR"}
SUPERVISOR_ROLES = {"SUPERVISOR", "ADMINISTRATOR"}


@dataclass
class Ctx:
    conn: object
    user: str
    user_id: int
    role: str
    request_id: str


def get_ctx(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer)):
    """One transaction per request; commits on success, rolls back on any error."""
    rid = request.state.request_id
    if creds is None:
        raise ApiError(401, "AUTH_REQUIRED", "Authentication is required.")
    try:
        claims = decode_token(creds.credentials)
    except jwt.PyJWTError:
        audit.log_activity(None, None, "AUTH_TOKEN_REJECTED", rid, status="DENIED")
        raise ApiError(401, "AUTH_INVALID", "The session is invalid or has expired.")
    with pool().connection() as conn:
        user = conn.execute("SELECT user_id, username, role, is_active FROM users WHERE username=%s", (claims["sub"],)).fetchone()
        if not user or not user["is_active"]:
            raise ApiError(401, "AUTH_INVALID", "The session is invalid or has expired.")
        conn.execute("SELECT set_config('app.user', %s, true)", (user["username"],))
        yield Ctx(conn, user["username"], user["user_id"], user["role"], rid)


def require_roles(ctx: Ctx, roles: set[str], action: str) -> None:
    if ctx.role not in roles:
        audit.log_activity(ctx.user, None, "PERMISSION_DENIED", ctx.request_id, status="DENIED", details={"action": action, "role": ctx.role})
        raise ApiError(403, "FORBIDDEN", "Your role is not permitted to perform this action.")


def load_case(ctx: Ctx, case_ref: str) -> dict:
    """Resolve the case and verify membership server-side. Unknown and unauthorized cases are indistinguishable (no leakage)."""
    row = ctx.conn.execute(
        """SELECT c.case_id, c.case_ref, c.title, c.status, c.created_at FROM cases c
           JOIN user_case_access a ON a.case_id = c.case_id WHERE c.case_ref=%s AND a.user_id=%s""",
        (case_ref, ctx.user_id)).fetchone()
    if not row:
        audit.log_activity(ctx.user, None, "CASE_ACCESS_DENIED", ctx.request_id, "case", case_ref[:64], "DENIED")
        raise ApiError(404, "CASE_NOT_FOUND", "No such case, or you do not have access to it.")
    return row


def case_dep(case_ref: str, ctx: Ctx = Depends(get_ctx)) -> tuple[Ctx, dict]:
    return ctx, load_case(ctx, case_ref)
