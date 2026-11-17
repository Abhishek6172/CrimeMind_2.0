# Phase 6 Report: Golden-Question Benchmark, Retrieval and LLM-Answer Evaluation

Run ID: `P6-20261102T053155Z-766b7f1` (current). Pre-fix bug-evidence run: `P6-20261101T133558Z-7be8caa`. Provider harness run: `P6PROV-20261101T183235Z-7be8caa`.
Benchmark: 541 questions, sha256 `2ff1dde1cfbd3ace…`, seeds 2026–2045, all synthetic. Answers here come from the **offline template provider only**; no live LLM was run.

## 1. Status

| Component | Status |
|---|---|
| Benchmark build (independent of system code) | EXECUTED |
| Retrieval evaluation (6 variants) | EXECUTED |
| Answer evaluation, offline template provider | EXECUTED |
| Gemini evaluation | NOT RUN |
| Anthropic evaluation | NOT RUN |
| Provider-harness unit tests | PASSED with mocked transport (not a provider experiment) |

No LLM result is reported or implied. Gemini/Anthropic are NOT RUN because their API keys are not set in this environment.

## 2. Retrieval (questions where retrieval applies; seed-level means, bootstrap 95% CI)

| variant | n questions | R@1 | R@5 | MRR | nDCG@5 | coverage@8 |
|---|---|---|---|---|---|---|
| full | 400 | 0.418 [0.408, 0.428] | 0.631 [0.612, 0.651] | 0.817 [0.801, 0.833] | 0.722 [0.709, 0.737] | 0.718 [0.711, 0.726] |
| bm25_only | 400 | 0.405 [0.395, 0.415] | 0.618 [0.599, 0.636] | 0.690 [0.679, 0.701] | 0.649 [0.638, 0.660] | 0.699 [0.693, 0.707] |
| no_entity_boost | 400 | 0.418 [0.408, 0.428] | 0.631 [0.612, 0.650] | 0.817 [0.801, 0.833] | 0.723 [0.709, 0.737] | 0.719 [0.712, 0.726] |
| no_ref_boost | 400 | 0.418 [0.408, 0.428] | 0.631 [0.612, 0.651] | 0.817 [0.801, 0.833] | 0.722 [0.709, 0.737] | 0.718 [0.711, 0.726] |
| no_typo | 400 | 0.405 [0.395, 0.415] | 0.618 [0.600, 0.637] | 0.690 [0.679, 0.701] | 0.649 [0.639, 0.661] | 0.699 [0.693, 0.707] |
| random | 400 | 0.002 [0.001, 0.003] | 0.021 [0.013, 0.031] | 0.094 [0.079, 0.111] | 0.035 [0.028, 0.043] | 0.033 [0.021, 0.047] |

The typo-tolerant matching is where the gain over plain BM25 comes from (`no_typo` equals `bm25_only`); the entity and exact-ref boosts show negligible effect on this benchmark. No new retrieval mechanism was added: nothing here justifies one yet, and the instructions required keeping baseline retrieval.

### By category (full retrieval)

| category | n | R@5 | MRR | coverage@8 |
|---|---|---|---|---|
| contradiction_analysis | 40 | 0.650 [0.500, 0.800] | 0.215 [0.200, 0.231] | 1.000 [1.000, 1.000] |
| entity_identification | 40 | 0.398 [0.378, 0.419] | 1.000 [1.000, 1.000] | 0.582 [0.553, 0.610] |
| evidence_lifecycle | 80 | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| evidence_lookup | 80 | 1.000 [1.000, 1.000] | 0.988 [0.969, 1.000] | 1.000 [1.000, 1.000] |
| investigation_summary | 40 | 0.460 [0.424, 0.505] | 0.723 [0.627, 0.817] | 0.590 [0.560, 0.622] |
| multi_hop | 40 | 0.073 [0.066, 0.080] | 0.503 [0.439, 0.570] | 0.123 [0.113, 0.134] |
| sql_investigation | 40 | 0.118 [0.111, 0.127] | 0.975 [0.938, 1.000] | 0.206 [0.186, 0.224] |
| timeline_reconstruction | 40 | 0.615 [0.566, 0.666] | 0.777 [0.683, 0.869] | 0.681 [0.650, 0.716] |

Weakest: multi-hop, SQL-investigation and entity-identification questions (low coverage@8).

## 3. Answer quality (offline template provider)

| metric | mean [95% CI] |
|---|---|
| valid | 1.000 [1.000, 1.000] |
| hallucination | 0.000 [0.000, 0.000] |
| unsupported_claim_rate | 0.000 [0.000, 0.000] |
| groundedness | 1.000 [1.000, 1.000] |
| context_recall | 0.839 [0.832, 0.845] |
| citation_completeness | 0.839 [0.832, 0.845] |
| citation_correctness | 0.241 [0.235, 0.248] |
| entity_recall | 0.858 [0.853, 0.863] |
| entity_precision | 0.266 [0.257, 0.276] |
| contradiction_awareness | 1.000 [1.000, 1.000] |
| correct_refusal | 0.000 [0.000, 0.000] |
| asserted_facts_on_unanswerable | 1.000 [1.000, 1.000] |
| temporal_consistency | 1.000 [1.000, 1.000] |
| status_reported | 1.000 [1.000, 1.000] |

The template provider restates retrieved records, so high groundedness and zero hallucination are expected and say nothing about an LLM. Its real weakness is that it never refuses: correct-refusal is 0 on unanswerable/missing-information questions, and citation correctness is low because it lists correlation citations wholesale.

## 4. Error attribution (retrieval vs generation)

| error type | questions |
|---|---|
| retrieval | 154 |
| none | 246 |

An answer is attributed to retrieval when required evidence was absent from the supplied context, and to generation when it was present but the answer missed it.

## 5. Application bug found by this evaluation

Before the fix, the answer validator rejected any answer quoting a CONTRADICTION_001 summary that contained a location code (e.g. `L-W06`), because that code was not in the allowed-entity set. Valid-answer rate on all questions: pre-fix 0.819 [0.786, 0.851], post-fix 1.000 [1.000, 1.000]; contradiction category pre-fix 0.475 [0.325, 0.625]. Fix: `backend/app/ai/context.py` allows identifiers appearing in correlation statements, uncertainties and evidence sources; regression test in `backend/tests/test_retrieval.py`. The pre-fix run is preserved as evidence.

## 6. Provider harness

```json
{
 "offline-template": {
  "status": "EXECUTED",
  "note": "deterministic template, not an LLM; evaluated on the full benchmark by research/phase6/run_phase6.py"
 },
 "gemini": {
  "status": "NOT_RUN",
  "reason": "GEMINI_API_KEY is not set"
 },
 "anthropic": {
  "status": "NOT_RUN",
  "reason": "ANTHROPIC_API_KEY is not set"
 }
}
```

## 7. Limitations
- Benchmark annotations come from the synthetic generator's ground truth; questions are templated, not natural user language.
- Template-provider answers cannot stand in for LLM behaviour.
- Metrics are deterministic string/ID checks, not semantic judgements (no LLM judge).
- Seed-level aggregation (n=20 seeds) gives wide intervals in small categories.

## 8. Reproduce
`python -m research.phase6.benchmark.build_benchmark` then `python -m research.phase6.run_phase6` then `python -m research.phase6.provider_eval`; tests: `python -m pytest research/phase6/tests`.
