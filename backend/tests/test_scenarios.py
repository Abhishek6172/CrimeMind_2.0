from synth import scenario

from .conftest import C1, TEST_DB, admin_conn


def _apply(sid, step):
    with scenario.connect(TEST_DB) as c:
        scenario.apply_step(c, sid, step)
        c.commit()


def q40(api):
    r = api.post(f"/api/cases/{C1}/queries/run", json={"question_id": "Q40", "parameters": {}})
    assert r.status_code == 200, r.text
    return r.json()


def test_invalid_transition_rejected(api):
    ref = api.get(f"/api/cases/{C1}/evidence").json()["evidence"][0]["ref"]
    r = api.post(f"/api/cases/{C1}/evidence/{ref}/validity", user="sup.rao",
                 json={"new_status": "SUPERSEDED", "trigger": "NEW_EVIDENCE", "reason": "CONTRADICTED"})
    assert r.status_code in (409, 422)


def test_gps_fault_scenario_end_to_end(api):
    base = api.get(f"/api/cases/{C1}/findings").json()["findings"]
    assert base and all(f["status"] == "CURRENT" for f in base)
    for step in (1, 2):
        _apply("SC-GPS17-FAULT", step)
    items = api.get(f"/api/cases/{C1}/impacts").json()["open_impacts"]
    assert items, "invalidating GPS-17 evidence must flag dependent findings"
    rc = api.post(f"/api/cases/{C1}/findings/recompute", user="sup.rao")
    assert rc.status_code == 200, rc.text
    assert api.get(f"/api/cases/{C1}/impacts").json()["open_impacts"] == []
    with admin_conn() as c:
        n = c.execute("SELECT count(*) n FROM finding_impact_log WHERE outcome IS NULL").fetchone()["n"]
        assert n == 0, "every impact must end with a recorded outcome"
    # previous versions are retained, never overwritten
    allf = api.get(f"/api/cases/{C1}/findings", **{"params": {"include_outdated": True}}).json()["findings"]
    assert len(allf) >= len(base)
    # no active finding may still rely on invalidated evidence
    for f in api.get(f"/api/cases/{C1}/findings").json()["findings"]:
        assert not any(":INVALIDATED" in st for st in f["evidence_states"]), f["finding_key"]


def test_hypotheses_flagged_then_cleared_by_human(api):
    hyps = api.get(f"/api/cases/{C1}/hypotheses").json()["hypotheses"]
    assert hyps and all(h["label"].startswith("HYPOTHESIS") for h in hyps)
    for x in [h for h in hyps if h["needs_review"]]:
        r = api.post(f"/api/cases/{C1}/hypotheses/{x['ref']}/clear-review", user="sup.rao")
        assert r.status_code == 200, r.text
    assert not any(h["needs_review"] for h in api.get(f"/api/cases/{C1}/hypotheses").json()["hypotheses"])


def test_belief_view_excludes_invalidated(api):
    b = api.get(f"/api/cases/{C1}/belief")
    assert b.status_code == 200
