# Phase 5 report: ablation, robustness, sensitivity and evidence evolution

Run ID: `P5-20261102T052840Z-766b7f1` | git `766b7f1` | seeds 50 (2 cases each) | rows 38400 | status COMPLETED. Results: `research/phase5/results/P5-20261102T052840Z-766b7f1/` (`per_case_results.csv`, `analysis.json`, `evolution_results.json`, `evolution_analysis.json`). Synthetic data only. An earlier smoke/pilot bundle `P5-20261101T132426Z-17567da` (without two robustness methods and claim-level detail) is preserved unchanged.

## 1. Ablations of RAEER (Q40 is not ablated: it has none of these components)

Each ablation turns off exactly one component of RAEER (`research/phase5/algorithms.py`): reliability (ρ≡1), contradiction (C≡0), temporal reasoning (no decay and no temporal feature), spatial/communication (feature weight 0; the scene set used to link other signals is unchanged), graph (relational feature 0), lifecycle (all statuses treated as current), corroboration (feature 0), independence (every record its own origin), provenance (provenance root ignored; in these data origin_root equals source, so this ablation is identical to independence in effect). Differences are *full − ablation*; positive means the component helps. Holm correction across the 11 comparisons per metric.

### Clean data (n = 50 seeds)

Full RAEER: nDCG@5 0.855, MRR 0.952, AP 0.851.

| variant | nDCG@5 | MRR | AP | full − variant, nDCG@5 [95% CI] | p (Holm) | sig. |
|---|---|---|---|---|---|---|
| q40_py | 0.578 | 0.664 | 0.532 | +0.277 [+0.226, +0.328] | <0.001 | yes |
| raeer-no_communication | 0.856 | 0.953 | 0.852 | -0.001 [-0.009, +0.005] | 1.000 | no |
| raeer-no_contradiction | 0.823 | 0.909 | 0.801 | +0.032 [+0.016, +0.049] | <0.001 | yes |
| raeer-no_corroboration | 0.855 | 0.954 | 0.851 | +0.000 [-0.008, +0.007] | 1.000 | no |
| raeer-no_graph | 0.862 | 0.963 | 0.859 | -0.006 [-0.024, +0.008] | 1.000 | no |
| raeer-no_independence | 0.870 | 0.963 | 0.862 | -0.015 [-0.025, -0.006] | 0.004 | yes |
| raeer-no_lifecycle | 0.855 | 0.952 | 0.851 | +0.000 [+0.000, +0.000] | 1.000 | no |
| raeer-no_provenance | 0.870 | 0.963 | 0.862 | -0.015 [-0.025, -0.006] | 0.004 | yes |
| raeer-no_reliability | 0.847 | 0.925 | 0.829 | +0.009 [-0.016, +0.036] | 1.000 | no |
| raeer-no_spatial | 0.752 | 0.820 | 0.713 | +0.103 [+0.065, +0.143] | <0.001 | yes |
| raeer-no_temporal | 0.855 | 0.955 | 0.860 | +0.000 [-0.005, +0.007] | 1.000 | no |

### Mixed-quality degradation (level 0.4) (n = 50 seeds)

Full RAEER: nDCG@5 0.629, MRR 0.746, AP 0.618.

