"""Unified research runner.  python -m research.run_all --phases 3 4 5 6 7 8 [--quick] [--seeds 2026-2075] [--workers 3] [--providers]

Runs the real experiments of each phase (no cached results), rebuilds each phase report from the stored results, then (phase 8) aggregates
results, draws the figures and writes the reproducibility manifest. --quick runs a reduced smoke configuration into a scratch directory,
does NOT touch the official results/reports, and is recorded as such. Works on Windows (no shell features used)."""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "research"
for p in (ROOT, ROOT / "backend"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
from research.common import runmeta   # noqa: E402

PY = sys.executable


def sh(args, log: Path, env=None):
    t = time.time()
    with open(log, "w", encoding="utf-8") as f:
        rc = subprocess.run([PY, *args], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, env=env).returncode
    return rc, round(time.time() - t, 1)


def file_hash(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def phase_plan(ph: int, a, scratch: Path | None):
    """list of (label, argv) for a phase."""
    seeds = ["--seeds", a.seeds] if a.seeds else []
    w = ["--workers", str(a.workers)]
    out = lambda name: ["--out", str(scratch / name)] if scratch else []
    if ph == 3:
        return [("experiment", ["-m", "research.phase3.run_phase3", *seeds, *w, *out("phase3")])] + ([] if scratch else [("report", [str(R / "phase3/reports/make_report.py")])])
    if ph == 4:
        return [("experiment", ["-m", "research.phase4.run_phase4", *seeds, *w, *out("phase4")])] + ([] if scratch else [("report", [str(R / "phase4/reports/make_report.py")])])
    if ph == 5:
        steps = [("experiment", ["-m", "research.phase5.run_phase5", *seeds, *w, *out("phase5")])]
        if scratch:
            steps.append(("analysis", ["-c", f"import sys,json,pathlib;d=pathlib.Path(r'{scratch / 'phase5'}');rd=d/(d/'LATEST.txt').read_text().strip();sys.argv=['x',str(rd)];import runpy;runpy.run_module('research.phase5.analyse',run_name='__main__')"]))
        else:
            steps += [("analysis", ["-m", "research.phase5.analyse"]), ("report", [str(R / "phase5/make_report.py")])]
        return steps
    if ph == 6:
        steps = [("benchmark", ["-m", "research.phase6.benchmark.build_benchmark"]) if not scratch else None,
                 ("experiment", ["-m", "research.phase6.run_phase6", *w, *out("phase6")]),
                 ("provider_harness", ["-m", "research.phase6.provider_eval", *(["--out", str(scratch / "phase6_providers")] if scratch else [])])]
        if not scratch:
            steps.append(("report", [str(R / "phase6/reports/make_report.py")]))
        return [s for s in steps if s]
    if ph == 7:
        return [("experiment", ["-m", "research.phase7.run_phase7", *(["--quick", "--out", str(scratch / "phase7")] if scratch else [])])] + (
            [] if scratch else [("docs", [str(R / "phase7/reports/make_docs.py")]), ("report", [str(R / "phase7/reports/make_report.py")])])
    return []


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phases", nargs="+", type=int, default=[3, 4, 5, 6, 7, 8])
    ap.add_argument("--seeds", default=None, help="e.g. 2026-2075 or 2026,2031 (phases 3,4,5); default from each phase config")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--quick", action="store_true", help="smoke run: seeds 2026-2028, phase 7 quick; writes to a scratch directory only")
    ap.add_argument("--dry-run", action="store_true", help="print the commands and exit")
    ap.add_argument("--out", default=None, help="directory for the run_all manifest/logs (default research/phase8/results/<run id>)")
    a = ap.parse_args(argv)
    if a.quick and not a.seeds:
        a.seeds = "2026-2028"
    run_id = runmeta.new_run_id("P8" if 8 in a.phases else "RA")
    out = Path(a.out) if a.out else R / "phase8" / "results" / (run_id + ("-quick" if a.quick else ""))
    scratch = out / "scratch" if a.quick else None
    plans = {ph: phase_plan(ph, a, scratch) for ph in a.phases}
    if a.dry_run:
        for ph, steps in plans.items():
            for label, args in steps:
                print(f"phase {ph} [{label}]: {PY} {' '.join(args)}")
        return 0
    (out / "logs").mkdir(parents=True, exist_ok=True)
    status = {}
    for ph in a.phases:
        for label, args in plans[ph]:
            key = f"phase{ph}.{label}"
            rc, secs = sh(args, out / "logs" / f"{key}.log")
            status[key] = dict(status="EXECUTED" if rc == 0 else "FAILED", return_code=rc, seconds=secs, command=f"python {' '.join(args)}")
            print(f"{key:28s} {status[key]['status']:9s} {secs:8.1f}s", flush=True)
            if rc != 0:
                break                     # later steps of this phase depend on this one
    if 8 in a.phases and not a.quick:
        from research.phase8 import aggregate, plots
        try:
            aggregate.write_index(out)
            plots.build(R / "phase8" / "figures")
            status["phase8.aggregate_and_figures"] = dict(status="EXECUTED")
        except Exception as e:
            status["phase8.aggregate_and_figures"] = dict(status="FAILED", error=f"{type(e).__name__}: {e}")
        rc, secs = sh([str(R / "phase8" / "build_final_report.py")], out / "logs" / "phase8.final_report.log")
        status["phase8.final_report"] = dict(status="EXECUTED" if rc == 0 else "FAILED", return_code=rc, seconds=secs)
    elif 8 in a.phases:
        status["phase8.aggregate_and_figures"] = dict(status="SKIPPED", reason="--quick never rewrites official aggregates, figures or reports")
    seeds_m = list(csv_rows(R / "seed_manifest.csv"))
    manifest = dict(run_id=run_id, quick=a.quick, phases=a.phases, command=" ".join([PY, "-m", "research.run_all", *(argv if argv is not None else sys.argv[1:])]),
                    environment=runmeta.environment(), git_commit=runmeta.git_commit(), git_dirty=runmeta.git_dirty(), steps=status,
                    datasets=[dict(seed=r["seed"], content_sha256=r["content_sha256"]) for r in seeds_m],
                    configs={str(p.relative_to(ROOT)).replace("\\", "/"): file_hash(p) for p in sorted(R.glob("phase*/configs/*.json")) + [R / "generation_config.json"]},
                    frozen_q40_bundle={str(p.relative_to(ROOT)).replace("\\", "/"): file_hash(p) for p in sorted((R / "results" / "baseline").glob("*")) if p.is_file()},
                    status="COMPLETED" if all(v["status"] in ("EXECUTED", "SKIPPED") for v in status.values()) else "COMPLETED_WITH_FAILURES")
    (out / "run_all_manifest.json").write_text(json.dumps(manifest, indent=1, default=str), encoding="utf-8")
    print("run", run_id, manifest["status"], "->", out)
    return 0 if manifest["status"] == "COMPLETED" else 1


def csv_rows(p):
    import csv
    return csv.DictReader(open(p, encoding="utf-8"))


if __name__ == "__main__":
    sys.exit(main())
