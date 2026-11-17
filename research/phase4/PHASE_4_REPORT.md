# Phase 4 report: reliability-aware ranking (Q40-R) and RAEER

Run ID: `P4-20261102T052715Z-766b7f1` | git `766b7f1` | seeds evaluated 50 | status COMPLETED | datasets hash-verified: True. Results: `research/phase4/results/P4-20261102T052715Z-766b7f1/`. Synthetic data only.

## 1. What was implemented

* **Q40-R** (`research/phase4/algorithms/q40r.py`): Q40 with the same six signals, weights and window, but each binary signal is replaced by the best reliability×lifecycle-status factor of its supporting records. Reliability switched off ⇒ identical to the frozen Q40 SQL (test `test_q40r_with_reliability_off_equals_frozen_q40_on_real_data`). Q40 itself is untouched.
* **RAEER** (`research/phase4/algorithms/raeer.py`, definition and equations in `research/phase4/docs/RAEER_DEFINITION.md`): the repository contained only the name (Reliability-Aware Evidence Evolution Ranking) and the six factors it should study, no formula. The formula is therefore an operational definition proposed for this study. It differs from Q40-R in graded geometry (150 m scene radius), temporal-consistency decay, noisy-OR over independent origins, relational support extended to scene persons, a bounded contradiction penalty and domain corroboration.
* Configuration `research/phase4/configs/phase4_config.json` was committed **before** any evaluation (`frozen_before_evaluation`) with weights equal to Q40's; nothing was tuned on ground truth, and each method was evaluated exactly once in this run.

## 2. Ranking results (mean over 50 seeds, 95% bootstrap CI)

| method | P@1 mean [95% CI] | P@3 mean [95% CI] | P@5 mean [95% CI] | R@5 mean [95% CI] | MRR mean [95% CI] | nDCG@5 mean [95% CI] | AP mean [95% CI] |
|---|---|---|---|---|---|---|---|
| random | 0.050 [0.045, 0.055] | 0.050 [0.046, 0.053] | 0.049 [0.046, 0.052] | 0.082 [0.078, 0.086] | 0.158 [0.152, 0.165] | 0.060 [0.057, 0.063] | 0.108 [0.104, 0.111] |
| communication_frequency | 0.310 [0.230, 0.390] | 0.230 [0.187, 0.273] | 0.200 [0.172, 0.230] | 0.315 [0.268, 0.363] | 0.480 [0.415, 0.547] | 0.349 [0.296, 0.402] | 0.299 [0.264, 0.335] |
| spatial_proximity | 0.370 [0.280, 0.470] | 0.340 [0.303, 0.377] | 0.368 [0.342, 0.394] | 0.627 [0.588, 0.667] | 0.608 [0.549, 0.669] | 0.512 [0.476, 0.550] | 0.471 [0.437, 0.506] |
| degree_centrality | 0.290 [0.200, 0.380] | 0.193 [0.153, 0.237] | 0.168 [0.138, 0.198] | 0.267 [0.217, 0.317] | 0.435 [0.358, 0.512] | 0.270 [0.216, 0.324] | 0.258 [0.221, 0.296] |
| pagerank | 0.370 [0.280, 0.460] | 0.287 [0.237, 0.337] | 0.250 [0.216, 0.282] | 0.410 [0.356, 0.462] | 0.551 [0.480, 0.619] | 0.370 [0.314, 0.424] | 0.349 [0.310, 0.389] |
| q40 | 0.460 [0.360, 0.560] | 0.470 [0.420, 0.520] | 0.362 [0.328, 0.396] | 0.608 [0.561, 0.655] | 0.664 [0.598, 0.730] | 0.578 [0.527, 0.627] | 0.532 [0.488, 0.575] |
| q40_r | 0.510 [0.410, 0.610] | 0.503 [0.450, 0.553] | 0.404 [0.370, 0.438] | 0.682 [0.629, 0.733] | 0.702 [0.638, 0.764] | 0.632 [0.582, 0.681] | 0.580 [0.535, 0.624] |
| raeer | 0.920 [0.870, 0.970] | 0.770 [0.723, 0.817] | 0.520 [0.484, 0.556] | 0.864 [0.820, 0.904] | 0.952 [0.919, 0.981] | 0.855 [0.821, 0.885] | 0.851 [0.809, 0.890] |

### RAEER − Q40

nDCG@5:

