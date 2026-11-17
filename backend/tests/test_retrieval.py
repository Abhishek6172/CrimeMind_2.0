import json

from app import db
from app.ai.context import build_context
from app.ai.service import analyze
from app.retrieval import search_evidence

from .conftest import C1, C2, admin_conn


def _case(ref):
    with admin_conn() as c:
        return c.execute("SELECT case_id, case_ref FROM cases WHERE case_ref=%s", (ref,)).fetchone()


def test_search_endpoint_finds_asked_evidence(api):
    j = api.get(f"/api/cases/{C1}/evidence-search", params={"q": "calls made by Rohit Sethi"}).json()
    top = j["results"][0]
    assert top["evidence_type"] == "CDR" and "Rohit Sethi" in top["description"]
    assert j["named_entities"] and all(r["matched_on"] for r in j["results"])
    assert api.get(f"/api/cases/{C1}/evidence-search", params={"q": "show E-0042"}).json()["results"][0]["ref"] == "E-0042"
    assert api.get(f"/api/cases/{C1}/evidence-search", params={"q": "CCTV footage Green Park lawn"}).json()["results"][0]["evidence_type"] == "CCTV"


def test_typos_are_tolerated_and_reported(api):
    j = api.get(f"/api/cases/{C1}/evidence-search", params={"q": "van borrowed by Rohit Sethy"}).json()
    assert j["typo_corrections"].get("sethy") == "sethi" and j["results"][0]["ref"] == "E-0312"


def test_search_is_case_scoped_and_authorised(api):
    # a user without access to CASE-2026-001 gets the same 404 as for a nonexistent case
    assert api.get(f"/api/cases/{C1}/evidence-search", user="inv.vikram", params={"q": "Rohit Sethi"}).status_code == 404
    # results for the other case only ever come from that case
    j = api.get(f"/api/cases/{C2}/evidence-search", user="inv.vikram", params={"q": "GPS location"}).json()
    with admin_conn() as c:
        own = {r["ref"] for r in c.execute("SELECT ref FROM evidence WHERE case_id=%s", (_case(C2)["case_id"],))}
        c1_names = {r["display_name"] for r in c.execute("SELECT display_name FROM entities WHERE case_id=%s", (_case(C1)["case_id"],))}
    assert j["results"] and {r["ref"] for r in j["results"]} <= own
    assert not any(n in json.dumps(j) for n in ("Rohit Sethi", "Meera Kulkarni"))
    assert c1_names  # sanity: the other case really has distinct people


def test_unrelated_or_empty_matches_return_nothing(api):
    assert api.get(f"/api/cases/{C1}/evidence-search", params={"q": "zzzzqqq xyzzy"}).json()["results"] == []
    assert api.get(f"/api/cases/{C1}/evidence-search", params={"q": "x"}).status_code == 422


def test_ai_context_carries_retrieved_evidence_and_it_is_citable(api):
    with db.connection("inv.asha") as conn:
        case = conn.execute("SELECT case_id, case_ref FROM cases WHERE case_ref=%s", (C1,)).fetchone()
        ctx = build_context(conn, case, "What do the bank records say about Meera Kulkarni and Rohit Sethi?")
        got = [e for e in ctx["evidence"] if e.get("retrieved")]
        assert got and {e["id"] for e in got} <= set(ctx["_allowed"]["evidence"])
        assert all(e["untrusted_source_text"] is not None for e in got)
        out = analyze(conn, "inv.asha", case, "What do the bank records say about Rohit Sethi?", "req-rag")
    assert out["status"] == "OK" and out["context_summary"]["evidence_retrieved"] > 0
    cited = [f for f in out["output"]["findings"] if f["evidence_ids"] and f["classification"] == "RECORDED FACT"]
    assert any("Rohit Sethi" in f["statement"] for f in cited)


def test_question_without_evidence_terms_retrieves_nothing(api):
    with db.connection("inv.asha") as conn:
        case = conn.execute("SELECT case_id, case_ref FROM cases WHERE case_ref=%s", (C1,)).fetchone()
        assert search_evidence(conn, case["case_id"], "Summarise the leads")["hits"] == []


def test_retrieval_recall_at_5_on_generated_queries(api):
    """Self-supervised check: ask for each person's GPS/bank/call record by name and expect the right record in the top 5."""
    kinds = {"GPS": "GPS location of", "CDR": "phone calls of", "TRANSACTION_RECORD": "bank statement of"}
    case = _case(C1)
    with admin_conn() as c:
        rows = c.execute("""SELECT e.ref, e.evidence_type, n.display_name FROM evidence e
                            JOIN evidence_entities x ON x.evidence_id=e.evidence_id JOIN entities n ON n.entity_id=x.entity_id
                            WHERE e.case_id=%s AND e.evidence_type = ANY(%s) AND n.entity_type='PERSON'""",
                         (case["case_id"], list(kinds))).fetchall()
        assert len(rows) > 100
        hit = 0
        for r in rows:
            top = [h["ref"] for h in search_evidence(c, case["case_id"], f"{kinds[r['evidence_type']]} {r['display_name']}", 5)["hits"]]
            hit += r["ref"] in top
    assert hit / len(rows) >= 0.9, f"recall@5 = {hit / len(rows):.3f}"


def test_identifiers_quoted_in_authorised_context_do_not_invalidate_answer(client_fixture=None):
    """Regression (found by Phase 6): a rule summary quoting a source key such as ACCESS:L-W06:P-075 made the validator reject
    the whole answer because L-W06 was not in the allowed entity set."""
    from app.ai.validator import validate
    ctx = {"_allowed": {"evidence": ["E-1"], "correlations": ["C-001"], "entities": ["P-001", "L-W06"], "incident_refs": []},
           "evidence": [{"id": "E-1", "validity_status": "SUPPORTED"}], "correlations": [{"id": "C-001", "classification": "INFERRED"}]}
    out = {"summary": "s", "uncertainties": [], "findings": [{"statement": "Placed at a venue (ACCESS:L-W06:P-001)", "classification": "UNCERTAIN",
                                                              "evidence_ids": ["E-1"], "correlation_ids": [], "confidence": None}]}
    assert validate(out, ctx) == []
    ctx["_allowed"]["entities"] = ["P-001"]
    assert any("L-W06" in p for p in validate(out, ctx))
