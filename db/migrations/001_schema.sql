-- =====================================================================
-- CrimeMind — 001_schema.sql
-- Data model for the Database + EVLM slice (SRS v6.0, Sections 3.6-3.12,
-- 4.9-4.13, 5.x). PostgreSQL 14+.
--
-- Conventions
--   * Every case-scoped table carries case_id; cross-table references use
--     composite (case_id, id) foreign keys so a record can never point at
--     another case's data (SRS 5.34, NFR-ING-005).
--   * "ref" columns are human-readable case-local codes (E1, F-17 ...).
--   * Nothing here ever deletes history (SRS CON-005, 5.43.1).
-- =====================================================================

-- ---------- Controlled vocabularies (SRS 3.9 Table 23, 3.10) ----------
CREATE TYPE validity_status  AS ENUM ('SUPPORTED','CHALLENGED','INVALIDATED','SUPERSEDED');

CREATE TYPE validity_reason  AS ENUM (
  'TIMESTAMP_ERROR','DEVICE_FAULT','SOURCE_RETRACTION',
  'CONTRADICTED_BY_STRONGER_SOURCE','CORRECTED_RECORD',
  'OWNERSHIP_TRANSFER','MANUAL_REVIEW','CORROBORATED');

-- Documented triggers of Table 25 plus the human override path (FR-035).
CREATE TYPE validity_trigger AS ENUM (
  'DOCUMENTED_CONTRADICTION','CONFIRMED_INVALIDITY',
  'REPLACEMENT_RECORD','CORROBORATION','MANUAL_OVERRIDE');

CREATE TYPE finding_status   AS ENUM ('CURRENT','RECOMPUTE_REQUIRED','OUTDATED');

CREATE TYPE user_role        AS ENUM (
  'INVESTIGATOR','SUPERVISOR','ADMINISTRATOR','DBA','AI_ML_DEVELOPER','RESEARCHER');

