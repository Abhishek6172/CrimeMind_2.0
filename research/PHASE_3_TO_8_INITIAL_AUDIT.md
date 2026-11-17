# Phase 3–8 initial audit (written at the start of Phase 3 work, state at commit cebe866 / tag `research-baseline-v1`)

## Existed and was reused unchanged
* Frozen Q40 SQL (M18 `overall`), baseline bundle `research/results/baseline/`, Phase 1 evaluator and event-based lifecycle evaluation, Phase 2 generator, 50 hash-manifested datasets and independent ground truth (`research/ground_truth/`, schema `gt`).
* Application: 18 SQL modules, registry of 40 questions, EVLM (append-only validity events, `change_validity()`), audit log, case isolation, retrieval (BM25 + boosts), AI provider layer with validator, FastAPI routers, React frontend; 72 backend tests.

## Incomplete or missing at the start
* No common ranking interface, no baselines other than Q40, no ranking metrics beyond the lifecycle evaluator, no statistics (CI, paired tests, correction).
* No reliability-aware or evidence-evolution-aware method; no ablation/robustness/sensitivity code.
* No golden-question benchmark, no retrieval/answer metrics, no provider harness (timeouts, retries, token/latency recording).
* SQL modules had no independent verification, no scalability data, no research-grade security tests.
* No unified runner, no result aggregation, no figures, no final report, no reproducibility manifest across phases.

## Broken or risky items found
* `generate_datasets.py` used `fcntl` (not Windows-compatible) → replaced by a portable lock.
* Ground-truth scenario IDs collided between the two cases of a seed (PK on `gt.scenario_events`) → suffixed with the case reference.
* A secondary-case actor lacked access needed by scenario steps → access added in the research seed.
* Later discovered by the new experiments (all fixed, with regression tests): answer validator rejecting valid quoted location codes; M8 `around` NULL ordering; NUL-byte identifier DataError.

## Reusable
Workspace builder (`SeedWorkspace`), `CaseView` abstraction, run-manifest helper, report utilities, scenario runner through `change_validity()`, existing retrieval/provider code.

## Needed modification of existing code (minimal, behaviour-preserving by default)
`retrieval.search_evidence` ablation flags (defaults unchanged); provider HTTP helper with bounded retries and call metadata; `ai/context.py` allowed-identifier set; `sql_engine` identifier checks; M8 module v1.1; scenario observation refs for suffixed scenario IDs.

## New components
`research/common`, `research/phase3`–`phase8`, `research/run_all.py`, tests for each phase, docs under `research/docs/`.
