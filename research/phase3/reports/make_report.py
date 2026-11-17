"""Render research/phase3/PHASE_3_REPORT.md from the latest Phase 3 result bundle."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from research.common.report_util import agg_table, f3, latest_run, load_analysis, md_table, pair_rows   # noqa: E402

RES = ROOT / "research/phase3/results"
MAIN = ["P@1", "P@3", "P@5", "R@5", "MRR", "nDCG@5", "AP"]
ORDER = ["random", "communication_frequency", "spatial_proximity", "degree_centrality", "pagerank", "pagerank_victim_personalised", "q40"]


def build(run=None):
    rd = Path(run) if run else latest_run(RES)
    an, man = load_analysis(rd)
    agg, pairs, cond = an["aggregate"], an["pairs"], an["conditions"]
    ms = [m for m in ORDER if m in agg]
    best = {k: max(ms, key=lambda m: agg[m][k]["mean"]) for k in MAIN}
    q = "q40"
    lines = [f"# Phase 3 report: ranking baselines and evaluation framework", "",
             f"Run ID: `{man['run_id']}` | git `{man['environment']['git_commit']}` | Python {man['environment']['python']} | PostgreSQL {man['environment'].get('postgres')} | "
             f"seeds evaluated: {man['seeds_evaluated']} (2 cases each) | status: {man['status']} | datasets re-derived from seed and hash-verified against the committed manifests: {man['hash_verified_all']}",
             "", "All numbers below are read from `research/phase3/results/" + man["run_id"] + "/` (`aggregate_metrics.csv`, `paired_comparisons.csv`, `per_seed_metrics.csv`, `analysis.json`). "
             "Data are synthetic; nothing here supports claims about real investigations.", "",
             "## 1. Methods", "",
             "All methods rank the same candidate set (every person except the victim) from the same `CaseView` (no ground truth), using only SUPPORTED records, with the same deterministic tie rule.", "",
             md_table(["method", "idea", "uses incident?"], [
                 ["random", "uniform random order; 100 repetitions per case, averaged within a case (repetitions are NOT independent datasets)", "no"],
                 ["communication_frequency", "equal-weight blend of communication count, unique partners, pre-incident-week frequency, recency to incident", "time only"],
                 ["spatial_proximity", "1/(1+d_min/100 m) over observations within ±60 min of the incident; no observation → 0", "yes"],
                 ["degree_centrality", "degree in the relationship graph (isolated nodes 0)", "no"],
                 ["pagerank", "weighted PageRank, damping 0.85, uniform teleport (own power iteration; checked against networkx in tests)", "no"],
                 ["pagerank_victim_personalised", "extra: PageRank with teleport mass on the victim", "victim only"],
                 ["q40", "frozen Q40 SQL (M18 `overall`) through an adapter; unscored candidates get 0", "yes"]]), "",
             "## 2. Evaluation protocol", "",
             "* Ground truth: `research/ground_truth/seed_<n>.json` (generator plan, independent of every ranking method). Relevant = grade ≥ 1 (perpetrator grade 3, accomplice grade 2); red herrings, bystanders, witnesses and background persons are grade 0. No label is indeterminate in this ground truth; the metric code excludes `None`/unlabelled candidates rather than counting them as negatives (unit-tested).",
             "* Unit of analysis = the seed: each seed's two cases are averaged, giving n = 50 paired observations per method. Case-level values are in `per_case_metrics.csv`.",
             "* P@K = hits in top K / K; R@K = hits / #relevant; AP = mean of precision at relevant ranks; nDCG gain 2^grade−1; MRR = 1/rank of first relevant. Cases without relevant leads would be excluded (none occurred).",
             "* **Ties**: descending raw score, then ascending SHA-256(dataset|case|candidate), independent of reference order and labels. Several methods produce many tied scores, so §5 reports optimistic/pessimistic tie bounds.",
             "* Statistics: bootstrap 95% CI of the mean (10 000 resamples, fixed seed); paired two-sided Wilcoxon signed-rank on per-seed differences; matched-pairs rank-biserial r; Holm correction across all pairs within each metric.", "",
             "## 3. Results (mean over 50 seeds)", "", agg_table(agg, ms, MAIN), "",
             "Best mean by metric: " + ", ".join(f"{k}: `{best[k]}`" for k in MAIN) + ".", "",
             "### Paired comparisons with Q40 (nDCG@5, Q40 minus other)", "", pair_rows(pairs, "nDCG@5", q), "",
             "### Paired comparisons with Q40 (MRR)", "", pair_rows(pairs, "MRR", q), "",
             "### Paired comparisons with Q40 (AP)", "", pair_rows(pairs, "AP", q), "",
             "## 4. Conditions: where methods succeed or fail", "",
             md_table(["method", "strong leads: median rank / in top-5", "medium", "weak", "red herrings in top-5", "nDCG@5 primary case / secondary case"],
                     [[m] + [f"{cond[m]['lead_rank_by_strength'][s]['median_rank']} / {cond[m]['lead_rank_by_strength'][s]['share_in_top5']:.0%}" for s in ("strong", "medium", "weak")]
                      + [f"{cond[m]['red_herrings_in_top5']} of {cond[m]['red_herrings_total']}", f"{f3(cond[m]['nDCG@5_by_case'].get('001'))} / {f3(cond[m]['nDCG@5_by_case'].get('002'))}"] for m in ms]), "",
             "Strength is the generator's evidence profile for each lead (strong = GPS+CCTV+calls+payment+tie; medium = GPS (and sometimes CCTV)+calls; weak = CCTV+calls for perpetrators). Rank is among all candidates (≈ 46–114).", "",
             "## 5. Tie sensitivity (mean over all cases)", "",
             md_table(["method", "mean distinct scores per case", "MRR pess.–opt.", "AP pess.–opt.", "nDCG@5 pess.–opt."],
                     [[m, f"{cond[m]['mean_distinct_scores']:.1f}"] + [f"{f3(cond[m]['tie_bounds_mean']['pessimistic'][k])}–{f3(cond[m]['tie_bounds_mean']['optimistic'][k])}" for k in ("MRR", "AP", "nDCG@5")] for m in ms]), "",
             "Methods with few distinct scores (Q40 is a sum of binary signals; spatial proximity is quantised by the generator's few venue locations) are sensitive to how ties are resolved; the headline numbers use the neutral hash rule and lie inside these bounds.", ""]
    return "\n".join(lines), rd, an


if __name__ == "__main__":
    text, rd, an = build()
    extra = (ROOT / "research/phase3/reports/interpretation.md").read_text() if (ROOT / "research/phase3/reports/interpretation.md").exists() else ""
    (ROOT / "research/phase3/PHASE_3_REPORT.md").write_text(text + "\n" + extra)
    print("wrote", rd.name)