-- ---------- Users, cases, access (SRS 3.3-3.5, 5.4, 5.28) ----------
CREATE TABLE users (
  user_id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  username       text      NOT NULL UNIQUE,
  password_hash  text      NOT NULL,           -- hash only, never plaintext (SRS 17.2)
  role           user_role NOT NULL,
  is_active      boolean   NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE cases (
  case_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_ref    text   NOT NULL UNIQUE,
  title       text   NOT NULL,
  status      text   NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','UNDER_REVIEW','CLOSED')),
  created_by  bigint REFERENCES users(user_id),
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE user_case_access (
  user_id  bigint NOT NULL REFERENCES users(user_id),
  case_id  bigint NOT NULL REFERENCES cases(case_id),
  granted_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, case_id)
);

-- ---------- Type registries (case-independent model) ----------
CREATE TABLE entity_types (
  entity_type text PRIMARY KEY,
  description text
);

CREATE TABLE event_types (
  event_type  text PRIMARY KEY,
  description text
);

-- reliability_weight is a MANUALLY ASSIGNED, rule-based heuristic weight.
-- It is not a probability that the evidence is true (SRS FR-024, 5.14).
CREATE TABLE evidence_types (
  evidence_type      text PRIMARY KEY,
  description        text,
  reliability_weight numeric(3,2) NOT NULL CHECK (reliability_weight BETWEEN 0 AND 1)
);

-- ---------- Entities and events (SRS 5.5-5.8) ----------
CREATE TABLE entities (
  entity_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id      bigint NOT NULL REFERENCES cases(case_id),
  entity_type  text   NOT NULL REFERENCES entity_types(entity_type),
  ref          text   NOT NULL,
  display_name text   NOT NULL,
  attributes   jsonb  NOT NULL DEFAULT '{}'::jsonb,
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (case_id, ref),
  UNIQUE (case_id, entity_id)
);

CREATE TABLE events (
  event_id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id            bigint NOT NULL REFERENCES cases(case_id),
  event_type         text   NOT NULL REFERENCES event_types(event_type),
  ref                text   NOT NULL,
  occurred_at        timestamptz,
  location_entity_id bigint,
  description        text,
  attributes         jsonb  NOT NULL DEFAULT '{}'::jsonb,
  created_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (case_id, ref),
  UNIQUE (case_id, event_id),
  FOREIGN KEY (case_id, location_entity_id) REFERENCES entities(case_id, entity_id)
);

-- ---------- Evidence (SRS 5.9-5.15) ----------
CREATE TABLE evidence (
  evidence_id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id                bigint NOT NULL REFERENCES cases(case_id),
  ref                    text   NOT NULL,
  evidence_type          text   NOT NULL REFERENCES evidence_types(evidence_type),
  source                 text   NOT NULL,          -- e.g. GPS-17, CAM-014
  source_record_id       text,
  evidence_timestamp     timestamptz,
  description            text,
  provenance             jsonb  NOT NULL DEFAULT '{}'::jsonb,
  reliability_score      numeric(3,2) CHECK (reliability_score BETWEEN 0 AND 1),
  validity_status        validity_status NOT NULL DEFAULT 'SUPPORTED',
  replaced_by_evidence_id bigint,
  -- Pointer to bulky derived content kept in MongoDB (documents, CV output).
  -- Example: {"store":"mongo","collection":"document_segments","id":"..."}
  content_ref            jsonb,
  processing_status      text   NOT NULL DEFAULT 'STORED',
  created_at             timestamptz NOT NULL DEFAULT now(),
  UNIQUE (case_id, ref),
  UNIQUE (case_id, evidence_id),
  FOREIGN KEY (case_id, replaced_by_evidence_id) REFERENCES evidence(case_id, evidence_id),
  CHECK ((validity_status = 'SUPERSEDED') = (replaced_by_evidence_id IS NOT NULL))
);
CREATE INDEX idx_evidence_case_status ON evidence(case_id, validity_status);

CREATE TABLE evidence_entities (
  case_id     bigint NOT NULL,
  evidence_id bigint NOT NULL,
  entity_id   bigint NOT NULL,
  PRIMARY KEY (evidence_id, entity_id),
  FOREIGN KEY (case_id, evidence_id) REFERENCES evidence(case_id, evidence_id),
  FOREIGN KEY (case_id, entity_id)   REFERENCES entities(case_id, entity_id)
);
CREATE INDEX idx_evidence_entities_entity ON evidence_entities(entity_id);

CREATE TABLE evidence_events (
  case_id     bigint NOT NULL,
  evidence_id bigint NOT NULL,
  event_id    bigint NOT NULL,
  PRIMARY KEY (evidence_id, event_id),
  FOREIGN KEY (case_id, evidence_id) REFERENCES evidence(case_id, evidence_id),
  FOREIGN KEY (case_id, event_id)    REFERENCES events(case_id, event_id)
);

-- ---------- EVLM: rules and event store (SRS 4.10, 4.11, 5.16-5.18) ----------
CREATE TABLE evlm_transition_rules (
  current_status             validity_status  NOT NULL,
  trigger_code               validity_trigger NOT NULL,
  new_status                 validity_status  NOT NULL,
  allowed_reasons            validity_reason[] NOT NULL,
  requires_triggering_evidence boolean NOT NULL DEFAULT false,
  PRIMARY KEY (current_status, trigger_code, new_status)   -- MANUAL_OVERRIDE has several targets
);

CREATE TABLE evidence_validity_events (
  event_id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id                bigint NOT NULL,
  evidence_id            bigint NOT NULL,
  previous_status        validity_status  NOT NULL,
  new_status             validity_status  NOT NULL,
  trigger_code           validity_trigger NOT NULL,
  triggering_evidence_id bigint,
  reason_code            validity_reason  NOT NULL,
  justification          text,
  changed_at             timestamptz NOT NULL DEFAULT clock_timestamp(),
  changed_by             text NOT NULL CHECK (btrim(changed_by) <> ''),
  CHECK (previous_status <> new_status),
  FOREIGN KEY (case_id, evidence_id)            REFERENCES evidence(case_id, evidence_id),
  FOREIGN KEY (case_id, triggering_evidence_id) REFERENCES evidence(case_id, evidence_id)
);
CREATE INDEX idx_validity_events_evidence ON evidence_validity_events(evidence_id, changed_at);

-- ---------- Findings, dependencies, versions (SRS 5.20-5.23) ----------
CREATE TABLE findings (
  finding_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id        bigint NOT NULL REFERENCES cases(case_id),
  finding_key    text   NOT NULL,                 -- stable across versions
  version        integer NOT NULL CHECK (version >= 1),
  statement      text   NOT NULL,
  classification text   NOT NULL
    CHECK (classification IN ('RECORDED_FACT','CORRELATED','INFERRED','AI_INFERRED','UNCERTAIN')),
  status         finding_status NOT NULL DEFAULT 'CURRENT',
  generated_by   text   NOT NULL,
  method         text,
  generated_at   timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE (case_id, finding_key, version),
  UNIQUE (case_id, finding_id)
);
-- At most one live (non-OUTDATED) version per finding.
CREATE UNIQUE INDEX uq_findings_one_live_version
  ON findings(case_id, finding_key) WHERE status <> 'OUTDATED';

CREATE TABLE finding_evidence_links (
  case_id     bigint NOT NULL,
  finding_id  bigint NOT NULL,
  evidence_id bigint NOT NULL,
  PRIMARY KEY (finding_id, evidence_id),
  FOREIGN KEY (case_id, finding_id)  REFERENCES findings(case_id, finding_id),
  FOREIGN KEY (case_id, evidence_id) REFERENCES evidence(case_id, evidence_id)
);
CREATE INDEX idx_fel_evidence ON finding_evidence_links(evidence_id);

-- Evidence Change -> Affected Finding -> Recomputation -> New Finding (FR-047)
CREATE TABLE finding_impact_log (
  impact_id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id               bigint NOT NULL,
  validity_event_id     bigint NOT NULL REFERENCES evidence_validity_events(event_id),
  affected_finding_id   bigint NOT NULL,
  status_before         finding_status NOT NULL,
  logged_at             timestamptz NOT NULL DEFAULT clock_timestamp(),
  recomputed_finding_id bigint,
  recomputed_at         timestamptz,
  FOREIGN KEY (case_id, affected_finding_id)   REFERENCES findings(case_id, finding_id),
  FOREIGN KEY (case_id, recomputed_finding_id) REFERENCES findings(case_id, finding_id)
);
CREATE INDEX idx_impact_open ON finding_impact_log(affected_finding_id) WHERE recomputed_at IS NULL;

-- ---------- Hypotheses (SRS 5.24, FR-086..FR-090) ----------
CREATE TABLE hypotheses (
  hypothesis_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id       bigint NOT NULL REFERENCES cases(case_id),
  ref           text   NOT NULL,
  title         text   NOT NULL,
  status        text   NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','SUPPORTED','REJECTED')),
  needs_review  boolean NOT NULL DEFAULT false,   -- set by impact propagation
  created_by    text   NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (case_id, ref),
  UNIQUE (case_id, hypothesis_id)
);

CREATE TABLE hypothesis_findings (
  case_id       bigint NOT NULL,
  hypothesis_id bigint NOT NULL,
  finding_id    bigint NOT NULL,   -- any version; resolved via finding_key at propagation time
  PRIMARY KEY (hypothesis_id, finding_id),
  FOREIGN KEY (case_id, hypothesis_id) REFERENCES hypotheses(case_id, hypothesis_id),
  FOREIGN KEY (case_id, finding_id)    REFERENCES findings(case_id, finding_id)
);

CREATE TABLE hypothesis_evidence (
  case_id       bigint NOT NULL,
  hypothesis_id bigint NOT NULL,
  evidence_id   bigint NOT NULL,
  stance        text   NOT NULL CHECK (stance IN ('SUPPORTS','CONTRADICTS')),
  PRIMARY KEY (hypothesis_id, evidence_id),
  FOREIGN KEY (case_id, hypothesis_id) REFERENCES hypotheses(case_id, hypothesis_id),
  FOREIGN KEY (case_id, evidence_id)   REFERENCES evidence(case_id, evidence_id)
);

-- ---------- Audit (SRS 5.29, 20.3, SEC-007) ----------
CREATE TABLE audit_log (
  audit_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  actor       text   NOT NULL,
  case_id     bigint,
  action_type text   NOT NULL,          -- INSERT / UPDATE / DELETE on object_type
  object_type text   NOT NULL,
  object_id   text   NOT NULL,
  old_data    jsonb,
  new_data    jsonb
);
CREATE INDEX idx_audit_case_time ON audit_log(case_id, occurred_at);
CREATE INDEX idx_audit_object ON audit_log(object_type, object_id);
