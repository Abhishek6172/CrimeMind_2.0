"""Authoring endpoints: add evidence/records to a case, bulk import, create cases, manage access, case notes."""
from typing import Optional

import psycopg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from .. import audit, data_entry as de
from ..deps import SUPERVISOR_ROLES, WRITE_ROLES, Ctx, case_dep, get_ctx, require_roles
from ..errors import ApiError
from ..sql_engine import jsonable

router = APIRouter(prefix="/api", tags=["authoring"])


def _created(ctx: Ctx, case: dict, kind: str, ref: str) -> dict:
    audit.log_activity(ctx.user, case["case_id"], f"{kind}_ADDED", ctx.request_id, kind.lower(), ref)
    return {"ref": ref, "message": f"{kind.title()} recorded. Analyses refresh automatically the next time they are viewed."}


@router.post("/cases/{case_ref}/entities", status_code=201)
def add_entity(body: de.NewEntity, dep=Depends(case_dep)):
    ctx, case = dep
    require_roles(ctx, WRITE_ROLES, "entity.create")
    return _created(ctx, case, "ENTITY", de.add_entity(ctx.conn, case, body))


@router.post("/cases/{case_ref}/evidence", status_code=201)
def add_evidence(body: de.NewEvidence, dep=Depends(case_dep)):
    ctx, case = dep
    require_roles(ctx, WRITE_ROLES, "evidence.create")
    return _created(ctx, case, "EVIDENCE", de.add_evidence(ctx.conn, case, ctx.user, body))


@router.post("/cases/{case_ref}/communications", status_code=201)
def add_comm(body: de.NewCommunication, dep=Depends(case_dep)):
    ctx, case = dep
    require_roles(ctx, WRITE_ROLES, "communication.create")
    return _created(ctx, case, "COMMUNICATION", de.add_communication(ctx.conn, case, body))


@router.post("/cases/{case_ref}/transactions", status_code=201)
def add_txn(body: de.NewTransaction, dep=Depends(case_dep)):
    ctx, case = dep
    require_roles(ctx, WRITE_ROLES, "transaction.create")
    return _created(ctx, case, "TRANSACTION", de.add_transaction(ctx.conn, case, body))


@router.post("/cases/{case_ref}/observations", status_code=201)
def add_obs(body: de.NewObservation, dep=Depends(case_dep)):
    ctx, case = dep
    require_roles(ctx, WRITE_ROLES, "observation.create")
    return _created(ctx, case, "OBSERVATION", de.add_observation(ctx.conn, case, body))


@router.post("/cases/{case_ref}/relationships", status_code=201)
def add_rel(body: de.NewRelationship, dep=Depends(case_dep)):
    ctx, case = dep
    require_roles(ctx, WRITE_ROLES, "relationship.create")
    return _created(ctx, case, "RELATIONSHIP", de.add_relationship(ctx.conn, case, body))


@router.post("/cases/{case_ref}/import")
def bulk_import(body: de.ImportBundle, dep=Depends(case_dep)):
    ctx, case = dep
    require_roles(ctx, WRITE_ROLES, "case.import")
    out = de.run_import(ctx.conn, case, ctx.user, body)
    audit.log_activity(ctx.user, case["case_id"], "CASE_IMPORT", ctx.request_id, "case", case["case_ref"],
                       "SUCCESS" if out["committed"] else ("FAILURE" if out["errors"] else "DRY_RUN"),
                       {"dry_run": body.dry_run, "errors": len(out["errors"]), "rows": out.get("created") or out.get("would_create")})
    return jsonable(out)


# ---------- case creation and access ----------
class NewCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=200)
    share_with: list[str] = []


def _definer_call(ctx: Ctx, sql: str, args: tuple):
    try:
        return ctx.conn.execute(sql, args).fetchone()
    except psycopg.errors.RaiseException as exc:
        raise ApiError(422, "RULE_VIOLATION", (exc.diag.message_primary or "Not permitted.")[:200])


@router.post("/cases", status_code=201)
def create_case(body: NewCase, ctx: Ctx = Depends(get_ctx)):
    require_roles(ctx, SUPERVISOR_ROLES, "case.create")
    ref = _definer_call(ctx, "SELECT create_case(%s) AS ref", (body.title,))["ref"]
    for u in sorted(set(body.share_with) - {ctx.user}):
        _definer_call(ctx, "SELECT grant_case_access(%s,%s)", (ref, u))
    cid = ctx.conn.execute("SELECT case_id FROM cases WHERE case_ref=%s", (ref,)).fetchone()["case_id"]
    audit.log_activity(ctx.user, cid, "CASE_CREATED", ctx.request_id, "case", ref, details={"shared_with": body.share_with})
    return {"case_ref": ref, "message": "Case created. Only you and the users you shared it with can open it."}


