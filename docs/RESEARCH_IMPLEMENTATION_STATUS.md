# CrimeMind - research implementation status

> Phase 1 update: the lifecycle evaluator is now event-based (see `research/IMPLEMENTATION_AUDIT.md`, `research/phases/PHASE_1_COMPLETION.md`); the suite has 60 tests. The baseline figures below are the frozen originals and keep the old metric's limitations.

Frozen baseline: git tag `research-baseline-v1` (application code as of 2026-10-31). Captured results: `research/results/baseline/`.
Status key: **A** implemented and covered by automated tests; **B** implemented, not experimentally evaluated; **C** proposed, not implemented.
"Tests" = the 49-test pytest suite (`backend/tests`), all passing at baseline.

## 1. Implemented features

| # | Feature | Status | Source files | How it is (or will be) tested |
|---|---|---|---|---|
| 1 | Multisource evidence store with provenance (`origin_root`), case-scoped composite FKs, append-only history | A | `db/migrations/001-004`, `app/data_entry.py` | `test_integrity.py`, `test_authoring.py`. Experiment: duplicate-source inflation property test (SQL validation) |
| 2 | Authentication, roles, case isolation, uniform 404, least-privilege DB role, hidden `gt` schema | A | `app/security.py`, `app/deps.py`, `db/migrations/006` | `test_security.py`. Experiment: cross-case isolation on every route |
| 3 | Evidence-lifecycle model (EVLM): SUPPORTED/CHALLENGED/INVALIDATED/SUPERSEDED, rules table, impact propagation to findings (RECOMPUTE_REQUIRED) and hypotheses | A (mechanism), B (accuracy) | `db/migrations/002_evlm.sql`, `app/correlation/engine.py` (`recompute_pending`), `synth/scenario.py` | `test_scenarios.py`; baseline run: 6/6 scripted steps flag exactly the expected findings. **Caveat:** see 3 below |
| 4 | 18 SQL modules / 40 registered questions, bind params only, timeouts, per-run audit | A (runs), B (correctness) | `app/sql_modules/*.sql`, `app/registry.py`, `app/sql_engine.py` | Smoke test only (all 40 registered). Experiment: independent Python oracle for each module |
| 5 | Correlation engine, 10 versioned rules (FACT / CORRELATED / INFERRED), common-link analysis | B | `app/correlation/` | Indirect (scenario/insight tests). Rule-level precision/recall not measured |
| 6 | **Q40** lead ranking (hand-weighted, 6 binary/capped signals) | B | `app/sql_modules/18_get_case_evidence_ranking.sql` (variant `overall`), exact config in `research/baseline/q40_config.json` | Baseline: one case, one seed (see section 2) |
| 7 | Evidence reliability scores | B - **not used by Q40** | `evidence_types.reliability_weight` (`db/migrations/001, 004`), trigger in `002_evlm.sql` | Used only by Q34/Q35 and displays. A reliability-aware ranker must be built before RQ2/H2 can be tested |
| 8 | Contradiction detection (`CONTRADICTION_001`, same person at distant places) | B - **not used by Q40** | `app/correlation/engine.py`, `app/insights.py` (movement plausibility, alibi) | Not evaluated |
| 9 | Relationship graph (FACT/CORRELATED/INFERRED edges), network metrics | A (API), B (quality) | `app/graph.py`, `app/insights.py` | `test_ai_graph.py`, `test_insights.py` |
| 10 | Insights: movement plausibility, alibi checker, anomaly flags, money trail, possible meetings | B | `app/insights.py` | `test_insights.py` (behaviour), no accuracy evaluation |
| 11 | Evidence retrieval (RAG): BM25 + named-entity + exact-reference boost, typo tolerance, case-scoped | A (behaviour), B (quality) | `app/retrieval.py`, `app/ai/context.py`, `app/routers/cases.py` (`evidence-search`) | `test_retrieval.py`. Self-supervised recall@5 = 1.000 on 287 template queries (easy; not a research result). No human-written question set yet |
| 12 | AI layer: controlled context, offline template provider, Anthropic and Gemini providers, output validator | A (with mocks), B (quality) | `app/ai/` | `test_ai_graph.py`, `test_retrieval.py`. **Never run against a real LLM.** Validator is regex/rule based; its misses are unmeasured |
| 13 | Data authoring, bulk import with dry run, notes, reports, audit log | A | `app/data_entry.py`, `app/reports.py`, `app/audit.py`, `routers/` | `test_authoring.py`, `test_ai_graph.py` |
| 14 | React UI (dashboard, evidence + search, graph, map, AI panel, reports, audit) | B | `frontend/src/` | No automated UI tests |
| 15 | Synthetic generator + isolated ground truth + scripted evolution scenarios | A (determinism), B (coverage) | `backend/synth/` | See `docs/SYNTHETIC_GENERATOR_AND_GROUND_TRUTH.md` |

