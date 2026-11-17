# Phase 3 report: ranking baselines and evaluation framework

Run ID: `P3-20261101T053604Z-cebe866` | git `cebe866` | Python 3.13.18 | PostgreSQL None | seeds evaluated: 50 (2 cases each) | status: COMPLETED | datasets re-derived from seed and hash-verified against the committed manifests: True

All numbers below are read from `research/phase3/results/P3-20261101T053604Z-cebe866/` (`aggregate_metrics.csv`, `paired_comparisons.csv`, `per_seed_metrics.csv`, `analysis.json`). Data are synthetic; nothing here supports claims about real investigations.

## 1. Methods

All methods rank the same candidate set (every person except the victim) from the same `CaseView` (no ground truth), using only SUPPORTED records, with the same deterministic tie rule.

| method | idea | uses incident? |
|---|---|---|
| random | uniform random order; 100 repetitions per case, averaged within a case (repetitions are NOT independent datasets) | no |
| communication_frequency | equal-weight blend of communication count, unique partners, pre-incident-week frequency, recency to incident | time only |
| spatial_proximity | 1/(1+d_min/100 m) over observations within ±60 min of the incident; no observation → 0 | yes |
| degree_centrality | degree in the relationship graph (isolated nodes 0) | no |
| pagerank | weighted PageRank, damping 0.85, uniform teleport (own power iteration; checked against networkx in tests) | no |
| pagerank_victim_personalised | extra: PageRank with teleport mass on the victim | victim only |
| q40 | frozen Q40 SQL (M18 `overall`) through an adapter; unscored candidates get 0 | yes |

## 2. Evaluation protocol

* Ground truth: `research/ground_truth/seed_<n>.json` (generator plan, independent of every ranking method). Relevant = grade ≥ 1 (perpetrator grade 3, accomplice grade 2); red herrings, bystanders, witnesses and background persons are grade 0. No label is indeterminate in this ground truth; the metric code excludes `None`/unlabelled candidates rather than counting them as negatives (unit-tested).
* Unit of analysis = the seed: each seed's two cases are averaged, giving n = 50 paired observations per method. Case-level values are in `per_case_metrics.csv`.
* P@K = hits in top K / K; R@K = hits / #relevant; AP = mean of precision at relevant ranks; nDCG gain 2^grade−1; MRR = 1/rank of first relevant. Cases without relevant leads would be excluded (none occurred).
* **Ties**: descending raw score, then ascending SHA-256(dataset|case|candidate), independent of reference order and labels. Several methods produce many tied scores, so §5 reports optimistic/pessimistic tie bounds.
* Statistics: bootstrap 95% CI of the mean (10 000 resamples, fixed seed); paired two-sided Wilcoxon signed-rank on per-seed differences; matched-pairs rank-biserial r; Holm correction across all pairs within each metric.

## 3. Results (mean over 50 seeds)

| method | P@1 mean [95% CI] | P@3 mean [95% CI] | P@5 mean [95% CI] | R@5 mean [95% CI] | MRR mean [95% CI] | nDCG@5 mean [95% CI] | AP mean [95% CI] |
|---|---|---|---|---|---|---|---|
| random | 0.050 [0.045, 0.055] | 0.050 [0.046, 0.053] | 0.049 [0.046, 0.052] | 0.082 [0.078, 0.086] | 0.158 [0.152, 0.165] | 0.060 [0.057, 0.063] | 0.108 [0.104, 0.111] |
| communication_frequency | 0.310 [0.230, 0.390] | 0.230 [0.187, 0.273] | 0.200 [0.172, 0.230] | 0.315 [0.268, 0.363] | 0.480 [0.415, 0.547] | 0.349 [0.296, 0.402] | 0.299 [0.264, 0.335] |
| spatial_proximity | 0.370 [0.280, 0.470] | 0.340 [0.303, 0.377] | 0.368 [0.342, 0.394] | 0.627 [0.588, 0.667] | 0.608 [0.549, 0.669] | 0.512 [0.476, 0.550] | 0.471 [0.437, 0.506] |
| degree_centrality | 0.290 [0.200, 0.380] | 0.193 [0.153, 0.237] | 0.168 [0.138, 0.198] | 0.267 [0.217, 0.317] | 0.435 [0.358, 0.512] | 0.270 [0.216, 0.324] | 0.258 [0.221, 0.296] |
| pagerank | 0.370 [0.280, 0.460] | 0.287 [0.237, 0.337] | 0.250 [0.216, 0.282] | 0.410 [0.356, 0.462] | 0.551 [0.480, 0.619] | 0.370 [0.314, 0.424] | 0.349 [0.310, 0.389] |
| pagerank_victim_personalised | 0.140 [0.080, 0.200] | 0.100 [0.070, 0.133] | 0.086 [0.064, 0.108] | 0.141 [0.103, 0.180] | 0.266 [0.214, 0.318] | 0.132 [0.097, 0.168] | 0.183 [0.156, 0.210] |
| q40 | 0.460 [0.360, 0.560] | 0.470 [0.420, 0.520] | 0.362 [0.328, 0.396] | 0.608 [0.561, 0.655] | 0.664 [0.598, 0.730] | 0.578 [0.527, 0.627] | 0.532 [0.488, 0.575] |

