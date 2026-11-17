"""Authoring: validated creation of entities, evidence and investigation records inside ONE authorised case.

Clients send refs (P-001, L-GP1, E-0308), never numeric ids; every ref is resolved inside the case, so a ref from
another case simply does not exist here. The database integrity triggers remain the final authority on type rules.
"""
import json
import re
from datetime import datetime
from typing import Any, Optional

import psycopg
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .errors import ApiError

ENTITY_PREFIX = {"PERSON": "P", "VEHICLE": "V", "LOCATION": "L", "ACCOUNT": "A", "DEVICE": "D", "ORGANIZATION": "O"}
REF_RE = re.compile(r"^[A-Z]{1,3}-[A-Za-z0-9]{1,12}$")
MAX_IMPORT_ROWS = 5000


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NewEntity(_Base):
    entity_type: str
    display_name: str = Field(min_length=1, max_length=200)
    attributes: dict[str, Any] = {}
    ref: Optional[str] = None

    @field_validator("ref")
    @classmethod
    def _ref(cls, v):
        if v is not None and not REF_RE.match(v):
            raise ValueError("ref must look like P-101")
        return v


class NewEvidence(_Base):
    evidence_type: str
    source: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=4000)
    evidence_timestamp: Optional[datetime] = None
    origin_root: Optional[str] = Field(None, max_length=160)
    entity_refs: list[str] = []
    ref: Optional[str] = None

    @field_validator("ref")
    @classmethod
    def _ref(cls, v):
        if v is not None and not re.match(r"^E-[A-Za-z0-9]{1,12}$", v):
            raise ValueError("ref must look like E-N010")
        return v


class NewCommunication(_Base):
    sender: str
    receiver: str
    comm_type: str
    occurred_at: datetime
    duration_sec: Optional[int] = Field(None, ge=0)
    evidence_ref: Optional[str] = None


class NewTransaction(_Base):
    from_entity: str
    to_entity: str
    txn_type: str
    amount: float = Field(gt=0)
    currency: str = Field("INR", min_length=3, max_length=3)
    occurred_at: datetime
    location: Optional[str] = None
    evidence_ref: Optional[str] = None


class NewObservation(_Base):
    subject: str
    location: str
    observed_from: datetime
    observed_to: datetime
    source_kind: str
    source: str = Field(min_length=1, max_length=120)
    evidence_ref: Optional[str] = None


class NewRelationship(_Base):
    entity_a: str
    entity_b: str
    rel_type: str
    strength: Optional[float] = Field(None, ge=0, le=1)
    evidence_ref: Optional[str] = None


class ImportBundle(_Base):
    dry_run: bool = True
    entities: list[NewEntity] = []
    evidence: list[NewEvidence] = []
    relationships: list[NewRelationship] = []
    communications: list[NewCommunication] = []
    transactions: list[NewTransaction] = []
    observations: list[NewObservation] = []


# ---------- helpers ----------
def _bad(field: str, msg: str) -> ApiError:
    return ApiError(422, "VALIDATION_ERROR", "The request is invalid.", {field: msg})


def entity_id(conn, case_id: int, ref: str, field: str, types: tuple[str, ...] | None = None) -> int:
    row = conn.execute("SELECT entity_id, entity_type FROM entities WHERE case_id=%s AND ref=%s", (case_id, ref)).fetchone()
    if not row:
        raise _bad(field, f"'{ref}' is not an entity in this case")
    if types and row["entity_type"] not in types:
        raise _bad(field, f"'{ref}' must be one of: {', '.join(types)}")
    return row["entity_id"]


def evidence_id(conn, case_id: int, ref: Optional[str], field: str = "evidence_ref") -> Optional[int]:
    if not ref:
        return None
    row = conn.execute("SELECT evidence_id FROM evidence WHERE case_id=%s AND ref=%s", (case_id, ref)).fetchone()
    if not row:
        raise _bad(field, f"'{ref}' is not evidence in this case")
    return row["evidence_id"]


def _next(conn, case_id: int, table: str, prefix: str, width: int) -> str:
    n = conn.execute(f"SELECT coalesce(max(substring(ref from %s)::int), 0) + 1 AS n FROM {table} WHERE case_id=%s AND ref ~ %s",
                     (f"^{prefix}-(\\d+)$", case_id, f"^{prefix}-\\d+$")).fetchone()["n"]
    return f"{prefix}-{n:0{width}d}"


def _log(conn, case_id: int, kind: str, ref: str) -> None:
    conn.execute("INSERT INTO case_data_log(case_id, kind, ref) VALUES (%s,%s,%s)", (case_id, kind, ref))