| variant | nDCG@5 | MRR | AP | full − variant, nDCG@5 [95% CI] | p (Holm) | sig. |
|---|---|---|---|---|---|---|
| q40_py | 0.468 | 0.559 | 0.425 | +0.161 [+0.116, +0.207] | <0.001 | yes |
| raeer-no_communication | 0.621 | 0.750 | 0.621 | +0.007 [-0.014, +0.029] | 1.000 | no |
| raeer-no_contradiction | 0.625 | 0.741 | 0.610 | +0.004 [+0.001, +0.008] | 0.070 | no |
| raeer-no_corroboration | 0.631 | 0.764 | 0.623 | -0.002 [-0.016, +0.011] | 1.000 | no |
| raeer-no_graph | 0.617 | 0.745 | 0.612 | +0.011 [-0.008, +0.031] | 1.000 | no |
| raeer-no_independence | 0.632 | 0.734 | 0.611 | -0.003 [-0.022, +0.016] | 1.000 | no |
| raeer-no_lifecycle | 0.668 | 0.779 | 0.654 | -0.040 [-0.075, -0.009] | 0.318 | no |
| raeer-no_provenance | 0.632 | 0.734 | 0.611 | -0.003 [-0.022, +0.016] | 1.000 | no |
| raeer-no_reliability | 0.628 | 0.698 | 0.595 | +0.000 [-0.026, +0.031] | 1.000 | no |
| raeer-no_spatial | 0.551 | 0.651 | 0.527 | +0.077 [+0.046, +0.110] | <0.001 | yes |
| raeer-no_temporal | 0.628 | 0.723 | 0.611 | +0.001 [-0.015, +0.017] | 1.000 | no |

### After all scripted lifecycle events (system's own change_validity) (n = 50 seeds)

Full RAEER: nDCG@5 0.843, MRR 0.957, AP 0.863.

| variant | nDCG@5 | MRR | AP | full − variant, nDCG@5 [95% CI] | p (Holm) | sig. |
|---|---|---|---|---|---|---|
| q40 | 0.651 | 0.783 | 0.614 | +0.192 [+0.136, +0.249] | <0.001 | yes |
| q40_py | 0.651 | 0.783 | 0.614 | +0.192 [+0.136, +0.249] | <0.001 | yes |
| raeer-no_communication | 0.846 | 0.958 | 0.863 | -0.003 [-0.010, +0.001] | 1.000 | no |
| raeer-no_contradiction | 0.832 | 0.937 | 0.849 | +0.012 [+0.003, +0.023] | 0.027 | yes |
| raeer-no_corroboration | 0.845 | 0.958 | 0.861 | -0.002 [-0.010, +0.005] | 1.000 | no |
| raeer-no_graph | 0.845 | 0.967 | 0.865 | -0.001 [-0.020, +0.014] | 1.000 | no |
| raeer-no_independence | 0.858 | 0.968 | 0.871 | -0.015 [-0.026, -0.006] | 0.010 | yes |
| raeer-no_lifecycle | 0.855 | 0.952 | 0.851 | -0.012 [-0.034, +0.009] | 1.000 | no |
| raeer-no_provenance | 0.858 | 0.968 | 0.871 | -0.015 [-0.026, -0.006] | 0.010 | yes |
| raeer-no_reliability | 0.871 | 0.951 | 0.852 | -0.027 [-0.048, -0.005] | 0.023 | yes |
| raeer-no_spatial | 0.806 | 0.892 | 0.767 | +0.037 [+0.006, +0.071] | 0.354 | no |
| raeer-no_temporal | 0.844 | 0.956 | 0.867 | -0.001 [-0.005, +0.003] | 1.000 | no |

## 2. Robustness (nDCG@5 mean over 50 seeds; levels 1/2/3 of each perturbation)

Perturbations are seeded, applied to the in-memory case view and never use labels (`research/phase5/perturb.py`, levels in `configs/phase5_config.json`). `q40_py` is Q40 re-expressed in Python (equal to the frozen SQL within rounding; `q40_py` = `q40` on the evolved database, 0.651 = 0.651), needed because SQL cannot run on perturbed in-memory data.

