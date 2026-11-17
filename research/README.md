# research/

Experimental framework around CrimeMind. Application code stays in `backend/`; nothing here edits it.

| Folder | Purpose | State |
|---|---|---|
| `baseline/` | Frozen Q40 configuration and `capture_baseline.py` (rebuilds the baseline from scratch) | done |
| `results/baseline/` | Saved test output, Q40 rankings and metrics before/after evolution, evolution steps, manifest | done |
| `datasets/`, `ground_truth/` | Multi-seed datasets and labels | Milestone 2 |
| `baselines/`, `evaluation/` | Ranking baselines, metrics, benchmark runner | Milestone 3 |
| `ablation/`, `robustness/`, `evidence_evolution/` | Experiments RQ1-RQ3 | later |
| `ai_evaluation/`, `sql_validation/`, `performance/` | Experiments RQ4, correctness, RQ5 | later |
| `figures/` | Figures generated from results only | later |

Reproduce the baseline: start PostgreSQL 16, then `python3 research/baseline/capture_baseline.py`.

## Phases 3–8 (research execution)
Run everything with `python -m research.run_all` (see `research/docs/EXECUTION_GUIDE.md`). Final report: `research/FINAL_RESEARCH_REPORT.md`; completion status: `research/PHASE_3_TO_8_FINAL_COMPLETION_REPORT.md`; guides in `research/docs/`.
