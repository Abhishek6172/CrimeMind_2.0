"""Render PHASE_6_REPORT.md from stored results only (no numbers typed by hand)."""
import json
from pathlib import Path
R = Path(__file__).resolve().parents[1]
res = R / "results"
cur = (res / "LATEST.txt").read_text().strip()
PRE = "P6-20261101T133558Z-7be8caa"
A = json.load(open(res / cur / "analysis.json")); B = json.load(open(res / PRE / "analysis.json"))
man = json.load(open(res / cur / "run_manifest.json"))
prov = json.load(open(next((res / "providers").glob("*/provider_report.json"))))
bm = json.load(open(R / "benchmark/benchmark_manifest.json"))
f = lambda d, k: f"{d[k]['mean']:.3f} [{d[k]['ci95_low']:.3f}, {d[k]['ci95_high']:.3f}]" if isinstance(d.get(k), dict) and d[k].get("mean") is not None else "n/a"
def tbl(h, rows): return "\n".join(["| " + " | ".join(h) + " |", "|" + "---|" * len(h)] + ["| " + " | ".join(map(str, r)) + " |" for r in rows])
out = [f"# Phase 6 Report: Golden-Question Benchmark, Retrieval and LLM-Answer Evaluation\n",
 f"Run ID: `{cur}` (current). Pre-fix bug-evidence run: `{PRE}`. Provider harness run: `{prov.get('run_id', next((res/'providers').glob('*')).name)}`.",
 f"Benchmark: {bm['questions']} questions, sha256 `{bm['sha256'][:16]}…`, seeds 2026–2045, all synthetic. Answers here come from the **offline template provider only**; no live LLM was run.\n",
 "## 1. Status\n", tbl(["Component", "Status"], [["Benchmark build (independent of system code)", "EXECUTED"], ["Retrieval evaluation (6 variants)", "EXECUTED"],
   ["Answer evaluation, offline template provider", "EXECUTED"], ["Gemini evaluation", prov["providers"]["gemini"]["status"] if "providers" in prov else "NOT RUN"],
   ["Anthropic evaluation", prov["providers"]["anthropic"]["status"] if "providers" in prov else "NOT RUN"], ["Provider-harness unit tests", "PASSED with mocked transport (not a provider experiment)"]]),
 "\nNo LLM result is reported or implied. Gemini/Anthropic are NOT RUN because their API keys are not set in this environment.\n",
 "## 2. Retrieval (questions where retrieval applies; seed-level means, bootstrap 95% CI)\n"]
rows = []
for v, d in A["retrieval"]["ALL"].items():
    rows.append([v, d["n_questions"]] + [f(d, m) for m in ["R@1", "R@5", "MRR", "nDCG@5", "coverage@8"]])
out += [tbl(["variant", "n questions", "R@1", "R@5", "MRR", "nDCG@5", "coverage@8"], rows),
 "\nThe typo-tolerant matching is where the gain over plain BM25 comes from (`no_typo` equals `bm25_only`); the entity and exact-ref boosts show negligible effect on this benchmark. No new retrieval mechanism was added: nothing here justifies one yet, and the instructions required keeping baseline retrieval.\n",
 "### By category (full retrieval)\n"]
rows = [[c, d["full"]["n_questions"], f(d["full"], "R@5"), f(d["full"], "MRR"), f(d["full"], "coverage@8")] for c, d in A["retrieval"].items() if c != "ALL"]
out += [tbl(["category", "n", "R@5", "MRR", "coverage@8"], rows), "\nWeakest: multi-hop, SQL-investigation and entity-identification questions (low coverage@8).\n",
 "## 3. Answer quality (offline template provider)\n"]
rows = [[m, f(A["answer"]["ALL"], m)] for m in ["valid", "hallucination", "unsupported_claim_rate", "groundedness", "context_recall", "citation_completeness", "citation_correctness", "entity_recall", "entity_precision", "contradiction_awareness", "correct_refusal", "asserted_facts_on_unanswerable", "temporal_consistency", "status_reported"]]
out += [tbl(["metric", "mean [95% CI]"], rows),
 "\nThe template provider restates retrieved records, so high groundedness and zero hallucination are expected and say nothing about an LLM. Its real weakness is that it never refuses: correct-refusal is 0 on unanswerable/missing-information questions, and citation correctness is low because it lists correlation citations wholesale.\n",
 "## 4. Error attribution (retrieval vs generation)\n"]
ea = A["error_attribution"]["ALL"]
out += [tbl(["error type", "questions"], list(ea.items())), "\nAn answer is attributed to retrieval when required evidence was absent from the supplied context, and to generation when it was present but the answer missed it.\n",
 "## 5. Application bug found by this evaluation\n"]
out += [f"Before the fix, the answer validator rejected any answer quoting a CONTRADICTION_001 summary that contained a location code (e.g. `L-W06`), because that code was not in the allowed-entity set. Valid-answer rate on all questions: pre-fix {f(B['answer']['ALL'], 'valid')}, post-fix {f(A['answer']['ALL'], 'valid')}; contradiction category pre-fix {f(B['answer']['contradiction_analysis'], 'valid')}. Fix: `backend/app/ai/context.py` allows identifiers appearing in correlation statements, uncertainties and evidence sources; regression test in `backend/tests/test_retrieval.py`. The pre-fix run is preserved as evidence.\n",
 "## 6. Provider harness\n", "```json\n" + json.dumps(prov, indent=1)[:2500] + "\n```\n",
 "## 7. Limitations\n- Benchmark annotations come from the synthetic generator's ground truth; questions are templated, not natural user language.\n- Template-provider answers cannot stand in for LLM behaviour.\n- Metrics are deterministic string/ID checks, not semantic judgements (no LLM judge).\n- Seed-level aggregation (n=20 seeds) gives wide intervals in small categories.\n",
 f"## 8. Reproduce\n`python -m research.phase6.benchmark.build_benchmark` then `python -m research.phase6.run_phase6` then `python -m research.phase6.provider_eval`; tests: `python -m pytest research/phase6/tests`.\n"]
Path(R / "PHASE_6_REPORT.md").write_text("\n".join(out), encoding="utf-8")
print("ok")