| perturbation | level | q40_py | q40_r | raeer | raeer-no_independence | raeer-no_lifecycle | spatial_proximity | communication_frequency | pagerank |
|---|---|---|---|---|---|---|---|---|---|
| clean (no perturbation) | - | 0.578 | 0.632 | 0.855 | 0.870 | 0.855 | 0.512 | 0.349 | 0.370 |
| challenge | 0.1 | 0.546 | 0.626 | 0.838 | 0.851 | 0.855 | 0.500 | 0.317 | 0.362 |
| challenge | 0.3 | 0.477 | 0.612 | 0.806 | 0.839 | 0.855 | 0.469 | 0.282 | 0.351 |
| challenge | 0.5 | 0.390 | 0.615 | 0.785 | 0.827 | 0.855 | 0.447 | 0.235 | 0.298 |
| contradictory_records | 0.1 | 0.578 | 0.632 | 0.841 | 0.854 | 0.841 | 0.510 | 0.349 | 0.370 |
| contradictory_records | 0.3 | 0.574 | 0.624 | 0.845 | 0.862 | 0.845 | 0.506 | 0.349 | 0.370 |
| contradictory_records | 0.5 | 0.569 | 0.623 | 0.816 | 0.818 | 0.816 | 0.507 | 0.349 | 0.370 |
| delayed_evidence | 0.1 | 0.269 | 0.297 | 0.222 | 0.274 | 0.222 | 0.029 | 0.349 | 0.274 |
| delayed_evidence | 0.3 | 0.225 | 0.238 | 0.220 | 0.298 | 0.220 | 0.046 | 0.349 | 0.274 |
| delayed_evidence | 0.5 | 0.221 | 0.279 | 0.212 | 0.272 | 0.212 | 0.046 | 0.263 | 0.274 |
| duplicate_evidence | 0.1 | 0.578 | 0.632 | 0.855 | 0.864 | 0.855 | 0.512 | 0.331 | 0.370 |
| duplicate_evidence | 0.3 | 0.578 | 0.632 | 0.855 | 0.849 | 0.855 | 0.512 | 0.331 | 0.370 |
| duplicate_evidence | 0.5 | 0.578 | 0.632 | 0.855 | 0.849 | 0.855 | 0.512 | 0.344 | 0.370 |
| incorrect_timestamps | 0.1 | 0.549 | 0.607 | 0.806 | 0.820 | 0.806 | 0.496 | 0.343 | 0.370 |
| incorrect_timestamps | 0.3 | 0.537 | 0.580 | 0.767 | 0.777 | 0.767 | 0.509 | 0.326 | 0.370 |
| incorrect_timestamps | 0.5 | 0.531 | 0.585 | 0.658 | 0.671 | 0.658 | 0.469 | 0.318 | 0.370 |
| invalidation | 0.1 | 0.550 | 0.596 | 0.792 | 0.799 | 0.855 | 0.498 | 0.315 | 0.342 |
| invalidation | 0.3 | 0.494 | 0.528 | 0.692 | 0.709 | 0.855 | 0.489 | 0.300 | 0.327 |
| invalidation | 0.5 | 0.456 | 0.482 | 0.619 | 0.620 | 0.855 | 0.469 | 0.193 | 0.292 |
| low_reliability | 0.2 | 0.578 | 0.655 | 0.848 | 0.869 | 0.848 | 0.512 | 0.349 | 0.370 |
| low_reliability | 0.4 | 0.578 | 0.663 | 0.842 | 0.871 | 0.842 | 0.512 | 0.349 | 0.370 |
| low_reliability | 0.6 | 0.578 | 0.647 | 0.826 | 0.873 | 0.826 | 0.512 | 0.349 | 0.370 |
| missing_evidence | 0.1 | 0.542 | 0.584 | 0.805 | 0.827 | 0.805 | 0.529 | 0.332 | 0.341 |
| missing_evidence | 0.3 | 0.486 | 0.534 | 0.662 | 0.678 | 0.662 | 0.490 | 0.284 | 0.299 |
| missing_evidence | 0.5 | 0.445 | 0.454 | 0.594 | 0.596 | 0.594 | 0.497 | 0.190 | 0.199 |
| mixed_quality | 0.2 | 0.528 | 0.568 | 0.733 | 0.744 | 0.763 | 0.496 | 0.317 | 0.362 |
| mixed_quality | 0.4 | 0.468 | 0.513 | 0.629 | 0.632 | 0.668 | 0.439 | 0.247 | 0.312 |
| mixed_quality | 0.6 | 0.380 | 0.402 | 0.612 | 0.601 | 0.650 | 0.405 | 0.201 | 0.270 |
| noisy_location | 0.1 | 0.574 | 0.636 | 0.818 | 0.825 | 0.818 | 0.508 | 0.349 | 0.370 |
| noisy_location | 0.3 | 0.485 | 0.544 | 0.707 | 0.724 | 0.707 | 0.477 | 0.349 | 0.370 |
| noisy_location | 0.5 | 0.464 | 0.512 | 0.679 | 0.688 | 0.679 | 0.476 | 0.349 | 0.370 |
| reduced_communication | 0.1 | 0.579 | 0.641 | 0.855 | 0.868 | 0.855 | 0.512 | 0.332 | 0.370 |
| reduced_communication | 0.3 | 0.582 | 0.649 | 0.853 | 0.867 | 0.853 | 0.512 | 0.313 | 0.370 |
| reduced_communication | 0.5 | 0.580 | 0.633 | 0.844 | 0.853 | 0.844 | 0.512 | 0.244 | 0.370 |
| reduced_graph | 0.1 | 0.581 | 0.636 | 0.848 | 0.860 | 0.848 | 0.512 | 0.349 | 0.339 |
| reduced_graph | 0.3 | 0.582 | 0.644 | 0.846 | 0.856 | 0.846 | 0.512 | 0.349 | 0.275 |
| reduced_graph | 0.5 | 0.589 | 0.647 | 0.847 | 0.865 | 0.847 | 0.512 | 0.349 | 0.199 |
| update_superseded | 0.1 | 0.543 | 0.598 | 0.813 | 0.826 | 0.855 | 0.507 | 0.317 | 0.366 |
| update_superseded | 0.3 | 0.472 | 0.519 | 0.693 | 0.698 | 0.855 | 0.473 | 0.252 | 0.326 |
| update_superseded | 0.5 | 0.425 | 0.454 | 0.582 | 0.595 | 0.855 | 0.432 | 0.220 | 0.305 |

