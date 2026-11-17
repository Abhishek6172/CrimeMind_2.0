"""Plain-Python data model for the SQL oracles. Loaded either from the committed CSV datasets (independent of PostgreSQL) or from the
raw base tables of a (possibly mutated) disposable database. Never from views and never through the SQL modules."""
import csv
import gzip
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

R = Path(__file__).resolve().parents[2]


def ts(v):
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _i(v):
    return None if v in (None, "") else int(v)


@dataclass
class Data:
    case_id: int
    entities: dict = field(default_factory=dict)       # id -> {type, ref, name, attrs}
    comms: list = field(default_factory=list)
    obs: list = field(default_factory=list)
    rels: list = field(default_factory=list)
    txns: list = field(default_factory=list)
    evidence: dict = field(default_factory=dict)       # id -> {ref,type,source,ts,status,rel,desc,prov}
    events: dict = field(default_factory=dict)
    event_entities: list = field(default_factory=list)  # (event_id, entity_id)
    evidence_entities: list = field(default_factory=list)
    evidence_events: list = field(default_factory=list)

    # evidence-derived fields as exposed by the SQL views (LEFT JOIN + coalesce) -- re-derived here from first principles
    def ev_ref(self, eid):
        return self.evidence[eid]["ref"] if eid in self.evidence else None

    def status(self, eid):
        return self.evidence[eid]["status"] if eid in self.evidence else "SUPPORTED"

    def origin(self, eid):
        e = self.evidence[eid]
        return (e.get("prov") or {}).get("origin_root") or e["source"]

    def ref(self, eid):
        return self.entities[eid]["ref"]


def _read(seed, name):
    with gzip.open(R / "datasets" / f"seed_{seed}" / f"{name}.csv.gz", "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def from_csv(seed: int, case_id: int) -> Data:
    d = Data(case_id)
    keep = lambda rows: [r for r in rows if int(r["case_id"]) == case_id]
    for r in keep(_read(seed, "entities")):
        d.entities[int(r["entity_id"])] = dict(type=r["entity_type"], ref=r["ref"], name=r["display_name"], attrs=json.loads(r["attributes"] or "{}"))
    for r in keep(_read(seed, "evidence")):
        d.evidence[int(r["evidence_id"])] = dict(ref=r["ref"], type=r["evidence_type"], source=r["source"], ts=ts(r["evidence_timestamp"]), status=r["validity_status"],
                                                 rel=None if r["reliability_score"] == "" else Decimal(r["reliability_score"]), desc=r["description"], prov=json.loads(r["provenance"] or "{}"))
    for r in keep(_read(seed, "communications")):
        d.comms.append(dict(ref=r["ref"], s=int(r["sender_id"]), r=int(r["receiver_id"]), type=r["comm_type"], at=ts(r["occurred_at"]), dur=_i(r["duration_sec"]), eid=_i(r["evidence_id"])))
    for r in keep(_read(seed, "location_observations")):
        d.obs.append(dict(ref=r["ref"], subj=int(r["subject_entity_id"]), loc=int(r["location_entity_id"]), frm=ts(r["observed_from"]), to=ts(r["observed_to"]),
                          kind=r["source_kind"], source=r["source"], eid=_i(r["evidence_id"])))
    for r in keep(_read(seed, "relationships")):
        d.rels.append(dict(ref=r["ref"], a=int(r["entity_a"]), b=int(r["entity_b"]), type=r["rel_type"], strength=None if r["strength"] == "" else Decimal(r["strength"]),
                           vfrom=ts(r["valid_from"]), vto=ts(r["valid_to"]), eid=_i(r["evidence_id"])))
    for r in keep(_read(seed, "transactions")):
        d.txns.append(dict(ref=r["ref"], f=int(r["from_entity_id"]), t=int(r["to_entity_id"]), amount=Decimal(r["amount"]), cur=r["currency"], type=r["txn_type"],
                           at=ts(r["occurred_at"]), loc=_i(r["location_entity_id"]), eid=_i(r["evidence_id"])))
    for r in keep(_read(seed, "events")):
        d.events[int(r["event_id"])] = dict(ref=r["ref"], type=r["event_type"], at=ts(r["occurred_at"]), loc=_i(r["location_entity_id"]), desc=r["description"] or None)
    d.event_entities = [(int(r["event_id"]), int(r["entity_id"])) for r in keep(_read(seed, "event_entities"))]
    d.evidence_entities = [(int(r["evidence_id"]), int(r["entity_id"])) for r in keep(_read(seed, "evidence_entities"))]
    d.evidence_events = [(int(r["evidence_id"]), int(r["event_id"])) for r in keep(_read(seed, "evidence_events"))]
    return d


def from_db(conn, case_id: int) -> Data:
    """Raw base tables only (no views)."""
    q = lambda sql: [dict(r) for r in conn.execute(sql, (case_id,)).fetchall()]
    d = Data(case_id)
    for r in q("SELECT * FROM entities WHERE case_id=%s"):
        d.entities[r["entity_id"]] = dict(type=r["entity_type"], ref=r["ref"], name=r["display_name"], attrs=r["attributes"])
    for r in q("SELECT * FROM evidence WHERE case_id=%s"):
        d.evidence[r["evidence_id"]] = dict(ref=r["ref"], type=r["evidence_type"], source=r["source"], ts=r["evidence_timestamp"], status=str(r["validity_status"]),
                                            rel=r["reliability_score"], desc=r["description"], prov=r["provenance"])
    for r in q("SELECT * FROM communications WHERE case_id=%s"):
        d.comms.append(dict(ref=r["ref"], s=r["sender_id"], r=r["receiver_id"], type=r["comm_type"], at=r["occurred_at"], dur=r["duration_sec"], eid=r["evidence_id"]))
    for r in q("SELECT * FROM location_observations WHERE case_id=%s"):
        d.obs.append(dict(ref=r["ref"], subj=r["subject_entity_id"], loc=r["location_entity_id"], frm=r["observed_from"], to=r["observed_to"], kind=r["source_kind"], source=r["source"], eid=r["evidence_id"]))
    for r in q("SELECT * FROM relationships WHERE case_id=%s"):
        d.rels.append(dict(ref=r["ref"], a=r["entity_a"], b=r["entity_b"], type=r["rel_type"], strength=r["strength"], vfrom=r["valid_from"], vto=r["valid_to"], eid=r["evidence_id"]))
    for r in q("SELECT * FROM transactions WHERE case_id=%s"):
        d.txns.append(dict(ref=r["ref"], f=r["from_entity_id"], t=r["to_entity_id"], amount=r["amount"], cur=r["currency"], type=r["txn_type"], at=r["occurred_at"], loc=r["location_entity_id"], eid=r["evidence_id"]))
    for r in q("SELECT * FROM events WHERE case_id=%s"):
        d.events[r["event_id"]] = dict(ref=r["ref"], type=r["event_type"], at=r["occurred_at"], loc=r["location_entity_id"], desc=r["description"])
    d.event_entities = [(r["event_id"], r["entity_id"]) for r in q("SELECT * FROM event_entities WHERE case_id=%s")]
    d.evidence_entities = [(r["evidence_id"], r["entity_id"]) for r in q("SELECT * FROM evidence_entities WHERE case_id=%s")]
    d.evidence_events = [(r["evidence_id"], r["event_id"]) for r in q("SELECT * FROM evidence_events WHERE case_id=%s")]
    return d
