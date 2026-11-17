-- =====================================================================
-- CrimeMind — 005_engine.sql
-- SQL question/module registry (SRS 8.5, 8.35), query audit (8.31),
-- activity log (20.3), correlation rules and results (9.32-9.36),
-- investigator reviews (20.4), reports (21), finding retirement (5.23).
-- =====================================================================

-- ---------- registry ----------
CREATE TABLE sql_modules (
  module_id   text PRIMARY KEY,                 -- M1 .. M18
  file_name   text NOT NULL,
  version     text NOT NULL,
  description text NOT NULL,
  status      text NOT NULL DEFAULT 'APPROVED' CHECK (status IN ('APPROVED','RETIRED'))
);

CREATE TABLE investigation_questions (
  question_id     text PRIMARY KEY,             -- Q1 .. Q40
  display_text    text NOT NULL,
  category        text NOT NULL,
  module_id       text NOT NULL REFERENCES sql_modules(module_id),
  variant         text NOT NULL DEFAULT 'default',
  required_params text[] NOT NULL DEFAULT '{}',
  optional_params text[] NOT NULL DEFAULT '{}',
  fixed_params    jsonb  NOT NULL DEFAULT '{}'::jsonb,
  version         text NOT NULL DEFAULT '1.0',
  status          text NOT NULL DEFAULT 'APPROVED' CHECK (status IN ('APPROVED','RETIRED'))
);

