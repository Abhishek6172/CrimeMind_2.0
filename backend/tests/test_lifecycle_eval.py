"""Regression tests for the event-based lifecycle evaluation and for EVLM behaviour (research Phase 1).

Tests run in file order on one freshly seeded database (module-scoped fixture); later tests rely on earlier state
only where noted.
"""
import psycopg
import pytest

from app.correlation.engine import recompute_pending
from synth import scenario
from synth.lifecycle import evaluate_events, history_integrity, prf, run_with_snapshots

from .conftest import C1, TEST_DB, admin_conn


def _case(c):
    return c.execute("SELECT case_id, case_ref FROM cases WHERE case_ref=%s", (C1,)).fetchone()


def _change(c, case_id, ev_ref, new, trig, reason, trig_ref=None, actor="sup.rao", just=None):
    eid = c.execute("SELECT evidence_id FROM evidence WHERE case_id=%s AND ref=%s", (case_id, ev_ref)).fetchone()["evidence_id"]
    tid = None
    if trig_ref:
        tid = c.execute("SELECT evidence_id FROM evidence WHERE case_id=%s AND ref=%s", (case_id, trig_ref)).fetchone()["evidence_id"]
    return c.execute("SELECT change_validity(%s,%s,%s::validity_status,%s::validity_trigger,%s::validity_reason,%s,%s,%s) AS id",
                     (case_id, eid, new, trig, reason, just, tid, actor)).fetchone()["id"]


def _status(c, case_id, ref):
    return c.execute("SELECT validity_status::text s FROM evidence WHERE case_id=%s AND ref=%s", (case_id, ref)).fetchone()["s"]


def _untouched_evidence(c, case_id, n=2):
    """SUPPORTED evidence that backs a live finding, is not used by any scripted scenario, and has no validity events yet."""
    scripted = {r["evidence_ref"] for r in c.execute("SELECT evidence_ref FROM gt.scenario_events")} | \
               {r["triggering_evidence_ref"] for r in c.execute("SELECT triggering_evidence_ref FROM gt.scenario_events") if r["triggering_evidence_ref"]}
    rows = c.execute(
        """SELECT e.ref, count(DISTINCT f.finding_key) AS nf FROM evidence e
           JOIN finding_evidence_links l ON l.evidence_id=e.evidence_id AND l.case_id=e.case_id
           JOIN findings f ON f.finding_id=l.finding_id AND f.case_id=l.case_id AND f.status='CURRENT'
           WHERE e.case_id=%s AND e.validity_status='SUPPORTED' AND e.ref <> ALL(%s)
             AND NOT EXISTS (SELECT 1 FROM evidence_validity_events v WHERE v.evidence_id=e.evidence_id)
           GROUP BY e.ref HAVING count(DISTINCT f.finding_key) BETWEEN 1 AND 6 ORDER BY e.ref""", (case_id, sorted(scripted))).fetchall()
    assert len(rows) >= n
    return [r["ref"] for r in rows[:n]]


# ---------------------------------------------------------------- metric conventions
def test_prf_conventions_match_manual_examples():
    assert prf({"a", "b", "c"}, {"a", "b", "d"}) == {"tp": 2, "fp": 1, "fn": 1, "precision": 0.6667, "recall": 0.6667, "f1": 0.6667}
    assert prf(set(), set())["f1"] == 1.0                      # nothing expected, nothing flagged
    assert prf({"x"}, set())["precision"] == 0.0 and prf({"x"}, set())["f1"] == 0.0   # false alarm only
    assert prf(set(), {"x"})["recall"] == 0.0 and prf(set(), {"x"})["f1"] == 0.0       # missed everything


# ---------------------------------------------------------------- full scripted run, intermediate states
def test_not_applied_steps_are_reported_not_scored(world):
    with admin_conn() as c:
        r = evaluate_events(c, C1)
    assert r["summary"]["steps_total"] == 6 and r["summary"]["steps_applied"] == 0
    assert all(s["passed"] is None for s in r["steps"])


