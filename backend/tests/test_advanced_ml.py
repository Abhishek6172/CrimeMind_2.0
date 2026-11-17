"""
Tests for CrimeMind Advanced Machine Learning Models:
1. GNN Criminal Syndicate Discovery (PyTorch GCN)
2. Financial Forensics (Isolation Forest & Smurfing)
3. Geographic Profiling (Rossmo's Formula & Jeopardy Surface)
"""

import pytest
from app.ml.syndicate_gnn import analyze_criminal_syndicate
from app.ml.financial_forensics import audit_financial_ledger
from app.ml.geographic_profiler import calculate_geographic_profile

def test_syndicate_gnn():
    res = analyze_criminal_syndicate([], [])
    assert res["status"] == "success"
    assert res["total_suspects"] >= 5
    assert len(res["predicted_links"]) > 0
    assert res["suspected_mastermind"] is not None
    assert "CELL" in res["nodes"][0]["community_cell"]
    print("GNN test passed! Mastermind found:", res["suspected_mastermind"]["name"])

def test_financial_forensics():
    res = audit_financial_ledger(reporting_threshold=50000.0)
    assert res["status"] == "success"
    assert res["total_transactions_analyzed"] >= 8
    assert res["anomalies_detected"] > 0
    assert res["smurfing_transactions_count"] > 0
    assert "digit_distribution" in res["benford_law_conformity"]
    print(f"Financial Forensics test passed! Suspicious volume: {res['total_suspicious_volume']}")

def test_geographic_profiler():
    res = calculate_geographic_profile(grid_size=20)
    assert res["status"] == "success"
    assert len(res["jeopardy_surface_points"]) > 0
    assert res["predicted_anchor_point"]["probability_confidence"] > 50.0
    assert res["predicted_anchor_point"]["lat"] > 0
    print(f"Geographic Profiler passed! Anchor point: {res['predicted_anchor_point']['lat']}, {res['predicted_anchor_point']['lng']}")
