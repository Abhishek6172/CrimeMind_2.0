"""Phase 4 tests: Q40-R equivalence with frozen Q40, reliability scoring, contradiction handling, lifecycle, RAEER calculation."""
import copy
import json
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from research.phase3.tests.test_phase3 import CFG as CFG3, T0, UTC, mini_case, pg   # noqa: F401  (pg fixture)
from research.phase4.algorithms import make

ROOT = Path(__file__).resolve().parents[3]
CFG = {**CFG3, **json.load(open(ROOT / "research/phase4/configs/phase4_config.json"))}


def ev(ref, typ, rel, status="SUPPORTED", origin=None, ents=()):
    return dict(type=typ, source=origin or ref, origin=origin or ref, reliability=rel, status=status, timestamp=T0, entities=list(ents))


def case_with_evidence():
    v = mini_case()
    ob = lambda ref, s, loc, dt, e, org: dict(ref=ref, subject=s, location=loc, t_from=T0 + timedelta(minutes=dt), t_to=T0 + timedelta(minutes=dt + 10),
                                              source_kind="GPS", evidence=e, status="SUPPORTED", origin=org)
    v.obs = [ob("O1", "P-001", "L-GP1", -5, "E1", "GPS:P-001"), ob("O2", "P-002", "L-GP1", -5, "E2", "CCTV:cam1")]
    v.comms, v.txns, v.rels = [], [], []
    v.evidence = {"E1": ev("E1", "GPS", 0.75, ents=["P-001"]), "E2": ev("E2", "CCTV", 0.70, ents=["P-002"])}
    return v


def test_q40r_with_reliability_off_equals_frozen_q40_on_real_data(pg):
    from research.common.casedata import load_case_view
    from research.common.workspace import SeedWorkspace
    with SeedWorkspace(2032, prefix="cm_p4t") as w:
        for c in w.cases():
            v = load_case_view(w.conn, c["case_ref"])
            q40 = {r.lead_id: r.raw_score for r in make("q40").rank("d", v, CFG)}
            q40r = {r.lead_id: r.raw_score for r in make("q40_r", features={"reliability": False}, name="x").rank("d", v, CFG)}
            diff = {k: (q40[k], q40r[k]) for k in q40 if abs(q40[k] - q40r[k]) > 0.0051}
            assert not diff, diff


def test_q40r_lower_reliability_lowers_score():
    v = case_with_evidence()
    r = {x.lead_id: x for x in make("q40_r").rank("d", v, CFG)}
    assert r["P-001"].factors["spatial"] == pytest.approx(0.75) and r["P-002"].factors["spatial"] == pytest.approx(0.70)
    assert r["P-001"].raw_score > r["P-002"].raw_score


def test_invalidated_evidence_is_not_current_support_but_challenged_keeps_half():
    v = case_with_evidence()
    v.evidence["E1"]["status"] = "INVALIDATED"
    assert make("q40_r").rank("d", v, CFG)[0].lead_id != "P-001" or make("q40_r").rank("d", v, CFG)[0].raw_score == 0
    f = {x.lead_id: x.factors for x in make("q40_r").rank("d", v, CFG)}
    assert f["P-001"]["spatial"] == 0.0
    v.evidence["E1"]["status"] = "CHALLENGED"
    f = {x.lead_id: x.factors for x in make("q40_r").rank("d", v, CFG)}
    assert f["P-001"]["spatial"] == pytest.approx(0.375)


def test_duplicate_records_of_one_origin_are_not_independent_corroboration():
    v = case_with_evidence()
    dup = dict(v.obs[0]); dup["ref"] = "O1b"; dup["evidence"] = "E1"
    v.obs.append(dup)
    a = {x.lead_id: x.factors["spatial"] for x in make("raeer").rank("d", v, CFG)}
    b = {x.lead_id: x.factors["spatial"] for x in make("raeer", features={"independence": False}).rank("d", v, CFG)}
    base = {x.lead_id: x.factors["spatial"] for x in make("raeer").rank("d", case_with_evidence(), CFG)}
    assert a["P-001"] == pytest.approx(base["P-001"])           # duplicate collapsed
    assert b["P-001"] > a["P-001"]                              # without independence handling it is double counted


