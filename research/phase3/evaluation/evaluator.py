"""Evaluator: runs ranking algorithms on a seed's cases and scores them with the ground truth.
Ground truth is loaded HERE ONLY (evaluator side) and compared with the ranking after it has been produced."""
import json
from pathlib import Path

from research.common.casedata import load_case_view
from research.common.workspace import SeedWorkspace, load_ground_truth
from research.phase3.algorithms import make
from research.phase3.metrics.ranking_metrics import METRIC_NAMES, evaluate_ranking, tie_bounds

CFG = json.load(open(Path(__file__).resolve().parents[1] / "configs" / "phase3_config.json"))


def condition_features(gt: dict, ranked: list[str], view=None) -> dict:
    pos = {r: i + 1 for i, r in enumerate(ranked)}
    n = len(ranked)
    leads = gt["relevant_leads"]
    by_strength = {}
    for l in leads:
        by_strength.setdefault(l["strength"], []).append(pos[l["ref"]])
    rh = [pos[r["ref"]] for r in gt["red_herrings"]]
    return {"lead_ranks": {l["ref"]: pos[l["ref"]] for l in leads}, "lead_strength_ranks": by_strength,
            "red_herring_ranks": rh, "n_candidates": n,
            "red_herrings_in_top5": sum(1 for x in rh if x <= 5), "perpetrator_rank": min((pos[l["ref"]] for l in leads if l["grade"] == 3), default=None),
            "lead_details": lead_details(gt, pos, view) if view is not None else []}


def lead_details(gt, pos, view):
    """Evaluator-side stratification features (use labels, so they live here and never in an algorithm)."""
    out = []
    for l in gt["relevant_leads"]:
        evs = [view.evidence[e] for e in l["supporting_evidence"] if e in view.evidence]
        rel = [e["reliability"] for e in evs if e["reliability"] is not None]
        types = sorted({e["type"] for e in evs})
        out.append({"ref": l["ref"], "kind": "lead", "grade": l["grade"], "strength": l["strength"], "rank": pos[l["ref"]],
                    "mean_reliability": sum(rel) / len(rel) if rel else None, "has_contradicting_evidence": bool(l["contradicting_evidence"]), "types": types})
    for r in gt["red_herrings"]:
        out.append({"ref": r["ref"], "kind": "red_herring", "decoy_type": r.get("type"), "rank": pos[r["ref"]], "has_contradicting_evidence": bool(r["contradicting_evidence"])})
    return out


def evaluate_methods(case_view, gt, dataset_id, methods, cfg=CFG, random_reps=None, maker=make):
    """Returns list of result rows (one per method) for one case."""
    grades = {k: v for k, v in gt["relevance_grades"].items()}
    out = []
    for m in methods:
        reps = (random_reps or cfg["random"]["repetitions"]) if m == "random" else 1
        acc, cond, tb = [], None, None
        for rep in range(reps):
            algo = maker(m, repetition=rep) if m == "random" else maker(m)
            res = algo.rank(dataset_id, case_view, cfg)
            ranked = [r.lead_id for r in sorted(res, key=lambda r: r.rank)]
            if sorted(ranked) != sorted(case_view.candidates):
                raise RuntimeError(f"{m}: ranking does not cover exactly the candidate set")
            acc.append(evaluate_ranking(ranked, grades))
            if rep == 0:
                cond = condition_features(gt, ranked, case_view)
                tb = tie_bounds({r.lead_id: r.raw_score for r in res}, grades)
                n_distinct = len({round(r.raw_score, 12) for r in res})
        row = {"method": m, "case_ref": case_view.case_ref, "n_repetitions": reps, "config_version": algo.config_version,
               "n_distinct_scores": n_distinct, "tie_bounds": tb, "conditions": cond}
        for k in ["n_candidates", "n_labelled", "n_excluded_unlabelled", "n_relevant"]:
            row[k] = acc[0][k]
        for k in METRIC_NAMES:
            vals = [a[k] for a in acc if a[k] is not None]
            row[k] = sum(vals) / len(vals) if vals else None
            if reps > 1 and vals:
                mu = row[k]
                row[k + "_within_seed_sd"] = (sum((v - mu) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5
        out.append(row)
    return out


def run_seed(seed: int, methods, cfg=CFG, keep=False, prefix="cm_p3", maker=make):
    gts = load_ground_truth(seed)
    rows = []
    with SeedWorkspace(seed, prefix=prefix, keep=keep) as w:
        for c in w.cases():
            view = load_case_view(w.conn, c["case_ref"])
            for r in evaluate_methods(view, gts[c["case_ref"]], f"seed_{seed}", methods, cfg, maker=maker):
                r["seed"] = seed
                r["hash_verified"] = w.hash_verified
                rows.append(r)
    return rows
