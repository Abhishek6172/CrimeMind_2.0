from synth import scenario

from .conftest import C1, C2, TEST_DB

B = f"/api/cases/{C1}/insights/"
WIN = "start=2026-08-14T15:00:00Z&end=2026-08-14T16:00:00Z"


def test_access_control(api):
    assert api.c.get(B + "jumps").status_code == 401
    assert api.get(f"/api/cases/{C2}/insights/jumps").status_code == 404
    assert api.get(f"/api/cases/{C2}/insights/network").status_code == 404


def test_jump_check_finds_the_gps_conflict(api):
    j = api.get(B + "jumps").json()
    assert j["total"] >= 1
    f = j["flags"][0]
    assert f["subject"]["ref"] == "P-004" and f["kind"] == "SIMULTANEOUS_PRESENCE"
    assert {s["source"] for s in j["sources_in_conflicts"]} >= {"GPS:GPS-17"}
    assert api.get(B + "jumps?max_speed_kmh=5").status_code == 422     # out of range parameter


def test_alibi_conflict_then_changes_after_gps_fault(api):
    assert api.get(B + f"alibi?person=P-004&{WIN}").json()["verdict"] == "CONFLICTING"
    with scenario.connect(TEST_DB) as c:
        for step in (1, 2):
            scenario.apply_step(c, "SC-GPS17-FAULT", step)
        c.commit()
    a = api.get(B + f"alibi?person=P-004&{WIN}").json()
    assert a["verdict"] == "RECORDED_ELSEWHERE"             # the invalidated GPS trace no longer counts as support
    assert a["excluded_unsupported_records"] >= 1 and a["excluded_by_type"]["observations"] >= 1
    assert api.get(B + "jumps").json()["total"] == 0


def test_alibi_validation(api):
    assert api.get(B + "alibi?person=P-9999&" + WIN).status_code == 422
    assert api.get(B + "alibi?person=P-004&start=2026-08-14T16:00:00Z&end=2026-08-14T15:00:00Z").status_code == 422
    assert api.get(B + "alibi?person=P-004&start=2026-01-01T00:00:00Z&end=2026-08-01T00:00:00Z").status_code == 422
    assert api.get(B + "alibi?person=L-GP1&" + WIN).status_code == 422          # not a person


def test_network_metrics(api):
    n = api.get(B + "network").json()
    assert n["people_count"] > 50 and n["communities"]
    top = n["people"][0]
    assert 0 <= top["betweenness"] <= 1 and top["pagerank"] > 0
    only = api.get(B + "network?domains=transaction").json()
    assert only["people_count"] < n["people_count"]
    assert api.get(B + "network?domains=bogus").status_code == 422


def test_anomalies_money_meetings_map(api):
    a = api.get(B + "anomalies").json()
    assert a["total"] == len(a["flags"]) and a["notice"]
    m = api.get(B + "money-trail?entity=P-002&max_hops=3").json()
    assert m["paths"] and m["paths"][0]["steps"][0]["from"] == "P-002"
    assert api.get(B + "money-trail?entity=P-002&direction=sideways").status_code == 422
    assert api.get(B + "money-trail?entity=P-2").status_code == 422
    assert "meetings" in api.get(B + "meetings").json()
    mp = api.get(B + "map?person=P-004").json()
    assert mp["locations"] and mp["incidents"] and mp["trail"]
    assert api.get(B + "map").json()["trail"] == []
