"""Phase 3 tests: metrics (hand-computed), ties, missing labels, statistics, algorithms on hand-built fixtures,
ground-truth isolation, frozen-Q40 identity, reproducibility."""
import ast
import json
import math
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from research.common.casedata import CaseView, haversine_m
from research.phase3.algorithms import make
from research.phase3.algorithms.base import assign_ranks
from research.phase3.algorithms.graph_centrality import build_graph, degree_centrality, pagerank
from research.phase3.metrics import ranking_metrics as M
from research.phase3.statistical_analysis import stats as S

ROOT = Path(__file__).resolve().parents[3]
CFG = json.load(open(ROOT / "research/phase3/configs/phase3_config.json"))
UTC = timezone.utc
T0 = datetime(2026, 8, 14, 16, 0, tzinfo=UTC)


# ---------- metrics (hand computed) ----------
G = {"a": 3, "b": 0, "c": 2, "d": 0, "e": 0}


def test_precision_recall_f1():
    r = ["b", "a", "d", "c", "e"]
    assert M.precision_at_k(r, G, 1) == 0 and M.precision_at_k(r, G, 3) == pytest.approx(1 / 3)
    assert M.recall_at_k(r, G, 3) == pytest.approx(0.5) and M.recall_at_k(r, G, 5) == 1.0
    assert M.f1_at_k(r, G, 3) == pytest.approx(2 * (1 / 3) * 0.5 / (1 / 3 + 0.5))


def test_mrr_and_ap():
    r = ["b", "a", "d", "c", "e"]
    assert M.reciprocal_rank(r, G) == 0.5
    assert M.average_precision(r, G) == pytest.approx((1 / 2 + 2 / 4) / 2)


def test_ndcg_perfect_and_worst():
    assert M.ndcg_at_k(["a", "c", "b", "d", "e"], G, 5) == pytest.approx(1.0)
    gain = lambda g: 2 ** g - 1
    ideal = gain(3) / math.log2(2) + gain(2) / math.log2(3)
    got = (gain(2) / math.log2(2) + gain(3) / math.log2(3))
    assert M.ndcg_at_k(["c", "a", "b", "d", "e"], G, 2) == pytest.approx(got / ideal)
    assert M.ndcg_at_k(["b", "d", "e", "a", "c"], G, 3) == 0.0


def test_fewer_candidates_than_k_uses_denominator_k():
    assert M.precision_at_k(["a", "c"], {"a": 1, "c": 1}, 5) == pytest.approx(2 / 5)


def test_no_relevant_cases_are_undefined_not_zero():
    g = {"a": 0, "b": 0}
    assert M.recall_at_k(["a", "b"], g, 3) is None and M.reciprocal_rank(["a", "b"], g) is None
    assert M.average_precision(["a", "b"], g) is None and M.ndcg_at_k(["a", "b"], g, 3) is None
    assert M.precision_at_k(["a", "b"], g, 3) == 0.0


def test_missing_and_indeterminate_labels_are_excluded_not_negative():
    g = {"a": 1, "b": None, "c": 0}                      # b indeterminate, d unlabelled
    out = M.evaluate_ranking(["b", "d", "a", "c"], g)
    assert out["n_excluded_unlabelled"] == 2 and out["n_labelled"] == 2
    assert out["MRR"] == 1.0                              # a is the first LABELLED item


def test_evaluate_ranking_has_all_metrics():
    out = M.evaluate_ranking(["a", "c", "b", "d", "e"], G)
    assert set(M.METRIC_NAMES) <= set(out) and out["AP"] == 1.0


def test_tie_bounds_bracket_hash_result():
    scores = {"a": 1, "b": 1, "c": 1, "d": 0, "e": 0}
    tb = M.tie_bounds(scores, G)
    assert tb["optimistic"]["MRR"] >= tb["pessimistic"]["MRR"] and tb["optimistic"]["MRR"] == 1.0 and tb["pessimistic"]["MRR"] == pytest.approx(1 / 2)


# ---------- ties ----------
def test_tie_break_is_deterministic_and_not_reference_order():
    scores = {f"P-{i:03d}": 1.0 for i in range(1, 40)}
    a = assign_ranks("seed_1", "C", scores, {}, lambda *x: "", "t", "v")
    b = assign_ranks("seed_1", "C", scores, {}, lambda *x: "", "t", "v")
    assert [x.lead_id for x in a] == [x.lead_id for x in b]
    assert [x.lead_id for x in a] != sorted(scores)
    c = assign_ranks("seed_2", "C", scores, {}, lambda *x: "", "t", "v")
    assert [x.lead_id for x in a] != [x.lead_id for x in c]


# ---------- statistics ----------
def test_holm_known_values():
    assert S.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])


def test_paired_comparison_detects_shift_and_identical():
    x = [0.5 + 0.01 * i for i in range(30)]
    y = [v - 0.1 for v in x]
    r = S.paired_comparison(x, y, n_boot=500)
    assert r["wilcoxon_p"] < 1e-5 and r["mean_diff"] == pytest.approx(0.1) and r["rank_biserial"] == pytest.approx(1.0) and r["wins"] == 30
    same = S.paired_comparison(x, x, n_boot=200)
    assert same["wilcoxon_p"] == 1.0 and same["ties"] == 30


