"""Run Phase 3: every ranking method on every seed, per-seed metrics, aggregates, paired statistics, condition analysis.
  python -m research.phase3.run_phase3 [--seeds 2026-2075] [--workers 3] [--run-id ID] [--methods ...]"""
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
from research.generate_datasets import parse_seeds   # noqa: E402
from research.phase3.algorithms import EXTRA_METHODS, PHASE3_METHODS   # noqa: E402
from research.phase3.evaluation.evaluator import CFG, run_seed   # noqa: E402
from research.phase3.metrics.ranking_metrics import METRIC_NAMES   # noqa: E402
from research.phase3.statistical_analysis.stats import all_pairs, summarise   # noqa: E402

OUT = ROOT / "research" / "phase3" / "results"


def _task(a):
    seed, methods = a
    try:
        return {"seed": seed, "rows": run_seed(seed, methods), "error": None}
    except Exception as e:
        return {"seed": seed, "rows": [], "error": f"{type(e).__name__}: {e}"[:400]}


def seed_level(rows, methods):
    """Mean over each seed's cases -> {method: {metric: [value per seed (aligned, sorted by seed)]}}."""
    seeds = sorted({r["seed"] for r in rows})
    out = {m: {k: [] for k in METRIC_NAMES} for m in methods}
    for s in seeds:
        for m in methods:
            rs = [r for r in rows if r["seed"] == s and r["method"] == m]
            for k in METRIC_NAMES:
                v = [r[k] for r in rs if r[k] is not None]
                out[m][k].append(sum(v) / len(v) if v else None)
    return seeds, out


def analyse(rows, methods, outdir: Path, cfg=CFG):
    seeds, sl = seed_level(rows, methods)
    stat = cfg["statistics"]
    with open(outdir / "per_case_metrics.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["seed", "case_ref", "method", "n_candidates", "n_relevant", "n_repetitions"] + METRIC_NAMES)
        for r in rows:
            w.writerow([r["seed"], r["case_ref"], r["method"], r["n_candidates"], r["n_relevant"], r["n_repetitions"]] + [r[k] for k in METRIC_NAMES])
    with open(outdir / "per_seed_metrics.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["seed", "method"] + METRIC_NAMES)
        for i, s in enumerate(seeds):
            for m in methods:
                w.writerow([s, m] + [sl[m][k][i] for k in METRIC_NAMES])
    agg = {m: {k: summarise(sl[m][k], stat["bootstrap_seed"], stat["bootstrap_resamples"]) for k in METRIC_NAMES} for m in methods}
    with open(outdir / "aggregate_metrics.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["method", "metric", "n_seeds", "mean", "median", "std", "ci95_low", "ci95_high"])
        for m in methods:
            for k in METRIC_NAMES:
                a = agg[m][k]; w.writerow([m, k, a["n"], a.get("mean"), a.get("median"), a.get("std"), a.get("ci95_low"), a.get("ci95_high")])
    pairs = {k: all_pairs({m: sl[m][k] for m in methods}, stat["bootstrap_seed"], stat["bootstrap_resamples"]) for k in METRIC_NAMES}
    with open(outdir / "paired_comparisons.csv", "w", newline="") as f:
        cols = ["metric", "A", "B", "n", "mean_diff", "ci95_low", "ci95_high", "wilcoxon_p", "p_holm", "significant_holm_0.05", "rank_biserial", "cohens_dz", "wins", "losses", "ties"]
        w = csv.writer(f); w.writerow(cols)
        for k, rs in pairs.items():
            for r in rs:
                w.writerow([k] + [r.get(c) for c in cols[1:]])
    # conditions: recall of leads by evidence strength; red-herring promotion; by case size
    cond = {}
    for m in methods:
        rs = [r for r in rows if r["method"] == m]
        strength, rh_top5, rh_n, by_size = {}, 0, 0, {}
        for r in rs:
            c = r["conditions"]
            for st, ranks in c["lead_strength_ranks"].items():
                strength.setdefault(st, []).extend(ranks)
            rh_top5 += c["red_herrings_in_top5"]; rh_n += len(c["red_herring_ranks"])
            by_size.setdefault(r["case_ref"].rsplit("-", 1)[1], []).append(r["nDCG@5"])
        cond[m] = {"lead_rank_by_strength": {st: {"n_leads": len(v), "median_rank": sorted(v)[len(v) // 2], "share_in_top5": sum(1 for x in v if x <= 5) / len(v),
                                                 "share_in_top10": sum(1 for x in v if x <= 10) / len(v)} for st, v in strength.items()},
                   "red_herrings_in_top5": rh_top5, "red_herrings_total": rh_n,
                   "nDCG@5_by_case": {k: sum(x for x in v if x is not None) / max(1, len([x for x in v if x is not None])) for k, v in by_size.items()},
                   "mean_distinct_scores": sum(r["n_distinct_scores"] for r in rs) / len(rs),
                   "tie_bounds_mean": {mode: {k: sum(r["tie_bounds"][mode][k] for r in rs if r["tie_bounds"][mode][k] is not None) / len(rs)
                                              for k in ("MRR", "AP", "nDCG@5")} for mode in ("optimistic", "pessimistic")}}
    json.dump({"aggregate": agg, "conditions": cond, "pairs": pairs}, open(outdir / "analysis.json", "w"), indent=1, default=str)
    return agg, pairs, cond


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default=CFG["seeds"])
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--methods", nargs="*", default=PHASE3_METHODS + EXTRA_METHODS)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    run_id = a.run_id or runmeta.new_run_id("P3")
    outdir = Path(a.out) / run_id
    outdir.mkdir(parents=True, exist_ok=False)
    seeds = parse_seeds(a.seeds)
    rows, errors = [], []
    with ProcessPoolExecutor(a.workers) as ex:
        for res in ex.map(_task, [(s, a.methods) for s in seeds]):
            (errors.append({"seed": res["seed"], "error": res["error"]}) if res["error"] else rows.extend(res["rows"]))
            print(res["seed"], "FAILED " + res["error"] if res["error"] else "ok", flush=True)
    agg, pairs, cond = analyse(rows, a.methods, outdir)
    ds_hash = {s: json.load(open(ROOT / "research/datasets" / f"seed_{s}" / "dataset_manifest.json"))["summary"]["content_sha256"] for s in seeds}
    runmeta.write_manifest(outdir, run_id, phase=3, methods=a.methods, seeds=seeds, dataset_hashes=ds_hash, config=CFG,
                           status="COMPLETED" if not errors else "COMPLETED_WITH_ERRORS", errors=errors,
                           seeds_evaluated=len({r["seed"] for r in rows}), hash_verified_all=all(r["hash_verified"] for r in rows))
    (Path(a.out) / "LATEST.txt").write_text(run_id)
    print("run", run_id, "seeds", len({r["seed"] for r in rows}), "errors", len(errors))
    return run_id


if __name__ == "__main__":
    main()