Best mean by metric: P@1: `q40`, P@3: `q40`, P@5: `spatial_proximity`, R@5: `spatial_proximity`, MRR: `q40`, nDCG@5: `q40`, AP: `q40`.

### Paired comparisons with Q40 (nDCG@5, Q40 minus other)

| comparison | mean diff | 95% CI | p (Wilcoxon) | p (Holm) | sig. @0.05 | rank-biserial r | wins/losses/ties (seeds) |
|---|---|---|---|---|---|---|---|
| q40 − communication_frequency | 0.229 | [0.153, 0.303] | <0.001 | <0.001 | yes | 0.751 | 39/11/0 |
| q40 − degree_centrality | 0.309 | [0.227, 0.386] | <0.001 | <0.001 | yes | 0.856 | 39/10/1 |
| q40 − pagerank | 0.208 | [0.131, 0.284] | <0.001 | <0.001 | yes | 0.698 | 36/13/1 |
| q40 − pagerank_victim_personalised | 0.446 | [0.392, 0.501] | <0.001 | <0.001 | yes | 1.000 | 50/0/0 |
| q40 − random | 0.518 | [0.466, 0.568] | <0.001 | <0.001 | yes | 1.000 | 50/0/0 |
| q40 − spatial_proximity | 0.066 | [0.023, 0.108] | 0.007 | 0.015 | yes | 0.435 | 29/20/1 |

### Paired comparisons with Q40 (MRR)

| comparison | mean diff | 95% CI | p (Wilcoxon) | p (Holm) | sig. @0.05 | rank-biserial r | wins/losses/ties (seeds) |
|---|---|---|---|---|---|---|---|
| q40 − communication_frequency | 0.184 | [0.093, 0.276] | <0.001 | 0.007 | yes | 0.549 | 35/14/1 |
| q40 − degree_centrality | 0.230 | [0.122, 0.332] | <0.001 | 0.004 | yes | 0.579 | 39/11/0 |
| q40 − pagerank | 0.114 | [0.012, 0.213] | 0.029 | 0.115 | no | 0.366 | 32/15/3 |
| q40 − pagerank_victim_personalised | 0.399 | [0.320, 0.477] | <0.001 | <0.001 | yes | 0.958 | 45/5/0 |
| q40 − random | 0.506 | [0.439, 0.573] | <0.001 | <0.001 | yes | 0.998 | 49/1/0 |
| q40 − spatial_proximity | 0.056 | [-0.023, 0.133] | 0.103 | 0.206 | no | 0.282 | 25/19/6 |

### Paired comparisons with Q40 (AP)

| comparison | mean diff | 95% CI | p (Wilcoxon) | p (Holm) | sig. @0.05 | rank-biserial r | wins/losses/ties (seeds) |
|---|---|---|---|---|---|---|---|
| q40 − communication_frequency | 0.233 | [0.178, 0.286] | <0.001 | <0.001 | yes | 0.898 | 44/6/0 |
| q40 − degree_centrality | 0.275 | [0.215, 0.329] | <0.001 | <0.001 | yes | 0.904 | 44/6/0 |
| q40 − pagerank | 0.183 | [0.123, 0.240] | <0.001 | <0.001 | yes | 0.771 | 41/9/0 |
| q40 − pagerank_victim_personalised | 0.349 | [0.302, 0.397] | <0.001 | <0.001 | yes | 1.000 | 50/0/0 |
| q40 − random | 0.425 | [0.380, 0.467] | <0.001 | <0.001 | yes | 1.000 | 50/0/0 |
| q40 − spatial_proximity | 0.061 | [0.023, 0.097] | 0.005 | 0.005 | yes | 0.454 | 31/19/0 |

## 4. Conditions: where methods succeed or fail

| method | strong leads: median rank / in top-5 | medium | weak | red herrings in top-5 | nDCG@5 primary case / secondary case |
|---|---|---|---|---|---|
| random | 29 / 11% | 29 / 3% | 33 / 5% | 7 of 149 | 0.035 / 0.085 |
| communication_frequency | 10 / 29% | 12 / 32% | 7 / 41% | 38 of 149 | 0.280 / 0.418 |
| spatial_proximity | 3 / 89% | 5 / 60% | 34 / 14% | 99 of 149 | 0.497 / 0.527 |
| degree_centrality | 13 / 29% | 16 / 23% | 10 / 35% | 15 of 149 | 0.230 / 0.309 |
| pagerank | 7 / 46% | 10 / 35% | 6 / 48% | 18 of 149 | 0.335 / 0.405 |
| pagerank_victim_personalised | 14 / 23% | 20 / 10% | 17 / 8% | 99 of 149 | 0.082 / 0.182 |
| q40 | 2 / 97% | 5 / 52% | 15 / 11% | 122 of 149 | 0.546 / 0.611 |

