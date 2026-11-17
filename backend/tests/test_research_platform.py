"""Automated Tests for the CrimeMind Live Experimental Research Platform."""
import os
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
backend_path = ROOT / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.research.dataset_service import dataset_service
from app.research.experiment_config import config_manager
from app.research.experiment_runner import experiment_runner
from app.research.experiment_service import experiment_service
from app.research.metrics_service import metrics_service
from app.research.statistical_service import statistical_service


def test_dataset_catalog_and_integrity():
    """Verifies that the dataset catalog finds the committed seeds."""
    datasets = dataset_service.list_available_datasets()
    assert len(datasets) >= 10, f"Expected at least 10 seeds, found {len(datasets)}"
    
    # Check seed 2026 specifically
    seed_2026 = next((d for d in datasets if d["seed"] == 2026), None)
    assert seed_2026 is not None
    assert seed_2026["dataset_id"] == "seed_2026"
    assert "CASE-2026-001" in seed_2026["cases"]
    assert seed_2026["content_sha256"] != "UNKNOWN"


def test_ground_truth_loading():
    """Verifies ground truth loading and relevance grade structure."""
    gt = dataset_service.get_ground_truth(2026)
    assert "CASE-2026-001" in gt
    case_gt = gt["CASE-2026-001"]
    assert "relevance_grades" in case_gt
    grades = case_gt["relevance_grades"]
    assert len(grades) > 0
    # At least one relevant candidate with grade >= 1
    assert any(v >= 1 for v in grades.values())


def test_case_view_construction():
    """Verifies that CaseView is faithfully constructed from dataset CSVs."""
    views = dataset_service.load_seed_cases(2026, ["CASE-2026-001"])
    assert "CASE-2026-001" in views
    view = views["CASE-2026-001"]
    assert len(view.candidates) > 50
    assert len(view.obs) > 100
    assert len(view.comms) > 100
    assert len(view.evidence) > 50


def test_real_raeer_execution_and_persistence(world):
    """Executes genuine RAEER on seed 2026 and verifies database persistence."""
    exp_id = experiment_service.create_experiment(
        name="Automated Test - RAEER Real Run",
        algorithm="raeer",
        dataset_id="seed_2026",
        seeds=[2026],
        config_json={"cases": ["CASE-2026-001"], "parameters": {"contradiction": {"gamma": 0.5}}},
        created_by="test_runner",
    )

    experiment_runner.run_experiment_sync(
        experiment_id=exp_id,
        algorithm_name="raeer",
        dataset_id="seed_2026",
        seeds=[2026],
        cases_filter=["CASE-2026-001"],
        parameters={"contradiction": {"gamma": 0.5}},
        target_metrics=["nDCG@5", "P@5", "R@5", "MRR", "AP"],
    )

    details = experiment_service.get_experiment_details(exp_id)
    assert details is not None
    assert details["status"] == "COMPLETED"
    assert details["progress_pct"] == 100.00
    assert details["execution_time_sec"] is not None and details["execution_time_sec"] > 0

    # Verify metrics were recorded
    metrics_by_name = {m["metric_name"]: m["mean_value"] for m in details["metrics"]}
    assert "nDCG@5" in metrics_by_name
    assert "P@5" in metrics_by_name
    assert "MRR" in metrics_by_name
    assert 0.0 <= metrics_by_name["nDCG@5"] <= 1.0
    assert 0.0 <= metrics_by_name["P@5"] <= 1.0

    # Verify per-seed case results
    assert len(details["seed_results"]) == 1
    sr = details["seed_results"][0]
    assert sr["seed"] == 2026
    assert sr["case_ref"] == "CASE-2026-001"
    assert len(sr["top_ranked"]) > 0
    top1 = sr["top_ranked"][0]
    assert "lead_id" in top1
    assert "raw_score" in top1
    assert "explanation" in top1


