"""Forensic Statement Credibility & Cognitive Load NLP Endpoints.
Provides REST APIs for Criteria-Based Content Analysis (CBCA), Statement Validity
Assessment (SVA), linguistic deception screening, and tactical interrogation assistance.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .. import audit, db
from ..deps import Ctx, get_ctx, load_case
from ..nlp.cbca_analyzer import CBCAAnalyzer
from ..nlp.schemas import StatementAnalysisRequest, StatementAnalysisResult
from ..sql_engine import jsonable

log = logging.getLogger("crimemind.nlp")
router = APIRouter(prefix="/api/cases/{case_ref}/nlp", tags=["statement-nlp"])
analyzer = CBCAAnalyzer()


# Default seeded statements for initial case exploration
DEFAULT_STATEMENTS = {
    "CASE-2026-001": [
        {
            "subject_name": "Karan Bhatt",
            "subject_role": "SUSPECT",
            "subject_entity_ref": "P-002",
            "statement_title": "Interrogation Transcript #1: Initial Alibi",
            "interviewer_name": "Inspector S. Deshmukh",
            "transcript_text": (
                "To be completely honest with you, I was nowhere near Green Park that evening. "
                "As God is my witness, I came straight back to my flat around eight thirty. "
                "I think I watched some television and had dinner alone. "
                "Around nine or ten, I might have gone out just for five minutes to buy cigarettes near the metro station, "
                "but I never set foot inside the central gazebo or near the lawn. "
                "Then next thing I know, the morning sirens woke me up. "
                "I would never hurt Meera in a million years, I swear on everything. "
                "The weapon? I don't own any weapon, someone must have planted that idea. "
                "You can ask anyone, I am an honest person."
            ),
        },
        {
            "subject_name": "Ananya Sharma",
            "subject_role": "WITNESS",
            "subject_entity_ref": "P-003",
            "statement_title": "Witness Deposition: Gazebo Perimeter Sighting",
            "interviewer_name": "Det. R. Roy",
            "transcript_text": (
                "I was walking my dog near the east pavilion around ten past ten. "
                "It was freezing cold and the ground was slick with wet leaves from the afternoon drizzle. "
                "The halogen park lamps were flickering, making that awful humming sound like they always do. "
                "I heard loud muffled shouting near the gazebo—a man's voice, very harsh and agitated, "
                "then a sharp thud like something heavy hit the wooden benches. "
                "I got scared and pulled my dog back into the shadowed path. "
                "I saw a tall man wearing a dark hooded jacket sprint past towards the south gate. "
                "Wait, actually, he stumbled over the curb first before running, almost dropping his phone. "
                "I can't be sure of his face because the hood was pulled low, but he was definitely carrying something metallic."
            ),
        },
    ],
    "CASE-2026-002": [
        {
            "subject_name": "Vikrant Rane",
            "subject_role": "SUSPECT",
            "subject_entity_ref": "P-P01",
            "statement_title": "Night Security Officer Interrogation",
            "interviewer_name": "Investigator T. Khan",
            "transcript_text": (
                "I arrived for duty at the gatehouse around eight PM as scheduled. "
                "Everything was totally normal and quiet. "
                "I conducted the regular perimeter rounds at nine PM and eleven PM according to protocol. "
                "I didn't see or hear any unauthorized vehicles or persons. "
                "I was inside the booth watching the monitor banks the entire time between ten and midnight. "
                "If the rear gate lock was cut, it must have been done from outside by professional burglars before my shift started. "
                "To be totally candid, I never heard an alarm trip. "
                "I am just a hardworking guard doing my job, I have no reason to lie to you."
            ),
        },
    ],
}


def _fetch_case_evidence_and_entities(conn, case_id: int):
    evidence = conn.execute(
        "SELECT evidence_id, ref, evidence_type, description, source, validity_status FROM evidence WHERE case_id = %s",
        (case_id,),
    ).fetchall()
    entities = conn.execute(
        "SELECT entity_id, ref, entity_type, display_name FROM entities WHERE case_id = %s",
        (case_id,),
    ).fetchall()
    return evidence, entities


@router.get("/statements")
def list_statements(case_ref: str, ctx: Ctx = Depends(get_ctx)):
    """Lists all statements for the case, seeding realistic transcripts if empty."""
    case_row = load_case(ctx, case_ref)
    case_id = case_row["case_id"]

    rows = ctx.conn.execute(
        """
        SELECT statement_id, case_id, subject_name, subject_role, subject_entity_ref,
               interviewer_name, interrogation_timestamp, statement_title, transcript_text,
               credibility_score, credibility_band, cognitive_load_score, metrics,
               sentence_analyses, tactical_questions, created_at
        FROM case_statements
        WHERE case_id = %s
        ORDER BY created_at ASC
        """,
        (case_id,),
    ).fetchall()

    if not rows and case_ref in DEFAULT_STATEMENTS:
        # Seed default realistic statements with full CBCA analysis
        evidence, entities = _fetch_case_evidence_and_entities(ctx.conn, case_id)
        seeded_rows = []

        for item in DEFAULT_STATEMENTS[case_ref]:
            analysis = analyzer.analyze(
                text=item["transcript_text"],
                case_evidence=evidence,
                case_entities=entities,
                subject_name=item["subject_name"],
            )

            row = ctx.conn.execute(
                """
                INSERT INTO case_statements (
                    case_id, subject_entity_ref, subject_name, subject_role,
                    interviewer_name, statement_title, transcript_text,
                    credibility_score, credibility_band, cognitive_load_score,
                    metrics, sentence_analyses, tactical_questions
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    case_id,
                    item.get("subject_entity_ref"),
                    item["subject_name"],
                    item["subject_role"],
                    item["interviewer_name"],
                    item["statement_title"],
                    item["transcript_text"],
                    analysis["credibility_score"],
                    analysis["credibility_band"],
                    analysis["cognitive_load_score"],
                    json.dumps(analysis["metrics"]),
                    json.dumps(analysis["sentence_analyses"]),
                    json.dumps(analysis["tactical_questions"]),
                ),
            ).fetchone()
            seeded_rows.append(row)

        ctx.conn.commit()
        rows = seeded_rows

    return jsonable(rows)