| comparison | mean diff | 95% CI | p (Wilcoxon) | p (Holm) | sig. @0.05 | rank-biserial r | wins/losses/ties (seeds) |
|---|---|---|---|---|---|---|---|
| raeer − communication_frequency | 0.506 | [0.441, 0.572] | <0.001 | <0.001 | yes | 1.000 | 50/0/0 |
| raeer − degree_centrality | 0.585 | [0.521, 0.648] | <0.001 | <0.001 | yes | 1.000 | 50/0/0 |
| raeer − pagerank | 0.485 | [0.423, 0.549] | <0.001 | <0.001 | yes | 1.000 | 50/0/0 |
| raeer − q40 | 0.277 | [0.226, 0.328] | <0.001 | <0.001 | yes | 0.964 | 47/2/1 |
| raeer − q40_r | 0.223 | [0.176, 0.271] | <0.001 | <0.001 | yes | 0.962 | 45/4/1 |
| raeer − random | 0.795 | [0.760, 0.826] | <0.001 | <0.001 | yes | 1.000 | 50/0/0 |
| raeer − spatial_proximity | 0.343 | [0.294, 0.388] | <0.001 | <0.001 | yes | 0.984 | 47/3/0 |

MRR:

| comparison | mean diff | 95% CI | p (Wilcoxon) | p (Holm) | sig. @0.05 | rank-biserial r | wins/losses/ties (seeds) |
|---|---|---|---|---|---|---|---|
| raeer − communication_frequency | 0.472 | [0.399, 0.546] | <0.001 | <0.001 | yes | 1.000 | 46/0/4 |
| raeer − degree_centrality | 0.518 | [0.437, 0.597] | <0.001 | <0.001 | yes | 1.000 | 45/0/5 |
| raeer − pagerank | 0.401 | [0.329, 0.476] | <0.001 | <0.001 | yes | 1.000 | 44/0/6 |
| raeer − q40 | 0.288 | [0.216, 0.359] | <0.001 | <0.001 | yes | 0.942 | 36/1/13 |
| raeer − q40_r | 0.250 | [0.186, 0.315] | <0.001 | <0.001 | yes | 0.997 | 33/1/16 |
| raeer − random | 0.794 | [0.761, 0.823] | <0.001 | <0.001 | yes | 1.000 | 50/0/0 |
| raeer − spatial_proximity | 0.344 | [0.275, 0.411] | <0.001 | <0.001 | yes | 0.978 | 39/3/8 |

### Q40-R vs Q40

nDCG@5:

| comparison | mean diff | 95% CI | p (Wilcoxon) | p (Holm) | sig. @0.05 | rank-biserial r | wins/losses/ties (seeds) |
|---|---|---|---|---|---|---|---|
| q40_r − communication_frequency | 0.283 | [0.210, 0.353] | <0.001 | <0.001 | yes | 0.860 | 41/9/0 |
| q40_r − degree_centrality | 0.362 | [0.285, 0.436] | <0.001 | <0.001 | yes | 0.915 | 41/9/0 |
| q40_r − pagerank | 0.262 | [0.188, 0.335] | <0.001 | <0.001 | yes | 0.815 | 39/11/0 |
| q40_r − q40 | 0.054 | [0.031, 0.078] | <0.001 | <0.001 | yes | 0.835 | 33/3/14 |
| q40_r − raeer | -0.223 | [-0.271, -0.176] | <0.001 | <0.001 | yes | -0.962 | 4/45/1 |
| q40_r − random | 0.572 | [0.522, 0.621] | <0.001 | <0.001 | yes | 1.000 | 50/0/0 |
| q40_r − spatial_proximity | 0.120 | [0.076, 0.164] | <0.001 | <0.001 | yes | 0.694 | 37/13/0 |

## 3. Stratified performance of relevant leads (all seeds, both cases; a lead can appear in several evidence-type strata)

Reliability strata split at the pooled median mean-reliability of a lead's supporting evidence (0.714).

