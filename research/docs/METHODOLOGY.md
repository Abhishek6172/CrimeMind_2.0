# Methodology (summary; full detail in FINAL_RESEARCH_REPORT.md)

* **Data**: 50 deterministic synthetic datasets (seeds 2026–2075), two cases each; hashes in `seed_manifest.csv`. Ground truth is stored apart (`research/ground_truth/`, schema `gt`) and is evaluator-only.
* **Unit of analysis**: seed (mean of its two cases). **Relevance**: perpetrator 3, accomplice 2; relevant = grade ≥ 1. **Metrics**: P/R/F1@1,3,5, MRR, nDCG@1,3,5 (gain 2^g − 1), AP/MAP.
* **Ties**: descending score, then ascending SHA-256(dataset|case|candidate); optimistic/pessimistic bounds reported.
* **Statistics**: bootstrap CI (10 000, fixed seed), paired Wilcoxon, rank-biserial, Cohen's d_z, Holm within metric.
* **Methods**: random, communication frequency, spatial proximity, degree, PageRank, frozen Q40, Q40-R, RAEER (`phase4/docs/RAEER_DEFINITION.md`).
* **Phase 5**: ablations, 13 seeded perturbation types, parameter sensitivity, evidence evolution via `change_validity()` with independently authored three-tier expectations.
* **Phase 6**: 541-question golden benchmark, retrieval and deterministic answer metrics (no LLM judge), error attribution retrieval vs generation.
* **Phase 7**: independent Python oracles for SQL modules compared on datasets and mutated edge-case databases; database/security/concurrency checks; scalability by case replication.
* **Integrity rules**: no ground truth in algorithms; frozen Q40 untouched; configurations versioned; every run has a unique ID and git commit; blocked experiments are labelled NOT RUN.
