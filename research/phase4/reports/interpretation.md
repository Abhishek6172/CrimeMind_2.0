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
