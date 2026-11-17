"""Research Platform REST API endpoints."""
import csv
import io
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from ..deps import Ctx, get_ctx
from .dataset_service import dataset_service
from .experiment_runner import experiment_runner
from .experiment_service import experiment_service
from .schemas import (
    CompareExperimentsRequest,
    ExperimentDetailResponse,
    ExperimentStatusResponse,
    RunExperimentRequest,
)

router = APIRouter(prefix="/api/research", tags=["research"])


# -------------------------------------------------------------------------
# Metadata & Catalog Queries
# -------------------------------------------------------------------------
@router.get("/datasets")
def list_datasets(ctx: Ctx = Depends(get_ctx)):
    """Returns catalog of all available synthetic research seeds and manifest hashes."""
    datasets = dataset_service.list_available_datasets()
    return {
        "count": len(datasets),
        "datasets": datasets,
        "default_seeds": [2026, 2027, 2028],
    }


@router.get("/algorithms")
def list_algorithms(ctx: Ctx = Depends(get_ctx)):
    """Returns supported research ranking algorithms and their parameter definitions."""
    return {
        "algorithms": [
            {
                "id": "raeer",
                "name": "RAEER (Reliability-Aware Evidence Evolution Ranking)",
                "category": "Proposed Method",
                "is_configurable": True,
                "description": "Multi-domain ranking with explicit evidence lifecycle discounting, temporal decay, and spatial contradiction penalty.",
                "default_parameters": {
                    "weights": {
                        "spatial": 0.35,
                        "temporal": 0.10,
                        "communication": 0.15,
                        "financial": 0.15,
                        "relational": 0.10,
                        "corroboration": 0.15,
                    },
                    "contradiction": {
                        "gamma": 0.5,
                        "distance_m": 1000.0,
                    },
                    "temporal_tau_minutes": 30.0,
                    "scene_radius_m": 150.0,
                    "corroboration_domains_cap": 3,
                    "features": {
                        "reliability": True,
                        "temporal": True,
                        "relational": True,
                        "independence": True,
                        "contradiction": True,
                        "lifecycle": True,
                        "provenance": True,
                        "corroboration": True,
                    },
                    "status_factor": {
                        "SUPPORTED": 1.0,
                        "CHALLENGED": 0.5,
                        "INVALIDATED": 0.0,
                        "SUPERSEDED": 0.0,
                    },
                },
            },
            {
                "id": "q40_r",
                "name": "Q40-R (Reliability-Weighted Baseline)",
                "category": "Baseline",
                "is_configurable": False,
                "description": "Q40 lead generation baseline upgraded with per-evidence reliability score weighting.",
            },
            {
                "id": "q40_py",
                "name": "Q40 (Frozen System Baseline)",
                "category": "Baseline",
                "is_configurable": False,
                "description": "Unweighted frozen Phase 3 SQL baseline (considers only SUPPORTED evidence records).",
            },
            {
                "id": "raeer-no_contradiction",
                "name": "RAEER Ablation: No Contradiction Penalty",
                "category": "Ablation",
                "is_configurable": False,
            },
            {
                "id": "raeer-no_lifecycle",
                "name": "RAEER Ablation: No Lifecycle Awareness",
                "category": "Ablation",
                "is_configurable": False,
            },
            {
                "id": "raeer-no_temporal",
                "name": "RAEER Ablation: No Temporal Decay",
                "category": "Ablation",
                "is_configurable": False,
            },
            {
                "id": "raeer-no_independence",
                "name": "RAEER Ablation: No Source Independence",
                "category": "Ablation",
                "is_configurable": False,
            },
        ]
    }


@router.get("/metrics")
def list_metrics(ctx: Ctx = Depends(get_ctx)):
    """Returns supported ranking evaluation metrics."""
    return {
        "metrics": [
            {"id": "nDCG@5", "name": "Normalized Discounted Cumulative Gain @ 5", "range": "[0, 1]", "higher_is_better": True},
            {"id": "P@5", "name": "Precision @ 5", "range": "[0, 1]", "higher_is_better": True},
            {"id": "R@5", "name": "Recall @ 5", "range": "[0, 1]", "higher_is_better": True},
            {"id": "MRR", "name": "Mean Reciprocal Rank", "range": "[0, 1]", "higher_is_better": True},
            {"id": "AP", "name": "Average Precision (MAP)", "range": "[0, 1]", "higher_is_better": True},
            {"id": "nDCG@3", "name": "Normalized Discounted Cumulative Gain @ 3", "range": "[0, 1]", "higher_is_better": True},
            {"id": "P@3", "name": "Precision @ 3", "range": "[0, 1]", "higher_is_better": True},
            {"id": "F1@5", "name": "F1-Score @ 5", "range": "[0, 1]", "higher_is_better": True},
        ]
    }