## 2. Preliminary baseline results (not general performance claims)

One case (CASE-2026-001), generator seed 2026, offline provider. Source: `research/results/baseline/`.

| Measure | Value |
|---|---|
| Tests | 49 passed |
| Q40 top 3 before scenarios | P-002 (0.85), P-004 (0.70, red herring), P-003 (0.55) |
| Precision@3 / Recall@3 | 0.667 / 1.0 (2 expected leads) |
| Red herring rank | 2 before scenarios; unranked after the GPS-17 trace is invalidated |
| Q40 after all 6 scripted steps | P-002, P-003, then ties at 0.25 (P-011, P-012, ...) |
| Findings flagged vs expected, per step | 6/6 steps exact match (see caveat 3) |
| Stale CURRENT findings | 0 |

## 3. Known limits that affect the research design

1. **One storyline.** Seeds change background persons and routines only. The incident, victim, perpetrator (P-002), accomplice (P-003) and red herring (P-004) are scripted and identical in every seed, so multi-seed runs measure robustness to background noise, not generalisation to different crimes. Varying the storyline needs generator work (Milestone 2).
2. **Only 2 relevant leads.** Precision/recall at K moves in large steps (0.33-0.5 per swap). Ties at 0.25 beyond rank 3 are broken alphabetically by entity ref, which can silently favour or hurt a method.
3. **Possible circularity in the evolution test.** `gt.scenario_events.expected_affected_finding_keys` is derived in `synth/seed.py` from the `correlation_evidence` table, which is the same dependency lineage EVLM uses to propagate impact. The 6/6 match therefore shows internal consistency, not independent correctness. RQ3 needs expectations defined from the scenario design, not from the system's own links.
4. **Q40 does not use reliability or contradiction.** The "evidence" signal is `min(1, independent_sources/3)` with weight 0.15; `reliability_score` is ignored. The roadmap's ablation "Q40 without reliability" does not apply to the current Q40; the ablatable components are spatial, temporal, communication, financial, relational and evidence-sources.
5. **No real-LLM evaluation.** Anthropic/Gemini paths are exercised with mocked HTTP only.
6. **Weights are hand-set**, not fitted; any tuning on the evaluation data would invalidate the comparison.

## 4. Proposed, not implemented (C)

| Item | Needed for |
|---|---|
| Storyline-varying generator + per-seed ground truth export (`research/datasets`, `research/ground_truth`) | RQ1, RQ2 |
| Baselines: random, communication frequency, incident proximity, degree/PageRank | RQ1 |
| Metrics module: P/R/F1@K, MRR, nDCG@K, mean/SD/95% CI | all ranking RQs |
| Ablation harness over Q40 signals | RQ1 |
| Reliability-aware and contradiction-aware Q40 variant (Q40-R) | RQ2 |
| Robustness scenarios A-D (normal, convincing red herring, contradictions, noise) | RQ2 |
| Independent evolution expectations + affected-finding precision/recall, ranking-update check | RQ3 |
| Golden question set (30-50), citation precision/recall, hallucinated-ID rate, provider comparison, adversarial validator tests | RQ4 |
| Independent Python oracles for 18 SQL modules + property tests | correctness |
| Scaled datasets (1x-100x) and timing/memory harness | RQ5 |
