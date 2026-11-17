# Phases 3–8 final completion report

Status taxonomy: **EXECUTED** (code ran and produced the stored result), **IMPLEMENTED_NOT_EXECUTED** (code exists, tested only with mocks or not run), **NOT RUN / BLOCKED** (needs something unavailable here), **NOT IMPLEMENTED**.
Unified run: `P8-20261102T052552Z-766b7f1` (`python -m research.run_all --phases 3 4 5 6 7 8`, status COMPLETED, every step EXECUTED). Metric tables of Phases 3 and 4 reproduced the earlier runs exactly.

| Phase | Deliverable | Status | Run ID | Report |
|---|---|---|---|---|
| 3 | Common interface, 5 baselines + frozen Q40 adapter, metrics, statistics | EXECUTED | P3-20261102T052553Z-766b7f1 | `research/phase3/PHASE_3_REPORT.md` |
| 4 | Q40-R, RAEER definition and implementation, contradiction handling, stratified results | EXECUTED | P4-20261102T052715Z-766b7f1 | `research/phase4/PHASE_4_REPORT.md` |
| 5 | Ablations, 13 perturbation types, sensitivity, evidence evolution, stability metrics | EXECUTED | P5-20261102T052840Z-766b7f1 | `research/phase5/PHASE_5_REPORT.md` |
| 6 | 541-question benchmark, retrieval + answer metrics, error attribution | EXECUTED (offline template provider) | P6-20261102T053155Z-766b7f1 | `research/phase6/PHASE_6_REPORT.md` |
| 6 | Live LLM evaluation (Gemini, Anthropic) | **NOT RUN** – no API credentials; harness IMPLEMENTED, tested with mocked transport only | – | same |
| 7 | SQL docs, oracles (M1–M17, M18.reliability, Q40), DB/security/concurrency checks, scalability | EXECUTED | P7-20261102T053251Z-766b7f1 | `research/phase7/PHASE_7_REPORT.md` |
| 7 | Oracles for M18 evidence_strength / connected_both / multi_domain | NOT IMPLEMENTED | – | – |
| 8 | Unified runner, aggregation, 9 figures, final report, guides, manifests | EXECUTED | P8-… | `research/FINAL_RESEARCH_REPORT.md` |

## Tests (pytest, this environment, Linux, PostgreSQL 16.15)
Backend: 73 passed, 0 failed, 0 skipped. Research: 87 passed, 0 failed, 0 skipped (phase3 26, phase4 11, phase5 18, phase6 15, phase7 11, phase8 6). Frontend: production build succeeds (no frontend unit tests exist). Mock-transport provider tests are code-path tests and are not counted as provider results. Not run: Windows execution; live providers.

## Defects found by the new experiments and fixed
Answer-validator rejection of quoted location codes; M8 `around` NULL ordering (module v1.1); NUL-byte identifier DataError. Each has a regression test and preserved before/after evidence.

## Files
Since the Phase 2 commit (cebe866): 231 added and 12 modified files (112 added excluding stored result files). Modified application files: `retrieval.py`, `ai/context.py`, `ai/providers.py`, `config.py`, `sql_engine.py`, SQL module 08, `synth/scenario.py`, three test files.

## Headline numbers and caveats
See `research/FINAL_RESEARCH_REPORT.md`. All results are synthetic; RAEER's advantage over Q40 is coupled to generator structure and must not be read as real-world accuracy. Phase 5 later-transition flagging recall is 0 (cause not investigated).

## Preserved
Frozen Q40 SQL and baseline bundle, Phase 1/2 results, datasets and manifests, application database (never touched; only disposable `cm_*` databases used), pre-fix evidence runs.