def test_event_based_evaluation_scores_intermediate_states_correctly(world):
    with admin_conn() as c:
        res = run_with_snapshots(c, scenario, C1)
        case_id = _case(c)["case_id"]
        final = {r["evidence_ref"]: _status(c, case_id, r["evidence_ref"]) for r in c.execute("SELECT DISTINCT evidence_ref FROM gt.scenario_events")}
        gt = c.execute("SELECT scenario_id, step, evidence_ref, expected_status FROM gt.scenario_events").fetchall()
    ev = res["events"]
    assert ev["summary"]["steps_applied"] == 6 and ev["summary"]["steps_passed"] == 6, ev["summary"]
    assert ev["summary"]["lifecycle_transition_accuracy"] == 1.0
    assert ev["summary"]["affected_finding_f1_micro"] == 1.0
    assert ev["summary"]["unnecessary_recomputation_rate"] == 0.0 and ev["summary"]["missed_recomputation_rate"] == 0.0
    # the legacy "compare each step to the FINAL status" method would have scored these steps as failures
    legacy_wrong = [(g["scenario_id"], g["step"]) for g in gt if final[g["evidence_ref"]] != g["expected_status"]]
    assert ("SC-GPS17-FAULT", 1) in legacy_wrong and ("SC-WITNESS", 1) in legacy_wrong
    by = {(s["scenario_id"], s["step"]): s for s in ev["steps"]}
    assert by[("SC-GPS17-FAULT", 2)]["previous_status"] == "CHALLENGED"          # chain SUPPORTED -> CHALLENGED -> INVALIDATED
    assert by[("SC-WITNESS", 2)]["previous_status"] == "CHALLENGED"              # chain SUPPORTED -> CHALLENGED -> SUPPORTED


def test_unrelated_state_is_stable_at_every_step(world):
    # re-reads the run above through the persisted log: nothing outside the scripted evidence changed status
    with admin_conn() as c:
        case_id = _case(c)["case_id"]
        changed = c.execute("""SELECT DISTINCT e.ref FROM evidence_validity_events v JOIN evidence e ON e.evidence_id=v.evidence_id
                               WHERE v.case_id=%s""", (case_id,)).fetchall()
        scripted = {r["evidence_ref"] for r in c.execute("SELECT evidence_ref FROM gt.scenario_events")}
    assert {r["ref"] for r in changed} == scripted


def test_recompute_uses_latest_valid_evidence_and_keeps_history(world):
    with admin_conn() as c:
        case = _case(c)
        h = history_integrity(c, case["case_id"])
        assert h["ok"], h["problems"]
        outdated = c.execute("SELECT count(*) n FROM findings WHERE case_id=%s AND status='OUTDATED'", (case["case_id"],)).fetchone()["n"]
        assert outdated > 0, "recomputation must retain old versions as OUTDATED rather than overwrite them"
        pending = c.execute("SELECT count(*) n FROM findings WHERE case_id=%s AND status='RECOMPUTE_REQUIRED'", (case["case_id"],)).fetchone()["n"]
        assert pending == 0


# ---------------------------------------------------------------- invalid and repeated transitions
def test_invalid_transitions_are_rejected_and_change_nothing(world):
    with admin_conn() as c:
        case_id = _case(c)["case_id"]
        superseded = c.execute("SELECT ref FROM evidence WHERE case_id=%s AND validity_status='SUPERSEDED' LIMIT 1", (case_id,)).fetchone()["ref"]
        ref, other = _untouched_evidence(c, case_id)
        n0 = c.execute("SELECT count(*) n FROM evidence_validity_events").fetchone()["n"]
    bad = [
        (superseded, "SUPPORTED", "CORROBORATION", "CORROBORATED", other, "sup.rao", None),                       # SUPERSEDED is terminal
        (ref, "SUPPORTED", "CORROBORATION", "CORROBORATED", other, "sup.rao", None),                              # SUPPORTED -> SUPPORTED
        (ref, "INVALIDATED", "DOCUMENTED_CONTRADICTION", "DEVICE_FAULT", None, "sup.rao", None),                  # wrong target for trigger
        (ref, "CHALLENGED", "DOCUMENTED_CONTRADICTION", "SOURCE_RETRACTION", None, "sup.rao", None),              # reason not allowed
        (ref, "SUPERSEDED", "REPLACEMENT_RECORD", "CORRECTED_RECORD", None, "sup.rao", None),                     # needs triggering evidence
        (ref, "INVALIDATED", "MANUAL_OVERRIDE", "MANUAL_REVIEW", None, "inv.asha", "Investigators may not override"),  # role
        (ref, "INVALIDATED", "MANUAL_OVERRIDE", "MANUAL_REVIEW", None, "sup.rao", "short"),                       # justification too short
        (ref, "CHALLENGED", "DOCUMENTED_CONTRADICTION", "DEVICE_FAULT", None, "inv.vikram", None),                # actor has no access to case
    ]
    for ev_ref, new, trig, reason, trig_ref, actor, just in bad:
        with admin_conn() as c, pytest.raises(psycopg.Error):
            _change(c, _case(c)["case_id"], ev_ref, new, trig, reason, trig_ref, actor, just)
    with admin_conn() as c:
        assert c.execute("SELECT count(*) n FROM evidence_validity_events").fetchone()["n"] == n0
        assert _status(c, _case(c)["case_id"], ref) == "SUPPORTED" and _status(c, _case(c)["case_id"], superseded) == "SUPERSEDED"


