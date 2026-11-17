"""Seed one research database: two independent parameterised storylines + independent ground truth (Phase 2).

Usage (database created first with scripts/init_db.py): python -m synth.research_seed --db NAME --seed 2026 --config research/generation_config.json
Ground truth is written to the isolated `gt` schema (legacy tables, for the existing evaluators) and returned as dicts
for research/ground_truth/seed_<seed>.json. The application role cannot read `gt`.
"""
import argparse
import json
import os
import random
import re
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.correlation.engine import run_and_persist
from app.security import hash_password
from .storylines import build_case

BASE = os.environ.get("CM_ADMIN_URL_BASE", "postgresql://postgres:postgres@localhost:5432")
USERS = [("admin", "ADMINISTRATOR"), ("inv.asha", "INVESTIGATOR"), ("sup.rao", "SUPERVISOR"), ("inv.vikram", "INVESTIGATOR")]
CASES = [("001", "primary", ["admin", "inv.asha", "sup.rao"]), ("002", "secondary", ["admin", "inv.vikram", "sup.rao"])]
ENTITY_TOKEN = re.compile(r"^[PVDO]-")


def key_entities(finding_key: str) -> set:
    """Person/vehicle/device/organisation references in a finding key (RULE|a|b|location); locations and events excluded."""
    return {t for t in finding_key.split("|")[1:] if ENTITY_TOKEN.match(t)}


def touched_entities(conn, case_id: int, evidence_ref: str) -> set:
    """Entities touched by any raw record citing the evidence (data-level attribution; not the correlation lineage)."""
    ev = conn.execute("SELECT evidence_id FROM evidence WHERE case_id=%s AND ref=%s", (case_id, evidence_ref)).fetchone()["evidence_id"]
    rows = conn.execute(
        """SELECT en.ref FROM entities en WHERE en.case_id=%(c)s AND en.entity_type <> 'LOCATION' AND en.entity_id IN (
             SELECT entity_id FROM evidence_entities WHERE case_id=%(c)s AND evidence_id=%(e)s
             UNION SELECT subject_entity_id FROM location_observations WHERE case_id=%(c)s AND evidence_id=%(e)s
             UNION SELECT sender_id FROM communications WHERE case_id=%(c)s AND evidence_id=%(e)s
             UNION SELECT receiver_id FROM communications WHERE case_id=%(c)s AND evidence_id=%(e)s
             UNION SELECT from_entity_id FROM transactions WHERE case_id=%(c)s AND evidence_id=%(e)s
             UNION SELECT to_entity_id FROM transactions WHERE case_id=%(c)s AND evidence_id=%(e)s
             UNION SELECT entity_a FROM relationships WHERE case_id=%(c)s AND evidence_id=%(e)s
             UNION SELECT entity_b FROM relationships WHERE case_id=%(c)s AND evidence_id=%(e)s)""", {"c": case_id, "e": ev}).fetchall()
    return {r["ref"] for r in rows}