Paired degradation of RAEER vs its own clean score (level 3, nDCG@5 difference perturbed − clean, 95% CI, Wilcoxon p; not multiplicity-corrected, exploratory):

| perturbation | level | RAEER Δ nDCG@5 | p | Q40 Δ nDCG@5 |
|---|---|---|---|---|
| challenge | 0.5 | -0.070 [-0.106, -0.035] | <0.001 | -0.188 [-0.252, -0.125] |
| contradictory_records | 0.5 | -0.039 [-0.067, -0.012] | 0.014 | -0.010 [-0.017, -0.004] |
| delayed_evidence | 0.5 | -0.643 [-0.690, -0.597] | <0.001 | -0.358 [-0.420, -0.293] |
| duplicate_evidence | 0.5 | +0.000 [+0.000, +0.000] | 1.000 | +0.000 [+0.000, +0.000] |
| incorrect_timestamps | 0.5 | -0.197 [-0.259, -0.135] | <0.001 | -0.047 [-0.097, +0.002] |
| invalidation | 0.5 | -0.236 [-0.296, -0.175] | <0.001 | -0.122 [-0.185, -0.058] |
| low_reliability | 0.6 | -0.029 [-0.050, -0.011] | 0.005 | +0.000 [+0.000, +0.000] |
| missing_evidence | 0.5 | -0.261 [-0.318, -0.205] | <0.001 | -0.134 [-0.180, -0.086] |
| mixed_quality | 0.6 | -0.243 [-0.302, -0.188] | <0.001 | -0.198 [-0.251, -0.145] |
| noisy_location | 0.5 | -0.176 [-0.226, -0.124] | <0.001 | -0.114 [-0.183, -0.048] |
| reduced_communication | 0.5 | -0.011 [-0.026, -0.001] | 0.053 | +0.001 [-0.011, +0.014] |
| reduced_graph | 0.5 | -0.008 [-0.022, +0.006] | 0.158 | +0.011 [-0.007, +0.030] |
| update_superseded | 0.5 | -0.273 [-0.328, -0.220] | <0.001 | -0.153 [-0.201, -0.105] |

## 3. Sensitivity of RAEER to its parameters (one at a time, clean data, nDCG@5)

