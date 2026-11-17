"""
FastAPI Router for Advanced Machine Learning Modules:
1. GNN Criminal Syndicate Discovery (PyTorch Spectral GCN)
2. Financial Forensics: Money Laundering & Smurfing Anomaly Detection (Isolation Forest)
3. Geographic Profiling: Serial Offender Spatial Forecasting (Rossmo's Formula)
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.ml.syndicate_gnn import analyze_criminal_syndicate
from app.ml.financial_forensics import audit_financial_ledger
from app.ml.geographic_profiler import calculate_geographic_profile

router = APIRouter(prefix="/api/ml", tags=["advanced_machine_learning"])

class GnnRequest(BaseModel):
    case_id: Optional[str] = "CASE-2026-001"
    nodes: Optional[List[Dict[str, Any]]] = None
    edges: Optional[List[Dict[str, Any]]] = None

class FinancialAuditRequest(BaseModel):
    case_id: Optional[str] = "CASE-2026-001"
    reporting_threshold: float = Field(default=50000.0, description="Reporting limit (e.g. INR 50,000 or USD 10,000)")
    transactions: Optional[List[Dict[str, Any]]] = None

class GeographicProfileRequest(BaseModel):
    case_id: Optional[str] = "CASE-2026-001"
    grid_size: int = Field(default=25, ge=10, le=50)
    buffer_radius_km: float = Field(default=1.2, ge=0.2, le=5.0)
    decay_exponent: float = Field(default=1.3, ge=0.5, le=3.0)
    crime_sites: Optional[List[Dict[str, Any]]] = None

@router.get("/overview")
async def get_ml_models_overview():
    """Metadata and status of all integrated advanced machine learning models."""
    return {
        "status": "active",
        "models": [
            {
                "id": "gnn_syndicate",
                "name": "Graph Neural Network Syndicate Link Prediction",
                "architecture": "2-Layer Spectral Graph Convolutional Network (PyTorch GCN)",
                "purpose": "Predicts unobserved criminal syndicate links and isolates the hidden Mastermind / Kingpin",
                "endpoint": "/api/ml/gnn/analyze"
            },
            {
                "id": "financial_isolation_forest",
                "name": "Financial Forensics & Smurfing Anomaly Detector",
                "architecture": "Scikit-Learn Isolation Forest (100 Trees) + Benford's Law + Velocity Hops",
                "purpose": "Detects structured transactions under reporting thresholds and rapid shell account dispersion",
                "endpoint": "/api/ml/financial/audit"
            },
            {
                "id": "rossmo_geographic_profiler",
                "name": "Geographic Profiler & Serial Offender Spatial Forecaster",
                "architecture": "Rossmo's Mathematical Geographic Formula + Manhattan Distance Decay",
                "purpose": "Calculates 2D/3D Jeopardy Surface and predicts offender anchor point / hideout coordinates",
                "endpoint": "/api/ml/spatial/profile"
            }
        ]
    }

@router.post("/gnn/analyze")
async def run_gnn_syndicate_analysis(req: GnnRequest):
    """Executes PyTorch Graph Convolutional Network on criminal network."""
    try:
        result = analyze_criminal_syndicate(
            nodes=req.nodes or [],
            known_edges=req.edges or []
        )
        result["case_id"] = req.case_id
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GNN analysis failed: {str(e)}")

@router.post("/financial/audit")
async def run_financial_audit(req: FinancialAuditRequest):
    """Runs Isolation Forest and structuring analysis on case transaction ledger."""
    try:
        result = audit_financial_ledger(
            transactions=req.transactions or [],
            reporting_threshold=req.reporting_threshold
        )
        result["case_id"] = req.case_id
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Financial forensics failed: {str(e)}")

@router.post("/spatial/profile")
async def run_geographic_profiling(req: GeographicProfileRequest):
    """Computes Rossmo's Jeopardy Probability Surface over crime sites."""
    try:
        result = calculate_geographic_profile(
            crime_sites=req.crime_sites or [],
            grid_size=req.grid_size,
            buffer_radius_km=req.buffer_radius_km,
            decay_exponent=req.decay_exponent
        )
        result["case_id"] = req.case_id
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Geographic profiling failed: {str(e)}")
