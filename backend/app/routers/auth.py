from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from .. import audit
from ..db import pool
from ..deps import Ctx, get_ctx
from ..errors import ApiError
from ..security import make_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Login(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: Login, request: Request):
    rid = request.state.request_id
    with pool().connection() as conn:
        u = conn.execute("SELECT username, role, password_hash, is_active FROM users WHERE username=%s", (body.username,)).fetchone()
    ok = verify_password(body.password, u["password_hash"] if u and u["is_active"] else None)
    if not ok:
        audit.log_activity(body.username[:64], None, "LOGIN", rid, status="FAILURE")
        raise ApiError(401, "INVALID_CREDENTIALS", "Invalid username or password.")   # same message either way
    audit.log_activity(u["username"], None, "LOGIN", rid)
    return {"access_token": make_token(u["username"], u["role"]), "token_type": "bearer",
            "user": {"username": u["username"], "role": u["role"]}}


@router.get("/me")
def me(ctx: Ctx = Depends(get_ctx)):
    return {"username": ctx.user, "role": ctx.role}