# -------------------------------------------------------------------------
# Experiment Execution & Management
# -------------------------------------------------------------------------
@router.post("/experiments/run")
def run_experiment(
    req: RunExperimentRequest,
    background_tasks: BackgroundTasks,
    ctx: Ctx = Depends(get_ctx),
):
    """Submits a genuine research experiment for background execution."""
    exp_id = experiment_service.create_experiment(
        name=req.name,
        algorithm=req.algorithm,
        dataset_id=req.dataset_id,
        seeds=req.seeds,
        config_json={
            "cases": req.cases,
            "parameters": req.parameters,
            "metrics": req.metrics,
            "perturbation": req.perturbation,
        },
        created_by=ctx.user,
    )

    background_tasks.add_task(
        experiment_runner.run_experiment_sync,
        experiment_id=exp_id,
        algorithm_name=req.algorithm,
        dataset_id=req.dataset_id,
        seeds=req.seeds,
        cases_filter=req.cases,
        parameters=req.parameters,
        target_metrics=req.metrics,
        perturbation=req.perturbation,
    )

    return {
        "experiment_id": exp_id,
        "name": req.name,
        "algorithm": req.algorithm,
        "status": "QUEUED",
        "message": f"Experiment #{exp_id} dispatched to background computation worker.",
    }


@router.post("/experiments/compare")
def compare_algorithms(
    req: CompareExperimentsRequest,
    background_tasks: BackgroundTasks,
    ctx: Ctx = Depends(get_ctx),
):
    """Dispatches a comparative study across multiple algorithms."""
    # Run in background
    def run_study():
        experiment_service.run_comparative_study_sync(
            study_name=req.name,
            algorithms=req.algorithms,
            seeds=req.seeds,
            cases_filter=req.cases,
            raeer_parameters=req.raeer_parameters,
            target_metrics=req.metrics,
        )

    background_tasks.add_task(run_study)

    return {
        "study_name": req.name,
        "algorithms": req.algorithms,
        "seeds": req.seeds,
        "status": "QUEUED",
        "message": "Comparative study across algorithms queued for execution.",
    }


@router.get("/experiments")
def list_experiments(
    limit: int = Query(50, ge=1, le=200),
    algorithm: Optional[str] = Query(None),
    ctx: Ctx = Depends(get_ctx),
):
    """Lists historical and recent live experiments."""
    return experiment_service.list_experiments(limit=limit, algorithm=algorithm)


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: int, ctx: Ctx = Depends(get_ctx)):
    """Retrieves complete experiment details including metrics and per-seed results."""
    exp = experiment_service.get_experiment_details(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return exp


@router.get("/experiments/{experiment_id}/status")
def get_experiment_status(experiment_id: int, ctx: Ctx = Depends(get_ctx)):
    """Lightweight polling endpoint for live execution progress."""
    status_row = experiment_service.get_experiment_status(experiment_id)
    if not status_row:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return status_row


@router.get("/experiments/{experiment_id}/results")
def get_experiment_results(experiment_id: int, ctx: Ctx = Depends(get_ctx)):
    """Retrieves metrics and per-seed rankings for a completed experiment."""
    exp = experiment_service.get_experiment_details(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return {
        "experiment_id": exp["experiment_id"],
        "name": exp["name"],
        "algorithm": exp["algorithm"],
        "status": exp["status"],
        "metrics": exp["metrics"],
        "seed_results": exp["seed_results"],
    }


@router.get("/experiments/{experiment_id}/logs")
def get_experiment_logs(
    experiment_id: int,
    limit: int = Query(200, ge=1, le=1000),
    ctx: Ctx = Depends(get_ctx),
):
    """Retrieves live execution logs for an experiment."""
    return experiment_service.get_experiment_logs(experiment_id, limit=limit)


@router.post("/experiments/{experiment_id}/cancel")
def cancel_experiment(experiment_id: int, ctx: Ctx = Depends(get_ctx)):
    """Cooperatively cancels a running experiment."""
    ok = experiment_service.cancel_experiment(experiment_id)
    return {"experiment_id": experiment_id, "cancelled": ok}


@router.get("/experiments/{experiment_id}/artifacts")
def export_experiment_artifact(
    experiment_id: int,
    format: str = Query("json"),
    ctx: Ctx = Depends(get_ctx),
):
    """Exports full experiment data as JSON or CSV."""
    exp = experiment_service.get_experiment_details(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["seed", "case_ref", "rank", "lead_id", "raw_score", "is_relevant", "relevance_grade", "explanation"])
        for sr in exp.get("seed_results", []):
            seed = sr["seed"]
            case_ref = sr["case_ref"]
            for cand in sr.get("top_ranked", []):
                writer.writerow([
                    seed,
                    case_ref,
                    cand.get("rank"),
                    cand.get("lead_id"),
                    cand.get("raw_score"),
                    cand.get("is_relevant"),
                    cand.get("relevance_grade"),
                    cand.get("explanation"),
                ])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=experiment_{experiment_id}_results.csv"},
        )

    return JSONResponse(
        content=exp,
        headers={"Content-Disposition": f"attachment; filename=experiment_{experiment_id}_results.json"},
    )
