"""Scalability harness. A disposable database holds seed data replicated k times INSIDE ONE CASE (k = 1, 2, 5, 10): each replica is a
disjoint copy of the case (entities, evidence, records, links) with refs suffixed '~<r>'. Entity-scoped queries therefore stay the same
size while case-wide queries (pairs, co-presence, top amounts, Q40, ranking) grow with k. This is a synthetic scaling model, not a
production workload; see the report."""
import json
import statistics
import time
from pathlib import Path

from research.common.workspace import SeedWorkspace
from research.phase7.compare import MODULES, run_sql
from research.phase7.oracles.data import from_db
from research.phase7.params import VARIANTS, param_sets

TABLE_COUNTS = ["entities", "evidence", "communications", "location_observations", "relationships", "transactions", "events", "evidence_entities"]


def replicate(conn, case_id: int, r: int):
    p = dict(c=case_id, r=f"~{r}")
    ex = lambda sql: conn.execute(sql, p)
    ex("""INSERT INTO entities(case_id,entity_type,ref,display_name,attributes)
          SELECT case_id,entity_type,ref||%(r)s,display_name,attributes FROM entities WHERE case_id=%(c)s AND ref NOT LIKE '%%~%%'""")
    ex("""INSERT INTO evidence(case_id,ref,evidence_type,source,source_record_id,evidence_timestamp,description,provenance,reliability_score,content_ref,processing_status)
          SELECT case_id,ref||%(r)s,evidence_type,source,source_record_id,evidence_timestamp,description,provenance,reliability_score,content_ref,processing_status
          FROM evidence WHERE case_id=%(c)s AND ref NOT LIKE '%%~%%' AND validity_status='SUPPORTED'""")
    ne = "LEFT JOIN evidence oe ON oe.evidence_id=X.evidence_id LEFT JOIN evidence ne ON ne.case_id=X.case_id AND ne.ref=oe.ref||%(r)s"
    mp = lambda alias, col: f"JOIN entities o_{alias} ON o_{alias}.entity_id=X.{col} JOIN entities n_{alias} ON n_{alias}.case_id=X.case_id AND n_{alias}.ref=o_{alias}.ref||%(r)s"
    ex(f"""INSERT INTO communications(case_id,ref,sender_id,receiver_id,comm_type,occurred_at,duration_sec,evidence_id)
           SELECT X.case_id,X.ref||%(r)s,n_s.entity_id,n_r.entity_id,X.comm_type,X.occurred_at,X.duration_sec,ne.evidence_id
           FROM communications X {mp('s','sender_id')} {mp('r','receiver_id')} {ne} WHERE X.case_id=%(c)s AND X.ref NOT LIKE '%%~%%'""")
    ex(f"""INSERT INTO location_observations(case_id,ref,subject_entity_id,location_entity_id,observed_from,observed_to,source_kind,source,evidence_id)
           SELECT X.case_id,X.ref||%(r)s,n_s.entity_id,n_l.entity_id,X.observed_from,X.observed_to,X.source_kind,X.source,ne.evidence_id
           FROM location_observations X {mp('s','subject_entity_id')} {mp('l','location_entity_id')} {ne} WHERE X.case_id=%(c)s AND X.ref NOT LIKE '%%~%%'""")
    ex(f"""INSERT INTO relationships(case_id,ref,entity_a,entity_b,rel_type,strength,valid_from,valid_to,evidence_id)
           SELECT X.case_id,X.ref||%(r)s,n_a.entity_id,n_b.entity_id,X.rel_type,X.strength,X.valid_from,X.valid_to,ne.evidence_id
           FROM relationships X {mp('a','entity_a')} {mp('b','entity_b')} {ne} WHERE X.case_id=%(c)s AND X.ref NOT LIKE '%%~%%'""")
    ex(f"""INSERT INTO transactions(case_id,ref,from_entity_id,to_entity_id,amount,currency,txn_type,occurred_at,location_entity_id,evidence_id)
           SELECT X.case_id,X.ref||%(r)s,n_f.entity_id,n_t.entity_id,X.amount,X.currency,X.txn_type,X.occurred_at,nl.entity_id,ne.evidence_id
           FROM transactions X {mp('f','from_entity_id')} {mp('t','to_entity_id')}
           LEFT JOIN entities ol ON ol.entity_id=X.location_entity_id LEFT JOIN entities nl ON nl.case_id=X.case_id AND nl.ref=ol.ref||%(r)s
           {ne} WHERE X.case_id=%(c)s AND X.ref NOT LIKE '%%~%%'""")
    ex("""INSERT INTO events(case_id,event_type,ref,occurred_at,location_entity_id,description,attributes)
          SELECT X.case_id,X.event_type,X.ref||%(r)s,X.occurred_at,nl.entity_id,X.description,X.attributes FROM events X
          LEFT JOIN entities ol ON ol.entity_id=X.location_entity_id LEFT JOIN entities nl ON nl.case_id=X.case_id AND nl.ref=ol.ref||%(r)s
          WHERE X.case_id=%(c)s AND X.ref NOT LIKE '%%~%%'""")
    ex("""INSERT INTO event_entities(case_id,event_id,entity_id,role)
          SELECT X.case_id,ne.event_id,n.entity_id,X.role FROM event_entities X JOIN events oe ON oe.event_id=X.event_id
          JOIN events ne ON ne.case_id=X.case_id AND ne.ref=oe.ref||%(r)s JOIN entities o ON o.entity_id=X.entity_id JOIN entities n ON n.case_id=X.case_id AND n.ref=o.ref||%(r)s
          WHERE X.case_id=%(c)s AND oe.ref NOT LIKE '%%~%%'""")
    ex("""INSERT INTO evidence_entities(case_id,evidence_id,entity_id)
          SELECT X.case_id,ne.evidence_id,n.entity_id FROM evidence_entities X JOIN evidence oe ON oe.evidence_id=X.evidence_id
          JOIN evidence ne ON ne.case_id=X.case_id AND ne.ref=oe.ref||%(r)s JOIN entities o ON o.entity_id=X.entity_id JOIN entities n ON n.case_id=X.case_id AND n.ref=o.ref||%(r)s
          WHERE X.case_id=%(c)s AND oe.ref NOT LIKE '%%~%%'""")
    conn.commit()


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, max(0, int(round(q * (len(xs) - 1)))))]


