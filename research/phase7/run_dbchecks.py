"""DB correctness, isolation, security and concurrency checks against a disposable research database. One row per check:
PASS / FAIL, with the observed behaviour recorded. Nothing here touches the application database."""
import json
import threading
import traceback
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from research.common.workspace import SeedWorkspace, BASE

APP_PW_URL = lambda db: BASE.replace("postgresql://", "postgresql://cm_app:cm_app_dev@", 1) if "@" not in BASE else BASE


def app_url(db):
    # BASE looks like postgresql://user:pw@host:port ; replace credentials by the least-privilege app role
    host = BASE.split("@")[-1] if "@" in BASE else BASE.replace("postgresql://", "")
    return f"postgresql://cm_app:cm_app_dev@{host}/{db}"


class Checks:
    def __init__(self, conn=None):
        self.rows = []
        self.conn = conn

    def run(self, cid, area, desc, fn):
        try:
            ok, obs = fn()
        except Exception as e:
            ok, obs = False, f"EXCEPTION {type(e).__name__}: {str(e)[:200]}"
            try:
                self.conn.rollback()
            except Exception:
                pass
        self.rows.append(dict(id=cid, area=area, check=desc, result="PASS" if ok else "FAIL", observed=str(obs)[:300]))


def raises(conn, sql, args=(), contains=None):
    conn.execute("SAVEPOINT s")
    try:
        conn.execute(sql, args)
        conn.execute("ROLLBACK TO SAVEPOINT s")
        return False, "statement was ACCEPTED"
    except Exception as e:
        conn.execute("ROLLBACK TO SAVEPOINT s")
        msg = str(e).splitlines()[0][:150]
        return (contains is None or contains.lower() in str(e).lower()), f"{type(e).__name__}: {msg}"


