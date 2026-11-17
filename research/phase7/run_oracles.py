"""Stage 'oracles' and 'edge': compare every SQL module variant with its independent oracle on committed datasets and on mutated edge-case DBs."""
import csv
import json
import time
import traceback
from pathlib import Path

from research.common.workspace import SeedWorkspace
from research.phase7.compare import compare
from research.phase7.edge_cases import mutate
from research.phase7.oracles.data import from_csv, from_db
from research.phase7.params import VARIANTS, param_sets


def _run(d, conn, seed, tag, extra=None, rows=None):
    for m, v in VARIANTS:
        sets = param_sets(d, m, v, seed)
        for pr in (extra or {}).get((m, v), []):
            sets.append(pr)
        for i, p in enumerate(sets):
            try:
                r = compare(d, conn, m, v, p)
            except Exception as e:
                conn.rollback()
                r = dict(match=False, n_sql=None, n_oracle=None, problems=[f"EXCEPTION {type(e).__name__}: {str(e)[:200]}"])
            rows.append(dict(source=tag, seed=seed, case_id=d.case_id, module=m, variant=v, param_set=i, historical=bool(p.get("include_historical")),
                             windowed=bool(p.get("start_time")), n_sql=r["n_sql"], n_oracle=r["n_oracle"], match=r["match"], problem=" | ".join(r["problems"])[:400]))


def run(seeds, out: Path, edge_seeds):
    rows, edge_log = [], []
    for s in seeds:
        with SeedWorkspace(s, prefix="cm_p7o") as ws:
            for c in ws.cases():
                d = from_csv(s, c["case_id"])
                _run(d, ws.conn, s, "dataset_csv", rows=rows)
    for s in edge_seeds:
        with SeedWorkspace(s, prefix="cm_p7e") as ws:
            for c in ws.cases():
                cid = c["case_id"]
                d0 = from_db(ws.conn, cid)
                log = []
                ids = mutate(ws.conn, cid, d0, log)
                edge_log.append(dict(seed=s, case_id=cid, mutations=log))
                d = from_db(ws.conn, cid)
                extra = {}
                e, a, b = ids.get("empty"), ids.get("a"), ids.get("b")
                persons = sorted(i for i, x in d.entities.items() if x["type"] == "PERSON")
                for m, v in VARIANTS:
                    ps = []
                    for hist in (False, True):
                        veh = sorted(i for i, x in d.entities.items() if x['type'] == 'VEHICLE')
                        base = dict(include_historical=hist, result_limit=1_000_000, event_id=sorted(d.events)[0], vehicle_id=ids.get('veh') or (veh[0] if veh else None))
                        loc = sorted(i for i, x in d.entities.items() if x["type"] == "LOCATION")[0]
                        ps.append(dict(base, entity_id=e, entity_id_1=e, entity_id_2=persons[0], location_id=loc))            # entity with no records
                        ps.append(dict(base, entity_id=a, entity_id_1=a, entity_id_2=b, location_id=loc, min_count=1, window_minutes=0, gap_minutes=1, max_hops=3))                                          # duplicates / NULLs / contradictory
                        t0 = d.comms[0]["at"]
                        ps.append(dict(base, entity_id=a, entity_id_1=a, entity_id_2=b, location_id=loc, start_time=t0, end_time=t0))   # both bounds equal a record time
                    extra[(m, v)] = ps
                _run(d, ws.conn, s, "edge_mutated", extra=extra, rows=rows)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "oracle_comparisons.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    json.dump(edge_log, open(out / "edge_mutation_log.json", "w"), indent=1)
    return rows, edge_log


def summarise(rows):
    by = {}
    for r in rows:
        k = f"{r['module']}.{r['variant']}"
        x = by.setdefault(k, dict(comparisons=0, matches=0, mismatches=0, examples=[]))
        x["comparisons"] += 1
        x["matches" if r["match"] else "mismatches"] += 1
        if not r["match"] and len(x["examples"]) < 2:
            x["examples"].append(dict(source=r["source"], seed=r["seed"], case_id=r["case_id"], problem=r["problem"]))
    return by


def run_q40(seeds, out: Path):
    """M18 'overall' (Q40, frozen SQL) versus the independent Python re-implementation `q40_py` on every case of the given seeds."""
    from research.common.casedata import load_case_view
    from research.phase3.algorithms import make as make3
    from research.phase5.algorithms import make as make5
    R = Path(__file__).resolve().parents[1]
    cfg3 = json.load(open(R / "phase3" / "configs" / "phase3_config.json"))
    cfg4 = json.load(open(R / "phase4" / "configs" / "phase4_config.json"))
    rows = []
    for s in seeds:
        with SeedWorkspace(s, prefix="cm_p7q") as ws:
            for c in ws.cases():
                view = load_case_view(ws.conn, c["case_ref"])
                a = make3("q40").rank(f"seed_{s}", view, cfg3)
                b = make5("q40_py").rank(f"seed_{s}", view, cfg4)
                sa = {x.lead_id: x.raw_score for x in a}
                sb = {x.lead_id: x.raw_score for x in b}
                diff = max((abs(sa[k] - sb.get(k, float("nan"))) for k in sa), default=0)
                rows.append(dict(seed=s, case=c["case_ref"], candidates=len(sa), max_abs_score_diff=diff, same_candidate_set=set(sa) == set(sb), match=diff < 1e-6 and set(sa) == set(sb)))
    json.dump(rows, open(out / "q40_vs_python.json", "w"), indent=1)
    return rows