| stratum | n | q40: median rank / top-5 share | q40_r: median rank / top-5 share | raeer: median rank / top-5 share |
|---|---|---|---|---|
| contradiction:lead has contradicting evidence | 35 | 2 / 83% | 2 / 89% | 1 / 100% |
| contradiction:no contradicting evidence | 267 | 5 / 57% | 4 / 64% | 2 / 84% |
| evidence_type:CCTV | 235 | 4 / 66% | 3 / 74% | 2 / 99% |
| evidence_type:CDR | 302 | 4 / 60% | 4 / 67% | 2 / 86% |
| evidence_type:DOCUMENT | 182 | 3 / 64% | 3 / 71% | 2 / 90% |
| evidence_type:GPS | 158 | 2 / 98% | 2 / 99% | 1 / 99% |
| evidence_type:TRANSACTION_RECORD | 190 | 4 / 66% | 3 / 74% | 2 / 99% |
| evidence_type:WITNESS_STATEMENT | 182 | 3 / 64% | 3 / 71% | 2 / 90% |
| red_herring:HIGH_COMMUNICATION | 48 | 5 / 67% | 5 / 58% | 7 / 29% |
| red_herring:HIGH_PROXIMITY | 44 | 4 / 75% | 4 / 70% | 7 / 27% |
| red_herring:MIXED | 57 | 1 / 100% | 1 / 100% | 3 / 98% |
| reliability:high (>= median) | 174 | 5 / 54% | 4 / 62% | 2 / 86% |
| reliability:low (< median) | 128 | 3 / 68% | 3 / 73% | 2 / 87% |

Red-herring strata list decoys (lower top-5 share is better for decoys).

## 4. Tie sensitivity

| method | distinct scores / case | nDCG@5 pessimistic–optimistic ties | red herrings in top-5 |
|---|---|---|---|
| random | 71.9 | 0.047–0.047 | 7 of 149 |
| communication_frequency | 71.9 | 0.349–0.349 | 38 of 149 |
| spatial_proximity | 12.4 | 0.311–0.796 | 99 of 149 |
| degree_centrality | 10.7 | 0.214–0.320 | 15 of 149 |
| pagerank | 71.9 | 0.370–0.370 | 18 of 149 |
| q40 | 9.6 | 0.504–0.651 | 122 of 149 |
| q40_r | 18.6 | 0.596–0.674 | 116 of 149 |
| raeer | 55.1 | 0.855–0.858 | 82 of 149 |

## 5. Interpretation

**What the data show**

* **Q40-R improves modestly on Q40**: nDCG@5 0.632 vs 0.578 (+0.054; Q40-R better on 33 of 50 seeds, worse on 3), significant after Holm correction. **However, a large part of this may be tie resolution rather than reliability evidence**: Q40 has ≈ 9.6 distinct scores per case (binary signals), Q40-R ≈ 18.6. Q40-R's value (0.632) lies inside Q40's own tie band (0.504–0.651). The reliability weights act mostly as a tie-breaker, which is a legitimate use of the information but a smaller claim than "reliability weighting improves ranking". Phase 5 isolates this.
* **RAEER is far better than Q40 on this benchmark**: P@1 0.92 vs 0.46, MRR 0.952 vs 0.664, nDCG@5 0.855 vs 0.578 (RAEER better on 47 of 50 seeds, Holm p < 0.001), and its result is insensitive to tie handling (0.855–0.858). It also pushes red-herring decoys down (82 of 149 in the top five vs 122 for Q40), most for the HIGH_COMMUNICATION and HIGH_PROXIMITY decoy types, and ranks weak leads better (median 11 vs 15).
* RAEER is better than the strongest simple baseline (spatial proximity) by 0.34 nDCG@5.

**Why this must not be read as "RAEER is a better investigative method"**

1. *Generator coupling.* RAEER's contradiction rule and its temporal-consistency decay work because the synthetic storylines plant (a) true-lead presence at the incident time and (b) an independent workplace-access-log alibi for red herrings. A method that looks for exactly these structures will find them in data built with them. The structures are realistic in kind, but the generator decides how clean and how common they are. The researcher also knew the generator's design when specifying the features; the rule itself was taken from the system's existing `CONTRADICTION_001` thresholds and fixed before evaluation, but this knowledge is a threat to validity.
2. *Which component matters is not yet known.* The six RAEER changes are bundled here. Phase 5 ablations decompose them; until then no component should be credited.
3. *Single generator family, 50 seeds, no real data.* Nothing here supports a claim about real investigations.
4. The strongest stratum results (e.g. leads with CCTV evidence: top-5 share 66% → 99%) come from the same bundled change and carry the same caveat.

**Contradiction handling.** The detected contradictions are structured location conflicts from a different origin; contradictory witness statements are free text and are not processed. A contradiction lowers the spatial feature by at most 50 % and is never treated as proof of innocence.

## 6. Limitations
* Reliability constants are per-evidence-type heuristics, not calibrated probabilities.
* RAEER parameters (R, τ, D, γ, weights) were not tuned; their sensitivity is evaluated in Phase 5, not here.
* All ranking scores are heuristics for prioritising leads for human review, not probabilities of guilt.