@router.get("/users")
def list_users(ctx: Ctx = Depends(get_ctx)):
    require_roles(ctx, SUPERVISOR_ROLES, "users.list")
    rows = ctx.conn.execute("SELECT username, role::text AS role FROM users WHERE is_active ORDER BY username").fetchall()
    return {"users": rows}


class AccessIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64)


@router.get("/cases/{case_ref}/access")
def list_access(dep=Depends(case_dep)):
    ctx, case = dep
    require_roles(ctx, SUPERVISOR_ROLES, "access.list")
    rows = ctx.conn.execute("SELECT u.username, u.role::text AS role, a.granted_at FROM user_case_access a JOIN users u ON u.user_id=a.user_id "
                            "WHERE a.case_id=%s ORDER BY u.username", (case["case_id"],)).fetchall()
    return jsonable({"access": rows})


@router.post("/cases/{case_ref}/access", status_code=201)
def grant_access(body: AccessIn, dep=Depends(case_dep)):
    ctx, case = dep
    require_roles(ctx, SUPERVISOR_ROLES, "access.grant")
    _definer_call(ctx, "SELECT grant_case_access(%s,%s)", (case["case_ref"], body.username))
    audit.log_activity(ctx.user, case["case_id"], "ACCESS_GRANTED", ctx.request_id, "user", body.username)
    return {"message": f"{body.username} can now open this case."}


@router.delete("/cases/{case_ref}/access/{username}")
def revoke_access(username: str, dep=Depends(case_dep)):
    ctx, case = dep
    require_roles(ctx, SUPERVISOR_ROLES, "access.revoke")
    _definer_call(ctx, "SELECT revoke_case_access(%s,%s)", (case["case_ref"], username))
    audit.log_activity(ctx.user, case["case_id"], "ACCESS_REVOKED", ctx.request_id, "user", username)
    return {"message": f"{username} no longer has access to this case."}


# ---------- notes / bookmarks ----------
class NoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_type: str
    target_ref: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)
    tags: list[str] = Field(default=[], max_length=10)
    bookmarked: bool = False


@router.post("/cases/{case_ref}/notes", status_code=201)
def add_note(body: NoteIn, dep=Depends(case_dep)):
    ctx, case = dep
    require_roles(ctx, WRITE_ROLES, "note.create")
    cid, q = case["case_id"], ctx.conn.execute
    exists = {"CASE": lambda: body.target_ref == case["case_ref"],
              "ENTITY": lambda: q("SELECT 1 FROM entities WHERE case_id=%s AND ref=%s", (cid, body.target_ref)).fetchone(),
              "EVIDENCE": lambda: q("SELECT 1 FROM evidence WHERE case_id=%s AND ref=%s", (cid, body.target_ref)).fetchone(),
              "FINDING": lambda: q("SELECT 1 FROM findings WHERE case_id=%s AND finding_key=%s", (cid, body.target_ref)).fetchone(),
              "HYPOTHESIS": lambda: q("SELECT 1 FROM hypotheses WHERE case_id=%s AND ref=%s", (cid, body.target_ref)).fetchone()}
    if body.target_type not in exists:
        raise ApiError(422, "VALIDATION_ERROR", "Unknown target type.", {"target_type": "invalid"})
    if not exists[body.target_type]():
        raise ApiError(404, "TARGET_NOT_FOUND", "That item does not exist in this case.")
    tags = sorted({t.strip().lower()[:30] for t in body.tags if t.strip()})
    r = q("INSERT INTO case_notes(case_id,target_type,target_ref,body,tags,bookmarked,author) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING note_id, created_at",
          (cid, body.target_type, body.target_ref, body.body.strip(), tags, body.bookmarked, ctx.user)).fetchone()
    audit.log_activity(ctx.user, cid, "NOTE_ADDED", ctx.request_id, body.target_type, body.target_ref)
    return jsonable({"note_id": r["note_id"], "created_at": r["created_at"]})


@router.get("/cases/{case_ref}/notes")
def list_notes(target_type: Optional[str] = None, target_ref: Optional[str] = None, bookmarked: Optional[bool] = None, tag: Optional[str] = None,
               dep=Depends(case_dep)):
    ctx, case = dep
    rows = ctx.conn.execute(
        """SELECT note_id, target_type, target_ref, body, tags, bookmarked, author, created_at FROM case_notes
           WHERE case_id=%s AND (%s::text IS NULL OR target_type=%s) AND (%s::text IS NULL OR target_ref=%s)
             AND (%s::boolean IS NULL OR bookmarked=%s) AND (%s::text IS NULL OR %s = ANY(tags))
           ORDER BY created_at DESC LIMIT 500""",
        (case["case_id"], target_type, target_type, target_ref, target_ref, bookmarked, bookmarked, tag, tag)).fetchall()
    return jsonable({"notes": rows, "notice": "Notes are investigator comments, not evidence. They are append-only; corrections are new notes."})
