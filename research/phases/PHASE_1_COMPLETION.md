# Phase 1 completion report

Scope (brief, Part 21): inspect repository, implementation audit, fix scenario evaluation, freeze original baseline, run regression tests.

| Item | IMPLEMENTED | TESTED | EXPERIMENTALLY VALIDATED | NOT COMPLETED / caveat |
|---|---|---|---|---|
| Repository inspection and audit (`research/IMPLEMENTATION_AUDIT.md`) | yes | n/a | n/a | Coverage is partial; see audit section 1 |
| Event-based lifecycle evaluation (`synth/lifecycle.py`, `synth/evaluate.py`) | yes | yes (11 new tests incl. 2 negative controls) | one case, one seed only | Expected affected findings remain derived from the system's own lineage (circular); fix is Phase 2 |
| Per-step checks: right evidence, valid previous state, permitted transition, applied status, triggering evidence | yes | yes | one seed | |
| Affected-finding precision / recall / F1, unnecessary and missed recomputation rates | yes | yes (manual examples + tampered expectations) | one seed: 1.0 / 1.0 / 1.0 on 6 steps | Trivially perfect because of the circularity above |
| Unrelated findings/evidence unchanged; history retained; recompute keeps old versions; CURRENT findings only on SUPPORTED evidence | yes (`run_with_snapshots`, `history_integrity`) | yes | one seed | |
| Regression tests: intermediate transitions, invalid transitions, repeated transitions, retraction + reinstatement, history preservation, unrelated stability | yes | 60/60 pass | n/a | |
| Bugs B1-B4 fixed | yes | B1, B2 by tests; B3/B4 by use | n/a | O1-O5 open |
| Original baseline frozen and preserved | yes (tag `research-baseline-v1`, `results/baseline/`, overwrite protection, Q40 SQL hash) | yes | Phase 1 rankings identical to frozen baseline | |
| Q40 weights unchanged | yes | hash comparison | n/a | |

## Measured results (CASE-2026-001, seed 2026, offline provider)

- Tests: 60 passed in 25-26 s.
- Event-based lifecycle after all six scripted steps: 6/6 steps applied and passed; transition accuracy 1.0; affected-finding P/R/F1 1.0/1.0/1.0; unnecessary and missed recomputation rates 0.0; history integrity ok.
- Before any step is applied the lifecycle metrics are reported as not available (no vacuous 1.0).
- The old metric reported 4/6 for the same final database state; the difference is the intermediate-state bug (B1), not a behaviour change.
- Q40 rankings before and after the scripted steps are identical to the frozen baseline.

## Remaining limitations carried forward

Circular lifecycle expectations; single storyline; two true leads; ties in Q40; Q40 ignores reliability and contradiction; live-LLM paths untested.

## Next phase (2): multi-seed datasets with generator-emitted, independent ground truth
