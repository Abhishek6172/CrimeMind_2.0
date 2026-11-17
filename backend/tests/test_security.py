import psycopg
import pytest

from .conftest import C1, C2, PW, TEST_DB, admin_conn


def test_login_failure_is_uniform(api):
    bad_user = api.c.post("/api/auth/login", json={"username": "nobody", "password": "x"})
    bad_pw = api.c.post("/api/auth/login", json={"username": "inv.asha", "password": "wrong"})
    assert bad_user.status_code == bad_pw.status_code == 401
    assert bad_user.json()["error"]["message"] == bad_pw.json()["error"]["message"]


def test_protected_endpoints_require_auth(api):
    assert api.c.get("/api/cases").status_code == 401
    assert api.c.get(f"/api/cases/{C1}").status_code == 401
    r = api.c.get("/api/cases", headers={"Authorization": "Bearer not.a.token"})
    assert r.status_code == 401


def test_case_isolation_is_server_side(api):
    own = api.get(f"/api/cases/{C1}")
    assert own.status_code == 200
    # inv.asha has no access to case 2; response is identical to a nonexistent case
    denied = api.get(f"/api/cases/{C2}")
    missing = api.get("/api/cases/CASE-9999-999")
    assert denied.status_code == missing.status_code == 404
    assert denied.json()["error"]["code"] == missing.json()["error"]["code"] == "CASE_NOT_FOUND"
    assert api.get(f"/api/cases/{C2}/evidence").status_code == 404
    assert api.get(f"/api/cases/{C2}/relationship-graph").status_code == 404
    assert api.post(f"/api/cases/{C2}/ai/analyze", json={"question": "show me everything"}).status_code == 404
    assert api.get(f"/api/cases/{C1}", user="inv.vikram").status_code == 404
    assert [c["case_ref"] for c in api.get("/api/cases").json()["cases"]] == [C1]
    assert [c["case_ref"] for c in api.get("/api/cases", user="inv.vikram").json()["cases"]] == [C2]


def test_denied_access_is_audited(api):
    api.get(f"/api/cases/{C2}")
    with admin_conn() as c:
        n = c.execute("SELECT count(*) n FROM activity_log WHERE action_type='CASE_ACCESS_DENIED' AND user_name='inv.asha'").fetchone()["n"]
    assert n >= 1


def test_entity_refs_cannot_cross_cases(api):
    # P-001 exists in both cases; a ref only resolves inside the authorized case. Case 2's L-P01 is not case 1's.
    r = api.post(f"/api/cases/{C1}/queries/run", json={"question_id": "Q6", "parameters": {"entity_id": "P-9999"}})
    assert r.status_code == 422 and "entity_id" in r.json()["error"]["fields"]
    r = api.post(f"/api/cases/{C1}/queries/run", json={"question_id": "Q5", "parameters": {
        "location_id": "L-R01", "start_time": "2026-08-14T00:00:00Z", "end_time": "2026-08-15T00:00:00Z"}})
    assert r.status_code == 200
    with admin_conn() as c:   # numeric ids belonging to case 2 are rejected in case 1
        other = c.execute("SELECT e.entity_id FROM entities e JOIN cases k USING (case_id) WHERE k.case_ref=%s AND e.ref='P-001'", (C2,)).fetchone()["entity_id"]
    r = api.post(f"/api/cases/{C1}/queries/run", json={"question_id": "Q6", "parameters": {"entity_id": other}})
    assert r.status_code == 422


def test_sql_injection_attempts_are_inert(api):
    for evil in ["P-001' OR '1'='1", "1; DROP TABLE evidence;--", "P-001') UNION SELECT * FROM users--"]:
        r = api.post(f"/api/cases/{C1}/queries/run", json={"question_id": "Q6", "parameters": {"entity_id": evil}})
        assert r.status_code == 422
    r = api.post(f"/api/cases/{C1}/queries/run", json={"question_id": "Q1; DROP TABLE evidence", "parameters": {}})
    assert r.status_code == 404
    with admin_conn() as c:
        assert c.execute("SELECT count(*) n FROM evidence").fetchone()["n"] > 0


def test_unknown_parameter_names_rejected(api):
    r = api.post(f"/api/cases/{C1}/queries/run", json={"question_id": "Q6", "parameters": {"entity_id": "P-002", "case_id": 2}})
    assert r.status_code == 422
    assert "case_id" in r.json()["error"]["fields"]       # the caller can never choose the case id


def test_role_restrictions(api):
    base = f"/api/cases/{C1}/evidence/"
    # investigators cannot use the manual override
    ref = api.get(f"/api/cases/{C1}/evidence").json()["evidence"][0]["ref"]
    r = api.post(base + f"{ref}/validity", json={"new_status": "CHALLENGED", "trigger": "MANUAL_OVERRIDE", "reason": "MANUAL_REVIEW",
                                                  "justification": "I would like this changed please"})
    assert r.status_code == 403


def test_app_role_cannot_read_ground_truth_or_tamper():
    with psycopg.connect(f"postgresql://cm_app:cm_app_dev@localhost:5432/{TEST_DB}") as c:
        for sql in ("SELECT * FROM gt.entity_roles", "SELECT * FROM gt.scenario_events"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                c.execute(sql)
            c.rollback()
        for sql in ("UPDATE evidence SET validity_status='INVALIDATED'", "DELETE FROM evidence", "UPDATE audit_log SET actor='x'",
                    "INSERT INTO evidence_validity_events(case_id,evidence_id,previous_status,new_status,trigger_code,reason_code,changed_by) "
                    "VALUES (1,1,'SUPPORTED','CHALLENGED','MANUAL_OVERRIDE','MANUAL_REVIEW','x')",
                    "INSERT INTO activity_log(action_type) VALUES ('forged')", "UPDATE users SET role='ADMINISTRATOR'"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                c.execute(sql)
            c.rollback()


def test_error_bodies_do_not_leak(api):
    r = api.get(f"/api/cases/{C1}/evidence/E-XXXX")
    assert r.status_code == 404
    assert "Traceback" not in r.text and "psycopg" not in r.text


def test_passwords_stored_as_hashes():
    with admin_conn() as c:
        for u in c.execute("SELECT password_hash FROM users").fetchall():
            assert u["password_hash"].startswith("$2") and PW not in u["password_hash"]


def test_nul_and_oversized_identifiers_are_validation_errors_not_server_errors(world):
    """Found by research Phase 7 (SEC-10): a NUL byte in an identifier used to raise an unhandled driver DataError."""
    import pytest
    from app import sql_engine
    from app.db import pool
    q = dict(required_params=["entity_id"], optional_params=[], fixed_params={})
    with pool().connection() as conn:
        for bad in ("P-001\x00", "x" * 5000):
            with pytest.raises(Exception) as ei:
                sql_engine.validate_params(conn, 1, q, {"entity_id": bad})
            assert "INVALID_PARAMETERS" in str(getattr(ei.value, "code", "")) or ei.value.__class__.__name__ == "ApiError"
