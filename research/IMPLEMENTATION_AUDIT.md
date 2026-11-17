# CrimeMind implementation audit (research Phase 1)

State described: git `research-baseline-v1` (9f05c41) plus the Phase 1 changes listed in section 8. Frozen baseline evidence in
`research/results/baseline/` was not modified (the capture script now refuses to overwrite it). Statements below were checked by
reading code or running it; anything not inspected is listed in section 1.

## 1. Inspection coverage (honest)

| Read in full | Read in part | Not read in detail |
|---|---|---|
| `README.md`, `synth/evaluate.py` (original), `synth/scenario.py`, `synth/seed.py`, `app/correlation/rules.py`, `app/retrieval.py`, `app/ai/{context,validator,service,providers}.py`, Q40 SQL (`18_get_case_evidence_ranking.sql`), `db/migrations/002_evlm.sql`, `tests/{conftest,test_scenarios,test_ai_graph}.py`, `research/baseline/*` | `synth/generator.py` (outline, RNG usage, header), `app/correlation/engine.py` (`run_and_persist`, `recompute_pending`, helpers), `app/insights.py` (function outline only), `db/migrations/001, 004, 006`, `frontend/` (Evidence page, API client) | `engine.compute()` rule bodies, `insights.py` internals, `graph.py`, `sql_engine.py`, the other 17 SQL modules, other test files, remaining frontend pages |

Consequence: claims about rule correctness, insight accuracy and the other SQL modules are **not** audited here; they are Phase 6 (SQL oracles).

## 2. What works (verified by running)

- 60 tests pass (49 original + 11 added in Phase 1), 26 s on PostgreSQL 16.15 / Python 3.13.
- Generator is deterministic per seed (identical evidence hash for two runs of seed 2026; seed 7 differs).
- Ground truth schema `gt` is unreadable by the application role (`permission denied for schema gt`).
- EVLM: transitions follow the rules table; invalid transitions, repeated transitions, role/justification violations and edits/deletes of history are rejected (tests).
- Q40 SQL file hash is unchanged since the baseline (`01bea117...`); Phase 1 rankings equal the frozen baseline rankings before and after the scripted steps.

## 3. Bugs

| ID | Finding | Status |
|---|---|---|
| B1 | `evaluate.py` compared each scripted step's expected status with the evidence's **final** status, so intermediate states (CHALLENGED before INVALIDATED / SUPPORTED) were scored wrong. The frozen baseline reports `scenario_steps_at_expected_status = 4` of 6 after all six steps were correctly applied | Fixed: event-based evaluation (`synth/lifecycle.py`). Old figures are kept unmodified in `results/baseline/` |
| B2 | `scenario.pending()` treated a step as done if **any** matching event existed, so a repeated transition (CHALLENGED -> SUPPORTED -> CHALLENGED) was skipped | Fixed: occurrence-aware; regression test `test_pending_counts_occurrences_of_identical_script_steps` |
| B3 | `evaluate.ranked_q40` returned an empty ranking silently if the result column was not found, which would score as precision 0 | Fixed: raises |
| B4 | `scenario.py` command line always used database `crimemind` | Fixed: `CM_DB` environment variable |
| O1 | Incident event `EVT-001` is hard-coded in the evaluator and capture script | Open (Phase 2: read from ground truth) |
| O2 | `scenario.apply_step` stamps arriving evidence with `now()`, so those timestamps differ between runs | Open; affects only arriving scenario evidence timestamps, not rankings |
| O3 | `requirements.txt` uses `>=` with no lock file; the baseline manifest records the versions actually used | Open |
| O4 | FastAPI `on_event` deprecation warnings (4 per run) | Open, cosmetic |
| O5 | Q40's spatial signal has no distance threshold (same location entity + 60-minute window) whereas rule `INCIDENT_PROXIMITY_001` uses 150 m + 60 minutes. Two definitions of "near the incident" | Open; relevant to the proximity baseline |

## 4. Incomplete functionality (relative to the research plan)

No baselines, metrics module, RAEER, ablation, robustness, AI/RAG evaluation, SQL oracles, scale generator, or report generator exist yet.
Evidence **reliability** and **contradiction** signals exist in the database but are unused by Q40 (`research/baseline/q40_config.json`).

## 5. Duplicate implementations

Q40 ranking retrieval exists in three places: `synth/lifecycle.ranked_q40` (used by `evaluate.py` now), `research/baseline/capture_baseline.full_ranking` (needs scores), and the application's query runner. Acceptable for now; Phase 3 consolidates under `research/baselines/q40_baseline.py`.

## 6. Research-methodology weaknesses

1. **One storyline.** Seeds vary background persons/routines only; perpetrator, accomplice, red herring and incident are scripted identically. Multi-seed statistics would measure noise robustness, not generalisation.
2. **Two relevant leads** per case: precision/recall move in steps of 0.33-0.5.
3. **Tied scores** (many persons at exactly 0.25) are broken alphabetically by entity ref.
4. **Circular lifecycle expectations.** `expected_affected_finding_keys` is generated in `seed.py` from `correlation_evidence`, the same lineage the EVLM trigger uses (`finding_evidence_links`). Event-based scoring now removes the final-state bug but **cannot** remove this circularity; 6/6 exact matches mean internal consistency. Phase 2 must emit expectations from the generator's own plan.
5. Ground truth lacks per-lead supporting/contradicting evidence lists and graded relevance.
6. Q40 weights are hand-set; no train/validation/test split exists, so any tuning must use new seeds.

## 7. Reproducibility controls

Present: seeded RNG, isolated `gt` schema, scripted scenarios applied through `change_validity()`, baseline manifest (versions, SQL hash, commit, seed), refusal to overwrite captured runs.
Missing: pinned dependencies (O3), a dataset manifest per seed, configuration file for generator parameters, experiment runner with resume/duplicate protection (Phase 8 of the brief: `research.run_all`).

## 8. Phase 1 changes

Created: `backend/synth/lifecycle.py`, `backend/tests/test_lifecycle_eval.py`, `research/IMPLEMENTATION_AUDIT.md`, `research/phases/PHASE_1_COMPLETION.md`, `research/results/phase1/`.
Modified: `backend/synth/evaluate.py` (event-based lifecycle block; unscored-step handling), `backend/synth/scenario.py` (B2, B4), `research/baseline/capture_baseline.py` (`--out`, `--force`, overwrite protection).
Not modified: application code under `backend/app/`, SQL modules, migrations, frontend, `research/results/baseline/`.
