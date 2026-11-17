"""Seed the database: users, cases, synthetic worlds, first correlation run, hypotheses, ground truth, scenarios.

Usage: python -m synth.seed [--db crimemind] [--seed 2026]   (database must exist: scripts/init_db.py)
Demo password for all seeded users comes from CM_DEMO_PASSWORD (default 'crimemind-demo'). Change it for any shared deployment.
"""
import argparse
import json
import os
import random
import sys

import psycopg
from psycopg.rows import dict_row

from app.correlation.engine import run_and_persist
from app.security import hash_password
from .generator import case_green_park, case_riverside, ts

USERS = [("admin", "ADMINISTRATOR"), ("inv.asha", "INVESTIGATOR"), ("sup.rao", "SUPERVISOR"), ("inv.vikram", "INVESTIGATOR")]


def scenario_defs(P, R, case_ref):
    karan = P["karan"]
    return [
        dict(scenario_id="SC-GPS17-FAULT", step=1, case_ref=case_ref,
             description="A diagnostic report shows GPS-17 had a clock/position fault; Karan's GPS trace is challenged.",
             evidence_ref=R["karan_gps"], triggering="E-D001", expected_status="CHALLENGED",
             trigger="DOCUMENTED_CONTRADICTION", reason="DEVICE_FAULT",
             payload={"evidence": {"ref": "E-D001", "evidence_type": "DEVICE_DIAGNOSTIC", "source": "DIAG:GPS-17",
                                   "description": "Manufacturer diagnostic: unit GPS-17 logged a position/clock fault on 14 Aug; positions unreliable.",
                                   "entities": [karan]}}),
        dict(scenario_id="SC-GPS17-FAULT", step=2, case_ref=case_ref,
             description="Fault confirmed; the GPS-17 trace is invalidated (history preserved).",
             evidence_ref=R["karan_gps"], triggering="E-D001", expected_status="INVALIDATED",
             trigger="CONFIRMED_INVALIDITY", reason="DEVICE_FAULT", payload={}),
        dict(scenario_id="SC-ACCESS-CORRECTED", step=1, case_ref=case_ref,
             description="Orbit Software Park issues a corrected access log; the original is superseded.",
             evidence_ref=R["karan_access"], triggering="E-D002", expected_status="SUPERSEDED",
             trigger="REPLACEMENT_RECORD", reason="CORRECTED_RECORD",
             payload={"evidence": {"ref": "E-D002", "evidence_type": "ACCESS_LOG", "source": "ACCESS:ORBIT-R2",
                                   "description": "Corrected Orbit Software Park badge log: Karan Bhatt in 18:05, out 22:15.",
                                   "entities": [karan]},
                      "observations": [{"subject": karan, "location": "L-W01", "from": ts(2, 18, 5).isoformat(),
                                        "to": ts(2, 22, 15).isoformat(), "kind": "ACCESS_LOG", "source": "ACCESS:ORBIT-R2"}]}),
        dict(scenario_id="SC-WITNESS", step=1, case_ref=case_ref,
             description="A camera clock audit contradicts the witness's timing; the statement is challenged.",
             evidence_ref=R["witness"], triggering="E-D003", expected_status="CHALLENGED",
             trigger="DOCUMENTED_CONTRADICTION", reason="CONTRADICTED_BY_STRONGER_SOURCE",
             payload={"evidence": {"ref": "E-D003", "evidence_type": "CCTV", "source": "CAM-05-AUDIT",
                                   "description": "CAM-05 clock audit: footage times are accurate; no van visible at 21:08.",
                                   "entities": []}}),
        dict(scenario_id="SC-WITNESS", step=2, case_ref=case_ref,
             description="Enhanced footage corroborates the statement; it returns to SUPPORTED.",
             evidence_ref=R["witness"], triggering="E-D004", expected_status="SUPPORTED",
             trigger="CORROBORATION", reason="CORROBORATED",
             payload={"evidence": {"ref": "E-D004", "evidence_type": "CCTV", "source": "CAM-05-ENH",
                                   "description": "Enhanced CAM-05 footage shows a van at the East Gate at 21:08.",
                                   "entities": []}}),
        dict(scenario_id="SC-TIP-RETRACTED", step=1, case_ref=case_ref,
             description="The anonymous tipster retracts the claim.",
             evidence_ref=R["tip"], triggering=None, expected_status="INVALIDATED",
             trigger="CONFIRMED_INVALIDITY", reason="SOURCE_RETRACTION", payload={}),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="crimemind")
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()
    base = os.environ.get("CM_ADMIN_URL_BASE", "postgresql://postgres:postgres@localhost:5432")
    pw = hash_password(os.environ.get("CM_DEMO_PASSWORD", "crimemind-demo"))
    rng = random.Random(args.seed)
    with psycopg.connect(f"{base}/{args.db}", row_factory=dict_row) as conn:
        conn.execute("SELECT set_config('app.user','admin',false)")
        users = {}
        for name, role in USERS:
            users[name] = conn.execute("INSERT INTO users(username, password_hash, role) VALUES (%s,%s,%s) RETURNING user_id",
                                       (name, pw, role)).fetchone()["user_id"]
        g1 = case_green_park(conn, rng, users)
        g2 = case_riverside(conn, rng, users)
        for case, who in ((g1, ["admin", "inv.asha", "sup.rao"]), (g2, ["admin", "inv.vikram"])):
            for u in who:
                conn.execute("INSERT INTO user_case_access(user_id, case_id) VALUES (%s,%s)", (users[u], case["w"].case_id))
        for case in (g1, g2):
            w = case["w"]
            run_and_persist(conn, {"case_id": w.case_id, "case_ref": w.case_ref}, "system.seed")
        w, P, R = g1["w"], g1["P"], g1["refs"]

        def finding(key):
            r = conn.execute("SELECT finding_id FROM findings WHERE case_id=%s AND finding_key=%s AND status<>'OUTDATED'",
                             (w.case_id, key)).fetchone()
            return r["finding_id"] if r else None

        # hypotheses (human-authored propositions, kept distinct from facts)
        def hypothesis(ref, title, keys, evid):
            hid = conn.execute("INSERT INTO hypotheses(case_id, ref, title, created_by) VALUES (%s,%s,%s,'inv.asha') RETURNING hypothesis_id",
                               (w.case_id, ref, title)).fetchone()["hypothesis_id"]
            for k in keys:
                fid = finding(k)
                if fid:
                    conn.execute("INSERT INTO hypothesis_findings(case_id, hypothesis_id, finding_id) VALUES (%s,%s,%s)", (w.case_id, hid, fid))
            for ref_, stance in evid:
                conn.execute("INSERT INTO hypothesis_evidence(case_id, hypothesis_id, evidence_id, stance) VALUES (%s,%s,%s,%s)",
                             (w.case_id, hid, w.ev[ref_], stance))
        hypothesis("H-001", "Rohit Sethi was near the incident location using Dev Malhotra's van",
                   [f"INCIDENT_PROXIMITY_001|{P['rohit']}|EVT-001", f"INCIDENT_PROXIMITY_001|V-01|EVT-001"],
                   [(R["rohit_gps"], "SUPPORTS"), (R["cctv_in"], "SUPPORTS")])
        hypothesis("H-002", "Karan Bhatt was at the incident location",
                   [f"INCIDENT_PROXIMITY_001|{P['karan']}|EVT-001"],
                   [(R["karan_gps"], "SUPPORTS"), (R["karan_access"], "CONTRADICTS")])

        # ---- ground truth (isolated schema) ----
        for role, key in (("VICTIM", "meera"), ("PERPETRATOR", "rohit"), ("ACCOMPLICE", "dev"), ("RED_HERRING", "karan"),
                          ("WITNESS", "sunita"), ("BYSTANDER", "imran"), ("BYSTANDER", "neha"), ("BYSTANDER", "latha")):
            conn.execute("INSERT INTO gt.entity_roles(case_ref, entity_ref, role) VALUES (%s,%s,%s)", (w.case_ref, P[key], role))
        for rank, key in ((1, "rohit"), (2, "dev")):
            conn.execute("INSERT INTO gt.expected_leads(case_ref, entity_ref, rank_hint) VALUES (%s,%s,%s)", (w.case_ref, P[key], rank))
        run = conn.execute("SELECT max(run_id) AS r FROM correlation_runs WHERE case_id=%s", (w.case_id,)).fetchone()["r"]
        for s in scenario_defs(P, R, w.case_ref):
            # intended dependents derived from correlation_evidence (independent of the EVLM trigger path)
            keys = [r["finding_key"] for r in conn.execute(
                """SELECT DISTINCT c.finding_key FROM correlations c JOIN correlation_evidence ce ON ce.correlation_id=c.correlation_id
                   WHERE c.case_id=%s AND c.run_id=%s AND ce.evidence_id=%s AND c.finding_key IS NOT NULL AND c.result_type<>'FACT'""",
                (w.case_id, run, w.ev[s["evidence_ref"]])).fetchall()]
            conn.execute(
                """INSERT INTO gt.scenario_events(scenario_id, step, case_ref, description, evidence_ref, payload, triggering_evidence_ref,
                       expected_status, trigger_code, reason_code, expected_affected_finding_keys)
                   VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)""",
                (s["scenario_id"], s["step"], s["case_ref"], s["description"], s["evidence_ref"], json.dumps(s["payload"]),
                 s["triggering"], s["expected_status"], s["trigger"], s["reason"], keys))
        conn.commit()
    counts = {}
    with psycopg.connect(f"{base}/{args.db}", row_factory=dict_row) as conn:
        for t in ("entities", "location_observations", "communications", "transactions", "relationships", "evidence", "correlations", "findings"):
            counts[t] = conn.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"]
    print("seeded:", counts)


if __name__ == "__main__":
    main()
