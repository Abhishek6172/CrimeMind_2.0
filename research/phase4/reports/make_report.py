"""Render research/phase4/PHASE_4_REPORT.md from the latest Phase 4 bundle."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from research.common.report_util import agg_table, f3, latest_run, load_analysis, md_table, pair_rows   # noqa: E402

RES = ROOT / "research/phase4/results"
MAIN = ["P@1", "P@3", "P@5", "R@5", "MRR", "nDCG@5", "AP"]
ORDER = ["random", "communication_frequency", "spatial_proximity", "degree_centrality", "pagerank", "q40", "q40_r", "raeer"]


def build():
    rd = latest_run(RES)
    an, man = load_analysis(rd)
    st = json.load(open(rd / "strata.json"))
    agg, pairs, cond = an["aggregate"], an["pairs"], an["conditions"]
    ms = [m for m in ORDER if m in agg]
    L = [f"# Phase 4 report: reliability-aware ranking (Q40-R) and RAEER", "",
         f"Run ID: `{man['run_id']}` | git `{man['environment']['git_commit']}` | seeds evaluated {man['seeds_evaluated']} | status {man['status']} | datasets hash-verified: {man['hash_verified_all']}. "
         f"Results: `research/phase4/results/{man['run_id']}/`. Synthetic data only.", "",
         "## 1. What was implemented", "",
         "* **Q40-R** (`research/phase4/algorithms/q40r.py`): Q40 with the same six signals, weights and window, but each binary signal is replaced by the best reliability×lifecycle-status factor of its supporting records. Reliability switched off ⇒ identical to the frozen Q40 SQL (test `test_q40r_with_reliability_off_equals_frozen_q40_on_real_data`). Q40 itself is untouched.",
         "* **RAEER** (`research/phase4/algorithms/raeer.py`, definition and equations in `research/phase4/docs/RAEER_DEFINITION.md`): the repository contained only the name (Reliability-Aware Evidence Evolution Ranking) and the six factors it should study, no formula. The formula is therefore an operational definition proposed for this study. It differs from Q40-R in graded geometry (150 m scene radius), temporal-consistency decay, noisy-OR over independent origins, relational support extended to scene persons, a bounded contradiction penalty and domain corroboration.",
         "* Configuration `research/phase4/configs/phase4_config.json` was committed **before** any evaluation (`frozen_before_evaluation`) with weights equal to Q40's; nothing was tuned on ground truth, and each method was evaluated exactly once in this run.", "",
         "## 2. Ranking results (mean over 50 seeds, 95% bootstrap CI)", "", agg_table(agg, ms, MAIN), "",
         "### RAEER − Q40", "", *[pair_rows(pairs, m, "raeer").split("\n")[0] if False else "" for m in ()],
         "nDCG@5:", "", pair_rows(pairs, "nDCG@5", "raeer"), "", "MRR:", "", pair_rows(pairs, "MRR", "raeer"), "",
         "### Q40-R vs Q40", "", "nDCG@5:", "", pair_rows(pairs, "nDCG@5", "q40_r"), "",
         "## 3. Stratified performance of relevant leads (all seeds, both cases; a lead can appear in several evidence-type strata)", "",
         f"Reliability strata split at the pooled median mean-reliability of a lead's supporting evidence ({st['reliability_split_median']:.3f}).", ""]
    keys = list(st["q40"].keys())
    L.append(md_table(["stratum", "n"] + [f"{m}: median rank / top-5 share" for m in ("q40", "q40_r", "raeer")],
                      [[k, st["q40"][k]["n"]] + [f"{st[m][k]['median_rank']} / {st[m][k]['share_top5']:.0%}" for m in ("q40", "q40_r", "raeer")] for k in keys]))
    L += ["", "Red-herring strata list decoys (lower top-5 share is better for decoys).", "",
          "## 4. Tie sensitivity", "",
          md_table(["method", "distinct scores / case", "nDCG@5 pessimistic–optimistic ties", "red herrings in top-5"],
                   [[m, f"{cond[m]['mean_distinct_scores']:.1f}", f"{f3(cond[m]['tie_bounds_mean']['pessimistic']['nDCG@5'])}–{f3(cond[m]['tie_bounds_mean']['optimistic']['nDCG@5'])}",
                     f"{cond[m]['red_herrings_in_top5']} of {cond[m]['red_herrings_total']}"] for m in ms]), ""]
    return "\n".join(L), rd


if __name__ == "__main__":
    t, rd = build()
    p = ROOT / "research/phase4/reports/interpretation.md"
    (ROOT / "research/phase4/PHASE_4_REPORT.md").write_text(t + "\n" + (p.read_text() if p.exists() else ""))
    print("wrote", rd.name)
