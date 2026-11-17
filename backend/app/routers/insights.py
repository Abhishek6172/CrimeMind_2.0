"""Deterministic investigative analytics (no language model): movement plausibility, alibi, network, anomalies, money trail, meetings, map."""
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query

from .. import audit, insights as ins
from ..correlation.engine import CaseData
from ..deps import WRITE_ROLES, case_dep, require_roles
from ..errors import ApiError
from ..sql_engine import jsonable, parse_time, resolve_entity as _resolve

router = APIRouter(prefix="/api/cases/{case_ref}/insights", tags=["insights"])


def resolve_entity(conn, case_id, value, expect, name):
    try:
        return _resolve(conn, case_id, value, expect, name)
    except ValueError as exc:
        raise ApiError(422, "VALIDATION_ERROR", "The request is invalid.", {name: str(exc)})


def _time(name, value):
    try:
        return parse_time(name, value)
    except ValueError as exc:
        raise ApiError(422, "VALIDATION_ERROR", "The request is invalid.", {name: str(exc)})


def _run(dep, name: str, fn, **audit_details):
    ctx, case = dep
    require_roles(ctx, WRITE_ROLES, f"insight.{name}")
    d = CaseData(ctx.conn, case["case_id"])
    out = fn(d, ctx, case)
    out["excluded_by_type"] = d.excluded
    audit.log_activity(ctx.user, case["case_id"], "INSIGHT_RUN", ctx.request_id, "insight", name, details=audit_details)
    return jsonable(out)


@router.get("/jumps")
def jumps(max_speed_kmh: float = Query(120, gt=10, le=1000), min_distance_m: float = Query(300, ge=0, le=100000), dep=Depends(case_dep)):
    return _run(dep, "jumps", lambda d, c, k: ins.impossible_jumps(d, max_speed_kmh, min_distance_m), max_speed_kmh=max_speed_kmh)


@router.get("/alibi")
def alibi(person: str, start: str, end: str, location: Optional[str] = None, radius_m: float = Query(150, ge=10, le=5000), dep=Depends(case_dep)):
    ctx, case = dep

    def go(d, c, k):
        p = resolve_entity(c.conn, k["case_id"], person, "PERSON", "person")
        s, e = _time("start", start), _time("end", end)
        if e <= s:
            raise ApiError(422, "VALIDATION_ERROR", "The window is invalid.", {"end": "must be after start"})
        if e - s > timedelta(days=14):
            raise ApiError(422, "VALIDATION_ERROR", "The window is too long.", {"end": "at most 14 days"})
        if location:
            t = resolve_entity(c.conn, k["case_id"], location, "LOCATION", "location")
        else:
            inc = [i for i in d.incidents if i["location_entity_id"]]
            if not inc:
                raise ApiError(422, "VALIDATION_ERROR", "Choose a location.", {"location": "required when the case has no incident location"})
            t = inc[0]["location_entity_id"]
        return ins.alibi(d, p, s, e, t, radius_m)
    return _run(dep, "alibi", go, person=person)


@router.get("/network")
def network(domains: str = "communication,transaction,relationship", dep=Depends(case_dep)):
    allowed = {"communication", "transaction", "relationship"}
    chosen = {x.strip() for x in domains.split(",") if x.strip()}
    if not chosen or not chosen <= allowed:
        raise ApiError(422, "VALIDATION_ERROR", "Unknown domain.", {"domains": "use communication, transaction, relationship"})
    return _run(dep, "network", lambda d, c, k: ins.network(d, chosen), domains=sorted(chosen))


@router.get("/anomalies")
def anomalies(dep=Depends(case_dep)):
    return _run(dep, "anomalies", lambda d, c, k: ins.anomalies(d))


@router.get("/money-trail")
def money_trail(entity: str, direction: str = Query("forward", pattern="^(forward|backward)$"), max_hops: int = Query(4, ge=1, le=6),
                min_amount: float = Query(0, ge=0), dep=Depends(case_dep)):
    return _run(dep, "money_trail", lambda d, c, k: ins.money_trail(d, resolve_entity(c.conn, k["case_id"], entity, None, "entity"), direction, max_hops, min_amount),
                entity=entity)


@router.get("/meetings")
def meetings(window_minutes: int = Query(30, ge=1, le=240), radius_m: float = Query(100, ge=10, le=2000), dep=Depends(case_dep)):
    return _run(dep, "meetings", lambda d, c, k: ins.meetings(d, window_minutes, radius_m))


@router.get("/map")
def map_view(person: Optional[str] = None, dep=Depends(case_dep)):
    return _run(dep, "map", lambda d, c, k: ins.map_data(d, resolve_entity(c.conn, k["case_id"], person, "PERSON", "person") if person else None))
