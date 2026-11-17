"""Retrieval and answer metrics for the golden benchmark (deterministic, no LLM-as-judge)."""
import math
import re

ID = re.compile(r"\b[PVLDO]-\d+\b")


def retrieval_metrics(ranked: list[str], relevant: set[str], entity_links: dict | None = None, expected_entities=(), budget: int = 8) -> dict:
    """ranked: evidence refs in rank order; relevant: non-empty set. P@k = hits/k; R@k = hits/|R|; nDCG binary; coverage@budget = share of
    relevant evidence inside the context budget (the AI layer receives at most `budget` retrieved items)."""
    out = {}
    for k in (1, 3, 5):
        hits = len(set(ranked[:k]) & relevant)
        out[f"P@{k}"] = hits / k
        out[f"R@{k}"] = hits / len(relevant)
    rr = next((1 / i for i, r in enumerate(ranked, 1) if r in relevant), 0.0)
    out["MRR"] = rr
    for k in (5, 8):
        dcg = sum(1 / math.log2(i + 1) for i, r in enumerate(ranked[:k], 1) if r in relevant)
        idcg = sum(1 / math.log2(i + 1) for i in range(1, min(len(relevant), k) + 1))
        out[f"nDCG@{k}"] = dcg / idcg
    out["coverage@8"] = len(set(ranked[:budget]) & relevant) / len(relevant)
    if entity_links is not None and expected_entities:
        top = ranked[:5]
        out["source_relevance@5"] = (sum(1 for r in top if set(entity_links.get(r, ())) & set(expected_entities)) / len(top)) if top else 0.0
    return out


def answer_metrics(q: dict, out: dict, ctx_ids: set, problems: list[str], names: dict | None = None) -> dict:
    findings = out.get("findings", []) if isinstance(out, dict) else []
    text = " ".join([out.get("summary", "")] + [f.get("statement", "") for f in findings] + [str(u) for u in out.get("uncertainties", [])]) if isinstance(out, dict) else ""
    cited = {e for f in findings for e in (f.get("evidence_ids") or [])}
    rel = set(q["supporting_evidence"])
    m = {"valid": float(not problems), "n_findings": len(findings)}
    m["hallucination"] = float(any(("not in the authorized context" in p) or ("not in the context" in p) for p in problems))
    cl = [f for f in findings if f.get("classification") in ("RECORDED FACT", "CORRELATED", "AI-INFERRED")]
    m["unsupported_claim_rate"] = (sum(1 for f in cl if not (f.get("evidence_ids") or f.get("correlation_ids"))) / len(cl)) if cl else 0.0
    m["groundedness"] = (sum(1 for f in findings if (f.get("evidence_ids") or f.get("correlation_ids")) and set(f.get("evidence_ids") or []) <= ctx_ids) / len(findings)) if findings else 1.0
    if rel:
        in_ctx = rel & ctx_ids
        m["context_recall"] = len(in_ctx) / len(rel)                           # retrieval-stage recall
        m["citation_completeness"] = len(cited & rel) / len(rel)               # answer recall of relevant evidence
        m["citation_correctness"] = (len(cited & rel) / len(cited)) if cited else None
        m["generation_given_context"] = (len(cited & rel) / len(in_ctx)) if in_ctx else None
        m["error_type"] = "retrieval" if len(in_ctx) < len(rel) else ("generation" if len(cited & rel) < len(in_ctx) else "none")
    exp = set(q["expected_entities"])
    if exp:
        said = set(ID.findall(text)) | {r for r, n in (names or {}).items() if n and n in text and r.startswith("P-")}
        m["entity_recall"] = len(said & exp) / len(exp)
        m["entity_precision"] = (len(said & exp) / len(said)) if said else None
    crit = q["evaluation_criteria"]
    if crit.get("must_refuse") or crit.get("must_state_absence"):
        absent = re.search(r"\bno [a-z ]{0,25}(?:records?|evidence|footage) (?:exists?|found|recorded|matched|available)\b|\bnone recorded\b|\bnot recorded\b|\bno supported records\b", text, re.I)
        asserted = [f for f in findings if f.get("classification") in ("RECORDED FACT", "CORRELATED")]
        m["correct_refusal"] = float(bool(absent))
        m["asserted_facts_on_unanswerable"] = float(bool(asserted))
    if crit.get("must_cite_contradicting"):
        want = set(crit["must_cite_contradicting"])
        m["contradiction_awareness"] = len(cited & want) / len(want)
    if q.get("expected_status"):
        e = next(iter(q["supporting_evidence"]))
        f = [x for x in findings if e in (x.get("evidence_ids") or [])]
        st = q["expected_status"]
        asserted_current = any(x["classification"] in ("RECORDED FACT", "CORRELATED") for x in f)
        if st == "SUPPORTED":
            m["temporal_consistency"] = float(asserted_current)                 # reinstated evidence may be used as current support
        else:
            m["temporal_consistency"] = float(not asserted_current)             # disputed/invalid evidence must NOT be presented as current support
            m["status_reported"] = float(any(st in x["statement"] and f"{e}" in " ".join(x.get("evidence_ids") or []) for x in f))
    return m
