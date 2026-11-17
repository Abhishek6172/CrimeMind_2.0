"""Render research/phase5/PHASE_5_REPORT.md from the latest Phase 5 bundle."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.common.report_util import f3, fp, md_table   # noqa: E402

RES = ROOT / "research/phase5/results"


def build():
    rd = RES / (RES / "LATEST.txt").read_text().strip()
    a = json.load(open(rd / "analysis.json")); e = json.load(open(rd / "evolution_analysis.json")); man = json.load(open(rd / "run_manifest.json"))
    L = ["# Phase 5 report: ablation, robustness, sensitivity and evidence evolution", "",
         f"Run ID: `{man['run_id']}` | git `{man['environment']['git_commit']}` | seeds {man['seeds_evaluated']} (2 cases each) | rows {man['rows']} | status {man['status']}. "
         f"Results: `research/phase5/results/{man['run_id']}/` (`per_case_results.csv`, `analysis.json`, `evolution_results.json`, `evolution_analysis.json`). Synthetic data only. "
         "An earlier smoke/pilot bundle `P5-20261101T132426Z-17567da` (without two robustness methods and claim-level detail) is preserved unchanged.", "",
         "## 1. Ablations of RAEER (Q40 is not ablated: it has none of these components)", "",
         "Each ablation turns off exactly one component of RAEER (`research/phase5/algorithms.py`): reliability (ρ≡1), contradiction (C≡0), temporal reasoning (no decay and no temporal feature), spatial/communication (feature weight 0; the scene set used to link other signals is unchanged), graph (relational feature 0), lifecycle (all statuses treated as current), corroboration (feature 0), independence (every record its own origin), provenance (provenance root ignored; in these data origin_root equals source, so this ablation is identical to independence in effect). "
         "Differences are *full − ablation*; positive means the component helps. Holm correction across the 11 comparisons per metric.", ""]
    for cond, title in (("clean", "Clean data"), ("mixed_quality", "Mixed-quality degradation (level 0.4)"), ("evolved", "After all scripted lifecycle events (system's own change_validity)")):
        b = a["ablation"].get(cond)
        if not b:
            continue
        rows = []
        for c in b["vs_full"]["nDCG@5"]:
            m = c["variant"]
            mm = b["means"][m]
            rows.append([m, f3(mm["nDCG@5"]["mean"]), f3(mm["MRR"]["mean"]), f3(mm["AP"]["mean"]), f"{c['mean_diff']:+.3f} [{c['ci95_low']:+.3f}, {c['ci95_high']:+.3f}]", fp(c["p_holm"]), "yes" if c["p_holm"] < .05 else "no"])
        full = b["means"]["raeer"]
        L += [f"### {title} (n = {b['n_seeds']} seeds)", "", f"Full RAEER: nDCG@5 {f3(full['nDCG@5']['mean'])}, MRR {f3(full['MRR']['mean'])}, AP {f3(full['AP']['mean'])}.", "",
              md_table(["variant", "nDCG@5", "MRR", "AP", "full − variant, nDCG@5 [95% CI]", "p (Holm)", "sig."], rows), ""]
    L += ["## 2. Robustness (nDCG@5 mean over 50 seeds; levels 1/2/3 of each perturbation)", "",
          "Perturbations are seeded, applied to the in-memory case view and never use labels (`research/phase5/perturb.py`, levels in `configs/phase5_config.json`). "
          "`q40_py` is Q40 re-expressed in Python (equal to the frozen SQL within rounding; `q40_py` = `q40` on the evolved database, 0.651 = 0.651), needed because SQL cannot run on perturbed in-memory data.", ""]
    ms = ["q40_py", "q40_r", "raeer", "raeer-no_independence", "raeer-no_lifecycle", "spatial_proximity", "communication_frequency", "pagerank"]
    cl = a["robustness_clean"]
    rows = [["clean (no perturbation)", "-"] + [f3(cl[m]["nDCG@5"]["mean"]) for m in ms]]
    for kind, lv in a["robustness"].items():
        for l in sorted(lv, key=float):
            rows.append([kind, l] + [f3(lv[l][m]["nDCG@5"]["mean"]) for m in ms])
    L += [md_table(["perturbation", "level"] + ms, rows), ""]
    L += ["Paired degradation of RAEER vs its own clean score (level 3, nDCG@5 difference perturbed − clean, 95% CI, Wilcoxon p; not multiplicity-corrected, exploratory):", ""]
    rows = []
    for kind, lv in a["robustness"].items():
        top = sorted(lv, key=float)[-1]
        d = lv[top]["raeer"]["delta_nDCG@5_vs_clean"]
        dq = lv[top]["q40_py"]["delta_nDCG@5_vs_clean"]
        rows.append([kind, top, f"{d['mean_diff']:+.3f} [{d['ci95_low']:+.3f}, {d['ci95_high']:+.3f}]", fp(d["wilcoxon_p"]), f"{dq['mean_diff']:+.3f} [{dq['ci95_low']:+.3f}, {dq['ci95_high']:+.3f}]"])
    L += [md_table(["perturbation", "level", "RAEER Δ nDCG@5", "p", "Q40 Δ nDCG@5"], rows), ""]
    L += ["## 3. Sensitivity of RAEER to its parameters (one at a time, clean data, nDCG@5)", "",
          md_table(["variant", "nDCG@5", "Δ vs default RAEER [95% CI]", "p (Wilcoxon, uncorrected)"],
                   [[m, f3(v["nDCG@5"]["mean"]), f"{v['delta_nDCG@5_vs_default_raeer']['mean_diff']:+.3f} [{v['delta_nDCG@5_vs_default_raeer']['ci95_low']:+.3f}, {v['delta_nDCG@5_vs_default_raeer']['ci95_high']:+.3f}]", fp(v['delta_nDCG@5_vs_default_raeer']['wilcoxon_p'])] for m, v in a["sensitivity"].items()]), "",
          "## 4. Evidence-evolution experiment", "",
          f"{e['cases']} cases, {e['steps']} scripted lifecycle steps applied through the system's own `change_validity()` and recomputation. Expected outcomes are the generator's ground truth (`must_flag`/`must_not_flag`/`indeterminate`), not the correlation lineage.", "",
          "### 4.1 History and event integrity (from the append-only `evidence_validity_events`)", "",
          md_table(["check", "result"], [["steps applied / scripted", f"{e['integrity']['steps_applied']} / {e['integrity']['steps_total']}"],
                                         ["transition checks (evidence identity, previous status, new status, trigger, reason, rule permitted)", f"{e['integrity']['transition_checks_failed_total']} failures; mean accuracy {e['integrity']['lifecycle_transition_accuracy_mean']:.3f}"],
                                         ["cases with consistent history (chains, contiguous finding versions, no CURRENT finding on non-SUPPORTED evidence)", f"{e['integrity']['history_ok_cases']} / {e['cases']}"],
                                         ["cases with unique event ids", f"{e['integrity']['event_ids_unique_cases']} / {e['cases']}"],
                                         ["cases with monotonic event timestamps", f"{e['integrity']['event_times_monotonic_cases']} / {e['cases']}"]]), "",
          "### 4.2 Affected-finding detection by the system (finding_impact_log vs independent expectations)", ""]
    ids = e["impact_detection"]
    L += [md_table(["subset", "steps", "expected (must-flag) findings", "detected", "recall", "must-not-flag findings flagged", "flagged total", "of which indeterminate"],
                   [[k, v["steps"], v["expected_findings"], v["detected"], f3(v["recall"]), v["must_not_flag_findings_flagged"], v["flagged_total"], v["flagged_indeterminate"]] for k, v in ids.items() if "steps" in v]), "",
          f"Claims whose only supporting record is the changed evidence: {ids['claims_with_single_supporting_record']['detected']} of {ids['claims_with_single_supporting_record']['expected']} expected flags detected; claims with redundant independent support: {ids['claims_with_redundant_support']['detected']} of {ids['claims_with_redundant_support']['expected']}.", "",
          "### 4.3 Ranking change per lifecycle step", "",
          md_table(["method", "steps with any score change", "mean Kendall τ", "mean Spearman ρ", "mean top-5 overlap", "mean rank displacement", "changes on non-touched candidates", "expected people updated / expected", "nDCG@5 initial → final"],
                   [[m, f"{v['steps_with_any_score_change']} / {v['of']}", f3(v["mean_kendall_tau"]), f3(v["mean_spearman"]), f3(v["mean_top5_overlap"]), f3(v["mean_rank_displacement"]),
                     v["unnecessary_changes_total"], f"{v['expected_people_updated']} / {v['expected_people']}", f"{f3(v['nDCG@5_initial_mean'])} → {f3(v['nDCG@5_final_mean'])}"] for m, v in e["ranking_change"].items()]), "",
          "Mean change in nDCG@5 per step, by scenario:", "",
          md_table(["scenario", "steps"] + list(next(iter(e["ndcg_change_by_scenario"].values())).keys())[:-1], [[k, v["n_steps"]] + [f"{v[m]:+.3f}" for m in list(v)[:-1]] for k, v in e["ndcg_change_by_scenario"].items()]), "",
          "### 4.4 Latency (this machine, PostgreSQL local)", "",
          md_table(["stage", "n", "p50 ms", "p95 ms", "p99 ms"], [[k, v["n"], f"{v['p50']:.1f}", f"{v['p95']:.1f}", f"{v['p99']:.1f}"] for k, v in e["latency_ms"].items()]), ""]
    return "\n".join(L), rd


if __name__ == "__main__":
    t, rd = build()
    p = ROOT / "research/phase5/reports/interpretation.md"
    (ROOT / "research/phase5/PHASE_5_REPORT.md").write_text(t + "\n" + (p.read_text() if p.exists() else ""))
    print("wrote", rd.name)