def test_repeated_transition_is_rejected(world):
    with admin_conn() as c:
        case_id = _case(c)["case_id"]
        ref, _ = _untouched_evidence(c, case_id)
        c.execute("SELECT set_config('app.user','sup.rao',false)")
        _change(c, case_id, ref, "CHALLENGED", "DOCUMENTED_CONTRADICTION", "DEVICE_FAULT")
        c.commit()
    with admin_conn() as c, pytest.raises(psycopg.Error):        # the same transition again, from CHALLENGED
        _change(c, _case(c)["case_id"], ref, "CHALLENGED", "DOCUMENTED_CONTRADICTION", "DEVICE_FAULT")
    with admin_conn() as c:
        n = c.execute("SELECT count(*) n FROM evidence_validity_events v JOIN evidence e ON e.evidence_id=v.evidence_id WHERE e.ref=%s", (ref,)).fetchone()["n"]
        assert n == 1


# ---------------------------------------------------------------- retraction and reinstatement
def test_retraction_and_reinstatement_flags_then_restores_findings(world):
    with admin_conn() as c:
        case = _case(c)
        case_id = case["case_id"]
        ref = c.execute("SELECT e.ref FROM evidence e WHERE e.case_id=%s AND e.validity_status='CHALLENGED' AND e.ref NOT IN (SELECT evidence_ref FROM gt.scenario_events)",
                        (case_id,)).fetchone()["ref"]                        # challenged by the previous test
        trigger = [r for r in _untouched_evidence(c, case_id, 3) if r != ref][0]
        keys = {r["finding_key"] for r in c.execute(
            """SELECT f.finding_key FROM findings f JOIN finding_evidence_links l ON l.finding_id=f.finding_id AND l.case_id=f.case_id
               JOIN evidence e ON e.evidence_id=l.evidence_id AND e.case_id=l.case_id
               WHERE f.case_id=%s AND e.ref=%s AND f.status IN ('CURRENT','RECOMPUTE_REQUIRED')""", (case_id, ref))}
        assert keys
        status = {r["finding_key"]: r["status"] for r in c.execute("SELECT finding_key, status::text status FROM findings WHERE case_id=%s AND status<>'OUTDATED'", (case_id,))}
        assert all(status[k] == "RECOMPUTE_REQUIRED" for k in keys), "challenge must flag every dependent finding"
        unrelated = {k: v for k, v in status.items() if k not in keys}
        c.execute("SELECT set_config('app.user','sup.rao',false)")
        _change(c, case_id, ref, "SUPPORTED", "CORROBORATION", "CORROBORATED", trigger)         # reinstatement
        c.commit()
        assert _status(c, case_id, ref) == "SUPPORTED"
        outcomes = recompute_pending(c, case, "system.evaluate")
        c.commit()
        flagged_now = {o["finding_key"] for o in outcomes}
        assert keys <= flagged_now
        after = {r["finding_key"]: (r["status"], r["version"]) for r in c.execute(
            "SELECT finding_key, status::text status, version FROM findings WHERE case_id=%s AND status<>'OUTDATED'", (case_id,))}
        assert all(after[k][0] == "CURRENT" for k in keys if k in after)
        for k, st in unrelated.items():
            if k not in flagged_now:
                assert after[k][0] == st, f"unrelated finding {k} changed"
        chain = [(r["previous_status"], r["new_status"]) for r in c.execute(
            "SELECT previous_status::text, new_status::text FROM evidence_validity_events v JOIN evidence e ON e.evidence_id=v.evidence_id WHERE e.ref=%s ORDER BY event_id", (ref,))]
        assert chain == [("SUPPORTED", "CHALLENGED"), ("CHALLENGED", "SUPPORTED")]
        assert history_integrity(c, case_id)["ok"]


# ---------------------------------------------------------------- history preservation
def test_history_cannot_be_rewritten_or_deleted(world):
    with admin_conn() as c:
        case_id = _case(c)["case_id"]
        n_ev = c.execute("SELECT count(*) n FROM evidence WHERE case_id=%s", (case_id,)).fetchone()["n"]
    for sql in ("UPDATE evidence_validity_events SET justification='x'", "DELETE FROM evidence_validity_events",
                "DELETE FROM evidence", "DELETE FROM findings", "UPDATE evidence SET validity_status='SUPPORTED' WHERE validity_status='INVALIDATED'"):
        with admin_conn() as c, pytest.raises(psycopg.Error):
            c.execute(sql)
    with admin_conn() as c:
        assert c.execute("SELECT count(*) n FROM evidence WHERE case_id=%s", (case_id,)).fetchone()["n"] == n_ev