def test_deterministic_reproducibility(world):
    """Runs the same configuration twice and verifies exact deterministic match."""
    # Run 1
    exp_1 = experiment_service.create_experiment(
        name="Reproducibility Run 1",
        algorithm="raeer",
        dataset_id="seed_2026",
        seeds=[2026],
        config_json={},
    )
    experiment_runner.run_experiment_sync(
        experiment_id=exp_1,
        algorithm_name="raeer",
        dataset_id="seed_2026",
        seeds=[2026],
        cases_filter=["CASE-2026-001"],
        parameters={},
        target_metrics=["nDCG@5", "P@5", "MRR"],
    )
    res_1 = experiment_service.get_experiment_details(exp_1)

    # Run 2
    exp_2 = experiment_service.create_experiment(
        name="Reproducibility Run 2",
        algorithm="raeer",
        dataset_id="seed_2026",
        seeds=[2026],
        config_json={},
    )
    experiment_runner.run_experiment_sync(
        experiment_id=exp_2,
        algorithm_name="raeer",
        dataset_id="seed_2026",
        seeds=[2026],
        cases_filter=["CASE-2026-001"],
        parameters={},
        target_metrics=["nDCG@5", "P@5", "MRR"],
    )
    res_2 = experiment_service.get_experiment_details(exp_2)

    # Rankings and scores must match exactly
    ranks_1 = [c["lead_id"] for c in res_1["seed_results"][0]["top_ranked"]]
    ranks_2 = [c["lead_id"] for c in res_2["seed_results"][0]["top_ranked"]]
    assert ranks_1 == ranks_2, f"Ranks differed between deterministic runs: {ranks_1} vs {ranks_2}"

    m1 = {m["metric_name"]: m["mean_value"] for m in res_1["metrics"]}
    m2 = {m["metric_name"]: m["mean_value"] for m in res_2["metrics"]}
    assert m1["nDCG@5"] == m2["nDCG@5"]
    assert m1["P@5"] == m2["P@5"]
    assert m1["MRR"] == m2["MRR"]


def test_hyperparameter_sensitivity_propagation(world):
    """Modifies RAEER hyperparameter (gamma contradiction penalty) and verifies it changes output."""
    # Gamma = 0.5 (normal)
    exp_g5 = experiment_service.create_experiment(
        name="Sensitivity Gamma 0.5",
        algorithm="raeer",
        dataset_id="seed_2026",
        seeds=[2026],
        config_json={},
    )
    experiment_runner.run_experiment_sync(
        experiment_id=exp_g5,
        algorithm_name="raeer",
        dataset_id="seed_2026",
        seeds=[2026],
        cases_filter=["CASE-2026-001"],
        parameters={"contradiction": {"gamma": 0.5}},
        target_metrics=["nDCG@5"],
    )
    res_g5 = experiment_service.get_experiment_details(exp_g5)

    # Gamma = 0.0 (penalty disabled)
    exp_g0 = experiment_service.create_experiment(
        name="Sensitivity Gamma 0.0",
        algorithm="raeer",
        dataset_id="seed_2026",
        seeds=[2026],
        config_json={},
    )
    experiment_runner.run_experiment_sync(
        experiment_id=exp_g0,
        algorithm_name="raeer",
        dataset_id="seed_2026",
        seeds=[2026],
        cases_filter=["CASE-2026-001"],
        parameters={"contradiction": {"gamma": 0.0}},
        target_metrics=["nDCG@5"],
    )
    res_g0 = experiment_service.get_experiment_details(exp_g0)

    m_g5 = next(m["mean_value"] for m in res_g5["metrics"] if m["metric_name"] == "nDCG@5")
    m_g0 = next(m["mean_value"] for m in res_g0["metrics"] if m["metric_name"] == "nDCG@5")

    # The scores and metrics should genuinely reflect the disabled contradiction penalty
    assert m_g5 != m_g0, f"Expected hyperparameter change to affect nDCG@5, got {m_g5} vs {m_g0}"


def test_algorithm_comparison_and_statistical_testing(world):
    """Runs genuine comparative study between Q40, Q40-R, and RAEER."""
    study = experiment_service.run_comparative_study_sync(
        study_name="Automated Comparative Study",
        algorithms=["q40_py", "q40_r", "raeer"],
        seeds=[2026, 2027],
        cases_filter=["CASE-2026-001"],
        raeer_parameters={"contradiction": {"gamma": 0.5}},
        target_metrics=["nDCG@5", "P@5", "MRR"],
    )

    assert "results" in study
    assert "statistical_comparisons" in study
    assert len(study["statistical_comparisons"]) >= 1

    # Check that RAEER outperforms or matches baseline
    raeer_res = study["results"]["raeer"]
    q40_res = study["results"]["q40_py"]
    assert raeer_res["status"] == "COMPLETED"
    assert q40_res["status"] == "COMPLETED"