@router.post("/analyze-statement")
def analyze_statement(
    case_ref: str,
    req: StatementAnalysisRequest,
    ctx: Ctx = Depends(get_ctx),
):
    """Executes live CBCA credibility and cognitive load analysis on arbitrary text."""
    case_row = load_case(ctx, case_ref)
    case_id = case_row["case_id"]

    evidence, entities = _fetch_case_evidence_and_entities(ctx.conn, case_id)
    analysis = analyzer.analyze(
        text=req.transcript_text,
        case_evidence=evidence,
        case_entities=entities,
        subject_name=req.subject_name,
    )

    audit.log_activity(
        ctx.user,
        case_id,
        "STATEMENT_ANALYZED",
        ctx.request_id,
        details={
            "subject": req.subject_name,
            "credibility_score": analysis["credibility_score"],
            "credibility_band": analysis["credibility_band"],
        },
    )

    return {
        "subject_name": req.subject_name,
        "subject_role": req.subject_role,
        "subject_entity_ref": req.subject_entity_ref,
        "statement_title": req.statement_title or f"Statement of {req.subject_name}",
        "transcript_text": req.transcript_text,
        "credibility_score": analysis["credibility_score"],
        "credibility_band": analysis["credibility_band"],
        "cognitive_load_score": analysis["cognitive_load_score"],
        "metrics": analysis["metrics"],
        "sentence_analyses": analysis["sentence_analyses"],
        "tactical_questions": analysis["tactical_questions"],
        "radar_dimensions": analysis["radar_dimensions"],
    }


@router.post("/statements")
def save_statement(
    case_ref: str,
    req: StatementAnalysisRequest,
    ctx: Ctx = Depends(get_ctx),
):
    """Analyzes and permanently saves an interrogation transcript into the case record."""
    case_row = load_case(ctx, case_ref)
    case_id = case_row["case_id"]

    evidence, entities = _fetch_case_evidence_and_entities(ctx.conn, case_id)
    analysis = analyzer.analyze(
        text=req.transcript_text,
        case_evidence=evidence,
        case_entities=entities,
        subject_name=req.subject_name,
    )

    title = req.statement_title or f"Interrogation: {req.subject_name}"

    row = ctx.conn.execute(
        """
        INSERT INTO case_statements (
            case_id, subject_entity_ref, subject_name, subject_role,
            interviewer_name, statement_title, transcript_text,
            credibility_score, credibility_band, cognitive_load_score,
            metrics, sentence_analyses, tactical_questions
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            case_id,
            req.subject_entity_ref,
            req.subject_name,
            req.subject_role,
            req.interviewer_name,
            title,
            req.transcript_text,
            analysis["credibility_score"],
            analysis["credibility_band"],
            analysis["cognitive_load_score"],
            json.dumps(analysis["metrics"]),
            json.dumps(analysis["sentence_analyses"]),
            json.dumps(analysis["tactical_questions"]),
        ),
    ).fetchone()

    ctx.conn.commit()
    return jsonable(row)


class FlagContradictionRequest(BaseModel):
    statement_id: Optional[int] = None
    subject_name: str
    evidence_ref: str
    contradiction_text: str
    action: str = "FLAG_FINDING"  # 'FLAG_FINDING' or 'CHALLENGE_EVIDENCE'


@router.post("/flag-contradiction")
def flag_contradiction(
    case_ref: str,
    req: FlagContradictionRequest,
    ctx: Ctx = Depends(get_ctx),
):
    """Integrates with the EVLM engine: records a statement contradiction finding or challenges evidence."""
    case_row = load_case(ctx, case_ref)
    case_id = case_row["case_id"]

    summary = f"Statement contradiction for {req.subject_name}: {req.contradiction_text}"

    # Insert a real finding into the findings table
    finding_row = ctx.conn.execute(
        """
        INSERT INTO findings (
            case_id, ref, title, description, status, confidence_score
        ) VALUES (
            %s,
            'FND-NLP-' || to_char(now(), 'HH24MISS'),
            %s,
            %s,
            'PRELIMINARY',
            0.88
        ) RETURNING finding_id, ref
        """,
        (case_id, f"Contradiction in statement of {req.subject_name}", summary),
    ).fetchone()

    # If action is CHALLENGE_EVIDENCE, mark evidence validity status
    if req.action == "CHALLENGE_EVIDENCE" and req.evidence_ref:
        ctx.conn.execute(
            """
            UPDATE evidence
            SET validity_status = 'CHALLENGED'
            WHERE case_id = %s AND ref = %s
            """,
            (case_id, req.evidence_ref),
        )

    ctx.conn.commit()

    audit.log_activity(
        ctx.user,
        case_id,
        "STATEMENT_CONTRADICTION_FLAGGED",
        ctx.request_id,
        details={"finding_ref": finding_row["ref"], "evidence_ref": req.evidence_ref},
    )

    return {
        "status": "SUCCESS",
        "finding": finding_row,
        "message": f"Recorded finding {finding_row['ref']} and updated case EVLM ledger.",
    }
