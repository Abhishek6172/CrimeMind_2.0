"""Phase 5 component tests: perturbations, stability metrics, sensitivity variants. DB-backed tests use a disposable seed-2026 database."""
import pytest

from research.phase5 import evolution, perturb, sensitivity


def test_rank_change_metrics_identical_and_reversed():
    same = evolution.rank_change_metrics({"order": list("abcde")}, {"order": list("abcde")})
    assert same["kendall_tau"] == 1.0 and same["top_k_overlap"] == 1.0 and same["max_rank_displacement"] == 0
    rev = evolution.rank_change_metrics({"order": list("abcde")}, {"order": list("edcba")})
    assert rev["kendall_tau"] == pytest.approx(-1.0) and rev["spearman_rho"] == pytest.approx(-1.0) and rev["max_rank_displacement"] == 4
    swap = evolution.rank_change_metrics({"order": list("abcdef")}, {"order": list("bacdef")}, k=2)
    assert swap["top_k_overlap"] == 1.0 and swap["mean_rank_displacement"] == pytest.approx(2 / 6)


def test_sensitivity_names_parse_to_variants():
    names = sensitivity.names()
    assert names and all(n.startswith("raeer@") for n in names)
    for n in names[:6] + names[-3:]:
        assert sensitivity.variant(n).name == n


def test_thirteen_perturbation_kinds_registered():
    assert len(perturb.KINDS) == 13


def test_rng_is_deterministic_and_depends_on_inputs():
    a = perturb.rng_for(1, "C", "k", 0.1).random()
    assert a == perturb.rng_for(1, "C", "k", 0.1).random()
    assert a != perturb.rng_for(2, "C", "k", 0.1).random() and a != perturb.rng_for(1, "C", "k", 0.3).random()


@pytest.fixture(scope="module")
def view():
    from research.common.casedata import load_case_view
    from research.common.workspace import SeedWorkspace
    with SeedWorkspace(2026, prefix="cm_p5t") as ws:
        yield load_case_view(ws.conn, ws.cases()[0]["case_ref"])


@pytest.mark.parametrize("kind", sorted(perturb.KINDS))
def test_perturbation_is_deterministic_and_does_not_mutate_input(view, kind):
    before = (len(view.obs), len(view.comms), len(view.txns), len(view.rels), {k: v["validity_status"] if "validity_status" in v else v.get("status") for k, v in view.evidence.items()})
    a = perturb.perturb(view, kind, 0.3, 7)
    b = perturb.perturb(view, kind, 0.3, 7)
    after = (len(view.obs), len(view.comms), len(view.txns), len(view.rels), {k: v["validity_status"] if "validity_status" in v else v.get("status") for k, v in view.evidence.items()})
    assert before == after                                                     # original untouched
    assert (a.obs, a.comms, a.txns, a.rels) == (b.obs, b.comms, b.txns, b.rels)   # same seed, same result


def test_missing_evidence_removes_records(view):
    p = perturb.perturb(view, "missing_evidence", 0.5, 3)
    assert len(p.obs) + len(p.comms) + len(p.txns) + len(p.rels) < len(view.obs) + len(view.comms) + len(view.txns) + len(view.rels)
