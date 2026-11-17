"""Deterministic Correlation Engine (SRS Section 9).

Inputs are CURRENT-BELIEF records only: a record whose backing evidence is CHALLENGED, INVALIDATED or
SUPERSEDED does not participate (SRS 9.39-9.40). Every result carries its source records, rule id/version
and thresholds (9.34-9.35). The LLM is never involved here.
"""
import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from itertools import combinations

from .rules import RULE_BY_ID

MAX_LISTED_SOURCES = 40


def haversine_m(a, b) -> float:
    (la1, lo1), (la2, lo2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    dphi, dl = p2 - p1, math.radians(lo2 - lo1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


@dataclass
class Corr:
    rule_id: str
    result_type: str
    entity_a: int
    entity_b: int | None = None
    location_id: int | None = None
    summary: str = ""
    sources: list = field(default_factory=list)       # [{"type":"obs","ref":"OBS-1"}]
    evidence_refs: set = field(default_factory=set)
    window_start: object = None
    window_end: object = None
    confidence: float | None = None
    uncertainties: list = field(default_factory=list)
    thresholds: dict = field(default_factory=dict)
    finding_key: str | None = None
    domains: list = field(default_factory=list)


def _cap(sources: list) -> list:
    if len(sources) <= MAX_LISTED_SOURCES:
        return sources
    return sources[:MAX_LISTED_SOURCES] + [{"type": "note", "ref": f"+{len(sources) - MAX_LISTED_SOURCES} more records"}]


class CaseData:
    def __init__(self, conn, case_id: int):
        self.case_id = case_id
        q = lambda sql: conn.execute(sql, (case_id,)).fetchall()
        self.ents = {r["entity_id"]: r for r in q("SELECT * FROM entities WHERE case_id=%s")}
        self.ref_of = {i: e["ref"] for i, e in self.ents.items()}
        self.name_of = {i: e["display_name"] for i, e in self.ents.items()}
        self.coord = {}
        for i, e in self.ents.items():
            a = e["attributes"] or {}
            if e["entity_type"] == "LOCATION" and "lat" in a and "lon" in a:
                self.coord[i] = (float(a["lat"]), float(a["lon"]))
        self.loc_kind = {i: (e["attributes"] or {}).get("kind", "") for i, e in self.ents.items() if e["entity_type"] == "LOCATION"}
        allobs = q("SELECT * FROM v_obs WHERE case_id=%s")
        allcomm = q("SELECT * FROM v_comms WHERE case_id=%s")
        alltxn = q("SELECT * FROM v_txns WHERE case_id=%s")
        allrel = q("SELECT * FROM v_rels WHERE case_id=%s")
        cur = lambda rows: [r for r in rows if r["validity_status"] == "SUPPORTED"]
        self.obs, self.comms, self.txns, self.rels = cur(allobs), cur(allcomm), cur(alltxn), cur(allrel)
        self.excluded = {"observations": len(allobs) - len(self.obs), "communications": len(allcomm) - len(self.comms),
                         "transactions": len(alltxn) - len(self.txns), "relationships": len(allrel) - len(self.rels)}
        self.evidence = {r["evidence_id"]: r for r in q("SELECT * FROM evidence WHERE case_id=%s")}
        self.ev_by_ref = {r["ref"]: r for r in self.evidence.values()}
        self.ev_entities = defaultdict(set)    # evidence_id -> {entity_id}
        for r in q("SELECT evidence_id, entity_id FROM evidence_entities WHERE case_id=%s"):
            self.ev_entities[r["evidence_id"]].add(r["entity_id"])
        self.incidents = [r for r in q("SELECT * FROM events WHERE case_id=%s") if r["event_type"] == "INCIDENT" and r["occurred_at"]]
        self.event_people = defaultdict(list)
        for r in q("SELECT event_id, entity_id, role FROM event_entities WHERE case_id=%s"):
            self.event_people[r["event_id"]].append(r)

    def etype(self, i): return self.ents[i]["entity_type"]
    def dist(self, la, lb):
        if la == lb:
            return 0.0
        if la in self.coord and lb in self.coord:
            return haversine_m(self.coord[la], self.coord[lb])
        return float("inf")


def _ev_ids(data: CaseData, refs) -> list:
    return [data.ev_by_ref[r]["evidence_id"] for r in refs if r in data.ev_by_ref]


def compute(data: CaseData) -> list[Corr]:
    out: list[Corr] = []
    d = data
    pair_comm, pair_txn = defaultdict(list), defaultdict(list)
    for c in d.comms:
        pair_comm[tuple(sorted((c["sender_id"], c["receiver_id"])))].append(c)
    for t in d.txns:
        pair_txn[tuple(sorted((t["from_entity_id"], t["to_entity_id"])))].append(t)

    # ---------------- FACT rules ----------------
    for r in d.rels:
        rid = "FACT_VEH_001" if r["rel_type"] in ("OWNS", "USES") else "FACT_REL_001"
        out.append(Corr(rid, "FACT", r["entity_a"], r["entity_b"],
                        summary=f"{d.name_of[r['entity_a']]} — {r['rel_type']} — {d.name_of[r['entity_b']]} (recorded)",
                        sources=[{"type": "relationship", "ref": r["ref"]}],
                        evidence_refs={r["evidence_ref"]} if r["evidence_ref"] else set(),
                        confidence=float(r["strength"]) if r["strength"] is not None else None,
                        thresholds={}, window_start=r["valid_from"], window_end=r["valid_to"]))
    for (a, b), rows in pair_comm.items():
        rows.sort(key=lambda x: x["occurred_at"])
        out.append(Corr("FACT_COMM_001", "FACT", a, b,
                        summary=f"{len(rows)} recorded communication(s) between {d.name_of[a]} and {d.name_of[b]}",
                        sources=_cap([{"type": "communication", "ref": x["ref"]} for x in rows]),
                        evidence_refs={x["evidence_ref"] for x in rows if x["evidence_ref"]},
                        window_start=rows[0]["occurred_at"], window_end=rows[-1]["occurred_at"],
                        uncertainties=["Communication content is not known."]))
    for (a, b), rows in pair_txn.items():
        rows.sort(key=lambda x: x["occurred_at"])
        total = sum(float(x["amount"]) for x in rows)
        out.append(Corr("FACT_TXN_001", "FACT", a, b,
                        summary=f"{len(rows)} recorded transaction(s) between {d.name_of[a]} and {d.name_of[b]}, total {total:,.2f}",
                        sources=_cap([{"type": "transaction", "ref": x["ref"]} for x in rows]),
                        evidence_refs={x["evidence_ref"] for x in rows if x["evidence_ref"]},
                        window_start=rows[0]["occurred_at"], window_end=rows[-1]["occurred_at"],
                        uncertainties=["The purpose of the transaction is not known."]))

    person_obs = [o for o in d.obs if d.etype(o["subject_entity_id"]) == "PERSON"]

    # ---------------- TEMPORAL_SPATIAL_001 ----------------
    rule = RULE_BY_ID["TEMPORAL_SPATIAL_001"]
    th = rule["thresholds"]
    tmax, dmax = timedelta(minutes=th["time_minutes"]), th["distance_meters"]
    excluded_kinds = set(th["excluded_location_kinds"])
    cand = [o for o in person_obs if d.loc_kind.get(o["location_entity_id"], "") not in excluded_kinds]
    by_loc = defaultdict(list)
    for o in cand:
        by_loc[o["location_entity_id"]].append(o)
    locs = list(by_loc)
    near = {l: [m for m in locs if d.dist(l, m) <= dmax] for l in locs}
    best: dict = {}
    for l in locs:
        for m in near[l]:
            if m < l:
                continue
            for o1 in by_loc[l]:
                for o2 in by_loc[m]:
                    if o1["subject_entity_id"] == o2["subject_entity_id"]:
                        continue
                    gap = max(timedelta(0), max(o1["observed_from"], o2["observed_from"]) - min(o1["observed_to"], o2["observed_to"]))
                    if gap > tmax:
                        continue
                    a, b = sorted((o1["subject_entity_id"], o2["subject_entity_id"]))
                    key = (a, b, l)
                    if key not in best or gap < best[key][0]:
                        best[key] = (gap, o1, o2)
    for (a, b, l), (gap, o1, o2) in sorted(best.items()):
        un = ["Co-presence does not establish that the persons knowingly met or interacted."]
        if (min(a, b), max(a, b)) not in pair_comm:
            un.append("No direct communication record identified between these persons.")
        if o1["origin_key"] == o2["origin_key"]:
            un.append("Both observations come from the same source; they are not independent.")
        mins = int(gap.total_seconds() // 60)
        out.append(Corr("TEMPORAL_SPATIAL_001", "CORRELATED", a, b, l,
                        summary=f"{d.name_of[a]} and {d.name_of[b]} were separately recorded at {d.name_of[l]} "
                                f"{'at overlapping times' if mins == 0 else f'{mins} min apart'}",
                        sources=[{"type": "observation", "ref": o1["ref"]}, {"type": "observation", "ref": o2["ref"]}],
                        evidence_refs={x for x in (o1["evidence_ref"], o2["evidence_ref"]) if x},
                        window_start=min(o1["observed_from"], o2["observed_from"]),
                        window_end=max(o1["observed_to"], o2["observed_to"]),
                        uncertainties=un, thresholds={"time_minutes": th["time_minutes"], "distance_meters": dmax},
                        finding_key=f"TEMPORAL_SPATIAL_001|{d.ref_of[a]}|{d.ref_of[b]}|{d.ref_of[l]}", domains=["CO_LOCATION"]))

    # ---------------- INCIDENT_PROXIMITY_001 ----------------
    rule = RULE_BY_ID["INCIDENT_PROXIMITY_001"]
    th = rule["thresholds"]
    span, dmax = timedelta(minutes=th["time_minutes"]), th["distance_meters"]
    incident_present: dict = defaultdict(set)     # incident event_id -> {person ids}
    for inc in d.incidents:
        if not inc["location_entity_id"]:
            continue
        bestp: dict = {}
        for o in d.obs:
            if o["location_entity_id"] is None or d.dist(o["location_entity_id"], inc["location_entity_id"]) > dmax:
                continue
            if o["observed_to"] < inc["occurred_at"] - span or o["observed_from"] > inc["occurred_at"] + span:
                continue
            t = inc["occurred_at"]
            delta = 0 if o["observed_from"] <= t <= o["observed_to"] else min(
                abs((o["observed_from"] - t).total_seconds()), abs((o["observed_to"] - t).total_seconds()))
            k = o["subject_entity_id"]
            if k not in bestp or delta < bestp[k][0]:
                bestp[k] = (delta, o)
        for k, (delta, o) in sorted(bestp.items()):
            if d.etype(k) == "PERSON":
                incident_present[inc["event_id"]].add(k)
            minutes = int(delta // 60)
            out.append(Corr("INCIDENT_PROXIMITY_001", "CORRELATED", k, None, inc["location_entity_id"],
                            summary=f"{d.name_of[k]} was recorded at {d.name_of[o['location_entity_id']]} "
                                    + (f"at the time of incident {inc['ref']}" if minutes == 0 else f"{minutes} min from the time of incident {inc['ref']}"),
                            sources=[{"type": "observation", "ref": o["ref"]}, {"type": "event", "ref": inc["ref"]}],
                            evidence_refs={o["evidence_ref"]} if o["evidence_ref"] else set(),
                            window_start=o["observed_from"], window_end=o["observed_to"],
                            uncertainties=["A recorded presence near the incident does not establish participation in it.",
                                           "Recorded " + o["source_kind"] + " position precision is limited."],
                            thresholds={"time_minutes": th["time_minutes"], "distance_meters": dmax},
                            finding_key=f"INCIDENT_PROXIMITY_001|{d.ref_of[k]}|{inc['ref']}", domains=["INCIDENT"]))

    # ---------------- SHARED_VEHICLE_001 ----------------
    veh = defaultdict(list)
    for r in d.rels:
        if r["rel_type"] in ("OWNS", "USES") and (r["valid_to"] is None):
            veh[r["entity_b"]].append(r)
    for v, rows in sorted(veh.items()):
        for r1, r2 in combinations(sorted(rows, key=lambda r: r["entity_a"]), 2):
            if r1["entity_a"] == r2["entity_a"]:
                continue
            a, b = r1["entity_a"], r2["entity_a"]
            out.append(Corr("SHARED_VEHICLE_001", "CORRELATED", a, b, None,
                            summary=f"{d.name_of[a]} and {d.name_of[b]} are both recorded as owner/user of {d.name_of[v]}",
                            sources=[{"type": "relationship", "ref": r1["ref"]}, {"type": "relationship", "ref": r2["ref"]}],
                            evidence_refs={x for x in (r1["evidence_ref"], r2["evidence_ref"]) if x},
                            uncertainties=["Shared vehicle use does not establish cooperation."],
                            finding_key=f"SHARED_VEHICLE_001|{d.ref_of[a]}|{d.ref_of[b]}|{d.ref_of[v]}", domains=["SHARED_VEHICLE"]))

    # ---------------- SHARED_EVIDENCE_001 ----------------
    shared_pairs = defaultdict(list)
    for eid, ents in d.ev_entities.items():
        ev = d.evidence[eid]
        if ev["validity_status"] != "SUPPORTED":
            continue
        people = sorted(i for i in ents if d.etype(i) == "PERSON")
        for a, b in combinations(people, 2):
            shared_pairs[(a, b)].append(ev)
    for (a, b), evs in sorted(shared_pairs.items()):
        origins = {e["provenance"].get("origin_root", e["source"]) for e in evs}
        un = ["Shared evidence does not establish coordination or intent."]
        if len(origins) < len(evs):
            un.append("Some of this evidence shares a source and is not independent.")
        out.append(Corr("SHARED_EVIDENCE_001", "INFERRED", a, b, None,
                        summary=f"{d.name_of[a]} and {d.name_of[b]} are both linked to {len(evs)} evidence record(s) "
                                f"from {len(origins)} independent source(s)",
                        sources=[{"type": "evidence", "ref": e["ref"]} for e in evs],
                        evidence_refs={e["ref"] for e in evs}, confidence=round(min(0.8, 0.4 + 0.1 * len(origins)), 2),
                        uncertainties=un, finding_key=f"SHARED_EVIDENCE_001|{d.ref_of[a]}|{d.ref_of[b]}", domains=["SHARED_EVIDENCE"]))

    # ---------------- CONTRADICTION_001 ----------------
    th = RULE_BY_ID["CONTRADICTION_001"]["thresholds"]
    by_person = defaultdict(list)
    for o in person_obs:
        by_person[o["subject_entity_id"]].append(o)
    for p, rows in sorted(by_person.items()):
        rows.sort(key=lambda o: o["observed_from"])
        seen = set()
        for o1, o2 in combinations(rows, 2):
            if o2["observed_from"] > o1["observed_to"]:
                continue
            if o1["origin_key"] == o2["origin_key"]:
                continue
            if d.dist(o1["location_entity_id"], o2["location_entity_id"]) <= th["distance_meters"]:
                continue
            key = tuple(sorted((o1["ref"], o2["ref"])))
            if key in seen:
                continue
            seen.add(key)
            l1, l2 = o1["location_entity_id"], o2["location_entity_id"]
            out.append(Corr("CONTRADICTION_001", "INFERRED", p, None, l1,
                            summary=f"Conflicting records: {d.name_of[p]} is placed at {d.name_of[l1]} ({o1['source']}) and at "
                                    f"{d.name_of[l2]} ({o2['source']}) during overlapping times",
                            sources=[{"type": "observation", "ref": o1["ref"]}, {"type": "observation", "ref": o2["ref"]}],
                            evidence_refs={x for x in (o1["evidence_ref"], o2["evidence_ref"]) if x},
                            window_start=max(o1["observed_from"], o2["observed_from"]),
                            window_end=min(o1["observed_to"], o2["observed_to"]),
                            uncertainties=["This identifies an inconsistency; it does not determine which source is correct."],
                            thresholds={"distance_meters": th["distance_meters"]}, confidence=None,
                            finding_key=f"CONTRADICTION_001|{d.ref_of[p]}|{'|'.join(key)}", domains=[]))

    # ---------------- MULTI_DOMAIN_001 ----------------
    th = RULE_BY_ID["MULTI_DOMAIN_001"]["thresholds"]
    pair_domains: dict = defaultdict(lambda: defaultdict(list))
    for (a, b), rows in pair_comm.items():
        if d.etype(a) == "PERSON" and d.etype(b) == "PERSON":
            pair_domains[(a, b)]["COMMUNICATION"] += [{"type": "communication", "ref": x["ref"]} for x in rows[:5]]
    for (a, b), rows in pair_txn.items():
        if d.etype(a) == "PERSON" and d.etype(b) == "PERSON":
            pair_domains[(a, b)]["TRANSACTION"] += [{"type": "transaction", "ref": x["ref"]} for x in rows[:5]]
    for c in out:
        if c.result_type == "FACT" or c.entity_b is None:
            continue
        key = tuple(sorted((c.entity_a, c.entity_b)))
        for dom in c.domains:
            pair_domains[key][dom] += c.sources
    for inc_id, people in incident_present.items():
        for a, b in combinations(sorted(people), 2):
            pair_domains[(a, b)]["INCIDENT"] += [{"type": "event", "ref": next(i["ref"] for i in d.incidents if i["event_id"] == inc_id)}]
    rel_pairs = {tuple(sorted((r["entity_a"], r["entity_b"]))): r for r in d.rels if r["rel_type"] not in ("OWNS", "USES")}
    for (a, b), doms in sorted(pair_domains.items()):
        if len(doms) < th["min_domains"]:
            continue
        srcs, evs = [], set()
        for lst in doms.values():
            srcs += lst
        for c in out:
            if c.entity_b is not None and tuple(sorted((c.entity_a, c.entity_b))) == (a, b) and c.result_type != "FACT":
                evs |= c.evidence_refs
        for (x, y), rows in ((k, v) for k, v in pair_comm.items() if k == (a, b)):
            evs |= {r["evidence_ref"] for r in rows if r["evidence_ref"]}
        for (x, y), rows in ((k, v) for k, v in pair_txn.items() if k == (a, b)):
            evs |= {r["evidence_ref"] for r in rows if r["evidence_ref"]}
        un = ["Multiple links do not establish coordination, intent or responsibility; investigator review is required."]
        if (a, b) in rel_pairs:
            un.append(f"A {rel_pairs[(a, b)]['rel_type']} relationship is recorded, which may explain some of these links.")
        if "COMMUNICATION" not in doms:
            un.append("No direct communication record identified.")
        out.append(Corr("MULTI_DOMAIN_001", "INFERRED", a, b, None,
                        summary=f"{d.name_of[a]} and {d.name_of[b]} are linked across {len(doms)} domains: "
                                f"{', '.join(sorted(doms))}",
                        sources=_cap(srcs), evidence_refs=evs, confidence=round(min(0.9, 0.35 + 0.15 * len(doms)), 2),
                        uncertainties=un, thresholds={"min_domains": th["min_domains"]},
                        finding_key=f"MULTI_DOMAIN_001|{d.ref_of[a]}|{d.ref_of[b]}", domains=sorted(doms)))
    return out


def run_and_persist(conn, case: dict, user: str, sync_findings: bool = True) -> dict:
    """Compute on current belief, persist run + results, register findings with their evidence dependencies."""
    case_id = case["case_id"]
    data = CaseData(conn, case_id)
    results = compute(data)
    versions = {rid: r["version"] for rid, r in RULE_BY_ID.items()}
    run = conn.execute(
        "INSERT INTO correlation_runs(case_id, run_by, rule_versions, result_count) VALUES (%s,%s,%s::jsonb,%s) RETURNING run_id, started_at",
        (case_id, user, json.dumps(versions), len(results))).fetchone()
    run_id = run["run_id"]
    persisted = []
    for n, c in enumerate(results, start=1):
        ref = f"C-{n:04d}"
        row = conn.execute(
            """INSERT INTO correlations(case_id, run_id, ref, rule_id, rule_version, result_type, entity_a, entity_b,
                    location_id, thresholds, window_start, window_end, confidence, summary, uncertainties,
                    source_records, finding_key)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING correlation_id""",
            (case_id, run_id, ref, c.rule_id, versions[c.rule_id], c.result_type, c.entity_a, c.entity_b,
             c.location_id, json.dumps(c.thresholds), c.window_start, c.window_end, c.confidence, c.summary,
             c.uncertainties, json.dumps(c.sources, default=str), c.finding_key)).fetchone()
        for eid in _ev_ids(data, c.evidence_refs):
            conn.execute("INSERT INTO correlation_evidence(case_id, correlation_id, evidence_id) VALUES (%s,%s,%s)",
                         (case_id, row["correlation_id"], eid))
        persisted.append((row["correlation_id"], c))
    created = 0
    if sync_findings:
        for _, c in persisted:
            if c.result_type == "FACT" or not c.finding_key or not c.evidence_refs:
                continue
            eids = _ev_ids(data, c.evidence_refs)
            live = conn.execute(
                "SELECT finding_id, status FROM findings WHERE case_id=%s AND finding_key=%s AND status<>'OUTDATED'",
                (case_id, c.finding_key)).fetchone()
            if live is None:
                last = conn.execute("SELECT coalesce(max(version),0) AS v FROM findings WHERE case_id=%s AND finding_key=%s",
                                    (case_id, c.finding_key)).fetchone()["v"]
                # A retired key that became supported again starts a new version rather than rewriting history.
                f = conn.execute(
                    """INSERT INTO findings(case_id, finding_key, version, statement, classification, status, generated_by, method)
                       VALUES (%s,%s,%s,%s,%s,'CURRENT',%s,%s) RETURNING finding_id""",
                    (case_id, c.finding_key, last + 1, c.summary, c.result_type, f"correlation-engine:{user}", c.rule_id)).fetchone()
                created += 1
                live = {"finding_id": f["finding_id"], "status": "CURRENT"}
            if live["status"] == "CURRENT":
                for eid in eids:
                    conn.execute("INSERT INTO finding_evidence_links(case_id, finding_id, evidence_id) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                                 (case_id, live["finding_id"], eid))
    return {"run_id": run_id, "result_count": len(results), "findings_created": created, "excluded_records": data.excluded,
            "started_at": run["started_at"]}


def recompute_pending(conn, case: dict, user: str) -> list[dict]:
    """Explicit recomputation of RECOMPUTE_REQUIRED findings against current belief (SRS 5.22-5.23).
    Never silent: each outcome is a new finding version or a retirement, both recorded."""
    case_id = case["case_id"]
    pending = conn.execute(
        "SELECT finding_id, finding_key, version FROM findings WHERE case_id=%s AND status='RECOMPUTE_REQUIRED' ORDER BY finding_id",
        (case_id,)).fetchall()
    if not pending:
        return []
    data = CaseData(conn, case_id)
    fresh = {c.finding_key: c for c in compute(data) if c.finding_key}
    outcomes = []
    for f in pending:
        c = fresh.get(f["finding_key"])
        eids = _ev_ids(data, c.evidence_refs) if c else []
        if c and eids:
            new_id = conn.execute(
                "SELECT record_recomputation(%s,%s,%s,%s,%s,%s,%s) AS id",
                (case_id, f["finding_id"], c.summary, c.result_type, f"recompute:{user}", c.rule_id, eids)).fetchone()["id"]
            outcomes.append({"finding_key": f["finding_key"], "previous_version": f["version"], "outcome": "RECOMPUTED",
                             "new_finding_id": new_id, "new_version": f["version"] + 1})
        else:
            conn.execute("SELECT retire_finding(%s,%s)", (case_id, f["finding_id"]))
            outcomes.append({"finding_key": f["finding_key"], "previous_version": f["version"], "outcome": "RETIRED_NO_SUPPORT",
                             "reason": "No currently supported evidence supports this finding."})
    return outcomes
