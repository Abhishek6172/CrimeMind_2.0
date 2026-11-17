"""Generate N independent research datasets with independent ground truth (Phase 2).

  python research/generate_datasets.py --seeds 2026-2075 [--workers 3] [--keep-db] [--force]

Per seed: creates DB cm_r_<seed>, seeds two storylines, validates, exports deterministic CSV.gz tables to
research/datasets/seed_<seed>/, writes research/ground_truth/seed_<seed>.json, drops the DB (unless --keep-db).
Seeds with a valid manifest are skipped (resume). Failures are logged to research/failures.json, never hidden.
"""
import argparse, csv, gzip, hashlib, io, json, subprocess, sys, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))
R = ROOT / "research"
TABLES = {"entities": "SELECT * FROM entities", "events": "SELECT * FROM events", "event_entities": "SELECT * FROM event_entities",
          "evidence": "SELECT * FROM evidence", "evidence_entities": "SELECT * FROM evidence_entities",
          "evidence_events": "SELECT * FROM evidence_events", "location_observations": "SELECT * FROM location_observations",
          "communications": "SELECT * FROM communications", "transactions": "SELECT * FROM transactions",
          "relationships": "SELECT * FROM relationships"}
DROP = {"created_at", "updated_at", "created_by", "updated_by"}


def parse_seeds(spec: str) -> list[int]:
    out = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def export_table(conn, name: str, sql: str, outdir: Path) -> dict:
    cur = conn.execute(f"SELECT * FROM ({sql}) t ORDER BY 1,2")
    cols = [c.name for c in cur.description if c.name not in DROP]
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    n = 0
    for r in cur:
        w.writerow(["" if r[c] is None else (json.dumps(r[c], sort_keys=True) if isinstance(r[c], (dict, list)) else r[c]) for c in cols])
        n += 1
    data = buf.getvalue().encode()
    with open(outdir / f"{name}.csv.gz", "wb") as f:   # mtime=0 -> deterministic bytes
        with gzip.GzipFile(fileobj=f, mode="wb", mtime=0) as gz:
            gz.write(data)
    return {"rows": n, "sha256": hashlib.sha256(data).hexdigest()}


def one_seed(seed: int, keep_db: bool, force: bool) -> dict:
    import psycopg
    from psycopg.rows import dict_row
    from synth.research_seed import seed_database, BASE
    from synth.dataset_validation import validate_case, check_no_leakage
    out = R / "datasets" / f"seed_{seed}"
    gtp = R / "ground_truth" / f"seed_{seed}.json"
    if (out / "dataset_manifest.json").exists() and gtp.exists() and not force:
        m = json.load(open(out / "dataset_manifest.json"))
        return {**m["summary"], "seed": seed, "status": "SKIPPED_EXISTING"}
    cfg = json.load(open(R / "generation_config.json"))
    db = f"cm_r_{seed}"
    t0 = time.time()
    from research.common.portable_lock import file_lock   # CREATE DATABASE contends on template1; serialise DB creation only
    with file_lock():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "init_db.py"), "--db", db, "--reset"], check=True, capture_output=True,
                       cwd=ROOT / "backend")
    gts = seed_database(db, seed, cfg)
    problems = []
    out.mkdir(parents=True, exist_ok=True)
    tables = {}
    with psycopg.connect(f"{BASE}/{db}", row_factory=dict_row) as conn:
        for g in gts.values():
            problems += validate_case(conn, g)
        problems += check_no_leakage(conn, list(gts))
        if problems:
            raise RuntimeError("dataset validation failed: " + "; ".join(problems[:5]))
        for name, sql in TABLES.items():
            tables[name] = export_table(conn, name, sql, out)
        findings = {c: conn.execute("SELECT count(*) n FROM findings f JOIN cases c USING(case_id) WHERE c.case_ref=%s AND f.status='CURRENT'", (c,)).fetchone()["n"] for c in gts}
    prim = gts[f"CASE-{seed}-001"]
    json.dump({"seed": seed, "config_version": cfg["config_version"], "cases": gts}, open(gtp, "w"), indent=1, sort_keys=True, default=str)
    content_hash = hashlib.sha256("".join(tables[k]["sha256"] for k in sorted(tables)).encode()).hexdigest()
    summary = {"leads": len(prim["relevant_leads"]), "red_herrings": len(prim["red_herrings"]), "persons": len(prim["eligible_entities"]) + 1,
               "findings": sum(findings.values()), "lifecycle_steps": sum(len(g["lifecycle"]) for g in gts.values()),
               "evidence_rows": tables["evidence"]["rows"], "content_sha256": content_hash}
    json.dump({"seed": seed, "database": db, "tables": tables, "summary": summary, "validation": "PASSED", "cases": sorted(gts),
               "seconds": round(time.time() - t0, 1)}, open(out / "dataset_manifest.json", "w"), indent=1, sort_keys=True)
    if not keep_db:
        with psycopg.connect(f"{BASE}/postgres", autocommit=True) as c:
            c.execute(f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)')
    return {**summary, "seed": seed, "status": "GENERATED"}


def _run(a):
    try:
        return one_seed(*a)
    except Exception as e:  # logged, never swallowed
        return {"seed": a[0], "status": "FAILED", "error": str(e)[:500]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="2026-2075")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--keep-db", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    seeds = parse_seeds(a.seeds)
    (R / "datasets").mkdir(exist_ok=True); (R / "ground_truth").mkdir(exist_ok=True)
    res = []
    with ProcessPoolExecutor(a.workers) as ex:
        for f in as_completed([ex.submit(_run, (s, a.keep_db, a.force)) for s in seeds]):
            r = f.result(); res.append(r); print(r["seed"], r["status"], r.get("error", ""), flush=True)
    res.sort(key=lambda r: r["seed"])
    ok = [r for r in res if r["status"] != "FAILED"]
    with open(R / "seed_manifest.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["seed", "status", "persons", "leads", "red_herrings", "findings", "lifecycle_steps", "evidence_rows", "content_sha256"])
        for r in ok:
            w.writerow([r["seed"], r["status"], r["persons"], r["leads"], r["red_herrings"], r["findings"], r["lifecycle_steps"], r["evidence_rows"], r["content_sha256"]])
    fails = [r for r in res if r["status"] == "FAILED"]
    json.dump(fails, open(R / "failures.json", "w"), indent=1)
    print(f"done: {len(ok)} ok, {len(fails)} failed")