-- ---------- query audit ----------
CREATE TABLE query_audit (
  query_exec_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  executed_at    timestamptz NOT NULL DEFAULT clock_timestamp(),
  user_name      text   NOT NULL,
  case_id        bigint REFERENCES cases(case_id),
  question_id    text,
  module_id      text,
  module_version text,
  params         jsonb  NOT NULL DEFAULT '{}'::jsonb,
  status         text   NOT NULL CHECK (status IN ('OK','EMPTY','ERROR','DENIED','INVALID')),
  result_count   integer,
  duration_ms    integer,
  error          text
);
CREATE INDEX idx_query_audit_case ON query_audit(case_id, executed_at);
CREATE TRIGGER trg_query_audit_immutable BEFORE UPDATE OR DELETE ON query_audit
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- ---------- activity log (API-level events) ----------
CREATE TABLE activity_log (
  audit_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  occurred_at  timestamptz NOT NULL DEFAULT clock_timestamp(),
  user_name    text,
  case_id      bigint,
  action_type  text NOT NULL,
  request_id   text,
  object_type  text,
  object_id    text,
  status       text NOT NULL DEFAULT 'SUCCESS',
  details      jsonb NOT NULL DEFAULT '{}'::jsonb,
  version_meta jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX idx_activity_case ON activity_log(case_id, occurred_at);
CREATE TRIGGER trg_activity_immutable BEFORE UPDATE OR DELETE ON activity_log
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- Only this definer function can write activity rows (audit integrity, SEC-007).
CREATE OR REPLACE FUNCTION log_activity(
  p_user text, p_case bigint, p_action text, p_request text,
  p_object_type text, p_object_id text, p_status text,
  p_details jsonb, p_version jsonb
) RETURNS bigint
LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
  INSERT INTO activity_log(user_name, case_id, action_type, request_id, object_type,
                           object_id, status, details, version_meta)
  VALUES (p_user, p_case, p_action, p_request, p_object_type, p_object_id,
          coalesce(p_status,'SUCCESS'), coalesce(p_details,'{}'), coalesce(p_version,'{}'))
  RETURNING audit_id
$$;

-- ---------- correlation ----------
CREATE TABLE correlation_rules (
  rule_id               text NOT NULL,
  version               integer NOT NULL,
  rule_name             text NOT NULL,
  description           text NOT NULL,
  rule_type             text NOT NULL,
  thresholds            jsonb NOT NULL DEFAULT '{}'::jsonb,
  input_types           text[] NOT NULL,
  output_classification text NOT NULL CHECK (output_classification IN ('FACT','CORRELATED','INFERRED')),
  status                text NOT NULL DEFAULT 'APPROVED' CHECK (status IN ('APPROVED','RETIRED')),
  PRIMARY KEY (rule_id, version)
);

CREATE TABLE correlation_runs (
  run_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id      bigint NOT NULL REFERENCES cases(case_id),
  started_at   timestamptz NOT NULL DEFAULT clock_timestamp(),
  run_by       text NOT NULL,
  rule_versions jsonb NOT NULL,           -- {"TEMPORAL_SPATIAL_001": 1, ...}
  result_count integer NOT NULL DEFAULT 0,
  UNIQUE (case_id, run_id)
);
CREATE INDEX idx_corr_runs_case ON correlation_runs(case_id, run_id DESC);

CREATE TABLE correlations (
  correlation_id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id         bigint NOT NULL,
  run_id          bigint NOT NULL,
  ref             text   NOT NULL,                 -- C-0001 within a run
  rule_id         text   NOT NULL,
  rule_version    integer NOT NULL,
  result_type     text   NOT NULL CHECK (result_type IN ('FACT','CORRELATED','INFERRED')),
  entity_a        bigint NOT NULL,
  entity_b        bigint,
  location_id     bigint,
  thresholds      jsonb  NOT NULL DEFAULT '{}'::jsonb,
  window_start    timestamptz,
  window_end      timestamptz,
  confidence      numeric(3,2),
  summary         text   NOT NULL,
  uncertainties   text[] NOT NULL DEFAULT '{}',
  source_records  jsonb  NOT NULL,                 -- [{"type":"obs","ref":"OBS-12"}, ...]
  finding_key     text,
  FOREIGN KEY (case_id, run_id)      REFERENCES correlation_runs(case_id, run_id),
  FOREIGN KEY (rule_id, rule_version) REFERENCES correlation_rules(rule_id, version),
  FOREIGN KEY (case_id, entity_a)    REFERENCES entities(case_id, entity_id),
  FOREIGN KEY (case_id, entity_b)    REFERENCES entities(case_id, entity_id),
  FOREIGN KEY (case_id, location_id) REFERENCES entities(case_id, entity_id),
  CHECK (source_records <> '[]'::jsonb)            -- never a result without source records (9.35)
);
CREATE INDEX idx_correlations_run ON correlations(case_id, run_id);

CREATE TABLE correlation_evidence (
  case_id        bigint NOT NULL,
  correlation_id bigint NOT NULL REFERENCES correlations(correlation_id),
  evidence_id    bigint NOT NULL,
  PRIMARY KEY (correlation_id, evidence_id),
  FOREIGN KEY (case_id, evidence_id) REFERENCES evidence(case_id, evidence_id)
);

-- ---------- investigator review (20.4): append-only ----------
CREATE TABLE reviews (
  review_id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id     bigint NOT NULL REFERENCES cases(case_id),
  target_type text   NOT NULL CHECK (target_type IN ('FINDING','CORRELATION','AI_ANALYSIS','HYPOTHESIS','REPORT')),
  target_ref  text   NOT NULL,
  decision    text   NOT NULL CHECK (decision IN ('ACCEPTED','REJECTED','CORRECTED','COMMENT')),
  comment     text,
  reviewer    text   NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX idx_reviews_case ON reviews(case_id, created_at);
CREATE TRIGGER trg_reviews_immutable BEFORE UPDATE OR DELETE ON reviews
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- ---------- AI analyses kept for audit / reproducibility (13, NFR-11) ----------
CREATE TABLE ai_analyses (
  analysis_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id       bigint NOT NULL REFERENCES cases(case_id),
  requested_by  text   NOT NULL,
  question      text   NOT NULL,
  provider      text   NOT NULL,
  status        text   NOT NULL CHECK (status IN ('OK','UNAVAILABLE','INVALID')),
  context_sha256 text  NOT NULL,
  output        jsonb,
  problems      jsonb  NOT NULL DEFAULT '[]'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TRIGGER trg_ai_immutable BEFORE UPDATE OR DELETE ON ai_analyses
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- ---------- reports ----------
CREATE TABLE reports (
  report_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id        bigint NOT NULL REFERENCES cases(case_id),
  generated_by   text   NOT NULL,
  generated_at   timestamptz NOT NULL DEFAULT clock_timestamp(),
  scope          jsonb  NOT NULL DEFAULT '{}'::jsonb,
  content        jsonb  NOT NULL,
  content_sha256 text   NOT NULL,
  version_meta   jsonb  NOT NULL DEFAULT '{}'::jsonb
);
CREATE TRIGGER trg_reports_immutable BEFORE UPDATE OR DELETE ON reports
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- ---------- finding retirement ----------
-- A recomputation that finds NO currently-supported basis must not silently
-- delete the finding: it is retired (OUTDATED) with the impact log closed.
ALTER TABLE finding_impact_log ADD COLUMN outcome text
  CHECK (outcome IN ('RECOMPUTED','RETIRED_NO_SUPPORT'));

CREATE OR REPLACE FUNCTION retire_finding(p_case_id bigint, p_finding_id bigint)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_status finding_status;
BEGIN
  SELECT status INTO v_status FROM findings
   WHERE finding_id = p_finding_id AND case_id = p_case_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Finding % not found in case %', p_finding_id, p_case_id; END IF;
  IF v_status <> 'RECOMPUTE_REQUIRED' THEN
    RAISE EXCEPTION 'Only RECOMPUTE_REQUIRED findings can be retired (status is %)', v_status;
  END IF;
  UPDATE findings SET status = 'OUTDATED' WHERE finding_id = p_finding_id;
  UPDATE finding_impact_log
     SET recomputed_at = clock_timestamp(), outcome = 'RETIRED_NO_SUPPORT'
   WHERE affected_finding_id = p_finding_id AND recomputed_at IS NULL;
END $$;

-- record_recomputation: also stamp the outcome
CREATE OR REPLACE FUNCTION mark_recomputed_outcome() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.recomputed_finding_id IS NOT NULL AND NEW.outcome IS NULL THEN
    NEW.outcome := 'RECOMPUTED';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_impact_outcome BEFORE UPDATE ON finding_impact_log
  FOR EACH ROW EXECUTE FUNCTION mark_recomputed_outcome();

-- Findings whose evidence base is entirely SUPPORTED are CURRENT; this view lets
-- the UI show impact queues.
CREATE OR REPLACE VIEW v_evidence_dependents AS
SELECT l.case_id, l.evidence_id, e.ref AS evidence_ref, e.validity_status,
       f.finding_id, f.finding_key, f.version, f.status AS finding_status
FROM finding_evidence_links l
JOIN evidence e ON e.evidence_id = l.evidence_id AND e.case_id = l.case_id
JOIN findings f ON f.finding_id = l.finding_id AND f.case_id = l.case_id
WHERE f.status <> 'OUTDATED';

CREATE TRIGGER trg_audit_reviews AFTER INSERT ON reviews
  FOR EACH ROW EXECUTE FUNCTION audit_row_change('review_id');
