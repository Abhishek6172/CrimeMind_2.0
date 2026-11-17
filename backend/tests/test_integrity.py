import psycopg
import pytest

from .conftest import admin_conn


def test_cross_case_references_blocked_by_database(world):
    with admin_conn() as c:
        k1 = c.execute("SELECT case_id FROM cases WHERE case_ref='CASE-2026-001'").fetchone()["case_id"]
        k2 = c.execute("SELECT case_id FROM cases WHERE case_ref='CASE-2026-002'").fetchone()["case_id"]
        a = c.execute("SELECT entity_id FROM entities WHERE case_id=%s AND entity_type='PERSON' LIMIT 1", (k1,)).fetchone()["entity_id"]
        b = c.execute("SELECT entity_id FROM entities WHERE case_id=%s AND entity_type='PERSON' LIMIT 1", (k2,)).fetchone()["entity_id"]
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            c.execute("INSERT INTO communications(case_id,ref,sender_id,receiver_id,comm_type,occurred_at) VALUES (%s,'X-1',%s,%s,'CALL',now())", (k1, a, b))


def test_type_rules_enforced(world):
    with admin_conn() as c:
        k = c.execute("SELECT case_id FROM cases WHERE case_ref='CASE-2026-001'").fetchone()["case_id"]
        person = c.execute("SELECT entity_id FROM entities WHERE case_id=%s AND ref='P-001'", (k,)).fetchone()["entity_id"]
        loc = c.execute("SELECT entity_id FROM entities WHERE case_id=%s AND ref='L-GP1'", (k,)).fetchone()["entity_id"]
        with pytest.raises(psycopg.errors.RaiseException):
            c.execute("INSERT INTO communications(case_id,ref,sender_id,receiver_id,comm_type,occurred_at) VALUES (%s,'X-2',%s,%s,'CALL',now())", (k, person, loc))
        c.rollback()
        with pytest.raises(psycopg.errors.RaiseException):    # observation location must be a LOCATION
            c.execute("INSERT INTO location_observations(case_id,ref,subject_entity_id,location_entity_id,observed_from,observed_to,source_kind,source) "
                      "VALUES (%s,'X-3',%s,%s,now(),now(),'GPS','x')", (k, person, person))


def test_history_is_never_deleted_or_rewritten(world):
    with admin_conn() as c:
        c.execute("SELECT set_config('app.user','admin',false)")
        for sql in ("DELETE FROM evidence", "DELETE FROM findings", "DELETE FROM communications", "UPDATE audit_log SET actor='x'"):
            with pytest.raises(psycopg.errors.RaiseException):
                c.execute(sql)
            c.rollback()
        # append-only tables may be empty after seeding (row triggers never fire on zero rows),
        # so assert the protective triggers exist rather than relying on data being present
        for table in ("activity_log", "evidence_validity_events", "query_audit", "reviews"):
            n = c.execute("SELECT count(*) n FROM pg_trigger t WHERE t.tgrelid=%s::regclass AND NOT t.tgisinternal "
                          "AND pg_get_triggerdef(t.oid) ILIKE '%%forbid_mutation%%'", (table,)).fetchone()["n"]
            assert n >= 1, table


def test_validity_cannot_change_outside_evlm(world):
    with admin_conn() as c:
        with pytest.raises(psycopg.errors.RaiseException):
            c.execute("UPDATE evidence SET validity_status='INVALIDATED' WHERE ref='E-0001'")
        c.rollback()


def test_registry_has_40_questions_and_18_modules(world):
    with admin_conn() as c:
        assert c.execute("SELECT count(*) n FROM investigation_questions").fetchone()["n"] == 40
        assert c.execute("SELECT count(*) n FROM sql_modules").fetchone()["n"] == 18
        # every module is used by at least one question (SRS 8.25)
        assert c.execute("SELECT count(*) n FROM sql_modules m WHERE NOT EXISTS (SELECT 1 FROM investigation_questions q WHERE q.module_id=m.module_id)").fetchone()["n"] == 0