def finalize_ground_truth(conn, built: dict, seed: int) -> dict:
    w = built["w"]
    cid, case_ref = w.case_id, built["case_ref"]
    current = sorted(r["finding_key"] for r in conn.execute("SELECT finding_key FROM findings WHERE case_id=%s AND status='CURRENT'", (cid,)))
    persons = sorted(r["ref"] for r in conn.execute("SELECT ref FROM entities WHERE case_id=%s AND entity_type='PERSON'", (cid,)))
    eligible = [p for p in persons if p != built["victim"]]
    leads, rhs = built["leads"], built["red_herrings"]
    lead_refs = {l["ref"] for l in leads}
    special = lead_refs | {r["ref"] for r in rhs} | {built["victim"]} | set(built["witnesses"])
    near_irrelevant = [b["ref"] for b in built["bystanders_near_scene"]]
    other = [p for p in eligible if p not in special and p not in near_irrelevant]
    claims = built["claims"]

    lifecycle, prev = [], {}
    for s in built["steps"]:
        target = s["evidence_ref"]
        touched = touched_entities(conn, cid, target)
        must = sorted(k for k, c in claims.items() if target in c["supporting"])
        neg = [k for k in current if key_entities(k) and not (key_entities(k) & touched)]
        key = (s["scenario_id"], target)
        lifecycle.append({"scenario_id": s["scenario_id"], "step": s["step"], "evidence_ref": target,
                          "expected_previous_status": prev.get(key, "SUPPORTED"), "expected_status": s["expected_status"],
                          "trigger": s["trigger"], "reason": s["reason"], "triggering_evidence_ref": s["triggering"],
                          "description": s["description"], "arriving_evidence": (s["payload"] or {}).get("evidence", {}).get("ref"),
                          "must_flag_keys": must, "must_not_flag_keys": neg,
                          "indeterminate_keys": sorted(set(current) - set(must) - set(neg)), "touched_entities": sorted(touched)})
        prev[key] = s["expected_status"]

    gt = {
        "seed": seed, "case_ref": case_ref, "size": built["size"], "params": built["params"],
        "incident": {"event_ref": "EVT-001", "location": "L-GP1", "time": built["T"].isoformat(), "victim": built["victim"]},
        "eligible_entities": eligible,
        "relevance_grades": {**{p: 0 for p in eligible}, **{l["ref"]: l["grade"] for l in leads}},
        "relevant_leads": leads, "red_herrings": rhs, "near_scene_irrelevant": built["bystanders_near_scene"],
        "other_irrelevant": other, "witnesses": built["witnesses"], "witness2_contradicts_a_lead": built["witness2_contradicts_a_lead"],
        "claims": claims, "findings_at_generation": len(current), "lifecycle": lifecycle,
        "notes": {"ties": "ranking ties must be handled by the evaluator consistently (not by entity reference order)",
                  "must_flag": "claims planted by the generator; independent of finding_evidence_links",
                  "must_not_flag": "findings with no entity touched by records citing the changed evidence"},
    }

    # legacy gt tables (existing evaluators); expected_affected_finding_keys = must_flag
    roles = [(built["victim"], "VICTIM")] + [(l["ref"], l["role"]) for l in leads] + [(r["ref"], "RED_HERRING") for r in rhs] + \
            [(p, "WITNESS") for p in built["witnesses"]] + [(p, "BYSTANDER") for p in built["bystanders"]]
    for ref, role in roles:
        conn.execute("INSERT INTO gt.entity_roles(case_ref, entity_ref, role) VALUES (%s,%s,%s)", (case_ref, ref, role))
    for l in leads:
        conn.execute("INSERT INTO gt.expected_leads(case_ref, entity_ref, rank_hint) VALUES (%s,%s,%s)", (case_ref, l["ref"], l["rank_hint"]))
    for s, lc in zip(built["steps"], lifecycle):
        conn.execute(
            """INSERT INTO gt.scenario_events(scenario_id, step, case_ref, description, evidence_ref, payload, triggering_evidence_ref,
                   expected_status, trigger_code, reason_code, expected_affected_finding_keys)
               VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s)""",
            (f'{s["scenario_id"]}@{case_ref}', s["step"], case_ref, s["description"], s["evidence_ref"], json.dumps(s["payload"]), s["triggering"],
             s["expected_status"], s["trigger"], s["reason"], lc["must_flag_keys"]))
    return gt


def seed_database(db: str, seed: int, cfg: dict) -> dict:
    pw = hash_password(os.environ.get("CM_DEMO_PASSWORD", "crimemind-demo"))
    gts = {}
    with psycopg.connect(f"{BASE}/{db}", row_factory=dict_row) as conn:
        conn.execute("SELECT set_config('app.user','admin',false)")
        users = {n: conn.execute("INSERT INTO users(username, password_hash, role) VALUES (%s,%s,%s) RETURNING user_id", (n, pw, r)).fetchone()["user_id"]
                 for n, r in USERS}
        built_all = []
        for suffix, size, who in CASES[:cfg["cases_per_seed"]]:
            case_ref = f"CASE-{seed}-{suffix}"
            rng = random.Random(f"crimemind-research-{seed}-{suffix}")
            built = build_case(conn, rng, users["admin"], case_ref, f"Research storyline {seed}-{suffix}", cfg, size)
            for u in who:
                conn.execute("INSERT INTO user_case_access(user_id, case_id) VALUES (%s,%s)", (users[u], built["w"].case_id))
            built_all.append(built)
        for built in built_all:
            run_and_persist(conn, {"case_id": built["w"].case_id, "case_ref": built["case_ref"]}, "system.seed")
        for built in built_all:
            gts[built["case_ref"]] = finalize_ground_truth(conn, built, seed)
        conn.commit()
    return gts


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--config", default=str(Path(__file__).resolve().parents[2] / "research" / "generation_config.json"))
    a = ap.parse_args()
    out = seed_database(a.db, a.seed, json.load(open(a.config)))
    print(json.dumps({k: {"leads": [l["ref"] for l in v["relevant_leads"]], "steps": len(v["lifecycle"])} for k, v in out.items()}))