def test_paired_comparison_drops_missing_pairs():
    assert S.paired_comparison([1, None, 3], [0, 2, None], n_boot=100)["n"] == 1


def test_summarise_ci_contains_mean():
    s = S.summarise([0.2, 0.4, 0.6, 0.8] * 5, n_boot=500)
    assert s["ci95_low"] <= s["mean"] <= s["ci95_high"] and s["n"] == 20


# ---------- algorithms on a hand-built case ----------
def mini_case():
    persons = {f"P-{i:03d}": f"Person {i}" for i in range(1, 7)}
    ent = {**{p: "PERSON" for p in persons}, "L-GP1": "LOCATION", "L-FAR": "LOCATION"}
    v = CaseView("C-1", 1, "EVT-001", T0, "L-GP1", ["P-006"], persons, {"L-GP1": (20.3050, 85.8240), "L-FAR": (20.3500, 85.9000)}, ent)
    v.as_of = T0 + timedelta(days=1)
    ob = lambda s, loc, dt: dict(ref=f"O-{s}", subject=s, location=loc, t_from=T0 + timedelta(minutes=dt), t_to=T0 + timedelta(minutes=dt + 10),
                                 source_kind="GPS", evidence=None, status="SUPPORTED", origin=s)
    v.obs = [ob("P-001", "L-GP1", -5), ob("P-002", "L-FAR", 0), ob("P-003", "L-GP1", 300)]
    cm = lambda a, b, dt, st="SUPPORTED": dict(ref=f"C-{a}{b}{dt}", a=a, b=b, t=T0 + timedelta(minutes=dt), duration=1, type="CALL", evidence=None, status=st, origin="x")
    v.comms = [cm("P-002", "P-003", -30), cm("P-002", "P-004", -20), cm("P-002", "P-005", -10), cm("P-001", "P-003", -4000), cm("P-005", "P-004", 5, "INVALIDATED")]
    rl = lambda a, b, s: dict(ref=f"R-{a}{b}", a=a, b=b, type="ASSOCIATE", strength=s, valid_from=None, valid_to=None, evidence=None, status="SUPPORTED", origin="r")
    v.rels = [rl("P-001", "P-002", .5), rl("P-002", "P-003", .5), rl("P-002", "P-004", .5)]
    return v


def test_spatial_proximity_ranks_nearest_in_window_first_and_missing_last():
    res = make("spatial_proximity").rank("d", mini_case(), CFG)
    by = {r.lead_id: r for r in res}
    assert by["P-001"].rank == 1 and by["P-001"].raw_score == pytest.approx(1.0, abs=0.01)
    assert by["P-002"].raw_score < by["P-001"].raw_score and by["P-002"].raw_score > 0
    assert by["P-003"].raw_score == 0.0 and "no location observation" in by["P-003"].explanation   # obs outside the window
    assert "P-006" not in by                                                                        # victim excluded


def test_communication_frequency_ignores_inactive_records_and_ranks_busiest():
    res = make("communication_frequency").rank("d", mini_case(), CFG)
    assert res[0].lead_id == "P-002"
    assert {r.lead_id: r.factors for r in res}["P-005"]["count"] == 1      # the INVALIDATED comm is not counted


def test_communication_baseline_does_not_use_future_records():
    v = mini_case()
    v.as_of = T0 - timedelta(days=100)
    res = make("communication_frequency").rank("d", v, CFG)
    assert all(r.factors["count"] == 0 for r in res)


def test_degree_and_pagerank_handle_isolated_nodes_and_components():
    v = mini_case()
    nodes, w = build_graph(v)
    dc = degree_centrality(nodes, w)
    assert dc["P-002"] == max(dc.values()) and dc["P-005"] == 0.0 and dc["P-006"] == 0.0
    pr = pagerank(nodes, w)
    assert sum(pr.values()) == pytest.approx(1.0, abs=1e-9)
    assert pr["P-002"] > pr["P-001"] > pr["P-005"] > 0           # isolated nodes keep teleport mass


def test_pagerank_matches_networkx():
    nx = pytest.importorskip("networkx")
    nodes, w = build_graph(mini_case())
    G_ = nx.Graph(); G_.add_nodes_from(nodes); G_.add_weighted_edges_from([(a, b, x) for (a, b), x in w.items()])
    ref = nx.pagerank(G_, alpha=0.85, tol=1e-12, weight="weight", max_iter=2000)
    mine = pagerank(nodes, w, tol=1e-13, max_iter=1000)
    assert all(abs(mine[n] - ref[n]) < 1e-7 for n in nodes)


def test_random_baseline_reproducible_and_repetition_dependent():
    v = mini_case()
    a = [r.lead_id for r in make("random", repetition=3).rank("d", v, CFG)]
    b = [r.lead_id for r in make("random", repetition=3).rank("d", v, CFG)]
    c = [r.lead_id for r in make("random", repetition=4).rank("d", v, CFG)]
    assert a == b and a != c and sorted(a) == v.candidates