def measure(conn, module, variant, case_id, params, reps, timeout_ms=60000):
    conn.execute(f"SET statement_timeout = {timeout_ms}")
    lat, n = [], None
    try:
        for _ in range(reps):
            t = time.perf_counter()
            rows = run_sql(conn, module, variant, case_id, params)
            lat.append((time.perf_counter() - t) * 1000)
            n = len(rows)
        conn.commit()
    except Exception as e:
        conn.rollback()
        return dict(error=type(e).__name__, n_runs=len(lat))
    return dict(n_runs=reps, rows=n, p50_ms=round(statistics.median(lat), 2), p95_ms=round(pct(lat, .95), 2), p99_ms=round(pct(lat, .99), 2), max_ms=round(max(lat), 2))


def explain(conn, module, variant, case_id, params):
    from research.phase7.compare import ALL_PARAMS
    full = {k: None for k in ALL_PARAMS}; full.update(include_historical=False); full.update(params); full["case_id"] = case_id
    conn.execute("SET statement_timeout = 60000")
    plan = conn.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + MODULES[module]["variants"][variant], full).fetchone()
    conn.rollback()
    return list(plan.values())[0][0]


def seq_scan_summary(plan):
    out = []
    def walk(n):
        if n.get("Node Type") in ("Seq Scan",):
            out.append((n.get("Relation Name"), round(n.get("Actual Total Time", 0) * n.get("Actual Loops", 1), 1), n.get("Actual Rows")))
        for c in n.get("Plans", []):
            walk(c)
    walk(plan["Plan"])
    return out


CANDIDATE_INDEXES = {
    "idx_cand_obs_loc_subj": "CREATE INDEX idx_cand_obs_loc_subj ON location_observations(case_id, location_entity_id, subject_entity_id, observed_from, observed_to)",
    "idx_cand_evid_ent_ev": "CREATE INDEX idx_cand_evid_ent_ev ON evidence_entities(case_id, entity_id, evidence_id)",
    "idx_cand_event_ent": "CREATE INDEX idx_cand_event_ent ON event_entities(case_id, entity_id)",
    "idx_cand_comm_time": "CREATE INDEX idx_cand_comm_time ON communications(case_id, occurred_at)",
    "idx_cand_obs_time": "CREATE INDEX idx_cand_obs_time ON location_observations(case_id, observed_from)",
}


