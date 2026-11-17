"""Aggregate Phase 5 results: ablations, robustness curves, sensitivity, evidence-evolution. Seed = unit of analysis."""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.phase3.statistical_analysis.stats import all_pairs, holm, paired_comparison, summarise   # noqa: E402

KEY = ("nDCG@5", "MRR", "AP")
ALL = ("P@1", "P@3", "P@5", "R@5", "MRR", "nDCG@5", "AP")


def load(rd: Path):
    rows = list(csv.DictReader(open(rd / "per_case_results.csv")))
    for r in rows:
        for k in ALL:
            r[k] = float(r[k]) if r[k] not in ("", "None") else None
        r["seed"] = int(r["seed"]); r["level"] = float(r["level"])
    return rows


def seed_means(rows, exp, cond, level=None):
    """{method: {metric: [per-seed means aligned by sorted seed]}}"""
    sel = [r for r in rows if r["experiment"] == exp and r["condition"] == cond and (level is None or r["level"] == level)]
    seeds = sorted({r["seed"] for r in sel})
    out = defaultdict(lambda: {k: [] for k in ALL})
    by = defaultdict(list)
    for r in sel:
        by[(r["method"], r["seed"])].append(r)
    for m in sorted({r["method"] for r in sel}):
        for s in seeds:
            rs = by[(m, s)]
            for k in ALL:
                v = [x[k] for x in rs if x[k] is not None]
                out[m][k].append(sum(v) / len(v) if v else None)
    return seeds, out


def analyse(rd: Path, cfg):
    rows = load(rd)
    res = {"ablation": {}, "robustness": {}, "sensitivity": {}}
    ab_methods = ["q40_py"] + cfg["ablations"]
    for cond in ("clean", "mixed_quality", "evolved"):
        seeds, sm = seed_means(rows, "ablation", cond)
        if not sm:
            continue
        block = {"n_seeds": len(seeds), "means": {m: {k: summarise(sm[m][k]) for k in ALL} for m in sm}, "vs_full": {}}
        for k in KEY:
            comps = []
            for m in sm:
                if m in ("raeer",):
                    continue
                c = paired_comparison(sm["raeer"][k], sm[m][k])
                comps.append({"variant": m, **c})
            ps = [c["wilcoxon_p"] for c in comps]
            for c, adj in zip(comps, holm(ps)):
                c["p_holm"] = adj
            block["vs_full"][k] = comps
        res["ablation"][cond] = block
    # robustness
    seeds, clean = seed_means(rows, "robustness", "clean")
    kinds = sorted({r["condition"] for r in rows if r["experiment"] == "robustness" and r["condition"] != "clean"})
    for kind in kinds:
        res["robustness"][kind] = {}
        for lv in sorted({r["level"] for r in rows if r["experiment"] == "robustness" and r["condition"] == kind}):
            _, sm = seed_means(rows, "robustness", kind, lv)
            res["robustness"][kind][str(lv)] = {m: {"nDCG@5": summarise(sm[m]["nDCG@5"]), "MRR": summarise(sm[m]["MRR"]),
                                                    "delta_nDCG@5_vs_clean": paired_comparison(sm[m]["nDCG@5"], clean[m]["nDCG@5"])} for m in sm}
    res["robustness_clean"] = {m: {k: summarise(clean[m][k]) for k in ALL} for m in clean}
    # sensitivity
    seeds, sm = seed_means(rows, "sensitivity", "clean")
    if sm:
        base = {"gamma": "raeer@gamma=0.5", "tau": "raeer@tau=30.0", "radius": "raeer@radius=150.0", "distance": "raeer@distance=1000.0"}
        _, ab = seed_means(rows, "ablation", "clean")
        for m in sorted(sm):
            res["sensitivity"][m] = {"nDCG@5": summarise(sm[m]["nDCG@5"]), "MRR": summarise(sm[m]["MRR"]),
                                     "delta_nDCG@5_vs_default_raeer": paired_comparison(sm[m]["nDCG@5"], ab["raeer"]["nDCG@5"])}
    return res


