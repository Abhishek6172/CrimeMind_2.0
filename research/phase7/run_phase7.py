"""Phase 7 runner: python -m research.phase7.run_phase7 [--stages oracles q40 db perf] [--quick]"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "backend"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
from research.common import runmeta   # noqa: E402

R = Path(__file__).resolve().parent


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", nargs="+", default=["oracles", "q40", "db", "perf"])
    ap.add_argument("--quick", action="store_true", help="2 seeds, scales 1,2, 5 repetitions (smoke run; recorded as such)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    cfg = json.load(open(R / "configs" / "phase7_config.json"))
    if a.quick:
        cfg["oracle_seeds"], cfg["edge_seeds"], cfg["q40_seeds"] = cfg["oracle_seeds"][:1], cfg["edge_seeds"][:1], cfg["q40_seeds"][:1]
        cfg["perf"].update(scales=[1, 2], repetitions=5)
    run_id = runmeta.new_run_id("P7")
    out = Path(a.out) if a.out else R / "results" / run_id
    out.mkdir(parents=True, exist_ok=True)
    status, errors = {}, {}
    from research.phase7 import run_oracles, run_dbchecks, run_perf
    steps = {
        "oracles": lambda: (lambda rows_log: json.dump(run_oracles.summarise(rows_log[0]), open(out / "oracle_summary.json", "w"), indent=1))(run_oracles.run(cfg["oracle_seeds"], out, cfg["edge_seeds"])),
        "q40": lambda: run_oracles.run_q40(cfg["q40_seeds"], out),
        "db": lambda: run_dbchecks.run(cfg["db_check_seed"], out),
        "perf": lambda: run_perf.run(cfg["perf"]["seed"], cfg["perf"]["scales"], cfg["perf"]["repetitions"], out, cfg["perf"]["slow_query_threshold_ms"]),
    }
    for s in a.stages:
        try:
            steps[s]()
            status[s] = "EXECUTED"
        except Exception as e:
            import traceback
            status[s] = "FAILED"
            errors[s] = traceback.format_exc()[-1500:]
    runmeta.write_manifest(out, run_id, phase="phase7", config=cfg, stages=status, quick=a.quick, errors=errors)
    json.dump(dict(run_id=run_id, stages=status, errors=errors), open(out / "stage_status.json", "w"), indent=1)
    if not errors and not a.quick:
        (R / "results" / "LATEST.txt").write_text(run_id)
    print(run_id, status)
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