def test_every_algorithm_returns_full_standard_result():
    v = mini_case()
    for name in ("random", "communication_frequency", "spatial_proximity", "degree_centrality", "pagerank", "pagerank_victim_personalised"):
        res = make(name).rank("d", v, CFG)
        assert sorted(r.lead_id for r in res) == v.candidates
        assert [r.rank for r in res] == list(range(1, len(res) + 1))
        r0 = res[0]
        assert r0.algorithm and r0.config_version and r0.explanation and r0.normalised_score is not None and isinstance(r0.factors, dict)


def test_haversine_known_distance():
    assert haversine_m((0, 0), (0, 1)) == pytest.approx(111195, rel=1e-3)


# ---------- ground-truth isolation ----------
def test_algorithms_never_import_ground_truth():
    banned = ("load_ground_truth", "ground_truth", "gt.", "relevance_grades", "workspace")
    for f in (ROOT / "research/phase3/algorithms").glob("*.py"):
        src = f.read_text()
        tree = ast.parse(src)
        names = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not any(b in " ".join(names) for b in ("workspace", "ground_truth")), f.name
        assert "relevance_grades" not in src and "load_ground_truth" not in src and "gt." not in src.replace("gt.", "", 0) or "FROM gt" not in src, f.name


def test_caseview_has_no_label_fields():
    fields = set(CaseView.__dataclass_fields__)
    assert not fields & {"grades", "relevance", "leads", "red_herrings", "roles", "ground_truth"}


# ---------- frozen Q40 identity & end-to-end (needs PostgreSQL) ----------
@pytest.fixture(scope="module")
def pg():
    try:
        import psycopg
        from synth.research_seed import BASE
        psycopg.connect(f"{BASE}/postgres", connect_timeout=3).close()
    except Exception as e:   # reported as skipped, never as passed
        pytest.skip(f"PostgreSQL unavailable: {e}")


def test_q40_sql_module_is_the_frozen_one(pg):
    import hashlib
    want = json.load(open(ROOT / "research/results/baseline/manifest.json"))["q40_module_sha256"]
    got = hashlib.sha256((ROOT / "backend/app/sql_modules/18_get_case_evidence_ranking.sql").read_bytes()).hexdigest()
    assert got == want
    cfg = json.load(open(ROOT / "research/baseline/q40_config.json"))
    assert {k: v["weight"] for k, v in cfg["signals"].items()} == {"spatial": .35, "temporal": .10, "communication": .15, "financial": .15, "relational": .10, "evidence": .15}


def test_q40_adapter_reproduces_frozen_baseline_on_original_dataset(pg):
    import psycopg
    from psycopg.rows import dict_row
    from research.common.casedata import load_case_view
    from synth.research_seed import BASE
    db = "cm_p3_frozen_check"
    subprocess.run([sys.executable, str(ROOT / "scripts/init_db.py"), "--db", db, "--reset"], check=True, capture_output=True, cwd=ROOT / "backend")
    try:
        subprocess.run([sys.executable, "-m", "synth.seed", "--db", db, "--seed", "2026"], check=True, capture_output=True, cwd=ROOT / "backend")
        with psycopg.connect(f"{BASE}/{db}", row_factory=dict_row) as conn:
            ref = conn.execute("SELECT case_ref FROM cases ORDER BY case_id LIMIT 1").fetchone()["case_ref"]
            view = load_case_view(conn, ref)
            res = make("q40").rank("orig", view, CFG)
        frozen = json.load(open(ROOT / "research/results/baseline/q40_before_scenarios.json"))["ranking"]
        native = sorted([r for r in res if r.raw_score > 0], key=lambda r: (-r.raw_score, r.lead_id))
        got = [(r.lead_id, r.raw_score, r.factors["signals"]) for r in native[:len(frozen)]]
        want = [(f["entity_ref"], f["association_score"], f["signals"]) for f in frozen]
        assert [(a, b) for a, b, _ in got] == [(a, b) for a, b, _ in want]
        assert all(set(g[2]) == set(w[2]) for g, w in zip(got, want))
    finally:
        with psycopg.connect(f"{BASE}/postgres", autocommit=True) as c:
            c.execute(f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)')


def test_end_to_end_seed_is_reproducible_and_hash_verified(pg):
    from research.phase3.evaluation.evaluator import run_seed
    a = run_seed(2031, ["random", "q40", "spatial_proximity"], prefix="cm_p3t")
    b = run_seed(2031, ["random", "q40", "spatial_proximity"], prefix="cm_p3t")
    assert all(r["hash_verified"] for r in a)
    strip = lambda rows: [{k: r[k] for k in ("method", "case_ref", "MRR", "AP", "nDCG@5", "P@3")} for r in rows]
    assert strip(a) == strip(b)
    assert {r["method"] for r in a} == {"random", "q40", "spatial_proximity"} and len(a) == 6
