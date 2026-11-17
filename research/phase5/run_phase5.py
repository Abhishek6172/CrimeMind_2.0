"""Phase 5: ablation, robustness, sensitivity and evidence-evolution experiments over the Phase 2 seeds.
  python -m research.phase5.run_phase5 [--seeds 2026-2075] [--workers 3] [--parts ablation robustness sensitivity evolution]"""
import argparse
import csv
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "backend"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
from research.common import runmeta   # noqa: E402
from research.common.casedata import load_case_view   # noqa: E402
from research.common.workspace import SeedWorkspace, load_ground_truth   # noqa: E402
from research.generate_datasets import parse_seeds   # noqa: E402
from research.phase3.evaluation import evaluator as ev3   # noqa: E402
from research.phase3.metrics.ranking_metrics import METRIC_NAMES   # noqa: E402
from research.phase4.run_phase4 import CFG as CFG45   # noqa: E402
from research.phase5 import perturb, sensitivity   # noqa: E402
from research.phase5.algorithms import make   # noqa: E402
from research.phase5.evolution import run_evolution   # noqa: E402

OUT = ROOT / "research" / "phase5" / "results"
CFG5 = json.load(open(ROOT / "research/phase5/configs/phase5_config.json"))
CFG = {**CFG45, **{k: v for k, v in CFG5.items() if k != "config_version"}, "config_version": f"{CFG45['config_version']}+p5:{CFG5['config_version']}"}
KEEP = ("P@1", "P@3", "P@5", "R@5", "MRR", "nDCG@5", "AP")


def _row(seed, exp, cond, level, r):
    return {"seed": seed, "case_ref": r["case_ref"], "experiment": exp, "condition": cond, "level": level, "method": r["method"],
            **{k: r[k] for k in KEEP}, "n_relevant": r["n_relevant"]}


def seed_task(a):
    seed, parts = a
    rows, evo = [], []
    try:
        gts = load_ground_truth(seed)
        with SeedWorkspace(seed, prefix="cm_p5") as w:
            for c in w.cases():
                ref = c["case_ref"]
                gt = gts[ref]
                view = load_case_view(w.conn, ref)
                ds = f"seed_{seed}"
                ev = lambda v, ms: ev3.evaluate_methods(v, gt, ds, ms, CFG, maker=make)
                if "ablation" in parts:
                    for r in ev(view, ["q40_py"] + CFG["ablations"]):
                        rows.append(_row(seed, "ablation", "clean", 0, r))
                    mixed = perturb.perturb(view, "mixed_quality", 0.4, seed)
                    for r in ev(mixed, ["q40_py"] + CFG["ablations"]):
                        rows.append(_row(seed, "ablation", "mixed_quality", 0.4, r))
                if "robustness" in parts:
                    for r in ev(view, CFG["methods_robustness"]):
                        rows.append(_row(seed, "robustness", "clean", 0, r))
                    for kind, levels in CFG["perturbations"].items():
                        for lv in levels:
                            pv = perturb.perturb(view, kind, lv, seed)
                            for r in ev(pv, CFG["methods_robustness"]):
                                rows.append(_row(seed, "robustness", kind, lv, r))
                if "sensitivity" in parts:
                    for r in ev(view, sensitivity.names()):
                        rows.append(_row(seed, "sensitivity", "clean", 0, r))
                if "evolution" in parts:
                    res = run_evolution(w.conn, ref, gt, CFG, CFG["evolution"], ds)
                    final = res.pop("final_view")
                    res["seed"] = seed
                    evo.append(res)
                    if "ablation" in parts:
                        for r in ev(final, ["q40_py"] + CFG["ablations"]):
                            rows.append(_row(seed, "ablation", "evolved", 1, r))
                        from research.phase3.algorithms import make as make3
                        r = ev3.evaluate_methods(final, gt, ds, ["q40"], CFG, maker=make)[0]   # frozen SQL on the evolved database
                        rows.append(_row(seed, "ablation", "evolved", 1, r))
        return {"seed": seed, "rows": rows, "evo": evo, "error": None}
    except Exception as e:
        import traceback
        return {"seed": seed, "rows": [], "evo": [], "error": f"{type(e).__name__}: {e} | {traceback.format_exc()[-600:]}"}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default=ev3.CFG["seeds"])
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--parts", nargs="*", default=["ablation", "robustness", "sensitivity", "evolution"])
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    run_id = a.run_id or runmeta.new_run_id("P5")
    outdir = Path(a.out) / run_id
    outdir.mkdir(parents=True, exist_ok=False)
    seeds = parse_seeds(a.seeds)
    rows, evo, errors = [], [], []
    with ProcessPoolExecutor(a.workers) as ex:
        for res in ex.map(seed_task, [(s, a.parts) for s in seeds]):
            if res["error"]:
                errors.append({"seed": res["seed"], "error": res["error"]})
            else:
                rows.extend(res["rows"]); evo.extend(res["evo"])
            print(res["seed"], "FAILED " + res["error"][:200] if res["error"] else "ok", flush=True)
    with open(outdir / "per_case_results.csv", "w", newline="") as f:
        cols = ["seed", "case_ref", "experiment", "condition", "level", "method", "n_relevant"] + list(KEEP)
        wr = csv.DictWriter(f, fieldnames=cols); wr.writeheader(); wr.writerows(rows)
    json.dump(evo, open(outdir / "evolution_results.json", "w"), indent=1, default=str)
    ds_hash = {s: json.load(open(ROOT / "research/datasets" / f"seed_{s}" / "dataset_manifest.json"))["summary"]["content_sha256"] for s in seeds}
    runmeta.write_manifest(outdir, run_id, phase=5, parts=a.parts, seeds=seeds, dataset_hashes=ds_hash, config=CFG, status="COMPLETED" if not errors else "COMPLETED_WITH_ERRORS",
                           errors=errors, seeds_evaluated=len({r["seed"] for r in rows}), rows=len(rows))
    (Path(a.out) / "LATEST.txt").write_text(run_id)
    print("run", run_id, "seeds", len({r["seed"] for r in rows}), "rows", len(rows), "errors", len(errors))
    return run_id


if __name__ == "__main__":
    main()
