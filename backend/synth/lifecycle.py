"""Event-based evaluation of evidence-lifecycle (EVLM) scenarios (research Phase 1).

Why this exists: the original evaluator compared each scripted step's expected status with the evidence's *final*
status. A record that goes SUPPORTED -> CHALLENGED -> INVALIDATED (or CHALLENGED -> SUPPORTED) can never match its
intermediate step, so correct behaviour was scored as wrong. Here every step is matched to the validity EVENT it
should have produced, in order, and checked on its own.

Per applied step the checks are:
  evidence_correct            the event is on the scripted evidence record
  previous_status_valid       previous status equals what the script implies (SUPPORTED, or the prior step's status)
  transition_permitted        (previous, trigger, new) exists in evlm_transition_rules
  new_status_applied          the event's new status is the scripted one
  triggering_evidence_correct triggering evidence ref equals the scripted one (or both absent)
  plus affected-finding precision / recall / F1 against gt.scenario_events.expected_affected_finding_keys.

Conventions for set metrics: precision is 1.0 when nothing was flagged (no false alarms), recall is 1.0 when nothing
was expected, F1 is 0 unless both are positive; both sets empty gives 1.0 / 1.0 / 1.0.

Expected sets are read from gt.* and are never used by the application. NOTE (known limitation, see
research/IMPLEMENTATION_AUDIT.md): the seeded expected_affected_finding_keys are derived from the same dependency
table that EVLM uses, so they test consistency, not independent correctness. Phase 2 replaces them with
generator-emitted expectations.
"""
from collections import defaultdict


def prf(actual: set, expected: set) -> dict:
    tp, fp, fn = len(actual & expected), len(actual - expected), len(expected - actual)
    p = tp / len(actual) if actual else 1.0
    r = tp / len(expected) if expected else 1.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    if not actual and not expected:
        p = r = f1 = 1.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)}


def ranked_q40(conn, case: dict, event_ref: str = "EVT-001", limit: int = 25) -> list[str]:
    from app.sql_engine import execute_question
    conn.execute("SELECT set_config('app.user','system.evaluate',false)")
    res = execute_question(conn, "system.evaluate", case, "Q40", {"event_id": event_ref, "result_limit": limit})
    rows = res.get("rows") or res.get("results") or []
    if not rows:
        return []
    if "entity_ref" not in rows[0]:
        raise KeyError("Q40 result has no entity_ref column; refusing to score an empty ranking silently")
    return [r["entity_ref"] for r in rows]


def _flagged_keys(conn, event_id: int) -> set:
    return {r["finding_key"] for r in conn.execute(
        """SELECT f.finding_key FROM finding_impact_log i JOIN findings f ON f.finding_id=i.affected_finding_id
           WHERE i.validity_event_id=%s""", (event_id,))}


