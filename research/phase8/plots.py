"""Publication figures drawn ONLY from stored results. Each figure: title, axis labels with units, legend, sample counts, a caption and
the source file; a figure index is written next to the images."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402

from research.phase8 import aggregate as A   # noqa: E402

plt.rcParams.update({"figure.dpi": 130, "font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": .25, "savefig.bbox": "tight", "figure.constrained_layout.use": True})
PAL = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf", "#ff7f0e"]
LABEL = {"random": "random", "communication_frequency": "comm. frequency", "spatial_proximity": "spatial proximity", "degree_centrality": "degree", "pagerank": "PageRank",
         "q40": "Q40 (frozen)", "q40_r": "Q40-R", "raeer": "RAEER", "pagerank_victim_personalised": "PPR (victim)"}
FIGS = []


def save(fig, out: Path, name, title, caption, source):
    p = out / f"{name}.png"
    fig.savefig(p); plt.close(fig)
    FIGS.append(dict(file=p.name, title=title, caption=caption, source=source))


def fig_ranking(out):
    hr = A.headline_ranking()
    order = ["random", "degree_centrality", "communication_frequency", "pagerank", "spatial_proximity", "q40", "q40_r", "raeer"]
    order = [m for m in order if m in hr]
    fig, ax = plt.subplots(1, 3, figsize=(11, 3.6), sharey=False)
    for a, met in zip(ax, ["P@1", "nDCG@5", "MRR"]):
        v = [hr[m][met]["mean"] for m in order]
        e = [[hr[m][met]["mean"] - hr[m][met]["lo"] for m in order], [hr[m][met]["hi"] - hr[m][met]["mean"] for m in order]]
        a.bar(range(len(order)), v, yerr=e, color=[PAL[0] if m not in ("q40", "q40_r", "raeer") else PAL[1] for m in order], capsize=2)
        a.set_xticks(range(len(order))); a.set_xticklabels([LABEL[m] for m in order], rotation=40, ha="right"); a.set_title(met); a.set_ylabel(f"{met} (mean over seeds, 0–1)"); a.set_ylim(0, 1.02)
    fig.suptitle("Lead ranking quality by method (n = 50 synthetic seeds; bars = 95% bootstrap CI)")
    save(fig, out, "fig01_ranking_comparison", "Ranking comparison", "Seed-level means (each seed = mean of its 2 cases). Red bars: Q40 family. Synthetic data; see Section 'Threats to validity' for generator coupling.", "phase3/results/<latest>/aggregate_metrics.csv; phase4/results/<latest>/aggregate_metrics.csv")


def fig_k(out):
    hr = A.headline_ranking()
    order = [m for m in ["random", "spatial_proximity", "pagerank", "q40", "q40_r", "raeer"] if m in hr]
    fig, ax = plt.subplots(1, 3, figsize=(11, 3.4))
    for a, base in zip(ax, ["P", "R", "nDCG"]):
        for i, m in enumerate(order):
            ks = [k for k in (1, 3, 5) if f"{base}@{k}" in hr[m]]
            a.plot(ks, [hr[m][f"{base}@{k}"]["mean"] for k in ks], marker="o", color=PAL[i], label=LABEL[m])
        a.set_xticks([1, 3, 5]); a.set_xlabel("K (cut-off rank)"); a.set_ylabel(f"{base}@K (0–1)"); a.set_title(f"{base}@K")
    ax[0].legend(fontsize=7)
    fig.suptitle("Precision, recall and nDCG at K (n = 50 seeds)")
    save(fig, out, "fig02_metrics_at_k", "Metrics at K", "Precision falls and recall rises with K as expected; relevant = perpetrator or accomplice.", "phase3/4 aggregate_metrics.csv")


def fig_ablation(out):
    a = A.load("phase5", "analysis.json")["ablation"]["clean"]["means"]
    names = [k for k in a if k.startswith("raeer-no_")]
    full = a["raeer"]["nDCG@5"]["mean"]
    d = sorted([(k.replace("raeer-no_", ""), a[k]["nDCG@5"]["mean"] - full) for k in names], key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    ax.barh([x[0] for x in d], [x[1] for x in d], color=[PAL[1] if x[1] < -0.005 else PAL[6] for x in d])
    ax.axvline(0, color="k", lw=.8); ax.set_xlabel("Change in nDCG@5 when the component is removed (absolute, vs full RAEER)"); ax.set_ylabel("Removed component")
    ax.set_title(f"RAEER ablation (clean data, n = 50 seeds; full RAEER nDCG@5 = {full:.3f})")
    save(fig, out, "fig03_ablation", "Ablation", "Negative = component helps. Most components show no detectable effect on clean data; spatial and contradiction handling matter most.", "phase5/results/<latest>/analysis.json (ablation.clean.means)")


def fig_robust(out):
    r = A.load("phase5", "analysis.json")["robustness"]
    kinds = ["challenge", "invalidation", "missing_evidence", "noisy_location", "reduced_communication", "incorrect_timestamps"]
    ms = ["q40_py", "q40_r", "raeer", "spatial_proximity", "communication_frequency"]
    fig, axs = plt.subplots(2, 3, figsize=(11, 6), sharey=True)
    clean = A.load("phase5", "analysis.json")["robustness_clean"]
    for ax, k in zip(axs.flat, kinds):
        lv = sorted(r[k], key=float)
        for i, m in enumerate(ms):
            ys = [clean[m]["nDCG@5"]["mean"] if m in clean and "nDCG@5" in clean[m] else None] + [r[k][l][m]["nDCG@5"]["mean"] for l in lv]
            ax.plot([0] + [float(l) for l in lv], ys, marker="o", color=PAL[i], label={"q40_py": "Q40", "q40_r": "Q40-R"}.get(m, LABEL.get(m, m)))
        ax.set_title(k.replace("_", " ")); ax.set_xlabel("perturbation level (fraction of data affected)"); ax.set_ylabel("nDCG@5 (0–1)")
    axs[0, 0].legend(fontsize=7)
    fig.suptitle("Robustness to seeded perturbations (n = 50 seeds per point; level 0 = unperturbed)")
    save(fig, out, "fig04_robustness", "Robustness", "Six of 13 perturbation types shown; all 13 are in the Phase 5 report. Level 0 is the clean run.", "phase5/results/<latest>/analysis.json (robustness, robustness_clean)")


def fig_evolution(out):
    e = A.load("phase5", "evolution_analysis.json")
    imp = e["impact_detection"]
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    labs = [{"all_steps": "all steps", "first_dispute_step": "first dispute\nof an item", "later_steps": "later\ntransitions"}.get(k, k.replace("_", " ")) for k in imp if isinstance(imp[k], dict) and "recall" in imp[k]]
    vals = [imp[k]["recall"] for k in imp if isinstance(imp[k], dict) and "recall" in imp[k]]
    ns = [imp[k]["expected_findings"] for k in imp if isinstance(imp[k], dict) and "recall" in imp[k]]
    ax[0].bar(labs, vals, color=PAL[0]); [ax[0].text(i, v + .01, f"n={n}", ha="center", fontsize=8) for i, (v, n) in enumerate(zip(vals, ns))]
    ax[0].set_ylim(0, 1); ax[0].set_ylabel("Recall of expected finding flags (0–1)"); ax[0].set_title("Impact detection after validity changes")
    lat = e["latency_ms"]
    ks = [k for k in lat if isinstance(lat[k], dict) and "p50" in lat[k]]
    ax[1].bar([k.replace("_ms_per_method", " (per method)").replace("_ms", "") for k in ks], [lat[k]["p50"] for k in ks], yerr=[[0 for _ in ks], [max(0, lat[k].get("p95", lat[k]["p50"]) - lat[k]["p50"]) for k in ks]], color=PAL[2], capsize=3)
    ax[1].set_ylabel("Latency per step (ms; bar = p50, whisker = p95)"); ax[1].set_title(f"Response time ({e['steps']} steps, {e['cases']} cases)")
    save(fig, out, "fig05_evolution", "Evidence evolution", "Expected-flag recall is measured against independently authored three-tier expectations; the 0 recall at later transitions is discussed in the Phase 5 report.", "phase5/results/<latest>/evolution_analysis.json")


def fig_rag(out):
    a = A.load("phase6", "analysis.json")["retrieval"]["ALL"]
    vs = list(a)
    fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.8))
    for i, met in enumerate(["MRR", "nDCG@5", "coverage@8"]):
        ax[0].bar([j + i * .27 for j in range(len(vs))], [a[v][met]["mean"] for v in vs], .27, label=met, color=PAL[i])
    ax[0].set_xticks([j + .27 for j in range(len(vs))]); ax[0].set_xticklabels(vs, rotation=30, ha="right"); ax[0].set_ylabel("Score (0–1)"); ax[0].legend(); ax[0].set_title(f"Retrieval variants (n = {a['full']['n_questions']} questions)")
    cats = {c: d["full"] for c, d in A.load("phase6", "analysis.json")["retrieval"].items() if c != "ALL"}
    ax[1].barh(list(cats), [cats[c]["coverage@8"]["mean"] for c in cats], color=PAL[1]); ax[1].set_xlabel("coverage@8 (share of required evidence in top 8)"); ax[1].set_title("Full retrieval by question category")
    fig.suptitle("Evidence retrieval over the golden-question benchmark (synthetic; BM25 + boosts)")
    save(fig, out, "fig06_retrieval", "Retrieval", "Typo-tolerant matching accounts for the gain over plain BM25 here; entity and reference boosts had negligible effect. Multi-hop and SQL-investigation questions are weakest.", "phase6/results/<latest>/analysis.json")


def fig_answers(out):
    a = A.load("phase6", "analysis.json")["answer"]["ALL"]
    mets = ["valid", "groundedness", "entity_recall", "citation_completeness", "citation_correctness", "correct_refusal", "hallucination"]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.barh(mets, [a[m]["mean"] for m in mets], color=PAL[3]); ax.set_xlim(0, 1.05); ax.set_xlabel("Mean over questions (0–1)")
    ax.set_title("Answer metrics — OFFLINE TEMPLATE provider only (no live LLM was evaluated)")
    save(fig, out, "fig07_answer_metrics", "Answer metrics (template provider)", "Template answers restate retrieved records, so groundedness is high and hallucination zero by construction; correct refusal is 0 because the template never refuses. No LLM provider result exists.", "phase6/results/<latest>/analysis.json (answer.ALL)")


def fig_sql(out):
    p = A.load("phase7", "scalability.json")
    sc = sorted(p["scales"], key=int)
    top = sorted(p["scales"][sc[-1]]["latency"], key=lambda n: -p["scales"][sc[-1]]["latency"][n].get("p95_ms", 0))[:8]
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
    for i, n in enumerate(top):
        ax[0].plot([int(k) for k in sc], [p["scales"][k]["latency"][n]["p95_ms"] for k in sc], marker="o", color=PAL[i % 10], label=n)
    ax[0].set_xscale("log"); ax[0].set_xticks([int(k) for k in sc]); ax[0].set_xticklabels([f"{k}x" for k in sc]); ax[0].set_xlabel("Data scale (case replicated k times)"); ax[0].set_ylabel("p95 latency (ms)"); ax[0].legend(fontsize=6); ax[0].set_title("Slowest SQL variants")
    allv = [p["scales"][sc[-1]]["latency"][n]["p95_ms"] for n in p["scales"][sc[-1]]["latency"]]
    ax[1].hist(allv, bins=15, color=PAL[0]); ax[1].set_xlabel(f"p95 latency at {sc[-1]}x (ms)"); ax[1].set_ylabel("Number of module variants"); ax[1].set_title(f"All {len(allv)} variants at {sc[-1]}x ({p['scales'][sc[-1]]['table_rows']['communications']} communications)")
    fig.suptitle("SQL module latency vs data scale (2 vCPU container, default PostgreSQL configuration)")
    save(fig, out, "fig08_sql_scalability", "SQL scalability", "Synthetic replication model; indicative only. p95 over repeated executions.", "phase7/results/<latest>/scalability.json")


def fig_oracle(out):
    s = A.load("phase7", "oracle_summary.json")
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ks = list(s)
    ax.bar(ks, [v["comparisons"] for v in s.values()], color=PAL[6], label="comparisons"); ax.bar(ks, [v["matches"] for v in s.values()], color=PAL[2], label="matched")
    ax.set_xticks(range(len(ks))); ax.set_xticklabels(ks, rotation=70, ha="right", fontsize=7); ax.set_ylabel("SQL-vs-oracle comparisons (count)"); ax.legend(); ax.set_title("SQL module verification against independent Python oracles")
    save(fig, out, "fig09_oracle_agreement", "Oracle agreement", "Green fully covering grey = every comparison matched (after the two defects found by this phase were fixed).", "phase7/results/<latest>/oracle_summary.json")


def build(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    FIGS.clear()
    for f in (fig_ranking, fig_k, fig_ablation, fig_robust, fig_evolution, fig_rag, fig_answers, fig_sql, fig_oracle):
        f(out)
    md = ["# Figure index", "", "All figures are generated by `python -m research.phase8.plots` from stored results (no hand-entered numbers).", ""]
    for f in FIGS:
        md += [f"## {f['title']}", f"![{f['title']}]({f['file']})", f"*Caption.* {f['caption']}", f"*Source:* `{f['source']}`", ""]
    (out / "figure_index.md").write_text("\n".join(md), encoding="utf-8")
    json.dump(FIGS, open(out / "figure_index.json", "w"), indent=1)
    return FIGS


if __name__ == "__main__":
    import sys
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "figures")