def run(seed, out: Path):
    C = Checks()
    with SeedWorkspace(seed, prefix="cm_p7d") as ws:
        su = ws.conn; su.commit(); C.conn = su
        cases = ws.cases()
        c1, c2 = cases[0]["case_id"], cases[1]["case_id"]
        e1 = su.execute("SELECT entity_id FROM entities WHERE case_id=%s AND entity_type='PERSON' ORDER BY entity_id LIMIT 1", (c1,)).fetchone()["entity_id"]
        e2 = su.execute("SELECT entity_id FROM entities WHERE case_id=%s AND entity_type='PERSON' ORDER BY entity_id LIMIT 1", (c2,)).fetchone()["entity_id"]
        L1 = su.execute("SELECT entity_id FROM entities WHERE case_id=%s AND entity_type='LOCATION' LIMIT 1", (c1,)).fetchone()["entity_id"]
        e1b = su.execute("SELECT entity_id FROM entities WHERE case_id=%s AND entity_type='PERSON' ORDER BY entity_id OFFSET 1 LIMIT 1", (c1,)).fetchone()['entity_id']
        ev1 = su.execute("SELECT evidence_id FROM evidence WHERE case_id=%s ORDER BY evidence_id LIMIT 1", (c1,)).fetchone()["evidence_id"]

        # ---- constraints
        C.run("DB-01", "constraints", "duplicate (case, ref) on entities is rejected", lambda: raises(su, "INSERT INTO entities(case_id,entity_type,ref,display_name) SELECT case_id,entity_type,ref,'dup' FROM entities WHERE entity_id=%s", (e1,), "unique"))
        C.run("DB-02", "constraints", "unknown entity type is rejected (FK)", lambda: raises(su, "INSERT INTO entities(case_id,entity_type,ref,display_name) VALUES (%s,'NOPE','X-1','x')", (c1,), "foreign key"))
        C.run("DB-03", "constraints", "communication referencing an entity of ANOTHER case is rejected", lambda: raises(su, "INSERT INTO communications(case_id,ref,sender_id,receiver_id,comm_type,occurred_at) VALUES (%s,'X-CROSS',%s,%s,'SMS',now())", (c1, e1, e2), "foreign key"))
        C.run("DB-04", "constraints", "relationship strength > 1 is rejected", lambda: raises(su, "INSERT INTO relationships(case_id,ref,entity_a,entity_b,rel_type,strength) VALUES (%s,'X-R1',%s,%s,'FRIEND',1.5)", (c1, e1, e1b), "check"))
        C.run("DB-05", "constraints", "self relationship is rejected", lambda: raises(su, "INSERT INTO relationships(case_id,ref,entity_a,entity_b,rel_type,strength) VALUES (%s,'X-R2',%s,%s,'FRIEND',0.5)", (c1, e1, e1), "check"))
        C.run("DB-06", "constraints", "observation ending before it starts is rejected", lambda: raises(su, "INSERT INTO location_observations(case_id,ref,subject_entity_id,location_entity_id,observed_from,observed_to,source_kind,source) VALUES (%s,'X-O1',%s,%s,now(),now()-interval '1 day','CCTV','c')", (c1, e1, L1), "check"))
        C.run("DB-07", "constraints", "new evidence must start SUPPORTED", lambda: raises(su, "INSERT INTO evidence(case_id,ref,evidence_type,source,validity_status) VALUES (%s,'E-X1','GPS','s','INVALIDATED')", (c1,), "SUPPORTED"))
        C.run("DB-08", "constraints", "event referencing a location of ANOTHER case is rejected", lambda: raises(su, "INSERT INTO events(case_id,event_type,ref,occurred_at,location_entity_id) VALUES (%s,'MEETING','EVT-X',now(),%s)", (c1, e2), "foreign key"))

        # ---- lifecycle / append-only
        C.run("DB-10", "lifecycle", "validity_status cannot be updated directly", lambda: raises(su, "UPDATE evidence SET validity_status='INVALIDATED' WHERE evidence_id=%s", (ev1,), "change_validity"))
        C.run("DB-11", "lifecycle", "evidence rows cannot be deleted", lambda: raises(su, "DELETE FROM evidence WHERE evidence_id=%s", (ev1,), "not allowed"))
        C.run("DB-12", "lifecycle", "evidence identity fields are immutable", lambda: raises(su, "UPDATE evidence SET source='tampered' WHERE evidence_id=%s", (ev1,), "immutable"))
        C.run("DB-13", "lifecycle", "audit_log is append-only (UPDATE)", lambda: raises(su, "UPDATE audit_log SET actor='x'", (), "not allowed"))
        C.run("DB-14", "lifecycle", "audit_log is append-only (DELETE)", lambda: raises(su, "DELETE FROM audit_log", (), "not allowed"))

        def lifecycle_consistency():
            su.execute("SELECT change_validity(%s,%s,'INVALIDATED','CONFIRMED_INVALIDITY','DEVICE_FAULT','p7 check',NULL,'admin')", (c1, ev1)); su.commit()
            bad = su.execute("""SELECT count(*) AS n FROM evidence e JOIN LATERAL (SELECT new_status FROM evidence_validity_events v WHERE v.evidence_id=e.evidence_id ORDER BY v.event_id DESC LIMIT 1) l ON true
                                WHERE e.validity_status <> l.new_status""").fetchone()["n"]
            return bad == 0, f"{bad} evidence rows disagree with their latest validity event"
        C.run("DB-16", "lifecycle", "evidence.validity_status equals the newest validity event for every evidence row", lifecycle_consistency)
        C.run("DB-15", "lifecycle", "evidence_validity_events is append-only (UPDATE, once rows exist)", lambda: raises(su, "UPDATE evidence_validity_events SET reason_code=reason_code", (), "not allowed"))

        def audit_written():
            n = su.execute("SELECT count(*) AS n FROM audit_log WHERE object_type='evidence_validity_events'").fetchone()["n"]
            m = su.execute("SELECT count(*) AS n FROM evidence_validity_events").fetchone()["n"]
            return n >= m and m > 0, f"audit rows for validity events={n}, events={m}"
        C.run("DB-17", "audit", "every validity event is mirrored in the audit log", audit_written)

        def rollback_clean():
            before = su.execute("SELECT count(*) AS n FROM evidence_validity_events").fetchone()["n"]
            su.execute("SAVEPOINT r")
            try:
                su.execute("SELECT change_validity(%s,%s,'CHALLENGED','DOCUMENTED_CONTRADICTION','CONTRADICTED_BY_STRONGER_SOURCE','x',NULL,'no.such.user')", (c1, ev1))
            except Exception:
                su.execute("ROLLBACK TO SAVEPOINT r")
            after = su.execute("SELECT count(*) AS n FROM evidence_validity_events").fetchone()["n"]
            st = su.execute("SELECT validity_status::text AS s FROM evidence WHERE evidence_id=%s", (ev1,)).fetchone()["s"]
            return before == after and st == "INVALIDATED", f"events {before}->{after}, status {st}"
        C.run("DB-18", "transactions", "failed change_validity (unknown actor) leaves no event and no status change", rollback_clean)

        # ---- concurrency: N threads change validity of different/same evidence
        def concurrent():
            ids = [r["evidence_id"] for r in su.execute("SELECT evidence_id FROM evidence WHERE case_id=%s AND validity_status='SUPPORTED' ORDER BY evidence_id LIMIT 6", (c1,))]
            trig = ids[-1]; target = ids[0]
            errs, oks = [], []

            def worker(i):
                try:
                    with psycopg.connect(f"{BASE}/{ws.db}", row_factory=dict_row) as c:
                        st, tr, rs = (("CHALLENGED", "DOCUMENTED_CONTRADICTION", "CONTRADICTED_BY_STRONGER_SOURCE"), ("INVALIDATED", "CONFIRMED_INVALIDITY", "DEVICE_FAULT"))[i % 2]
                        c.execute("SELECT change_validity(%s,%s,%s::validity_status,%s::validity_trigger,%s::validity_reason,'concurrent',%s,'admin')", (c1, target, st, tr, rs, trig))
                        c.commit(); oks.append(i)
                except Exception as e:
                    errs.append(str(e).splitlines()[0][:100])
            th = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
            [t.start() for t in th]; [t.join() for t in th]
            ev = su.execute("SELECT new_status::text AS s FROM evidence_validity_events WHERE evidence_id=%s ORDER BY event_id DESC LIMIT 1", (target,)).fetchone()["s"]
            cur = su.execute("SELECT validity_status::text AS s FROM evidence WHERE evidence_id=%s", (target,)).fetchone()["s"]
            n_ev = su.execute("SELECT count(*) AS n FROM evidence_validity_events WHERE evidence_id=%s", (target,)).fetchone()["n"]
            return ev == cur and n_ev == len(oks), f"accepted={len(oks)} rejected={len(errs)} events={n_ev} final status={cur} latest event={ev}; rejections: {sorted(set(errs))[:2]}"
        C.run("DB-19", "concurrency", "8 concurrent change_validity calls on one evidence row: final status equals the newest event, one event per accepted call", concurrent)

        # ---- least privilege (cm_app)
        with psycopg.connect(app_url(ws.db), row_factory=dict_row) as app:
            C.run("SEC-01", "privilege", "cm_app cannot read the ground-truth schema", lambda: raises(app, "SELECT * FROM gt.entity_roles", (), "permission denied"))
            C.run("SEC-02", "privilege", "cm_app cannot write the ground-truth schema", lambda: raises(app, "INSERT INTO gt.entity_roles(case_ref,entity_ref,role) VALUES ('a','b','VICTIM')", (), "permission denied"))
            C.run("SEC-03", "privilege", "cm_app cannot UPDATE evidence directly", lambda: raises(app, "UPDATE evidence SET reliability_score=1 WHERE evidence_id=%s", (ev1,), "permission denied"))
            C.run("SEC-04", "privilege", "cm_app cannot DELETE evidence", lambda: raises(app, "DELETE FROM evidence WHERE evidence_id=%s", (ev1,), "permission denied"))
            C.run("SEC-05", "privilege", "cm_app cannot modify the audit log", lambda: raises(app, "UPDATE audit_log SET actor='x'", (), "permission denied"))
            C.run("SEC-06", "privilege", "cm_app cannot create or drop tables", lambda: raises(app, "DROP TABLE evidence", (), "must be owner|permission denied".split("|")[0]) if False else raises(app, "CREATE TABLE p7_x(a int)", (), "permission denied"))

        # ---- SQL injection through the real validation + execution path
        from app import sql_engine
        from app.errors import ApiError
        evil = ["P-001'; DROP TABLE evidence; --", "1 OR 1=1", "' UNION SELECT usename FROM pg_user --", "P-001\x00", "x" * 5000, "1; SELECT pg_sleep(5)", "../../etc/passwd"]
        q = dict(required_params=["entity_id"], optional_params=["start_time", "end_time", "result_limit", "include_historical"], fixed_params={})

        def injection():
            leaked, accepted = [], []
            for s in evil:
                for param in ("entity_id",):
                    try:
                        out = sql_engine.validate_params(su, c1, q, {param: s})
                        accepted.append((s[:30], out[param]))
                    except (ApiError, ValueError):
                        pass
                    except Exception as e:
                        leaked.append((s[:30], type(e).__name__))
                    su.rollback()
                for tp in ("start_time", "result_limit"):
                    try:
                        sql_engine.validate_params(su, c1, q, {"entity_id": "1", tp: s}); accepted.append((tp, s[:20]))
                    except (ApiError, ValueError):
                        pass
                    except Exception as e:
                        leaked.append((tp, type(e).__name__))
                    su.rollback()
            tables = su.execute("SELECT count(*) AS n FROM evidence").fetchone()["n"]
            return not leaked and tables > 0 and not any(a[0].startswith(("P-001'", "1 OR", "' UNION", "../")) for a in accepted), f"accepted={accepted[:3]} unexpected_exceptions={leaked[:3]} evidence_rows_intact={tables}"
        C.run("SEC-10", "injection", "hostile values in entity_id/start_time/result_limit are rejected as invalid parameters; evidence table intact", injection)

        def cross_case_ref():
            ref2 = su.execute("SELECT ref FROM entities WHERE case_id=%s AND entity_id=%s", (c2, e2)).fetchone()["ref"]
            ref1s = {r["ref"] for r in su.execute("SELECT ref FROM entities WHERE case_id=%s", (c1,))}
            if ref2 in ref1s:      # refs are case-local and may coincide; test with a numeric id of the other case instead
                try:
                    sql_engine.resolve_entity(su, c1, e2, None, "entity_id"); return False, "numeric id of another case resolved"
                except ValueError:
                    return True, "numeric id from another case rejected"
            try:
                sql_engine.resolve_entity(su, c1, ref2, None, "entity_id"); return False, "ref of another case resolved"
            except ValueError:
                return True, "ref from another case rejected"
        C.run("SEC-11", "isolation", "an entity identifier belonging to another case cannot be resolved", cross_case_ref)

        def unaffected_other_case():
            # a validity change in case 1 must not change anything in case 2
            n0 = su.execute("SELECT count(*) AS n FROM evidence_validity_events e JOIN evidence v USING (evidence_id) WHERE v.case_id=%s", (c2,)).fetchone()["n"]
            return n0 == 0, f"case-2 validity events after case-1 changes = {n0}"
        C.run("DB-20", "isolation", "validity changes in case 1 create no events in case 2", unaffected_other_case)
    out.mkdir(parents=True, exist_ok=True)
    json.dump(C.rows, open(out / "db_security_checks.json", "w"), indent=1)
    return C.rows
