# RAEER: Reliability-Aware Evidence Evolution Ranking — operational definition

## Provenance of the name and the ambiguity
The name and the six factors it must investigate (evidence reliability, temporal consistency, relational support, source
independence, contradictory evidence, evidence lifecycle status) come from the project's earlier implementation specification
(Part 7 of the master prompt). **No mathematical definition existed anywhere in the repository.** Everything below is therefore
a *proposed operational definition made for this study*, not a previously established method. It is an experimental heuristic.

## Distinction from Q40 and Q40-R
| | Q40 (frozen) | Q40-R | RAEER |
|---|---|---|---|
| Signals | 5 binary + evidence count | same 6, binary → max record trust | 6 graded features |
| Reliability | not used | per-record trust ρ (max within a signal) | ρ per record, combined by noisy-OR over *independent origins* |
| Scene definition | same location entity | same | any observation within R = 150 m (INCIDENT_PROXIMITY_001 threshold) |
| Time | window membership | window membership | exponential temporal consistency t = exp(−gap/τ) |
| Relations | with victim only | with victim only | with victim **or scene persons**, weighted by relationship strength |
| Contradiction | none | none | CONTRADICTION_001-style location conflicts lower the spatial feature (≤ γ) |
| Corroboration | #origins/3 | Σ ρ per origin / 3 | strength of independent supporting domains / 3 |
| Lifecycle | SUPPORTED only | status factor φ | status factor φ |

Same weights as Q40 are used on purpose (no tuning), so differences come from feature definitions.

## Definitions
Notation: candidate p (person other than the victim); incident time T at location x*; window W = ±60 min; R = 150 m;
τ = 30 min; D = 1000 m; γ = 0.5.

* Record trust: ρ(r) = rel(e(r)) · φ(status(e(r))), rel from the evidence table (missing → 0.5), φ: SUPPORTED 1, CHALLENGED 0.5, INVALIDATED/SUPERSEDED 0. Invalidated evidence therefore never counts as current support, but stays in the database (historical traceability is untouched).
* Origin o(r): provenance `origin_root` (else `source`). Within an origin only the **maximum** value counts, so duplicated records of one source are not independent corroboration.
* Temporal consistency: t(r) = exp(−g/τ), g = 0 if T lies inside the record's interval, else the distance from T to the nearest interval end.
* noisy-OR over origins: N(v₁…vₘ) = 1 − Π(1 − vᵢ) ∈ [0,1].

Features (all in [0, 1]; missing evidence ⇒ 0, never an error):

1. f_spatial = N over origins of max{ρ·t : obs of p within W and ≤ R metres of x*}
2. f_temporal = N over origins of max{ρ·t : any activity of p (observation start, communication, transaction) within W}
3. f_comm = N over origins of max{ρ : communication of p with the victim or with a person who has f_spatial > 0}
4. f_fin = same for transactions
5. f_rel = N over origins of max{ρ·strength : non-OWNS/USES relationship with the victim or a scene person}
6. f_corr = min(1, (f_spatial + f_comm + f_fin + f_rel)/3)
7. Contradiction C(p) = max over pairs (A, B) of p's records, A at the scene within W, B > D metres from A's location, overlapping in time, **different origin**, of ρ(B)/(ρ(A)+ρ(B)); 0 if none. f_spatial' = f_spatial · (1 − γ·C).

Score: **RAEER(p) = 0.35 f_spatial' + 0.10 f_temporal + 0.15 f_comm + 0.15 f_fin + 0.10 f_rel + 0.15 f_corr ∈ [0,1]**.
Ranking: descending score; ties by the common hash rule (research/phase3). The score is not a probability.

Contradiction semantics: a contradiction reduces the weight of the contradicted claim by at most γ = 50 %; it is never treated as proof of innocence or guilt. Only structured location conflicts are detected; contradictory witness statements are text and are **not** processed (limitation).

Complexity: O(|obs| + |comms| + |txns| + |rels| + Σₚ |scene obs of p|·|obs of p|) per case, i.e. effectively linear in the records for these datasets.

## Q40-R
score_R(p) = Σ_s w_s σ_s(p) + w_e·min(1, Σ_o max ρ / 3), σ_s = max over supporting records of ρ (0 if none), identical weights/window/population to Q40; with reliability disabled and all evidence SUPPORTED it equals Q40 exactly (unit-tested against the frozen SQL).

## Parameter provenance (no tuning)
R, D from existing correlation rules; τ = W/2; γ = 0.5 as the midpoint "contradiction can halve but not erase"; weights = Q40's; ρ default 0.5 = neutral midpoint. These were fixed before any evaluation (`configs/phase4_config.json`, `frozen_before_evaluation: true`). Sensitivity to γ, τ, R, D and the weights is measured in Phase 5.

## Known assumptions / limitations
* Reliability scores are per-evidence-type heuristic constants, not calibrated probabilities.
* The alibi/contradiction mechanism relies on structured location records from a source with a different origin; in these synthetic data alibis are generated that way, so RAEER's contradiction rule is **coupled to the generator's design** (a real investigation may not provide such records).
* A scene person must be observed within R metres; evidence lacking location is not used spatially.
