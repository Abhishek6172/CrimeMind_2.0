from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SentenceAnalysis(BaseModel):
    sentence_idx: int
    text: str
    word_count: int
    credibility_score: float
    cognitive_load_score: float
    status: str  # 'VERACIOUS', 'NEUTRAL', 'STRAINED', 'DECEPTIVE', 'CONTRADICTORY'
    flags: List[str] = []
    sensory_words: List[str] = []
    hedges: List[str] = []
    evidence_conflicts: List[Dict[str, Any]] = []


class TacticalQuestion(BaseModel):
    category: str  # 'SENSORY_PROBE', 'COGNITIVE_OVERLOAD', 'REVERSE_CHRONOLOGY', 'EVIDENCE_DISCREPANCY'
    question: str
    rationale: str
    expected_truthful_response: str
    expected_deceptive_reaction: str
    relevant_evidence_ref: Optional[str] = None


class StatementAnalysisRequest(BaseModel):
    transcript_text: str
    subject_name: str
    subject_role: str = "SUSPECT"  # 'SUSPECT', 'WITNESS', 'VICTIM', 'PERSON_OF_INTEREST'
    subject_entity_ref: Optional[str] = None
    statement_title: Optional[str] = None
    interviewer_name: Optional[str] = "Lead Investigator"


class StatementAnalysisResult(BaseModel):
    statement_id: Optional[int] = None
    subject_name: str
    subject_role: str
    subject_entity_ref: Optional[str] = None
    statement_title: str
    transcript_text: str
    credibility_score: float
    credibility_band: str  # 'HIGH_VERACITY', 'AMBIGUOUS', 'DECEPTIVE_INDICATORS'
    cognitive_load_score: float
    metrics: Dict[str, Any]
    sentence_analyses: List[SentenceAnalysis]
    tactical_questions: List[TacticalQuestion]
    radar_dimensions: Dict[str, float]
    created_at: Optional[datetime] = None
