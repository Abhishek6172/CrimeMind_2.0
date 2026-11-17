"""Phase 4: Q40-R and RAEER against Q40 and all Phase 3 baselines, identical datasets and conditions.
  python -m research.phase4.run_phase4 [--seeds 2026-2075] [--workers 3]"""
import argparse
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
from research.phase3.algorithms import PHASE3_METHODS   # noqa: E402
from research.phase3.evaluation import evaluator as ev3   # noqa: E402
from research.phase3.run_phase3 import analyse   # noqa: E402
from research.phase4.algorithms import PHASE4_NEW, make   # noqa: E402

OUT = ROOT / "research" / "phase4" / "results"
CFG4 = json.load(open(ROOT / "research/phase4/configs/phase4_config.json"))
CFG = {**ev3.CFG, **CFG4, "config_version": f"p3:{ev3.CFG['config_version']}+p4:{CFG4['config_version']}"}
METHODS = PHASE3_METHODS + PHASE4_NEW


def _task(a):
    seed, methods = a
    try:
        return {"seed": seed, "rows": ev3.run_seed(seed, methods, cfg=CFG, prefix="cm_p4", maker=make), "error": None}
    except Exception as e:
        return {"seed": seed, "rows": [], "error": f"{type(e).__name__}: {e}"[:400]}


def strata(rows, methods):
    """Stratified lead ranks (evaluator-side; uses labels). Strata are defined independently of the method."""
    allrel = sorted(d["mean_reliability"] for r in rows if r["method"] == methods[0] for d in r["conditions"]["lead_details"] if d["kind"] == "lead" and d["mean_reliability"] is not None)
    med = allrel[len(allrel) // 2]
    out = {"reliability_split_median": med}
    for m in methods:
        groups = {}
        for r in (x for x in rows if x["method"] == m):
            for d in r["conditions"]["lead_details"]:
                if d["kind"] == "lead":
                    groups.setdefault(("reliability", "low (< median)" if (d["mean_reliability"] or 0) < med else "high (>= median)"), []).append(d["rank"])
                    groups.setdefault(("contradiction", "lead has contradicting evidence" if d["has_contradicting_evidence"] else "no contradicting evidence"), []).append(d["rank"])
                    for t in d["types"]:
                        groups.setdefault(("evidence_type", t), []).append(d["rank"])
                else:
                    groups.setdefault(("red_herring", d.get("decoy_type") or "?"), []).append(d["rank"])
        out[m] = {f"{k}:{v}": {"n": len(rs), "median_rank": sorted(rs)[len(rs) // 2], "share_top5": sum(1 for x in rs if x <= 5) / len(rs),
                                "mrr_like": sum(1 / x for x in rs) / len(rs)} for (k, v), rs in sorted(groups.items())}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default=ev3.CFG["seeds"])
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--methods", nargs="*", default=METHODS)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    run_id = a.run_id or runmeta.new_run_id("P4")
    outdir = Path(a.out) / run_id
    outdir.mkdir(parents=True, exist_ok=False)
    seeds = parse_seeds(a.seeds)
    rows, errors = [], []
    with ProcessPoolExecutor(a.workers) as ex:
        for res in ex.map(_task, [(s, a.methods) for s in seeds]):
            (errors.append({"seed": res["seed"], "error": res["error"]}) if res["error"] else rows.extend(res["rows"]))
            print(res["seed"], "FAILED " + res["error"] if res["error"] else "ok", flush=True)
    analyse(rows, a.methods, outdir, cfg=CFG)
    st = strata(rows, a.methods)
    json.dump(st, open(outdir / "strata.json", "w"), indent=1)
    ds_hash = {s: json.load(open(ROOT / "research/datasets" / f"seed_{s}" / "dataset_manifest.json"))["summary"]["content_sha256"] for s in seeds}
    runmeta.write_manifest(outdir, run_id, phase=4, methods=a.methods, seeds=seeds, dataset_hashes=ds_hash, config=CFG, status="COMPLETED" if not errors else "COMPLETED_WITH_ERRORS",
                           errors=errors, seeds_evaluated=len({r["seed"] for r in rows}), hash_verified_all=all(r["hash_verified"] for r in rows))
    (Path(a.out) / "LATEST.txt").write_text(run_id)
    print("run", run_id, "seeds", len({r["seed"] for r in rows}), "errors", len(errors))
    return run_id


if __name__ == "__main__":
    main()
