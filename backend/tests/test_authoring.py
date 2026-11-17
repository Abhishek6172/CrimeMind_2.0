from .conftest import C1, C2, admin_conn

T = "2026-08-14T15:35:00Z"


def test_add_evidence_and_records_refresh_analysis(api):
    base = f"/api/cases/{C1}"
    r = api.post(base + "/evidence", json={"evidence_type": "CCTV", "source": "CAM-09", "description": "Camera 9 sees a person at the east gate",
                                           "evidence_timestamp": T, "origin_root": "CCTV:CAM-09", "entity_refs": ["P-004", "L-GP2"]})
    assert r.status_code == 201, r.text
    ev = r.json()["ref"]
    assert ev.startswith("E-N")
    r = api.post(base + "/observations", json={"subject": "P-004", "location": "L-GP2", "observed_from": T, "observed_to": "2026-08-14T15:40:00Z",
                                               "source_kind": "CCTV", "source": "CAM-09", "evidence_ref": ev})
    assert r.status_code == 201, r.text
    assert api.post(base + "/communications", json={"sender": "P-004", "receiver": "P-005", "comm_type": "CALL", "occurred_at": T, "duration_sec": 60}).status_code == 201
    assert api.post(base + "/transactions", json={"from_entity": "P-004", "to_entity": "P-005", "txn_type": "TRANSFER", "amount": 500, "occurred_at": T}).status_code == 201
    assert api.post(base + "/relationships", json={"entity_a": "P-004", "entity_b": "P-005", "rel_type": "ASSOCIATE"}).status_code == 201
    assert api.get(base + f"/evidence/{ev}").json()["evidence"]["validity_status"] == "SUPPORTED"
    run1 = api.get(base + "/correlations").json()["run"]["run_id"]
    api.post(base + "/communications", json={"sender": "P-005", "receiver": "P-004", "comm_type": "SMS", "occurred_at": T})
    assert api.get(base + "/correlations").json()["run"]["run_id"] != run1      # a record without evidence still makes the run stale


def test_validation_and_isolation(api):
    base = f"/api/cases/{C1}"
    r = api.post(base + "/communications", json={"sender": "P-004", "receiver": "P-9999", "comm_type": "CALL", "occurred_at": T})
    assert r.status_code == 422 and "receiver" in r.json()["error"]["fields"]
    r = api.post(base + "/communications", json={"sender": "P-004", "receiver": "L-GP1", "comm_type": "CALL", "occurred_at": T})
    assert r.status_code == 422                     # location cannot be a communication party
    r = api.post(base + "/observations", json={"subject": "P-004", "location": "L-GP2", "observed_from": T, "observed_to": "2026-08-14T15:00:00Z", "source_kind": "GPS", "source": "x"})
    assert r.status_code == 422
    r = api.post(base + "/entities", json={"entity_type": "LOCATION", "display_name": "No coords"})
    assert r.status_code == 422
    assert api.post(base + "/entities", json={"entity_type": "PERSON", "display_name": "X", "unexpected": 1}).status_code == 422   # extra fields rejected
    assert api.post(f"/api/cases/{C2}/entities", json={"entity_type": "PERSON", "display_name": "Z"}).status_code == 404            # no access
    assert api.c.post(base + "/entities", json={"entity_type": "PERSON", "display_name": "Z"}).status_code == 401
    r = api.post(base + "/entities", json={"entity_type": "PERSON", "display_name": "Ravi <script>alert(1)</script>"})
    assert r.status_code == 201
    new = r.json()["ref"]
    assert new == "P-101"


def test_bulk_import_atomic_and_dry_run(api):
    base = f"/api/cases/{C1}"
    with admin_conn() as c:
        before = c.execute("SELECT count(*) n FROM entities").fetchone()["n"]
    good = {"entities": [{"entity_type": "PERSON", "display_name": "Imp One", "ref": "P-201"}, {"entity_type": "PERSON", "display_name": "Imp Two", "ref": "P-202"}],
            "communications": [{"sender": "P-201", "receiver": "P-202", "comm_type": "CALL", "occurred_at": T}]}
    r = api.post(base + "/import", json={**good, "dry_run": True}).json()
    assert r["committed"] is False and not r["errors"]
    with admin_conn() as c:
        assert c.execute("SELECT count(*) n FROM entities").fetchone()["n"] == before
    bad = {**good, "communications": good["communications"] + [{"sender": "P-201", "receiver": "NOPE", "comm_type": "CALL", "occurred_at": T}]}
    r = api.post(base + "/import", json={**bad, "dry_run": False}).json()
    assert r["committed"] is False and r["errors"][0]["index"] == 1
    with admin_conn() as c:
        assert c.execute("SELECT count(*) n FROM entities").fetchone()["n"] == before     # all-or-nothing
    r = api.post(base + "/import", json={**good, "dry_run": False}).json()
    assert r["committed"] is True and r["refs"]["entities"] == ["P-201", "P-202"]


def test_case_creation_and_access(api):
    assert api.post("/api/cases", json={"title": "Test case"}).status_code == 403             # investigator cannot
    r = api.post("/api/cases", user="sup.rao", json={"title": "Harbour Theft"})
    assert r.status_code == 201, r.text
    ref = r.json()["case_ref"]
    assert api.get(f"/api/cases/{ref}", user="sup.rao").status_code == 200
    assert api.get(f"/api/cases/{ref}").status_code == 404                                    # inv.asha has no access
    assert api.post(f"/api/cases/{ref}/access", user="sup.rao", json={"username": "inv.asha"}).status_code == 201
    assert api.get(f"/api/cases/{ref}").status_code == 200
    assert api.post(f"/api/cases/{ref}/access", json={"username": "inv.vikram"}).status_code == 403   # investigator cannot grant
    assert api.c.delete(f"/api/cases/{ref}/access/inv.asha", headers=api.login("sup.rao")).status_code == 200
    assert api.get(f"/api/cases/{ref}").status_code == 404
    assert api.c.delete(f"/api/cases/{ref}/access/sup.rao", headers=api.login("sup.rao")).status_code == 422   # cannot lock yourself out
    assert api.post(f"/api/cases/{C2}/access", user="sup.rao", json={"username": "inv.asha"}).status_code == 404   # no access to case 2, cannot grant it
    with admin_conn() as c:
        acts = {r["action_type"] for r in c.execute("SELECT action_type FROM activity_log").fetchall()}
    assert {"CASE_CREATED", "ACCESS_GRANTED", "ACCESS_REVOKED"} <= acts


def test_notes(api):
    base = f"/api/cases/{C1}"
    r = api.post(base + "/notes", json={"target_type": "ENTITY", "target_ref": "P-004", "body": "Check workplace badge records", "tags": ["Follow-up", "alibi"], "bookmarked": True})
    assert r.status_code == 201, r.text
    assert api.post(base + "/notes", json={"target_type": "ENTITY", "target_ref": "P-9999", "body": "x"}).status_code == 404
    got = api.get(base + "/notes", params={"bookmarked": True, "tag": "follow-up"}).json()["notes"]
    assert got and got[0]["author"] == "inv.asha"
    with admin_conn() as c:
        import psycopg
        try:
            c.execute("UPDATE case_notes SET body='edited'"); raise AssertionError("note was editable")
        except psycopg.errors.RaiseException:
            pass