def analyse_evolution(rd: Path, cfg):
    evo = json.load(open(rd / "evolution_results.json"))
    methods = cfg["evolution"]["methods"]
    steps = [dict(s, seed=c["seed"], case_ref=c["case_ref"]) for c in evo for s in c["steps"]]
    first = lambda s: s["new_status"] in ("CHALLENGED", "INVALIDATED", "SUPERSEDED") and s["step"] == 1
    out = {"cases": len(evo), "steps": len(steps),
           "integrity": {"history_ok_cases": sum(c["history_ok"] for c in evo), "event_ids_unique_cases": sum(c["event_ids_unique"] for c in evo),
                         "event_times_monotonic_cases": sum(c["event_times_monotonic"] for c in evo),
                         "transition_checks_failed_total": sum(c["event_checks_failed"] for c in evo),
                         "steps_applied": sum(c["event_eval"]["steps_applied"] for c in evo), "steps_total": sum(c["event_eval"]["steps_total"] for c in evo),
                         "lifecycle_transition_accuracy_mean": float(np.mean([c["event_eval"]["lifecycle_transition_accuracy"] for c in evo]))},
           "impact_detection": {}, "ranking_change": {}, "latency_ms": {}}
    for label, sel in (("all_steps", steps), ("first_dispute_step", [s for s in steps if s["step"] == 1]), ("later_steps", [s for s in steps if s["step"] > 1])):
        must = sum(s["must_flag"] for s in sel); det = sum(s["detected_expected"] for s in sel)
        neg = sum(s["must_not_flag"] for s in sel)
        out["impact_detection"][label] = {"steps": len(sel), "expected_findings": must, "detected": det, "recall": det / must if must else None,
                                          "must_not_flag_findings_flagged": sum(s["false_alarm_must_not"] for s in sel),
                                          "flagged_total": sum(s["flagged"] for s in sel), "flagged_indeterminate": sum(s["flagged_indeterminate"] for s in sel),
                                          "flagged_unclassified": sum(s["flagged_unclassified"] for s in sel)}
    gtc = {}
    for sd in {c["seed"] for c in evo}:
        gtc.update(json.load(open(ROOT / "research/ground_truth" / f"seed_{sd}.json"))["cases"])
    sole = [0, 0]; red = [0, 0]
    for s in steps:
        claims = gtc[s["case_ref"]]["claims"]
        for k in s["must_keys"]:
            tgt = sole if len(claims[k]["supporting"]) == 1 else red
            tgt[0] += 1; tgt[1] += int(k in s["flagged_keys"])
    out["impact_detection"]["claims_with_single_supporting_record"] = {"expected": sole[0], "detected": sole[1]}
    out["impact_detection"]["claims_with_redundant_support"] = {"expected": red[0], "detected": red[1], "note": "the claim keeps independent support after the changed evidence fails; the system lineage records only part of the support"}
    for m in methods:
        ms = [s["methods"][m] for s in steps]
        chg = [x for x in ms if x["n_score_changes"] > 0]
        out["ranking_change"][m] = {
            "steps_with_any_score_change": len(chg), "of": len(ms),
            "mean_kendall_tau": float(np.mean([x["kendall_tau"] for x in ms])), "mean_spearman": float(np.mean([x["spearman_rho"] for x in ms])),
            "mean_top5_overlap": float(np.mean([x["top_k_overlap"] for x in ms])), "mean_rank_displacement": float(np.mean([x["mean_rank_displacement"] for x in ms])),
            "unnecessary_changes_total": int(sum(x["unnecessary_changes"] for x in ms)), "changes_on_touched_total": int(sum(x["changes_on_touched"] for x in ms)),
            "expected_people": int(sum(x["expected_people"] for x in ms)), "expected_people_updated": int(sum(x["expected_people_updated"] for x in ms)),
            "missed_expected_updates": int(sum(x["missed_expected_updates"] for x in ms)),
            "nDCG@5_initial_mean": float(np.mean([c["initial_metrics"][m]["nDCG@5"] for c in evo])), "nDCG@5_final_mean": float(np.mean([c["final_metrics"][m]["nDCG@5"] for c in evo])),
            "MRR_initial_mean": float(np.mean([c["initial_metrics"][m]["MRR"] for c in evo])), "MRR_final_mean": float(np.mean([c["final_metrics"][m]["MRR"] for c in evo]))}
    # per-scenario nDCG change for lifecycle-aware vs blind
    sc = defaultdict(lambda: defaultdict(list))
    for c in evo:
        prev = {m: c["initial_metrics"][m]["nDCG@5"] for m in methods}
        for s in c["steps"]:
            for m in methods:
                sc[s["scenario"]][m].append(s["methods"][m]["after_nDCG@5"] - prev[m])
                prev[m] = s["methods"][m]["after_nDCG@5"]
    out["ndcg_change_by_scenario"] = {k: {m: float(np.mean(v)) for m, v in d.items()} | {"n_steps": len(d[methods[0]])} for k, d in sc.items()}
    for key in ("apply_ms", "recompute_ms", "rank_ms_per_method"):
        v = np.array([s[key] for s in steps if (key != "recompute_ms" or s["recompute_ms"] > 0.5)])
        out["latency_ms"][key] = {"n": int(len(v)), "p50": float(np.percentile(v, 50)), "p95": float(np.percentile(v, 95)), "p99": float(np.percentile(v, 99)), "mean": float(v.mean())}
    return out


if __name__ == "__main__":
    cfg = json.load(open(ROOT / "research/phase5/configs/phase5_config.json"))
    import sys
    rd = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "research/phase5/results" / (ROOT / "research/phase5/results/LATEST.txt").read_text().strip()
    json.dump(analyse(rd, cfg), open(rd / "analysis.json", "w"), indent=1, default=str)
    json.dump(analyse_evolution(rd, cfg), open(rd / "evolution_analysis.json", "w"), indent=1, default=str)
    print("analysed", rd.name)