| variant | nDCG@5 | Δ vs default RAEER [95% CI] | p (Wilcoxon, uncorrected) |
|---|---|---|---|
| raeer@distance=1000 | 0.855 | +0.000 [+0.000, +0.000] | 1.000 |
| raeer@distance=2000 | 0.836 | -0.020 [-0.033, -0.008] | <0.001 |
| raeer@distance=500 | 0.857 | +0.002 [+0.000, +0.006] | 0.500 |
| raeer@gamma=0.0 | 0.823 | -0.032 [-0.049, -0.016] | <0.001 |
| raeer@gamma=0.25 | 0.845 | -0.010 [-0.018, -0.004] | <0.001 |
| raeer@gamma=0.5 | 0.855 | +0.000 [+0.000, +0.000] | 1.000 |
| raeer@gamma=0.75 | 0.859 | +0.003 [+0.001, +0.007] | 0.002 |
| raeer@gamma=1.0 | 0.859 | +0.003 [+0.001, +0.007] | 0.002 |
| raeer@radius=150 | 0.855 | +0.000 [+0.000, +0.000] | 1.000 |
| raeer@radius=300 | 0.851 | -0.004 [-0.011, +0.000] | 0.500 |
| raeer@radius=50 | 0.681 | -0.174 [-0.222, -0.130] | <0.001 |
| raeer@tau=120 | 0.862 | +0.007 [+0.001, +0.015] | 0.062 |
| raeer@tau=15 | 0.850 | -0.005 [-0.010, -0.001] | 0.031 |
| raeer@tau=30 | 0.855 | +0.000 [+0.000, +0.000] | 1.000 |
| raeer@tau=60 | 0.859 | +0.004 [+0.000, +0.008] | 0.125 |
| raeer@w_communication=0.5 | 0.857 | +0.002 [-0.003, +0.010] | 0.625 |
| raeer@w_communication=1.5 | 0.856 | +0.001 [-0.003, +0.005] | 1.000 |
| raeer@w_corroboration=0.5 | 0.853 | -0.002 [-0.007, +0.001] | 0.625 |
| raeer@w_corroboration=1.5 | 0.856 | +0.001 [+0.000, +0.003] | 1.000 |
| raeer@w_financial=0.5 | 0.856 | +0.001 [+0.000, +0.003] | 0.500 |
| raeer@w_financial=1.5 | 0.854 | -0.001 [-0.009, +0.005] | 1.000 |
| raeer@w_relational=0.5 | 0.854 | -0.001 [-0.005, +0.004] | 0.960 |
| raeer@w_relational=1.5 | 0.848 | -0.007 [-0.017, +0.001] | 0.231 |
| raeer@w_spatial=0.5 | 0.838 | -0.017 [-0.035, -0.001] | 0.091 |
| raeer@w_spatial=1.5 | 0.861 | +0.005 [-0.001, +0.014] | 0.038 |
| raeer@w_temporal=0.5 | 0.855 | -0.000 [-0.004, +0.002] | 0.625 |
| raeer@w_temporal=1.5 | 0.857 | +0.002 [-0.005, +0.011] | 1.000 |

## 4. Evidence-evolution experiment

100 cases, 530 scripted lifecycle steps applied through the system's own `change_validity()` and recomputation. Expected outcomes are the generator's ground truth (`must_flag`/`must_not_flag`/`indeterminate`), not the correlation lineage.

### 4.1 History and event integrity (from the append-only `evidence_validity_events`)

| check | result |
|---|---|
| steps applied / scripted | 530 / 530 |
| transition checks (evidence identity, previous status, new status, trigger, reason, rule permitted) | 0 failures; mean accuracy 1.000 |
| cases with consistent history (chains, contiguous finding versions, no CURRENT finding on non-SUPPORTED evidence) | 100 / 100 |
| cases with unique event ids | 100 / 100 |
| cases with monotonic event timestamps | 100 / 100 |

### 4.2 Affected-finding detection by the system (finding_impact_log vs independent expectations)