Strength is the generator's evidence profile for each lead (strong = GPS+CCTV+calls+payment+tie; medium = GPS (and sometimes CCTV)+calls; weak = CCTV+calls for perpetrators). Rank is among all candidates (≈ 46–114).

## 5. Tie sensitivity (mean over all cases)

| method | mean distinct scores per case | MRR pess.–opt. | AP pess.–opt. | nDCG@5 pess.–opt. |
|---|---|---|---|---|
| random | 71.9 | 0.154–0.154 | 0.099–0.099 | 0.047–0.047 |
| communication_frequency | 71.9 | 0.480–0.480 | 0.299–0.299 | 0.349–0.349 |
| spatial_proximity | 12.4 | 0.289–0.946 | 0.318–0.714 | 0.311–0.796 |
| degree_centrality | 10.7 | 0.339–0.510 | 0.206–0.312 | 0.214–0.320 |
| pagerank | 71.9 | 0.551–0.551 | 0.349–0.349 | 0.370–0.370 |
| pagerank_victim_personalised | 71.9 | 0.266–0.266 | 0.183–0.183 | 0.132–0.132 |
| q40 | 9.6 | 0.571–0.762 | 0.482–0.595 | 0.504–0.651 |

Methods with few distinct scores (Q40 is a sum of binary signals; spatial proximity is quantised by the generator's few venue locations) are sensitive to how ties are resolved; the headline numbers use the neutral hash rule and lie inside these bounds.

## 6. Interpretation (written after inspecting the results above)

* **Every incident-aware method beats random by a wide margin** (Q40 vs random: nDCG@5 +0.52, 50/0 seeds, Holm p < 0.001). Random scores ≈ the expected value for a population of ≈ 2–4 relevant among ≈ 46–114 candidates, which sanity-checks the metrics.
* **Q40 has the highest mean on P@1, P@3, MRR, nDCG@5 and AP**, but **spatial proximity alone is close**: the Q40 advantage over spatial is small (nDCG@5 +0.066, Holm p = 0.015; AP +0.061, Holm p = 0.005) and **not significant for MRR** (p_Holm = 0.21), and spatial proximity has the higher P@5 and R@5. The data therefore support "Q40 is at least as good as the best single-signal baseline and modestly better on graded/ranked metrics", not "Q40 is clearly superior". Q40 is significantly better than the communication, degree-centrality and victim-personalised PageRank baselines on nDCG@5 and AP; against plain PageRank it is significant on nDCG@5 and AP but not on MRR after Holm correction.
* **Where Q40 works**: strong leads (median rank 2, 97% in the top five). **Where it fails**: weak leads (the generator's weak perpetrators have only CCTV and calls, so Q40's dominant spatial signal is absent; median rank 15, 11% in the top five) and **red herrings** – 122 of 149 decoys appear in Q40's top five, because Q40 scores presence near the scene and has no notion of contradicting evidence. Spatial proximity behaves the same way (99 of 149). This is exactly the weakness the Phase 4 reliability- and contradiction-aware methods target.
* **Graph baselines beat random (significantly) even though they never look at the incident.** This is most plausibly a generator artefact, not a property of investigations: the storyline builder plants ASSOCIATE relationships around the victim and the perpetrator/accomplices (`backend/synth/storylines.py`), which raises the degree of true leads. The victim-personalised variant, which ranks closeness to the victim, performs worse than plain centrality, which is consistent with that explanation but does not prove it. These baselines should not be read as evidence that graph centrality finds culprits in real cases.
* **Ties matter for Q40 and spatial proximity.** Q40 averages about 10 distinct scores per case (binary signals with fixed weights), so its nDCG@5 ranges from 0.50 (pessimistic ties) to 0.65 (optimistic ties) around the reported 0.578; spatial proximity ranges from 0.31 to 0.80. The ordering Q40 > spatial is therefore **not robust to tie handling**: under pessimistic ties spatial's mean nDCG@5 (0.31) falls well below Q40's (0.50), under optimistic ties it exceeds it (0.80 vs 0.65). Conclusions about these two methods should be treated as provisional until a tie-free score (Phase 4) is evaluated.
* Frozen-Q40 integrity: the adapter reproduces the original frozen baseline ranking on the original seed-2026 dataset (test `test_q40_adapter_reproduces_frozen_baseline_on_original_dataset`), and the SQL module hash equals the frozen hash.

## 7. Limitations of this phase

* Synthetic data, one scenario family (two cases per seed, identical template), 50 seeds: results do not generalise to real investigations.
* Baseline hyper-parameters (equal communication weights, 100 m spatial scale) were fixed a priori and not tuned; other settings could change the baseline ordering.
* Relevance labels are binary-ish (grade 2/3); accomplice grade 2 is a generator design choice.
* The graph baselines are confounded by planted relationships (see §6).
* Statistical tests treat the 50 seeds as independent draws from one generator; they say nothing about other generators.
* Random-baseline variability within a seed is recorded (`*_within_seed_sd` fields) but not used for inference.
