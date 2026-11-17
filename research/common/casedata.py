"""CaseView: the information available to ranking algorithms. Built from the database; contains NO ground truth.

Only records whose evidence validity is SUPPORTED are 'active' (same convention as Q40 include_historical=false).
Inactive records stay in the view (with their status) because reliability-aware methods may reason about them.
"""
import math
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CaseView:
    case_ref: str
    case_id: int
    incident_ref: str
    incident_time: datetime
    incident_location: str            # entity ref
    victims: list
    persons: dict                     # ref -> display_name
    locations: dict                   # ref -> (lat, lon)
    ent_type: dict                    # ref -> entity_type
    obs: list = field(default_factory=list)       # dict(ref, subject, location, t_from, t_to, source_kind, evidence, status, origin)
    comms: list = field(default_factory=list)     # dict(ref, a, b, t, duration, type, evidence, status, origin)
    txns: list = field(default_factory=list)
    rels: list = field(default_factory=list)      # dict(ref, a, b, type, strength, valid_from, valid_to, evidence, status, origin)
    evidence: dict = field(default_factory=dict)  # ref -> dict(type, source, origin, reliability, status, timestamp, entities)
    activity: list = field(default_factory=list)  # dict(entity, t, ref, status)
    as_of: datetime | None = None
    db: object = None                 # live connection, used ONLY by the frozen-Q40 adapter (never by feature code)
    case_meta: dict = field(default_factory=dict)

    @property
    def candidates(self) -> list:
        """All persons except the victim(s): the same scored population Q40 uses."""
        return sorted(p for p in self.persons if p not in set(self.victims))

    def active(self, rows):
        return [r for r in rows if r["status"] == "SUPPORTED"]


def haversine_m(a, b) -> float:
    (la1, lo1), (la2, lo2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    dphi, dl = p2 - p1, math.radians(lo2 - lo1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def load_case_view(conn, case_ref: str, event_ref: str = "EVT-001") -> CaseView:
    c = conn.execute("SELECT case_id FROM cases WHERE case_ref=%s", (case_ref,)).fetchone()
    cid = c["case_id"]
    ents = conn.execute("SELECT entity_id, ref, entity_type, display_name, attributes FROM entities WHERE case_id=%s", (cid,)).fetchall()
    by_id = {e["entity_id"]: e["ref"] for e in ents}
    ev = conn.execute("""SELECT e.occurred_at, e.ref, l.ref AS loc, e.event_id FROM events e
                         LEFT JOIN entities l ON l.case_id=e.case_id AND l.entity_id=e.location_entity_id
                         WHERE e.case_id=%s AND e.ref=%s""", (cid, event_ref)).fetchone()
    victims = [by_id[r["entity_id"]] for r in conn.execute(
        "SELECT entity_id FROM event_entities WHERE case_id=%s AND event_id=%s AND role='VICTIM'", (cid, ev["event_id"]))]
    locs = {e["ref"]: (float(e["attributes"]["lat"]), float(e["attributes"]["lon"])) for e in ents
            if e["entity_type"] == "LOCATION" and e["attributes"] and "lat" in e["attributes"]}
    v = CaseView(case_ref, cid, event_ref, ev["occurred_at"], ev["loc"], victims,
                 {e["ref"]: e["display_name"] for e in ents if e["entity_type"] == "PERSON"}, locs,
                 {e["ref"]: e["entity_type"] for e in ents})
    for r in conn.execute("SELECT * FROM v_obs WHERE case_id=%s ORDER BY ref", (cid,)):
        v.obs.append(dict(ref=r["ref"], subject=by_id[r["subject_entity_id"]], location=by_id[r["location_entity_id"]], t_from=r["observed_from"],
                          t_to=r["observed_to"], source_kind=r["source_kind"], evidence=r["evidence_ref"], status=r["validity_status"], origin=r["origin_key"]))
    for r in conn.execute("SELECT * FROM v_comms WHERE case_id=%s ORDER BY ref", (cid,)):
        v.comms.append(dict(ref=r["ref"], a=by_id[r["sender_id"]], b=by_id[r["receiver_id"]], t=r["occurred_at"], duration=r["duration_sec"],
                            type=r["comm_type"], evidence=r["evidence_ref"], status=r["validity_status"], origin=r["origin_key"]))
    for r in conn.execute("SELECT * FROM v_txns WHERE case_id=%s ORDER BY ref", (cid,)):
        v.txns.append(dict(ref=r["ref"], a=by_id[r["from_entity_id"]], b=by_id[r["to_entity_id"]], t=r["occurred_at"], amount=float(r["amount"]),
                           evidence=r["evidence_ref"], status=r["validity_status"], origin=r["origin_key"]))
    for r in conn.execute("SELECT * FROM v_rels WHERE case_id=%s ORDER BY ref", (cid,)):
        v.rels.append(dict(ref=r["ref"], a=by_id[r["entity_a"]], b=by_id[r["entity_b"]], type=r["rel_type"], strength=float(r["strength"] or 0),
                           valid_from=r["valid_from"], valid_to=r["valid_to"], evidence=r["evidence_ref"], status=r["validity_status"], origin=r["origin_key"]))
    ee = {}
    for r in conn.execute("SELECT evidence_id, entity_id FROM evidence_entities WHERE case_id=%s", (cid,)):
        ee.setdefault(r["evidence_id"], []).append(by_id[r["entity_id"]])
    for r in conn.execute("SELECT * FROM evidence WHERE case_id=%s ORDER BY ref", (cid,)):
        v.evidence[r["ref"]] = dict(type=r["evidence_type"], source=r["source"], origin=(r["provenance"] or {}).get("origin_root", r["source"]),
                                    reliability=float(r["reliability_score"]) if r["reliability_score"] is not None else None,
                                    status=r["validity_status"], timestamp=r["evidence_timestamp"], entities=sorted(ee.get(r["evidence_id"], [])))
    for r in conn.execute("SELECT entity_id, occurred_at, ref, validity_status FROM v_activity WHERE case_id=%s", (cid,)):
        v.activity.append(dict(entity=by_id[r["entity_id"]], t=r["occurred_at"], ref=r["ref"], status=r["validity_status"]))
    times = [x["t_to"] for x in v.obs] + [x["t"] for x in v.comms] + [x["t"] for x in v.txns]
    v.db, v.case_meta = conn, {"case_id": cid, "case_ref": case_ref}
    v.as_of = max(times) if times else v.incident_time
    return v