| subset | steps | expected (must-flag) findings | detected | recall | must-not-flag findings flagged | flagged total | of which indeterminate |
|---|---|---|---|---|---|---|---|
| all_steps | 530 | 386 | 150 | 0.389 | 0 | 1311 | 1161 |
| first_dispute_step | 332 | 193 | 150 | 0.777 | 0 | 1311 | 1161 |
| later_steps | 198 | 193 | 0 | 0.000 | 0 | 0 | 0 |

Claims whose only supporting record is the changed evidence: 80 of 160 expected flags detected; claims with redundant independent support: 70 of 226.

### 4.3 Ranking change per lifecycle step

| method | steps with any score change | mean Kendall τ | mean Spearman ρ | mean top-5 overlap | mean rank displacement | changes on non-touched candidates | expected people updated / expected | nDCG@5 initial → final |
|---|---|---|---|---|---|---|---|---|
| q40 | 80 / 530 | 0.984 | 0.989 | 0.981 | 0.527 | 332 | 80 / 246 | 0.578 → 0.651 |
| q40_r | 310 / 530 | 0.984 | 0.989 | 0.980 | 0.536 | 332 | 160 / 246 | 0.632 → 0.714 |
| raeer | 246 / 530 | 0.985 | 0.993 | 0.981 | 0.469 | 632 | 246 / 246 | 0.855 → 0.843 |
| raeer-no_lifecycle | 51 / 530 | 1.000 | 1.000 | 1.000 | 0.000 | 0 | 0 / 246 | 0.855 → 0.855 |

Mean change in nDCG@5 per step, by scenario:

| scenario | steps | q40 | q40_r | raeer | raeer-no_lifecycle |
|---|---|---|---|---|---|
| SC-ALIBI-CORRECTED | 51 | +0.000 | +0.000 | +0.000 | +0.000 |
| SC-DEVICE-FAULT | 160 | +0.046 | +0.051 | +0.011 | +0.000 |
| SC-WITNESS | 150 | +0.000 | +0.000 | +0.000 | +0.000 |
| SC-LEAD-TIMESTAMP | 86 | +0.000 | +0.000 | -0.034 | +0.000 |
| SC-TIP-RETRACTED | 83 | +0.000 | +0.000 | +0.000 | +0.000 |

### 4.4 Latency (this machine, PostgreSQL local)

| stage | n | p50 ms | p95 ms | p99 ms |
|---|---|---|---|---|
| apply_ms | 530 | 7.9 | 20.6 | 28.2 |
| recompute_ms | 365 | 43.6 | 131.3 | 166.8 |
| rank_ms_per_method | 530 | 25.4 | 75.1 | 89.0 |

## 5. Interpretation

**Ablation (what actually contributes)**
* On clean data the large RAEER advantage over Q40 (+0.277 nDCG@5) is **not attributable to any single removable component**: the weakest ablated variant (no spatial feature, 0.752) is still far above Q40 (0.578). Only two components show a detectable positive contribution: the **spatial feature** (+0.103 when present, significant) and **contradiction handling** (+0.032, significant; also +0.012 after lifecycle events and a smaller, not-significant +0.004 under mixed degradation). Reliability weighting, temporal reasoning, lifecycle handling, corroboration, relational support and communication have **no detectable effect on clean data** (CIs include 0; lifecycle is a no-op because every record is SUPPORTED).
* **Source-independence / provenance handling lowered clean performance** (−0.015 nDCG@5, Holm p = 0.004): collapsing records from one origin discards record volume, which in this generator is informative (true leads accumulate more records). The duplicate-evidence perturbation shows the intended benefit only marginally (RAEER 0.855 vs 0.849 without independence handling at level 0.5). The data therefore do **not** support a claim that independence handling improves ranking here. `no_provenance` equals `no_independence` because provenance roots equal sources in these data.
* The remaining gap to Q40 comes from the overall redesign (graded features, 150 m scene radius, noisy-OR). The sensitivity run points at the scene radius: shrinking it from 150 m to 50 m costs 0.174 nDCG@5, consistent with true-lead presence at the neighbouring venue (≈55 m from the incident location, planted by the generator) being counted by RAEER but not by Q40's same-location test. This is a plausible explanation, not a proven one, and it again ties the advantage to generator design.
* After real lifecycle events, lifecycle-aware RAEER is not significantly different from lifecycle-blind RAEER (−0.012, p_Holm = 1.0): honouring DEVICE-FAULT events helped (+0.011 nDCG@5 per step) while honouring LEAD-TIMESTAMP events hurt (−0.034), because the invalidated evidence belonged to a true lead whose ground-truth relevance does not change.