def translate_db_error(exc: Exception) -> ApiError:
    """Database integrity failures become field-level 422s; internals are never leaked."""
    if isinstance(exc, psycopg.errors.UniqueViolation):
        return ApiError(422, "DUPLICATE", "That record already exists in this case.")
    if isinstance(exc, (psycopg.errors.CheckViolation, psycopg.errors.ForeignKeyViolation, psycopg.errors.InvalidTextRepresentation,
                        psycopg.errors.NumericValueOutOfRange, psycopg.errors.StringDataRightTruncation)):
        return ApiError(422, "VALIDATION_ERROR", "A value violates a data rule.")
    if isinstance(exc, psycopg.errors.RaiseException):
        msg = (exc.diag.message_primary or "The record violates an integrity rule.")
        return ApiError(422, "INTEGRITY_RULE", msg[:300])
    raise exc


# ---------- creators (each returns the new ref) ----------
def add_entity(conn, case: dict, d: NewEntity) -> str:
    cid = case["case_id"]
    if d.entity_type not in ENTITY_PREFIX:
        raise _bad("entity_type", "must be one of " + ", ".join(ENTITY_PREFIX))
    attrs = dict(d.attributes)
    if d.entity_type == "LOCATION":
        try:
            lat, lon = float(attrs["lat"]), float(attrs["lon"])
        except (KeyError, TypeError, ValueError):
            raise _bad("attributes", "a LOCATION needs numeric lat and lon")
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise _bad("attributes", "lat/lon out of range")
        attrs["lat"], attrs["lon"] = lat, lon
    ref = d.ref or _next(conn, cid, "entities", ENTITY_PREFIX[d.entity_type], 3)
    if d.ref and not d.ref.startswith(ENTITY_PREFIX[d.entity_type] + "-"):
        raise _bad("ref", f"a {d.entity_type} ref must start with {ENTITY_PREFIX[d.entity_type]}-")
    try:
        conn.execute("INSERT INTO entities(case_id, entity_type, ref, display_name, attributes) VALUES (%s,%s,%s,%s,%s::jsonb)",
                     (cid, d.entity_type, ref, d.display_name.strip(), json.dumps(attrs)))
    except psycopg.Error as exc:
        raise translate_db_error(exc)
    _log(conn, cid, "ENTITY", ref)
    return ref


def add_evidence(conn, case: dict, user: str, d: NewEvidence) -> str:
    cid = case["case_id"]
    if not conn.execute("SELECT 1 FROM evidence_types WHERE evidence_type=%s", (d.evidence_type,)).fetchone():
        raise _bad("evidence_type", "not a registered evidence type")
    ids = [entity_id(conn, cid, r, "entity_refs") for r in d.entity_refs]
    ref = d.ref or _next_e(conn, cid)
    try:
        eid = conn.execute(
            """INSERT INTO evidence(case_id, ref, evidence_type, source, evidence_timestamp, description, provenance)
               VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING evidence_id""",
            (cid, ref, d.evidence_type, d.source, d.evidence_timestamp, d.description,
             json.dumps({"origin_root": d.origin_root or d.source, "added_by": user}))).fetchone()["evidence_id"]
        for i in sorted(set(ids)):
            conn.execute("INSERT INTO evidence_entities(case_id, evidence_id, entity_id) VALUES (%s,%s,%s)", (cid, eid, i))
    except psycopg.Error as exc:
        raise translate_db_error(exc)
    _log(conn, cid, "EVIDENCE", ref)
    return ref


def _next_e(conn, cid: int) -> str:
    n = conn.execute("SELECT coalesce(max(substring(ref from '^E-N(\\d+)$')::int), 0) + 1 AS n FROM evidence WHERE case_id=%s AND ref ~ '^E-N\\d+$'",
                     (cid,)).fetchone()["n"]
    return f"E-N{n:03d}"