def evaluate_events(conn, case_ref: str | None = None) -> dict:
    """Post-hoc, event-based check of every scripted scenario step against the recorded validity events."""
    steps_gt = conn.execute("SELECT * FROM gt.scenario_events WHERE (%s::text IS NULL OR case_ref=%s) ORDER BY scenario_id, step",
                            (case_ref, case_ref)).fetchall()
    rules = {(r["current_status"], r["trigger_code"], r["new_status"]) for r in
             conn.execute("SELECT current_status::text current_status, trigger_code::text trigger_code, new_status::text new_status FROM evlm_transition_rules")}
    cursor = defaultdict(lambda: 0)            # (scenario, evidence) -> last matched event_id
    prev_status = {}                           # (scenario, evidence) -> status implied by the previous step
    out, tp = [], dict(tp=0, fp=0, fn=0)
    flagged_total = expected_total = 0
    for s in steps_gt:
        case = conn.execute("SELECT case_id FROM cases WHERE case_ref=%s", (s["case_ref"],)).fetchone()
        ev = conn.execute("SELECT evidence_id FROM evidence WHERE case_id=%s AND ref=%s", (case["case_id"], s["evidence_ref"])).fetchone()
        key = (s["scenario_id"], s["evidence_ref"])
        expected_prev = prev_status.get(key, "SUPPORTED")
        prev_status[key] = s["expected_status"]
        row = {"scenario_id": s["scenario_id"], "step": s["step"], "evidence_ref": s["evidence_ref"], "expected_status": s["expected_status"]}
        e = conn.execute(
            """SELECT v.*, v.previous_status::text ps, v.new_status::text ns, v.trigger_code::text tc, v.reason_code::text rc, t.ref AS trig_ref
               FROM evidence_validity_events v LEFT JOIN evidence t ON t.case_id=v.case_id AND t.evidence_id=v.triggering_evidence_id
               WHERE v.case_id=%s AND v.evidence_id=%s AND v.event_id > %s AND v.new_status=%s::validity_status
                 AND v.trigger_code=%s::validity_trigger AND v.reason_code=%s::validity_reason
               ORDER BY v.event_id LIMIT 1""",
            (case["case_id"], ev["evidence_id"], cursor[key], s["expected_status"], s["trigger_code"], s["reason_code"])).fetchone()
        if not e:
            row.update({"applied": False, "passed": None})
            out.append(row)
            continue
        cursor[key] = e["event_id"]
        flagged = _flagged_keys(conn, e["event_id"])
        expected = set(s["expected_affected_finding_keys"] or [])
        m = prf(flagged, expected)
        checks = {
            "evidence_correct": e["evidence_id"] == ev["evidence_id"],
            "previous_status_valid": e["ps"] == expected_prev,
            "transition_permitted": (e["ps"], e["tc"], e["ns"]) in rules,
            "new_status_applied": e["ns"] == s["expected_status"],
            "triggering_evidence_correct": (e["trig_ref"] or None) == (s["triggering_evidence_ref"] or None),
        }
        row.update({"applied": True, "event_id": e["event_id"], "previous_status": e["ps"], "checks": checks,
                    "flagged": sorted(flagged), "expected": sorted(expected), "false_positives": sorted(flagged - expected),
                    "false_negatives": sorted(expected - flagged), **m,
                    "transition_ok": all(checks.values()), "passed": all(checks.values()) and m["f1"] == 1.0})
        for k in tp:
            tp[k] += m[k]
        flagged_total += len(flagged)
        expected_total += len(expected)
        out.append(row)
    applied = [r for r in out if r["applied"]]
    agg_p = tp["tp"] / (tp["tp"] + tp["fp"]) if (tp["tp"] + tp["fp"]) else 1.0
    agg_r = tp["tp"] / (tp["tp"] + tp["fn"]) if (tp["tp"] + tp["fn"]) else 1.0
    if not applied:      # nothing to score: report that, instead of vacuous perfect values
        return {"steps": out, "summary": {"steps_total": len(out), "steps_applied": 0, "steps_not_applied": len(out), "steps_passed": 0,
                                          "lifecycle_transition_accuracy": None, "affected_finding_precision_micro": None,
                                          "affected_finding_recall_micro": None, "affected_finding_f1_micro": None,
                                          "unnecessary_recomputation_rate": None, "missed_recomputation_rate": None}}
    return {
        "steps": out,
        "summary": {
            "steps_total": len(out), "steps_applied": len(applied), "steps_not_applied": len(out) - len(applied),
            "steps_passed": sum(1 for r in applied if r["passed"]),
            "lifecycle_transition_accuracy": round(sum(r["transition_ok"] for r in applied) / len(applied), 4) if applied else None,
            "affected_finding_precision_micro": round(agg_p, 4), "affected_finding_recall_micro": round(agg_r, 4),
            "affected_finding_f1_micro": round(2 * agg_p * agg_r / (agg_p + agg_r), 4) if (agg_p + agg_r) else 0.0,
            "unnecessary_recomputation_rate": round(tp["fp"] / flagged_total, 4) if flagged_total else 0.0,
            "missed_recomputation_rate": round(tp["fn"] / expected_total, 4) if expected_total else 0.0,
        },
    }


def history_integrity(conn, case_id: int) -> dict:
    """History must be preserved: event chains are consistent, finding versions are contiguous with one live version,
    and no CURRENT finding rests on evidence that is not SUPPORTED."""
    problems = defaultdict(list)
    chains = defaultdict(list)
    for v in conn.execute("SELECT evidence_id, previous_status::text ps, new_status::text ns, event_id FROM evidence_validity_events WHERE case_id=%s ORDER BY event_id", (case_id,)):
        chains[v["evidence_id"]].append(v)
    for eid, evs in chains.items():
        prev = "SUPPORTED"
        for v in evs:
            if v["ps"] != prev:
                problems["broken_event_chain"].append({"evidence_id": eid, "event_id": v["event_id"], "expected_previous": prev, "found": v["ps"]})
            prev = v["ns"]
        cur = conn.execute("SELECT validity_status::text s FROM evidence WHERE evidence_id=%s", (eid,)).fetchone()
        if cur is None:
            problems["evidence_missing"].append(eid)
        elif cur["s"] != prev:
            problems["evidence_status_differs_from_last_event"].append({"evidence_id": eid, "status": cur["s"], "last_event": prev})
    versions = defaultdict(list)
    for f in conn.execute("SELECT finding_key, version, status::text st FROM findings WHERE case_id=%s", (case_id,)):
        versions[f["finding_key"]].append(f)
    for k, fs in versions.items():
        vs = sorted(f["version"] for f in fs)
        if vs != list(range(1, len(vs) + 1)):
            problems["non_contiguous_versions"].append(k)
        if sum(f["st"] != "OUTDATED" for f in fs) > 1:
            problems["multiple_live_versions"].append(k)
    stale = conn.execute(
        """SELECT DISTINCT f.finding_key FROM findings f JOIN finding_evidence_links l ON l.finding_id=f.finding_id AND l.case_id=f.case_id
           JOIN evidence e ON e.evidence_id=l.evidence_id AND e.case_id=l.case_id
           WHERE f.case_id=%s AND f.status='CURRENT' AND e.validity_status<>'SUPPORTED'""", (case_id,)).fetchall()
    if stale:
        problems["current_finding_on_non_supported_evidence"] = sorted(r["finding_key"] for r in stale)
    return {"ok": not problems, "problems": dict(problems), "evidence_with_events": len(chains), "finding_keys": len(versions)}


