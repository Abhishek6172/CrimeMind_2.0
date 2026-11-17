"""Phase 6 tests. Tests whose names start with test_mocked_ use httpx.MockTransport: they verify the harness code path only and are
NOT evidence that any live provider was evaluated."""
import ast
import hashlib
import json
from pathlib import Path

import httpx
import pytest

from research.phase6.metrics import answer_metrics, retrieval_metrics

ROOT = Path(__file__).resolve().parents[3]
BENCH = ROOT / "research/phase6/benchmark/golden_questions.jsonl"


def test_retrieval_metrics_hand_computed():
    m = retrieval_metrics(["a", "x", "b", "y", "z"], {"a", "b", "c"})
    assert m["P@1"] == 1 and m["R@1"] == pytest.approx(1 / 3) and m["P@3"] == pytest.approx(2 / 3) and m["R@3"] == pytest.approx(2 / 3)
    assert m["MRR"] == 1.0 and m["coverage@8"] == pytest.approx(2 / 3)
    import math
    dcg = 1 + 1 / math.log2(4)
    idcg = 1 + 1 / math.log2(3) + 1 / math.log2(4)
    assert m["nDCG@5"] == pytest.approx(dcg / idcg)
    assert retrieval_metrics(["x", "y"], {"a"})["MRR"] == 0.0


def test_source_relevance_uses_entity_links():
    m = retrieval_metrics(["a", "b"], {"a"}, {"a": ["P-1"], "b": ["P-2"]}, ["P-1"])
    assert m["source_relevance@5"] == 0.5


Q = {"supporting_evidence": ["E-1", "E-2"], "expected_entities": ["P-1"], "evaluation_criteria": {}}


def test_answer_metrics_citation_and_error_attribution():
    out = {"summary": "s", "uncertainties": [], "findings": [{"statement": "Evidence E-1 about Asha", "classification": "RECORDED FACT", "evidence_ids": ["E-1", "E-9"], "correlation_ids": []}]}
    m = answer_metrics(Q, out, {"E-1", "E-2", "E-9"}, [], {"P-1": "Asha"})
    assert m["citation_completeness"] == 0.5 and m["citation_correctness"] == 0.5 and m["entity_recall"] == 1.0
    assert m["error_type"] == "generation" and m["context_recall"] == 1.0
    m2 = answer_metrics(Q, out, {"E-1", "E-9"}, [], {})
    assert m2["error_type"] == "retrieval" and m2["entity_recall"] == 0.0          # name not in the supplied map, id absent from text


def test_hallucination_and_unsupported_claims_detected():
    out = {"summary": "s", "uncertainties": [], "findings": [{"statement": "x", "classification": "RECORDED FACT", "evidence_ids": [], "correlation_ids": []}]}
    m = answer_metrics(Q, out, set(), ["finding 1: statement mentions identifier 'P-9' that is not in the context"], {})
    assert m["hallucination"] == 1.0 and m["unsupported_claim_rate"] == 1.0 and m["valid"] == 0.0


def test_refusal_detection_is_strict():
    q = {**Q, "supporting_evidence": [], "expected_entities": [], "evaluation_criteria": {"must_refuse": True}}
    bad = {"summary": "No language model was used. Records were recorded.", "uncertainties": [], "findings": [{"statement": "Evidence E-3 records: x", "classification": "RECORDED FACT", "evidence_ids": ["E-3"], "correlation_ids": []}]}
    good = {"summary": "No supported records matched this request.", "uncertainties": [], "findings": []}
    assert answer_metrics(q, bad, {"E-3"}, [], {})["correct_refusal"] == 0.0
    assert answer_metrics(q, good, set(), [], {})["correct_refusal"] == 1.0


def test_temporal_consistency_rules():
    q = {**Q, "supporting_evidence": ["E-1"], "expected_entities": [], "expected_status": "CHALLENGED"}
    cur = {"summary": "s", "uncertainties": [], "findings": [{"statement": "E-1 is fine", "classification": "RECORDED FACT", "evidence_ids": ["E-1"], "correlation_ids": []}]}
    ok = {"summary": "s", "uncertainties": [], "findings": [{"statement": "E-1 is currently CHALLENGED", "classification": "UNCERTAIN", "evidence_ids": ["E-1"], "correlation_ids": []}]}
    assert answer_metrics(q, cur, {"E-1"}, [], {})["temporal_consistency"] == 0.0
    m = answer_metrics(q, ok, {"E-1"}, [], {})
    assert m["temporal_consistency"] == 1.0 and m["status_reported"] == 1.0


# ---------- benchmark ----------
def _qs():
    return [json.loads(l) for l in BENCH.read_text().splitlines()]