def add_communication(conn, case: dict, d: NewCommunication) -> str:
    cid = case["case_id"]
    s = entity_id(conn, cid, d.sender, "sender", ("PERSON", "DEVICE", "ACCOUNT", "ORGANIZATION"))
    r = entity_id(conn, cid, d.receiver, "receiver", ("PERSON", "DEVICE", "ACCOUNT", "ORGANIZATION"))
    if s == r:
        raise _bad("receiver", "sender and receiver must differ")
    if d.comm_type not in ("CALL", "SMS", "EMAIL", "CHAT"):
        raise _bad("comm_type", "must be CALL, SMS, EMAIL or CHAT")
    ev = evidence_id(conn, cid, d.evidence_ref)
    ref = _next(conn, cid, "communications", "COMM", 5)
    try:
        conn.execute("INSERT INTO communications(case_id, ref, sender_id, receiver_id, comm_type, occurred_at, duration_sec, evidence_id) "
                     "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (cid, ref, s, r, d.comm_type, d.occurred_at, d.duration_sec, ev))
    except psycopg.Error as exc:
        raise translate_db_error(exc)
    _log(conn, cid, "COMMUNICATION", ref)
    return ref


def add_transaction(conn, case: dict, d: NewTransaction) -> str:
    cid = case["case_id"]
    a = entity_id(conn, cid, d.from_entity, "from_entity")
    b = entity_id(conn, cid, d.to_entity, "to_entity")
    if a == b:
        raise _bad("to_entity", "from and to must differ")
    if d.txn_type not in ("TRANSFER", "PAYMENT", "WITHDRAWAL", "DEPOSIT", "PURCHASE"):
        raise _bad("txn_type", "invalid transaction type")
    loc = entity_id(conn, cid, d.location, "location", ("LOCATION",)) if d.location else None
    ev = evidence_id(conn, cid, d.evidence_ref)
    ref = _next(conn, cid, "transactions", "TXN", 5)
    try:
        conn.execute("INSERT INTO transactions(case_id, ref, from_entity_id, to_entity_id, amount, currency, txn_type, occurred_at, location_entity_id, evidence_id) "
                     "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (cid, ref, a, b, d.amount, d.currency.upper(), d.txn_type, d.occurred_at, loc, ev))
    except psycopg.Error as exc:
        raise translate_db_error(exc)
    _log(conn, cid, "TRANSACTION", ref)
    return ref


def add_observation(conn, case: dict, d: NewObservation) -> str:
    cid = case["case_id"]
    s = entity_id(conn, cid, d.subject, "subject", ("PERSON", "VEHICLE"))
    l = entity_id(conn, cid, d.location, "location", ("LOCATION",))
    if d.observed_to < d.observed_from:
        raise _bad("observed_to", "must not be before observed_from")
    if d.source_kind not in ("GPS", "CCTV", "ACCESS_LOG", "WITNESS", "OTHER"):
        raise _bad("source_kind", "invalid source kind")
    ev = evidence_id(conn, cid, d.evidence_ref)
    ref = _next(conn, cid, "location_observations", "OBS", 5)
    try:
        conn.execute("INSERT INTO location_observations(case_id, ref, subject_entity_id, location_entity_id, observed_from, observed_to, source_kind, source, evidence_id) "
                     "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", (cid, ref, s, l, d.observed_from, d.observed_to, d.source_kind, d.source, ev))
    except psycopg.Error as exc:
        raise translate_db_error(exc)
    _log(conn, cid, "OBSERVATION", ref)
    return ref


def add_relationship(conn, case: dict, d: NewRelationship) -> str:
    cid = case["case_id"]
    a = entity_id(conn, cid, d.entity_a, "entity_a")
    b = entity_id(conn, cid, d.entity_b, "entity_b")
    if a == b:
        raise _bad("entity_b", "the two entities must differ")
    if d.rel_type not in ("FAMILY", "FRIEND", "COLLEAGUE", "EMPLOYER", "OWNS", "USES", "ASSOCIATE", "ACCOUNT_OF"):
        raise _bad("rel_type", "invalid relationship type")
    ev = evidence_id(conn, cid, d.evidence_ref)
    ref = _next(conn, cid, "relationships", "REL", 4)
    try:
        conn.execute("INSERT INTO relationships(case_id, ref, entity_a, entity_b, rel_type, strength, evidence_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                     (cid, ref, a, b, d.rel_type, d.strength, ev))
    except psycopg.Error as exc:
        raise translate_db_error(exc)
    _log(conn, cid, "RELATIONSHIP", ref)
    return ref


# ---------- bulk import (all-or-nothing, per-row error report, dry run) ----------
class _Rollback(Exception):
    pass


def run_import(conn, case: dict, user: str, bundle: ImportBundle) -> dict:
    total = sum(len(getattr(bundle, k)) for k in ("entities", "evidence", "relationships", "communications", "transactions", "observations"))
    if total == 0:
        raise ApiError(422, "VALIDATION_ERROR", "The import contains no rows.")
    if total > MAX_IMPORT_ROWS:
        raise ApiError(422, "IMPORT_TOO_LARGE", f"At most {MAX_IMPORT_ROWS} rows per import.")
    errors, created = [], {}
    plan = [("entities", bundle.entities, lambda d: add_entity(conn, case, d)),
            ("evidence", bundle.evidence, lambda d: add_evidence(conn, case, user, d)),
            ("relationships", bundle.relationships, lambda d: add_relationship(conn, case, d)),
            ("communications", bundle.communications, lambda d: add_communication(conn, case, d)),
            ("transactions", bundle.transactions, lambda d: add_transaction(conn, case, d)),
            ("observations", bundle.observations, lambda d: add_observation(conn, case, d))]
    try:
        with conn.transaction():
            for section, rows, fn in plan:
                for i, d in enumerate(rows):
                    try:
                        with conn.transaction():        # savepoint: one bad row never poisons the rest of the report
                            created.setdefault(section, []).append(fn(d))
                    except ApiError as e:
                        errors.append({"section": section, "index": i, "message": e.message, "fields": e.fields})
            if errors or bundle.dry_run:
                raise _Rollback()
    except _Rollback:
        pass
    committed = not errors and not bundle.dry_run
    return {"dry_run": bundle.dry_run, "committed": committed, "would_create" if not committed else "created":
            {k: len(v) for k, v in created.items()}, "refs": created if committed else None, "errors": errors,
            "message": ("Imported." if committed else "Nothing was written. Fix the listed rows and resubmit." if errors
                        else "Dry run only: nothing was written.")}
