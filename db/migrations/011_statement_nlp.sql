-- ============================================================================
-- Migration 011: Forensic Statement Credibility & Cognitive Load NLP Platform
-- Implements Criteria-Based Content Analysis (CBCA), Statement Validity 
-- Assessment (SVA), Linguistic Deception Markers, and Interrogation Intelligence.
-- ============================================================================

CREATE TABLE IF NOT EXISTS case_statements (
    statement_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    case_id BIGINT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    subject_entity_ref TEXT,
    subject_name TEXT NOT NULL,
    subject_role TEXT NOT NULL DEFAULT 'SUSPECT', -- 'SUSPECT', 'WITNESS', 'VICTIM', 'PERSON_OF_INTEREST'
    interviewer_name TEXT NOT NULL DEFAULT 'Lead Investigator',
    interrogation_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    statement_title TEXT NOT NULL,
    transcript_text TEXT NOT NULL,
    credibility_score NUMERIC(5, 2) NOT NULL DEFAULT 50.0,
    credibility_band TEXT NOT NULL DEFAULT 'AMBIGUOUS', -- 'HIGH_VERACITY', 'AMBIGUOUS', 'DECEPTIVE_INDICATORS'
    cognitive_load_score NUMERIC(5, 2) NOT NULL DEFAULT 50.0,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    sentence_analyses JSONB NOT NULL DEFAULT '[]'::jsonb,
    tactical_questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_case_statements_case ON case_statements(case_id);
CREATE INDEX IF NOT EXISTS idx_case_statements_role ON case_statements(subject_role);