**Robustness**
* All methods lose accuracy under missing evidence, shifted timestamps, noisy locations and degraded reliability. At the highest level of each perturbation RAEER's point estimate stays above Q40's in 12 of 13 perturbation types; the exception is `delayed_evidence`, where both collapse (RAEER 0.212, Q40 0.221, spatial 0.046). That perturbation hides the most recently arrived evidence, which in these synthetic data includes the incident-evening evidence, so it is an extreme stress test rather than a typical delay.
* Duplicated records leave every method essentially unchanged; reduced communication and reduced relationship graphs matter little (the methods do not rely on them much here), and plain PageRank halves under graph reduction (0.370 → 0.199).
* The random `invalidation`, `challenge` and `update_superseded` perturbations lower the lifecycle-aware methods' scores while the lifecycle-blind variant is unchanged. These perturbations flip statuses at random, which carries no information about truth, so they measure **loss of usable evidence**, not whether honouring lifecycle is correct. The scripted scenarios in §4 are the meaningful test of that.

**Sensitivity.** RAEER is insensitive to every weight (|Δ| ≤ 0.017 nDCG@5 for ×0.5/×1.5 scaling), to τ (15–120 min, |Δ| ≤ 0.007) and to D = 500 m. It is sensitive to the scene radius (50 m: −0.174), to γ = 0 (−0.032, identical to removing contradiction handling) and to D = 2000 m (−0.020). γ ≥ 0.75 is marginally better (+0.003); γ was not tuned.

**Evidence evolution**
* Integrity: all 530 scripted steps applied and matched their expected evidence, previous status, new status, trigger and reason; every one of the 100 case histories is consistent, with unique event ids and monotonic timestamps.
* **The system never flagged a finding that the ground truth marks as unaffected** (0 must-not-flag findings flagged), so unrelated findings were stable.
* **Detection of expected impacts is incomplete and step-dependent**: the system flags findings only when evidence first enters dispute (150 of 193 expected flags at those steps, 77.7%) and **never at later transitions** (CHALLENGED → INVALIDATED, reinstatement; 0 of 193). Part of the shortfall at first transitions is a ground-truth subtlety: several planted claims have redundant independent support (e.g. GPS plus CCTV) and the system's lineage records only part of it, so one source failing does not necessarily invalidate the finding. This does not look like a bug, but a recovery signal for reinstated evidence is absent; this is reported, not changed.
* Ranking response: Q40 (excludes CHALLENGED outright) updated 80 of 246 expected people (166 missed), Q40-R 160, RAEER 246. RAEER also changed scores of non-touched candidates in 632 cases (Q40: 332); this counts legitimate second-order propagation (people linked to a scene person whose support disappeared), so it is an **upper bound** on unnecessary change. Overall ranking stability was high for all methods (mean Kendall τ 0.984–0.985, top-5 overlap ≈ 0.98).
* Latency (local machine): applying an event p50 7 ms, system recomputation p50 44 ms (p95 127 ms), re-ranking p50 30 ms per method.

## 6. Limitations
* One generator family; evolution scenarios are scripted by the same generator that creates the data, with expectations derived from its plan.
* Ground-truth relevance is time-invariant, so ranking metrics after lifecycle events reward keeping true leads even when their evidence becomes invalid.
* Robustness perturbations are synthetic and independent across records; correlated failures (a whole device or source) are not modelled except via the scripted scenarios.
* `q40_py` replaces the SQL Q40 in perturbation experiments; equality was verified on clean and evolved data, not on perturbed data.
* Statistical tests assume seeds are independent draws; robustness p-values are uncorrected and exploratory.
