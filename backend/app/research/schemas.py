"""Pydantic schemas for the Research Platform."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RAEERWeights(BaseModel):
    spatial: float = Field(0.35, ge=0.0, le=1.0, description="Spatial proximity signal weight")
    temporal: float = Field(0.10, ge=0.0, le=1.0, description="Temporal window decay signal weight")
    communication: float = Field(0.15, ge=0.0, le=1.0, description="Communication tie strength weight")
    financial: float = Field(0.15, ge=0.0, le=1.0, description="Transaction network weight")
    relational: float = Field(0.10, ge=0.0, le=1.0, description="Relational graph weight")
    corroboration: float = Field(0.15, ge=0.0, le=1.0, description="Cross-domain corroboration weight")


class RAEERContradiction(BaseModel):
    gamma: float = Field(0.5, ge=0.0, le=1.0, description="Contradiction penalty attenuation (0=disabled, 1=max penalty)")
    distance_m: float = Field(1000.0, ge=50.0, le=10000.0, description="Distance threshold for conflicting location records (m)")


class RAEERFeatures(BaseModel):
    reliability: bool = Field(True, description="Enable per-evidence reliability score weighting")
    temporal: bool = Field(True, description="Enable exponential temporal decay toward incident time")
    relational: bool = Field(True, description="Enable relational graph feature")
    independence: bool = Field(True, description="Enable provenance-root deduplication across records")
    contradiction: bool = Field(True, description="Enable contradiction penalty calculation")
    lifecycle: bool = Field(True, description="Enable evidence lifecycle state discounting")
    provenance: bool = Field(True, description="Enable source provenance tracking")
    corroboration: bool = Field(True, description="Enable independent cross-domain corroboration")


class StatusFactors(BaseModel):
    SUPPORTED: float = Field(1.0, ge=0.0, le=1.0)
    CHALLENGED: float = Field(0.5, ge=0.0, le=1.0)
    INVALIDATED: float = Field(0.0, ge=0.0, le=1.0)
    SUPERSEDED: float = Field(0.0, ge=0.0, le=1.0)


class RAEERHyperparameters(BaseModel):
    weights: RAEERWeights = Field(default_factory=RAEERWeights)
    contradiction: RAEERContradiction = Field(default_factory=RAEERContradiction)
    temporal_tau_minutes: float = Field(30.0, ge=1.0, le=360.0, description="Temporal half-life / tau decay scale (minutes)")
    scene_radius_m: float = Field(150.0, ge=10.0, le=2000.0, description="Incident scene radius threshold (m)")
    corroboration_domains_cap: int = Field(3, ge=1, le=5, description="Domain count cap for corroboration normalization")
    features: RAEERFeatures = Field(default_factory=RAEERFeatures)
    status_factor: StatusFactors = Field(default_factory=StatusFactors)


class RunExperimentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="Experiment display name")
    algorithm: str = Field("raeer", description="Algorithm identifier: raeer, q40_py, q40_r, or ablation variant")
    dataset_id: str = Field("synthetic_seeds", description="Dataset identifier")
    seeds: List[int] = Field(default=[2026, 2027, 2028], min_length=1, description="List of random seeds to evaluate against")
    cases: Optional[List[str]] = Field(None, description="Optional case_ref filter (e.g. ['CASE-2026-001'])")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Algorithm-specific hyperparameter overrides")
    metrics: List[str] = Field(
        default=["nDCG@5", "P@5", "R@5", "MRR", "AP"],
        description="List of target evaluation metrics to compute"
    )
    perturbation: Optional[Dict[str, Any]] = Field(None, description="Optional perturbation stress-test config (type, level)")


class CompareExperimentsRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    algorithms: List[str] = Field(default=["q40_py", "q40_r", "raeer"], min_length=2)
    seeds: List[int] = Field(default=[2026, 2027, 2028], min_length=1)
    cases: Optional[List[str]] = Field(None)
    raeer_parameters: Optional[Dict[str, Any]] = Field(None)
    metrics: List[str] = Field(default=["nDCG@5", "P@5", "R@5", "MRR", "AP"])


class MetricSummary(BaseModel):
    metric_name: str
    mean_value: float
    std_dev: Optional[float] = None
    std_err: Optional[float] = None
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class SeedCaseResult(BaseModel):
    seed: int
    case_ref: str
    metrics: Dict[str, Any]
    top_ranked: List[Dict[str, Any]]
    n_candidates: int
    n_relevant: int


class ExperimentStatusResponse(BaseModel):
    experiment_id: int
    name: str
    algorithm: str
    dataset_id: str
    seeds: List[int]
    status: str
    progress_pct: float
    current_step: Optional[str] = None
    execution_time_sec: Optional[float] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ExperimentDetailResponse(ExperimentStatusResponse):
    config_json: Dict[str, Any]
    metrics: List[MetricSummary] = []
    seed_results: List[SeedCaseResult] = []
    log_count: int = 0
