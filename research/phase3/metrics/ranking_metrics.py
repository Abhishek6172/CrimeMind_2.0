"""Ranking metrics against graded ground-truth labels.

Conventions (documented in PHASE_3_REPORT.md):
  * grades: {candidate: int|None}. grade >= 1 is 'relevant' for the binary metrics; None = indeterminate/unlabelled and is
    EXCLUDED from the ranking before scoring (never treated as a negative). Candidates absent from `grades` count as unlabelled.
  * P@K = hits in top K / K (denominator K even when fewer than K labelled candidates exist).  R@K = hits in top K / R, R = #relevant.
    F1@K = 2PR/(P+R) (0 if both 0).  RR = 1/rank of the first relevant.  AP = (1/R) * sum over relevant ranks r of P@r.
  * nDCG@K: gain 2^grade - 1, discount 1/log2(rank + 1); ideal ordering from the labelled grades.
  * A case with R = 0 has undefined recall/RR/AP/nDCG: returned as None and excluded from means (counted by the caller).
  * Ties are resolved BEFORE these functions by the common deterministic rule; the input is a total order.
"""
import math

KS = (1, 3, 5)


def _prepare(ranked, grades):
    lab = [r for r in ranked if grades.get(r) is not None]
    return lab, {r: grades[r] for r in lab}, len(ranked) - len(lab)


def precision_at_k(ranked, grades, k):
    lab, g, _ = _prepare(ranked, grades)
    return sum(1 for r in lab[:k] if g[r] >= 1) / k


def recall_at_k(ranked, grades, k):
    lab, g, _ = _prepare(ranked, grades)
    R = sum(1 for r in lab if g[r] >= 1)
    return None if R == 0 else sum(1 for r in lab[:k] if g[r] >= 1) / R


def f1_at_k(ranked, grades, k):
    p, r = precision_at_k(ranked, grades, k), recall_at_k(ranked, grades, k)
    if r is None:
        return None
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def reciprocal_rank(ranked, grades):
    lab, g, _ = _prepare(ranked, grades)
    if not any(g[r] >= 1 for r in lab):
        return None
    for i, r in enumerate(lab, 1):
        if g[r] >= 1:
            return 1.0 / i
    return 0.0


def average_precision(ranked, grades):
    lab, g, _ = _prepare(ranked, grades)
    R = sum(1 for r in lab if g[r] >= 1)
    if R == 0:
        return None
    hits, s = 0, 0.0
    for i, r in enumerate(lab, 1):
        if g[r] >= 1:
            hits += 1
            s += hits / i
    return s / R


def dcg(gains):
    return sum(x / math.log2(i + 1) for i, x in enumerate(gains, 1))


def ndcg_at_k(ranked, grades, k):
    lab, g, _ = _prepare(ranked, grades)
    if not any(g[r] >= 1 for r in lab):
        return None
    gain = lambda x: 2 ** x - 1
    ideal = sorted((gain(v) for v in g.values()), reverse=True)[:k]
    return dcg([gain(g[r]) for r in lab[:k]]) / dcg(ideal)


def evaluate_ranking(ranked, grades) -> dict:
    lab, g, excluded = _prepare(ranked, grades)
    out = {"n_candidates": len(ranked), "n_labelled": len(lab), "n_excluded_unlabelled": excluded,
           "n_relevant": sum(1 for r in lab if g[r] >= 1)}
    for k in KS:
        out[f"P@{k}"] = precision_at_k(ranked, grades, k)
        out[f"R@{k}"] = recall_at_k(ranked, grades, k)
        out[f"F1@{k}"] = f1_at_k(ranked, grades, k)
        out[f"nDCG@{k}"] = ndcg_at_k(ranked, grades, k)
    out["MRR"] = reciprocal_rank(ranked, grades)
    out["AP"] = average_precision(ranked, grades)
    return out


METRIC_NAMES = [f"{m}@{k}" for m in ("P", "R", "F1", "nDCG") for k in KS] + ["MRR", "AP"]


def tie_bounds(scores: dict, grades: dict) -> dict:
    """Sensitivity to tie resolution: metrics when relevant candidates are placed FIRST (optimistic) or LAST (pessimistic)
    within every group of equal scores. The reported (hash tie-break) value lies between them."""
    out = {}
    for mode in ("optimistic", "pessimistic"):
        sign = -1 if mode == "optimistic" else 1
        order = sorted(scores, key=lambda r: (-scores[r], sign * (grades.get(r) or 0), r))
        m = evaluate_ranking(order, grades)
        out[mode] = {k: m[k] for k in ("MRR", "AP", "nDCG@5", "P@3", "R@5")}
    return out