# ---------------------------------------------------------------- repeated script steps are applied once each
def test_pending_counts_occurrences_of_identical_script_steps(world):
    with admin_conn() as c:
        case_id = _case(c)["case_id"]
        target, trig = _untouched_evidence(c, case_id, 2)
        base = dict(case_ref=C1, evidence_ref=target, payload="{}")
        rows = [(1, "CHALLENGED", "DOCUMENTED_CONTRADICTION", "DEVICE_FAULT", None),
                (2, "SUPPORTED", "CORROBORATION", "CORROBORATED", trig),
                (3, "CHALLENGED", "DOCUMENTED_CONTRADICTION", "DEVICE_FAULT", None)]
        for step, st, tc, rc, tr in rows:
            c.execute("""INSERT INTO gt.scenario_events(scenario_id, step, case_ref, description, evidence_ref, payload, triggering_evidence_ref,
                         expected_status, trigger_code, reason_code, expected_affected_finding_keys)
                         VALUES ('TEST-REPEAT',%s,%s,'repeat',%s,'{}'::jsonb,%s,%s,%s,%s,'{}')""", (step, C1, target, tr, st, tc, rc))
        c.commit()
    try:
        def pend():
            with admin_conn() as c:
                return [r["step"] for r in scenario.pending(c) if r["scenario_id"] == "TEST-REPEAT"]
        assert pend() == [1, 2, 3]
        for expected_next in (1, 2):
            with admin_conn() as c:
                scenario.apply_step(c, "TEST-REPEAT", expected_next)
            assert pend()[0] == expected_next + 1
        # step 3 repeats step 1's transition; the old existence check would already consider it done
        assert pend() == [3]
        with admin_conn() as c:
            scenario.apply_step(c, "TEST-REPEAT", 3)
            assert _status(c, case_id, target) == "CHALLENGED"
            ev = evaluate_events(c, C1)
        assert pend() == []
        mine = [s for s in ev["steps"] if s["scenario_id"] == "TEST-REPEAT"]
        assert [s["applied"] for s in mine] == [True, True, True]
        assert [s["previous_status"] for s in mine] == ["SUPPORTED", "CHALLENGED", "SUPPORTED"]
        assert all(s["transition_ok"] for s in mine)
    finally:
        with admin_conn() as c:
            c.execute("DELETE FROM gt.scenario_events WHERE scenario_id='TEST-REPEAT'")
            c.commit()


# ---------------------------------------------------------------- negative controls: the evaluator can fail
def test_evaluator_detects_wrong_expectations_and_wrong_chains(world):
    """Tamper with the expected sets inside a transaction that is never committed; the evaluator must report errors."""
    with admin_conn() as c:
        row = c.execute("SELECT scenario_id, step, expected_affected_finding_keys k FROM gt.scenario_events WHERE cardinality(expected_affected_finding_keys) >= 2 LIMIT 1").fetchone()
        keep, drop = row["k"][0], row["k"][1]
        c.execute("UPDATE gt.scenario_events SET expected_affected_finding_keys=%s WHERE scenario_id=%s AND step=%s",
                  ([keep, "BOGUS|P-999|EVT-001"], row["scenario_id"], row["step"]))
        r = evaluate_events(c, C1)
        s = next(x for x in r["steps"] if x["scenario_id"] == row["scenario_id"] and x["step"] == row["step"])
        assert s["passed"] is False and s["f1"] < 1.0
        assert "BOGUS|P-999|EVT-001" in s["false_negatives"] and s["false_positives"]
        assert r["summary"]["unnecessary_recomputation_rate"] > 0 and r["summary"]["missed_recomputation_rate"] > 0
        c.rollback()
    with admin_conn() as c:   # wrong scripted triggering evidence
        c.execute("UPDATE gt.scenario_events SET triggering_evidence_ref='E-D999' WHERE scenario_id='SC-WITNESS' AND step=2")
        r = evaluate_events(c, C1)
        s = next(x for x in r["steps"] if x["scenario_id"] == "SC-WITNESS" and x["step"] == 2)
        assert s["checks"]["triggering_evidence_correct"] is False and s["transition_ok"] is False
        c.rollback()
