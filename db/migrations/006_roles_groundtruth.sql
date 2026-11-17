-- =====================================================================
-- CrimeMind — 006_roles_groundtruth.sql
-- Least-privilege application role (SRS 17.3, SEC-00x) and the isolated
-- evaluation-only ground-truth schema (SRS 6.12, 17.7).
--
-- The role `cm_app` is created by scripts/init_db.py (password from the
-- environment, never from source). It can read operational tables, insert
-- new records, and change evidence validity ONLY through SECURITY DEFINER
-- functions. It has no access whatsoever to schema `gt`.
-- =====================================================================

-- ---------- ground truth: evaluation only ----------
CREATE SCHEMA gt;
REVOKE ALL ON SCHEMA gt FROM PUBLIC;

CREATE TABLE gt.entity_roles (
  case_ref   text NOT NULL,
  entity_ref text NOT NULL,
  role       text NOT NULL CHECK (role IN ('VICTIM','PERPETRATOR','ACCOMPLICE','RED_HERRING','WITNESS','BYSTANDER')),
  notes      text,
  PRIMARY KEY (case_ref, entity_ref)
);

-- Intended evidence-evolution steps (SRS 6.14, 6.30). The generator does NOT
-- write these into the investigation tables; they are applied by a scenario
-- runner through change_validity() so CrimeMind's own EVLM produces the result.
CREATE TABLE gt.scenario_events (
  scenario_id            text NOT NULL,
  step                   integer NOT NULL,
  case_ref               text NOT NULL,
  description            text NOT NULL,
  evidence_ref           text NOT NULL,
  payload                jsonb NOT NULL DEFAULT '{}'::jsonb,   -- evidence/records that ARRIVE in this step (applied first)
  triggering_evidence_ref text,
  expected_status        validity_status NOT NULL,
  trigger_code           validity_trigger NOT NULL,
  reason_code            validity_reason NOT NULL,
  expected_affected_finding_keys text[] NOT NULL DEFAULT '{}',
  PRIMARY KEY (scenario_id, step)
);

CREATE TABLE gt.expected_leads (
  case_ref   text NOT NULL,
  entity_ref text NOT NULL,
  rank_hint  integer,
  PRIMARY KEY (case_ref, entity_ref)
);

-- ---------- SECURITY DEFINER hardening of the EVLM entry points ----------
ALTER FUNCTION audit_row_change()            SECURITY DEFINER SET search_path = public;
ALTER FUNCTION apply_validity_event()        SECURITY DEFINER SET search_path = public;
ALTER FUNCTION change_validity(bigint,bigint,validity_status,validity_trigger,validity_reason,text,bigint,text)
                                             SECURITY DEFINER SET search_path = public;
ALTER FUNCTION record_recomputation(bigint,bigint,text,text,text,text,bigint[])
                                             SECURITY DEFINER SET search_path = public;
ALTER FUNCTION clear_hypothesis_review(bigint,bigint)
                                             SECURITY DEFINER SET search_path = public;

-- ---------- grants for the application role ----------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cm_app') THEN
    RAISE EXCEPTION 'Role cm_app must exist before running this migration (see scripts/init_db.py)';
  END IF;
END $$;

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM cm_app;
GRANT USAGE ON SCHEMA public TO cm_app;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO cm_app;

-- new records the application may create
GRANT INSERT ON
  entities, events, evidence, event_entities, evidence_entities, evidence_events,
  relationships, communications, transactions, location_observations,
  findings, finding_evidence_links,
  hypotheses, hypothesis_findings, hypothesis_evidence,
  reviews, reports, ai_analyses,
  correlation_runs, correlations, correlation_evidence,
  query_audit
TO cm_app;

-- humans may move a hypothesis between OPEN / SUPPORTED / REJECTED
GRANT UPDATE (status, updated_at) ON hypotheses TO cm_app;

-- Deliberately NOT granted: any write to users, cases, user_case_access,
-- evidence_validity_events, audit_log, activity_log, sql_modules,
-- investigation_questions, correlation_rules, finding_impact_log, or findings (UPDATE).
-- Those change only via SECURITY DEFINER functions or the admin tooling.

GRANT EXECUTE ON FUNCTION log_activity(text,bigint,text,text,text,text,text,jsonb,jsonb) TO cm_app;
GRANT EXECUTE ON FUNCTION retire_finding(bigint,bigint) TO cm_app;
