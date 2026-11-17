"""Paired statistics across datasets (seeds). Each method is evaluated on the SAME seeds, so comparisons are paired.
Repetitions of the random baseline are averaged WITHIN a seed first and never treated as independent datasets."""
import itertools
import math

import numpy as np
from scipy import stats as sps


def summarise(x, seed=20260101, n_boot=10000):
    x = np.asarray([v for v in x if v is not None and not math.isnan(v)], float)
    if len(x) == 0:
        return {"n": 0}
    rng = np.random.default_rng(seed)
    boots = rng.choice(x, size=(n_boot, len(x)), replace=True).mean(axis=1)
    return {"n": int(len(x)), "mean": float(x.mean()), "median": float(np.median(x)), "std": float(x.std(ddof=1)) if len(x) > 1 else 0.0,
            "ci95_low": float(np.percentile(boots, 2.5)), "ci95_high": float(np.percentile(boots, 97.5))}


def paired_comparison(x, y, seed=20260101, n_boot=10000):
    """x, y aligned per seed (None/NaN pairs dropped). Two-sided Wilcoxon signed-rank on the paired differences."""
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None and not (math.isnan(a) or math.isnan(b))]
    d = np.array([a - b for a, b in pairs], float)
    n = len(d)
    if n == 0:
        return {"n": 0}
    rng = np.random.default_rng(seed)
    boots = rng.choice(d, size=(n_boot, n), replace=True).mean(axis=1)
    nz = d[d != 0]
    if len(nz) == 0:
        p, rbc = 1.0, 0.0
    else:
        p = float(sps.wilcoxon(nz, zero_method="wilcox", alternative="two-sided", method="auto").pvalue)
        ranks = sps.rankdata(np.abs(nz))
        rbc = float((ranks[nz > 0].sum() - ranks[nz < 0].sum()) / ranks.sum())     # matched-pairs rank-biserial correlation
    sd = d.std(ddof=1) if n > 1 else 0.0
    return {"n": n, "mean_diff": float(d.mean()), "ci95_low": float(np.percentile(boots, 2.5)), "ci95_high": float(np.percentile(boots, 97.5)),
            "wilcoxon_p": p, "rank_biserial": rbc, "cohens_dz": float(d.mean() / sd) if sd > 0 else (0.0 if d.mean() == 0 else float("inf")),
            "wins": int((d > 0).sum()), "losses": int((d < 0).sum()), "ties": int((d == 0).sum())}


def holm(pvals: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values (monotone, capped at 1)."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj, running = [0.0] * m, 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adj[i] = running
    return adj


def all_pairs(values_by_method: dict, seed=20260101, n_boot=10000):
    """Every ordered pair (A,B) once (A before B in name order): A - B. Holm applied across the pair family."""
    rows = []
    for a, b in itertools.combinations(sorted(values_by_method), 2):
        r = paired_comparison(values_by_method[a], values_by_method[b], seed, n_boot)
        rows.append({"A": a, "B": b, **r})
    ps = [r["wilcoxon_p"] for r in rows if r.get("n")]
    adj = iter(holm(ps))
    for r in rows:
        if r.get("n"):
            r["p_holm"] = next(adj)
            r["significant_holm_0.05"] = r["p_holm"] < 0.05
    return rows
