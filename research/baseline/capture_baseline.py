#!/usr/bin/env python3
"""Reproducible capture of the frozen CrimeMind research baseline (Milestone 1).

Rebuilds a scratch database from scratch, runs the existing test suite, evaluates Q40 BEFORE and AFTER the six scripted
evidence-evolution steps, and writes everything under research/results/baseline/. It changes no application code.

Usage (PostgreSQL 16 running, admin postgres/postgres):
    python3 research/baseline/capture_baseline.py [--seed 2026] [--db research_baseline]
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
OUT = ROOT / "research" / "results" / "baseline"
BASE = os.environ.get("CM_ADMIN_URL_BASE", "postgresql://postgres:postgres@localhost:5432")
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("CM_JWT_SECRET", "research-baseline-not-a-secret")
os.environ["CM_AI_PROVIDER"] = "offline"          # the baseline never calls an LLM


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=BACKEND, capture_output=True, text=True, env={**os.environ, **kw.pop("env", {})}, **kw)


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def evaluate(db: str, k_values=(1, 2, 3, 5)) -> list[dict]:
    out = []
    for k in k_values:
        r = run([sys.executable, "-m", "synth.evaluate", "--db", db, "--k", str(k)])
        text = r.stdout[r.stdout.index("{"):r.stdout.rindex("}") + 1]
        out.append(json.loads(text))
    return out


def full_ranking(db: str) -> list[dict]:
    import psycopg
    from psycopg.rows import dict_row
    from app.sql_engine import execute_question
    with psycopg.connect(f"{BASE}/{db}", row_factory=dict_row) as conn:
        case = conn.execute("SELECT case_id, case_ref FROM cases WHERE case_ref='CASE-2026-001'").fetchone()
        conn.execute("SELECT set_config('app.user','system.evaluate',false)")
        res = execute_question(conn, "system.evaluate", case, "Q40", {"event_id": "EVT-001", "result_limit": 25})
        rows = res.get("rows") or res.get("results") or []
        return [{"rank": i + 1, "entity_ref": r["entity_ref"], "association_score": float(r["association_score"]),
                 "signals": r["contributing_signals"], "independent_sources": r["independent_evidence_sources"]} for i, r in enumerate(rows)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--db", default="research_baseline")
    ap.add_argument("--out", default=str(OUT), help="results directory (default: the frozen baseline folder)")
    ap.add_argument("--force", action="store_true", help="allow overwriting an existing results directory")
    a = ap.parse_args()
    out_dir = Path(a.out)
    if (out_dir / "manifest.json").exists() and not a.force:
        raise SystemExit(f"{out_dir} already holds a captured run; refusing to overwrite experimental evidence. Use --out or --force.")
    out_dir.mkdir(parents=True, exist_ok=True)
    globals()["OUT"] = out_dir

    # 1. unit/integration tests (they build their own crimemind_test database)
    t = run([sys.executable, "-m", "pytest", "tests", "-q", f"--junitxml={OUT / 'pytest_junit.xml'}", "-p", "no:cacheprovider"])
    (OUT / "pytest_output.txt").write_text(t.stdout + t.stderr)
    summary = [l for l in t.stdout.splitlines() if " passed" in l or " failed" in l]

    # 2. fresh scratch database with the baseline seed
    run([sys.executable, str(ROOT / "scripts" / "init_db.py"), "--db", a.db, "--reset"])
    s = run([sys.executable, "-m", "synth.seed", "--db", a.db, "--seed", str(a.seed)])
    seeded = next((l for l in s.stdout.splitlines() if l.startswith("seeded:")), s.stdout + s.stderr)

    # 3. Q40 before any evidence change
    before = {"ranking": full_ranking(a.db), "metrics_by_k": evaluate(a.db)}

    # 4. apply the six scripted evidence-evolution steps through the system's own change_validity()
    import psycopg
    from psycopg.rows import dict_row
    from synth import scenario
    scenario.BASE = BASE
    steps = []
    with psycopg.connect(f"{BASE}/{a.db}", row_factory=dict_row) as conn:
        while True:
            pend = scenario.pending(conn)
            if not pend:
                break
            res = scenario.apply_step(conn, pend[0]["scenario_id"], pend[0]["step"])
            f, e = set(res["flagged_findings"]), set(res["expected"])
            res.update({"flagged_not_expected": sorted(f - e), "expected_not_flagged": sorted(e - f),
                        "matches_expected": f == e})
            steps.append(res)
    after = {"ranking": full_ranking(a.db), "metrics_by_k": evaluate(a.db)}

    (OUT / "q40_before_scenarios.json").write_text(json.dumps(before, indent=2, default=str))
    (OUT / "q40_after_scenarios.json").write_text(json.dumps(after, indent=2, default=str))
    (OUT / "evidence_evolution_steps.json").write_text(json.dumps(steps, indent=2, default=str))

    # 5. environment + provenance manifest
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or None
    q40 = BACKEND / "app" / "sql_modules" / "18_get_case_evidence_ranking.sql"
    manifest = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator_seed": a.seed, "database": a.db, "seeded_counts": seeded, "git_commit": git,
        "python": platform.python_version(), "platform": platform.platform(),
        "packages": {p: metadata.version(p) for p in ("fastapi", "psycopg", "pytest", "httpx", "bcrypt", "PyJWT", "networkx")},
        "postgres": subprocess.run(["psql", "--version"], capture_output=True, text=True).stdout.strip(),
        "ai_provider": "offline-template (no LLM)", "tests": summary,
        "q40_module_sha256": sha256(q40), "q40_config": "research/baseline/q40_config.json",
        "scenario_steps_matching_expected": f"{sum(x['matches_expected'] for x in steps)}/{len(steps)}",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