def test_benchmark_schema_and_categories():
    qs = _qs()
    need = {"question_id", "dataset_id", "case_id", "question", "expected_answer", "supporting_evidence", "expected_source_records", "answerability", "evaluation_criteria", "category"}
    assert all(need <= set(q) for q in qs)
    assert len({q["question_id"] for q in qs}) == len(qs)
    cats = {q["category"] for q in qs}
    assert cats >= {"entity_identification", "timeline_reconstruction", "relationship_analysis", "evidence_lookup", "contradiction_analysis", "missing_information",
                    "investigation_summary", "evidence_lifecycle", "sql_investigation", "multi_hop", "unanswerable"}
    assert {"answerable", "answerable_negative", "unanswerable"} <= {q["answerability"] for q in qs}


def test_benchmark_supporting_evidence_exists_in_dataset():
    import csv, gzip
    for seed in (2026, 2031):
        refs = {r["ref"] for r in csv.DictReader(gzip.open(ROOT / f"research/datasets/seed_{seed}/evidence.csv.gz", "rt"))}
        for q in _qs():
            if q["dataset_id"] == f"seed_{seed}" and q["state"] == "initial":
                assert set(q["supporting_evidence"]) <= refs, q["question_id"]


def test_benchmark_is_reproducible_and_independent_of_system_code():
    man = json.load(open(BENCH.parent / "benchmark_manifest.json"))
    assert hashlib.sha256(BENCH.read_bytes()).hexdigest() == man["sha256"]
    tree = ast.parse((BENCH.parent / "build_benchmark.py").read_text())
    mods = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(m.startswith(("app", "synth", "research.phase3", "research.phase4", "research.common.workspace")) for m in mods)


def test_unanswerable_questions_have_no_evidence_annotations():
    assert all(not q["supporting_evidence"] for q in _qs() if q["answerability"] != "answerable")


# ---------- provider harness (MOCKED transport) ----------
def _gemini(transport):
    from app.ai.providers import GeminiProvider
    return GeminiProvider("test-key-not-real", "gemini-test", transport)


def test_mocked_retry_on_rate_limit_then_success_records_usage(monkeypatch):
    from app import config
    monkeypatch.setattr(config, "AI_RETRY_BASE_WAIT", 0.0)
    calls = []

    def handler(req):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, json={})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"summary":"ok","findings":[],"uncertainties":[],"confidence":null}'}]}}],
                                         "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 5}})
    p = _gemini(httpx.MockTransport(handler))
    out = p.generate({"case_reference": "C"}, "q")
    assert out["summary"] == "ok" and p.last_call["attempts"] == 2 and p.last_call["errors"] == ["HTTP 429"] and p.last_call["usage"]["promptTokenCount"] == 11


def test_mocked_client_error_is_not_retried_and_key_not_recorded(monkeypatch):
    from app import config
    from app.ai.providers import ProviderUnavailable
    monkeypatch.setattr(config, "AI_RETRY_BASE_WAIT", 0.0)
    calls = []
    p = _gemini(httpx.MockTransport(lambda req: (calls.append(1), httpx.Response(400, json={}))[1]))
    with pytest.raises(ProviderUnavailable):
        p.generate({}, "q")
    assert len(calls) == 1 and "test-key-not-real" not in json.dumps(p.last_call)


def test_mocked_persistent_server_error_gives_up_after_bounded_retries(monkeypatch):
    from app import config
    from app.ai.providers import ProviderUnavailable
    monkeypatch.setattr(config, "AI_RETRY_BASE_WAIT", 0.0)
    monkeypatch.setattr(config, "AI_MAX_RETRIES", 2)
    calls = []
    p = _gemini(httpx.MockTransport(lambda req: (calls.append(1), httpx.Response(503, json={}))[1]))
    with pytest.raises(ProviderUnavailable):
        p.generate({}, "q")
    assert len(calls) == 3


def test_mocked_timeout_is_retried_then_reported(monkeypatch):
    from app import config
    from app.ai.providers import ProviderUnavailable
    monkeypatch.setattr(config, "AI_RETRY_BASE_WAIT", 0.0)
    calls = []

    def h(req):
        calls.append(1)
        raise httpx.ReadTimeout("slow", request=req)
    p = _gemini(httpx.MockTransport(h))
    with pytest.raises(ProviderUnavailable):
        p.generate({}, "q")
    assert len(calls) == 1 + config.AI_MAX_RETRIES and p.last_call["errors"][0] == "ReadTimeout"


def test_provider_without_credentials_is_reported_not_run(monkeypatch):
    from app import config
    from research.phase6 import provider_eval
    monkeypatch.setattr(config, "GEMINI_API_KEY", ""); monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    cp = provider_eval.configured_providers()
    assert cp["gemini"][0] is None and "not set" in cp["gemini"][1] and cp["anthropic"][0] is None
