"""Dataset validation (Phase 2): reject incomplete datasets, inconsistent references and label leakage."""
import re

import psycopg
from psycopg.rows import dict_row

LEAK = re.compile(r"perpetrator|accomplice|red[ _]herring|decoy|ground[ _]truth|relevant lead|true lead|misleading lead", re.I)
REQUIRED = ["seed", "case_ref", "incident", "eligible_entities", "relevance_grades", "relevant_leads", "red_herrings",
            "near_scene_irrelevant", "other_irrelevant", "claims", "lifecycle", "params"]


def validate_case(conn, gt: dict) -> list[str]:
    P = []
    for k in REQUIRED:
        if k not in gt:
            P.append(f"ground truth is missing '{k}'")
    if P:
        return P
    case = conn.execute("SELECT case_id FROM cases WHERE case_ref=%s", (gt["case_ref"],)).fetchone()
    if not case:
        return [f"case {gt['case_ref']} does not exist"]
    cid = case["case_id"]
    persons = {r["ref"] for r in conn.execute("SELECT ref FROM entities WHERE case_id=%s AND entity_type='PERSON'", (cid,))}
    evidence = {r["ref"]: r["validity_status"] for r in conn.execute("SELECT ref, validity_status::text FROM evidence WHERE case_id=%s", (cid,))}
    current = {r["finding_key"] for r in conn.execute("SELECT finding_key FROM findings WHERE case_id=%s AND status='CURRENT'", (cid,))}
    victim = gt["incident"]["victim"]
    leads, rhs = gt["relevant_leads"], gt["red_herrings"]
    if not leads:
        P.append("no relevant leads")
    if not rhs:
        P.append("no red herrings")
    if victim not in persons:
        P.append(f"victim {victim} is not a person in the case")
    if sorted(gt["eligible_entities"]) != sorted(persons - {victim}):
        P.append("eligible entity set differs from the persons in the case (minus victim)")
    ids = [l["ref"] for l in leads] + [r["ref"] for r in rhs] + [b["ref"] for b in gt["near_scene_irrelevant"]]
    if len(ids) != len(set(ids)):
        P.append("an entity holds more than one role")
    for ref in ids + [victim]:
        if ref not in persons:
            P.append(f"{ref} is not a person in the case")
    if set(gt["relevance_grades"]) != set(gt["eligible_entities"]):
        P.append("relevance grades do not cover exactly the eligible entities")
    for l in leads:
        if not l["supporting_evidence"]:
            P.append(f"lead {l['ref']} has no supporting evidence")
    for r in rhs:
        if not r["supporting_evidence"]:
            P.append(f"red herring {r['ref']} has no apparent supporting evidence")
        if not r["contradicting_evidence"]:
            P.append(f"red herring {r['ref']} has no contradicting evidence")
    for who in leads + rhs:
        for e in who["supporting_evidence"] + who["contradicting_evidence"]:
            if e not in evidence:
                P.append(f"{who['ref']} references unknown evidence {e}")
    for k, c in gt["claims"].items():
        if k not in current:
            P.append(f"planted claim {k} was not produced as a finding by the correlation engine")
        for e in c["supporting"]:
            if e not in evidence:
                P.append(f"claim {k} cites unknown evidence {e}")
    # lifecycle script consistency
    rules = {(r["current_status"], r["trigger_code"], r["new_status"]) for r in conn.execute(
        "SELECT current_status::text current_status, trigger_code::text trigger_code, new_status::text new_status FROM evlm_transition_rules")}
    arriving = {s["arriving_evidence"] for s in gt["lifecycle"] if s["arriving_evidence"]}
    for s in gt["lifecycle"]:
        t = f"{s['scenario_id']}#{s['step']}"
        if s["evidence_ref"] not in evidence:
            P.append(f"{t}: target evidence {s['evidence_ref']} does not exist")
        if (s["expected_previous_status"], s["trigger"], s["expected_status"]) not in rules:
            P.append(f"{t}: transition {s['expected_previous_status']} -> {s['expected_status']} via {s['trigger']} is not permitted by the EVLM rules")
        trig = s["triggering_evidence_ref"]
        if trig and trig not in evidence and trig not in arriving:
            P.append(f"{t}: triggering evidence {trig} neither exists nor arrives")
        if not set(s["must_flag_keys"]) <= current:
            P.append(f"{t}: must-flag keys not among current findings")
        if set(s["must_flag_keys"]) & set(s["must_not_flag_keys"]):
            P.append(f"{t}: must-flag and must-not-flag overlap")
        if not s["must_not_flag_keys"]:
            P.append(f"{t}: no must-not-flag findings, so unrelated stability cannot be tested")
    return P


def check_no_leakage(conn, case_refs: list[str]) -> list[str]:
    """Role words must not appear in anything a ranking method can read (entities, evidence, events, provenance)."""
    P = []
    q = """SELECT 'entity' k, ref, display_name || ' ' || attributes::text AS t FROM entities WHERE case_id=ANY(%(c)s)
           UNION ALL SELECT 'evidence', ref, coalesce(description,'') || ' ' || source || ' ' || provenance::text FROM evidence WHERE case_id=ANY(%(c)s)
           UNION ALL SELECT 'event', ref, coalesce(description,'') FROM events WHERE case_id=ANY(%(c)s)
           UNION ALL SELECT 'case', case_ref, title FROM cases WHERE case_ref=ANY(%(r)s)"""
    cids = [r["case_id"] for r in conn.execute("SELECT case_id FROM cases WHERE case_ref=ANY(%s)", (case_refs,))]
    for r in conn.execute(q, {"c": cids, "r": case_refs}):
        if LEAK.search(r["t"] or ""):
            P.append(f"label word in {r['k']} {r['ref']}")
    return P


def check_gt_isolation(app_url: str) -> list[str]:
    """The application role must not be able to read ground truth."""
    try:
        with psycopg.connect(app_url) as c:
            c.execute("SELECT 1 FROM gt.expected_leads LIMIT 1")
        return ["application role can read schema gt"]
    except psycopg.Error:
        return []
