"""Evidence-evolution scenario runner (SRS 6.14, 6.27).

Reads intended steps from gt.scenario_events (admin only), lets the new evidence ARRIVE, then asks CrimeMind's own
change_validity() to perform the transition. The runner never edits findings or hypotheses: any downstream effect
is produced by EVLM, which is what the evaluation measures.

Usage: python -m synth.scenario list|apply <scenario_id> <step>|next
"""
import json
import os
import sys

import psycopg
from psycopg.rows import dict_row

BASE = os.environ.get("CM_ADMIN_URL_BASE", "postgresql://postgres:postgres@localhost:5432")
ACTOR = "sup.rao"


def connect(db=None):
    db = db or os.environ.get("CM_DB", "crimemind")
    return psycopg.connect(f"{BASE}/{db}", row_factory=dict_row)


def pending(conn):
    """Steps not yet applied, in order.

    A step is done when the number of recorded validity events matching its (evidence, new status, trigger, reason)
    reaches the step's occurrence number among identical script steps. The earlier version only tested for existence,
    so a repeated transition (e.g. CHALLENGED -> SUPPORTED -> CHALLENGED) was wrongly treated as already applied.
    """
    rows = conn.execute("SELECT * FROM gt.scenario_events ORDER BY scenario_id, step").fetchall()
    out, seen = [], {}
    for r in rows:
        case = conn.execute("SELECT case_id FROM cases WHERE case_ref=%s", (r["case_ref"],)).fetchone()
        ev = conn.execute("SELECT evidence_id FROM evidence WHERE case_id=%s AND ref=%s", (case["case_id"], r["evidence_ref"])).fetchone()
        key = (ev["evidence_id"], r["expected_status"], r["trigger_code"], r["reason_code"])
        seen[key] = seen.get(key, 0) + 1
        n = conn.execute("""SELECT count(*) AS n FROM evidence_validity_events WHERE evidence_id=%s AND new_status=%s::validity_status
                            AND trigger_code=%s::validity_trigger AND reason_code=%s::validity_reason""",
                         (ev["evidence_id"], r["expected_status"], r["trigger_code"], r["reason_code"])).fetchone()["n"]
        if n < seen[key]:
            out.append(r)
    return out


def apply_step(conn, scenario_id: str, step: int) -> dict:
    r = conn.execute("SELECT * FROM gt.scenario_events WHERE scenario_id=%s AND step=%s", (scenario_id, step)).fetchone()
    if not r:
        raise SystemExit(f"no such step {scenario_id}/{step}")
    conn.execute("SELECT set_config('app.user', %s, false)", (ACTOR,))
    case = conn.execute("SELECT case_id FROM cases WHERE case_ref=%s", (r["case_ref"],)).fetchone()
    cid = case["case_id"]
    pl = r["payload"] or {}
    if "evidence" in pl:
        e = pl["evidence"]
        eid = conn.execute(
            """INSERT INTO evidence(case_id, ref, evidence_type, source, evidence_timestamp, description, provenance)
               VALUES (%s,%s,%s,%s,now(),%s,%s::jsonb) RETURNING evidence_id""",
            (cid, e["ref"], e["evidence_type"], e["source"], e["description"], json.dumps({"origin_root": e["source"]}))).fetchone()["evidence_id"]
        for ref in e.get("entities", []):
            ent = conn.execute("SELECT entity_id FROM entities WHERE case_id=%s AND ref=%s", (cid, ref)).fetchone()
            conn.execute("INSERT INTO evidence_entities(case_id, evidence_id, entity_id) VALUES (%s,%s,%s)", (cid, eid, ent["entity_id"]))
        for n, o in enumerate(pl.get("observations", []), 1):
            s = conn.execute("SELECT entity_id FROM entities WHERE case_id=%s AND ref=%s", (cid, o["subject"])).fetchone()["entity_id"]
            l = conn.execute("SELECT entity_id FROM entities WHERE case_id=%s AND ref=%s", (cid, o["location"])).fetchone()["entity_id"]
            conn.execute("""INSERT INTO location_observations(case_id, ref, subject_entity_id, location_entity_id, observed_from, observed_to,
                            source_kind, source, evidence_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                         (cid, (f"OBS-N{scenario_id[-3:]}{step}{n}" if "@" not in scenario_id else f"OBS-N{__import__('zlib').crc32(scenario_id.encode()) % 10**6:06d}{step}{n}"), s, l, o["from"], o["to"], o["kind"], o["source"], eid))
    target = conn.execute("SELECT evidence_id FROM evidence WHERE case_id=%s AND ref=%s", (cid, r["evidence_ref"])).fetchone()["evidence_id"]
    trig = None
    if r["triggering_evidence_ref"]:
        trig = conn.execute("SELECT evidence_id FROM evidence WHERE case_id=%s AND ref=%s", (cid, r["triggering_evidence_ref"])).fetchone()["evidence_id"]
    ev_id = conn.execute("SELECT change_validity(%s,%s,%s::validity_status,%s::validity_trigger,%s::validity_reason,%s,%s) AS id",
                         (cid, target, r["expected_status"], r["trigger_code"], r["reason_code"], r["description"], trig)).fetchone()["id"]
    conn.commit()
    flagged = [x["finding_key"] for x in conn.execute(
        "SELECT f.finding_key FROM finding_impact_log i JOIN findings f ON f.finding_id=i.affected_finding_id WHERE i.validity_event_id=%s", (ev_id,))]
    return {"scenario": scenario_id, "step": step, "evidence": r["evidence_ref"], "new_status": r["expected_status"],
            "validity_event_id": ev_id, "flagged_findings": sorted(flagged), "expected": sorted(r["expected_affected_finding_keys"])}


if __name__ == "__main__":
    with connect() as c:
        cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
        if cmd == "list":
            for r in pending(c):
                print(f"{r['scenario_id']} step {r['step']}: {r['description']}")
        elif cmd == "apply":
            print(apply_step(c, sys.argv[2], int(sys.argv[3])))
        elif cmd == "next":
            p = pending(c)
            print(apply_step(c, p[0]["scenario_id"], p[0]["step"]) if p else "no pending steps")