def test_raeer_spatial_feature_is_noisy_or_with_temporal_decay():
    v = case_with_evidence()
    f = {x.lead_id: x.factors for x in make("raeer").rank("d", v, CFG)}
    # interval [T-5, T+5] contains T -> t = 1 ; one origin ; spatial = rho
    assert f["P-001"]["spatial"] == pytest.approx(0.75)
    v2 = case_with_evidence()
    v2.obs[0]["t_from"], v2.obs[0]["t_to"] = T0 + timedelta(minutes=30), T0 + timedelta(minutes=40)    # 30 min after T
    g = {x.lead_id: x.factors for x in make("raeer").rank("d", v2, CFG)}
    assert g["P-001"]["spatial"] == pytest.approx(0.75 * 2.718281828 ** -1, rel=1e-3)
    h = {x.lead_id: x.factors for x in make("raeer", features={"temporal": False}).rank("d", v2, CFG)}
    assert h["P-001"]["spatial"] == pytest.approx(0.75)


def test_raeer_score_hand_computed():
    v = case_with_evidence()
    r = {x.lead_id: x for x in make("raeer").rank("d", v, CFG)}["P-001"]
    f = r.factors
    expect = 0.35 * 0.75 + 0.10 * 0.75 + 0.15 * min(1, 0.75 / 3)
    assert r.raw_score == pytest.approx(expect, abs=1e-6)


def test_contradiction_lowers_but_never_erases_and_is_not_proof():
    v = case_with_evidence()
    far = dict(ref="O3", subject="P-001", location="L-FAR", t_from=T0 - timedelta(minutes=10), t_to=T0 + timedelta(minutes=10), source_kind="ACCESS",
               evidence="E3", status="SUPPORTED", origin="ACCESS:office")
    v.obs.append(far); v.evidence["E3"] = ev("E3", "ACCESS_LOG", 0.80, ents=["P-001"], origin="ACCESS:office")
    with_c = {x.lead_id: x.factors for x in make("raeer").rank("d", v, CFG)}["P-001"]
    no_c = {x.lead_id: x.factors for x in make("raeer", features={"contradiction": False}).rank("d", v, CFG)}["P-001"]
    c = 0.80 / (0.75 + 0.80)
    assert with_c["contradiction_strength"] == pytest.approx(c, abs=1e-3)
    assert with_c["spatial_after_contradiction"] == pytest.approx(0.75 * (1 - 0.5 * c), abs=1e-3)
    assert 0 < with_c["spatial_after_contradiction"] < no_c["spatial_after_contradiction"] == pytest.approx(0.75)


def test_same_origin_conflict_is_not_a_contradiction():
    v = case_with_evidence()
    far = dict(ref="O3", subject="P-001", location="L-FAR", t_from=T0 - timedelta(minutes=10), t_to=T0 + timedelta(minutes=10), source_kind="GPS",
               evidence="E1", status="SUPPORTED", origin="GPS:P-001")
    v.obs.append(far)
    assert {x.lead_id: x.factors for x in make("raeer").rank("d", v, CFG)}["P-001"]["contradiction_strength"] == 0.0


def test_ablation_changes_only_the_intended_component():
    v = case_with_evidence()
    full = {x.lead_id: x.factors for x in make("raeer").rank("d", v, CFG)}
    nor = {x.lead_id: x.factors for x in make("raeer", features={"reliability": False}).rank("d", v, CFG)}
    assert nor["P-001"]["spatial"] == pytest.approx(1.0) and full["P-001"]["spatial"] == pytest.approx(0.75)
    norel = {x.lead_id: x.factors for x in make("raeer", features={"relational": False}).rank("d", v, CFG)}
    assert norel["P-001"]["spatial"] == full["P-001"]["spatial"] and norel["P-001"]["relational"] == 0.0


def test_raeer_and_q40r_are_distinct_from_each_other_and_scores_in_unit_interval():
    v = mini_case()
    a = [r.raw_score for r in make("raeer").rank("d", v, CFG)]
    b = [r.raw_score for r in make("q40_r").rank("d", v, CFG)]
    assert all(0 <= x <= 1 for x in a + b) and a != b


def test_config_is_marked_frozen_and_weights_match_q40():
    q = json.load(open(ROOT / "research/baseline/q40_config.json"))["signals"]
    c = CFG["q40r"]["weights"]
    assert c["spatial"] == q["spatial"]["weight"] and c["communication"] == q["communication"]["weight"] and CFG["frozen_before_evaluation"] is True