def _snap(conn, case_id: int) -> dict:
    return {"findings": {r["finding_id"]: (r["finding_key"], r["status"]) for r in
                         conn.execute("SELECT finding_id, finding_key, status::text status FROM findings WHERE case_id=%s", (case_id,))},
            "evidence": {r["ref"]: r["s"] for r in conn.execute("SELECT ref, validity_status::text s FROM evidence WHERE case_id=%s", (case_id,))}}


def run_with_snapshots(conn, scenario, case_ref: str, recompute: bool = True, ranking_k: int = 5) -> dict:
    """Apply every pending scripted step through the system's own change_validity(), snapshotting state around each
    step to verify that nothing unrelated moved, then (optionally) run the explicit recomputation and verify it."""
    from app.correlation.engine import recompute_pending
    case = conn.execute("SELECT case_id, case_ref FROM cases WHERE case_ref=%s", (case_ref,)).fetchone()
    per_step = []
    ranking = {"initial": ranked_q40(conn, case)[:ranking_k]}
    while True:
        pend = [r for r in scenario.pending(conn) if r["case_ref"] == case_ref]
        if not pend:
            break
        s = pend[0]
        before = _snap(conn, case["case_id"])
        res = scenario.apply_step(conn, s["scenario_id"], s["step"])
        after = _snap(conn, case["case_id"])
        expected = set(res["expected"])
        changed_f = sorted({before["findings"][fid][0] for fid, (k, st) in after["findings"].items()
                            if fid in before["findings"] and before["findings"][fid][1] != st})
        changed_e = sorted(ref for ref, st in after["evidence"].items() if ref in before["evidence"] and before["evidence"][ref] != st)
        top = ranked_q40(conn, case)[:ranking_k]
        ranking[f"{s['scenario_id']}#{s['step']}"] = top
        per_step.append({"scenario_id": s["scenario_id"], "step": s["step"], "evidence_ref": s["evidence_ref"],
                         "findings_newly_flagged": changed_f,
                         "unrelated_findings_changed": sorted(set(changed_f) - expected),
                         "unrelated_evidence_changed": [r for r in changed_e if r != s["evidence_ref"]],
                         "ranking_top": top})
    rec = None
    if recompute:
        conn.execute("SELECT set_config('app.user','system.evaluate',false)")
        pre = _snap(conn, case["case_id"])
        outcomes = recompute_pending(conn, case, "system.evaluate")
        conn.commit()
        post = _snap(conn, case["case_id"])
        bad = []
        for o in outcomes:
            olds = [(fid, st) for fid, (k, st) in post["findings"].items() if k == o["finding_key"]]
            if o["outcome"] == "RECOMPUTED":
                if not any(st == "CURRENT" for _, st in olds) or sum(1 for _, st in olds if st == "OUTDATED") < 1:
                    bad.append({"finding_key": o["finding_key"], "problem": "old version not retained as OUTDATED or new version not CURRENT"})
        still = [k for fid, (k, st) in post["findings"].items() if st == "RECOMPUTE_REQUIRED"]
        rec = {"outcomes": outcomes, "recomputed": sum(o["outcome"] == "RECOMPUTED" for o in outcomes),
               "retired": sum(o["outcome"] == "RETIRED_NO_SUPPORT" for o in outcomes), "still_recompute_required": still,
               "history_retained_problems": bad, "finding_rows_before": len(pre["findings"]), "finding_rows_after": len(post["findings"])}
        ranking["after_recompute"] = ranked_q40(conn, case)[:ranking_k]
    return {"case_ref": case_ref, "steps": per_step, "recompute": rec, "ranking_top_by_stage": ranking,
            "history": history_integrity(conn, case["case_id"]), "events": evaluate_events(conn, case_ref)}