def run(seed, scales, reps, out: Path, slow_ms=50):
    out.mkdir(parents=True, exist_ok=True)
    res = dict(seed=seed, scales={}, plans={}, index_experiment={}, config={})
    with SeedWorkspace(seed, prefix="cm_p7p") as ws:
        conn = ws.conn
        res["config"] = dict(postgres=ws.pg_version(), **{r["name"]: r["setting"] + (r["unit"] or "") for r in conn.execute(
            "SELECT name,setting,unit FROM pg_settings WHERE name IN ('shared_buffers','work_mem','effective_cache_size','max_parallel_workers_per_gather','random_page_cost','jit')")})
        case = ws.cases()[0]["case_id"]
        done = 1
        for k in scales:
            for r in range(done + 1, k + 1):
                replicate(conn, case, r)
            done = max(done, k)
            conn.execute("ANALYZE"); conn.commit()
            d_params = {}
            d = from_db(conn, case) if k == scales[0] else None
            if d is not None:
                base_data = d
            counts = {t: conn.execute(f"SELECT count(*) AS n FROM {t} WHERE case_id=%s", (case,)).fetchone()["n"] for t in TABLE_COUNTS}
            # parameter sets are fixed from the ORIGINAL (k=1) data so each scale answers the same questions over a larger case
            lat = {}
            for m, v in VARIANTS + [("M18", x) for x in ("reliability", "evidence_strength", "connected_both", "multi_domain", "overall")]:
                if m == "M18":
                    persons = sorted(i for i, e in base_data.entities.items() if e["type"] == "PERSON")
                    locs = sorted(i for i, e in base_data.entities.items() if e["type"] == "LOCATION")
                    ev = sorted(i for i, e in base_data.events.items() if e["type"] == "INCIDENT")
                    pr = dict(entity_id=persons[0], location_id=locs[0], event_id=ev[0], window_minutes=60)
                else:
                    pr = {kk: vv for kk, vv in param_sets(base_data, m, v, seed)[0].items()}
                    pr["result_limit"] = 200
                lat[f"{m}.{v}"] = measure(conn, m, v, case, pr, reps)
                lat[f"{m}.{v}"]["params"] = {a: (b.isoformat() if hasattr(b, "isoformat") else b) for a, b in pr.items() if b is not None}
            res["scales"][k] = dict(table_rows=counts, latency=lat)
            print(f"scale {k}x done", counts["communications"], "comms", flush=True)
        # plans for the slowest queries at the largest scale
        top = sorted(((kk, vv.get("p95_ms", 0)) for kk, vv in res["scales"][scales[-1]]["latency"].items()), key=lambda x: -x[1])[:6]
        for kk, _ in top:
            m, v = kk.split(".")
            pr = {a: (__import__("datetime").datetime.fromisoformat(b) if a in ("start_time", "end_time") else b) for a, b in res["scales"][scales[-1]]["latency"][kk]["params"].items()}
            plan = explain(conn, m, v, case, pr)
            res["plans"][kk] = dict(execution_ms=plan.get("Execution Time"), planning_ms=plan.get("Planning Time"), seq_scans=seq_scan_summary(plan), shared_hit=plan["Plan"].get("Shared Hit Blocks"), shared_read=plan["Plan"].get("Shared Read Blocks"))
        # index experiment: measure candidates one at a time at the largest scale, on queries slower than slow_ms
        slow = [kk for kk, vv in res["scales"][scales[-1]]["latency"].items() if vv.get("p95_ms", 0) > slow_ms]
        res["index_experiment"]["queries_over_threshold"] = slow
        res["index_experiment"]["threshold_ms"] = slow_ms
        res["index_experiment"]["candidates"] = {}
        for name, ddl in CANDIDATE_INDEXES.items():
            conn.execute(ddl); conn.execute("ANALYZE"); conn.commit()
            after = {}
            for kk in slow:
                m, v = kk.split(".")
                pr = {a: (__import__("datetime").datetime.fromisoformat(b) if a in ("start_time", "end_time") else b) for a, b in res["scales"][scales[-1]]["latency"][kk]["params"].items()}
                after[kk] = measure(conn, m, v, case, pr, reps)
            res["index_experiment"]["candidates"][name] = {kk: dict(before_p95=res["scales"][scales[-1]]["latency"][kk]["p95_ms"], after_p95=a.get("p95_ms")) for kk, a in after.items()}
            conn.execute(f"DROP INDEX {name}"); conn.commit()
    json.dump(res, open(out / "scalability.json", "w"), indent=1, default=str)
    return res
