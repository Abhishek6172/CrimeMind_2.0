-- =====================================================================
-- CrimeMind — 002_evlm.sql
-- Evidence Validity Lifecycle Model (SRS 3.9-3.12, 4.10-4.13, FR-030..FR-055)
--
-- Flow:  change_validity() -> evidence_validity_events (append-only)
--        -> trigger applies status to evidence
--        -> trigger propagates impact to findings + hypotheses
--        -> record_recomputation() creates the next finding version
-- Evidence is never deleted; every status change is an event.
-- =====================================================================

-- ---------- helpers ----------
-- Application sets: SELECT set_config('app.user','<username>', false);
CREATE OR REPLACE FUNCTION current_actor() RETURNS text
LANGUAGE sql STABLE AS $$
  SELECT coalesce(nullif(current_setting('app.user', true), ''), session_user::text)
$$;

-- ---------- transition rules (data, not code: SRS Table 25) ----------
INSERT INTO evlm_transition_rules
  (current_status, trigger_code, new_status, allowed_reasons, requires_triggering_evidence) VALUES
 ('SUPPORTED','DOCUMENTED_CONTRADICTION','CHALLENGED',
    ARRAY['TIMESTAMP_ERROR','DEVICE_FAULT','CONTRADICTED_BY_STRONGER_SOURCE','MANUAL_REVIEW']::validity_reason[], false),
 ('SUPPORTED','CONFIRMED_INVALIDITY','INVALIDATED',
    ARRAY['SOURCE_RETRACTION','DEVICE_FAULT','TIMESTAMP_ERROR']::validity_reason[], false),
 ('CHALLENGED','CONFIRMED_INVALIDITY','INVALIDATED',
    ARRAY['TIMESTAMP_ERROR','DEVICE_FAULT','SOURCE_RETRACTION','CONTRADICTED_BY_STRONGER_SOURCE']::validity_reason[], false),
 ('CHALLENGED','CORROBORATION','SUPPORTED',
    ARRAY['CORROBORATED']::validity_reason[], true),
 ('SUPPORTED','REPLACEMENT_RECORD','SUPERSEDED',
    ARRAY['CORRECTED_RECORD','OWNERSHIP_TRANSFER']::validity_reason[], true),
 ('CHALLENGED','REPLACEMENT_RECORD','SUPERSEDED',
    ARRAY['CORRECTED_RECORD','OWNERSHIP_TRANSFER']::validity_reason[], true),
 ('INVALIDATED','REPLACEMENT_RECORD','SUPERSEDED',
    ARRAY['CORRECTED_RECORD','OWNERSHIP_TRANSFER']::validity_reason[], true),
 -- Human override (FR-035): supervisor/administrator only, justification mandatory.
 ('SUPPORTED','MANUAL_OVERRIDE','CHALLENGED',  ARRAY['MANUAL_REVIEW']::validity_reason[], false),
 ('SUPPORTED','MANUAL_OVERRIDE','INVALIDATED', ARRAY['MANUAL_REVIEW']::validity_reason[], false),
 ('CHALLENGED','MANUAL_OVERRIDE','SUPPORTED',  ARRAY['MANUAL_REVIEW']::validity_reason[], false),
 ('CHALLENGED','MANUAL_OVERRIDE','INVALIDATED',ARRAY['MANUAL_REVIEW']::validity_reason[], false),
 ('INVALIDATED','MANUAL_OVERRIDE','SUPPORTED', ARRAY['MANUAL_REVIEW']::validity_reason[], false),
 ('INVALIDATED','MANUAL_OVERRIDE','CHALLENGED',ARRAY['MANUAL_REVIEW']::validity_reason[], false);
-- No rows leave SUPERSEDED: it is terminal.

-- ---------- reliability default + evidence integrity ----------
CREATE OR REPLACE FUNCTION validate_evidence() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF NEW.validity_status <> 'SUPPORTED' OR NEW.replaced_by_evidence_id IS NOT NULL THEN
      RAISE EXCEPTION 'New evidence must start SUPPORTED; use change_validity() for later changes';
    END IF;
    IF NEW.reliability_score IS NULL THEN
      SELECT reliability_weight INTO NEW.reliability_score
      FROM evidence_types WHERE evidence_type = NEW.evidence_type;
    END IF;
  ELSIF TG_OP = 'UPDATE' THEN
    -- Status columns may only change through the EVLM event path.
    IF (NEW.validity_status IS DISTINCT FROM OLD.validity_status
        OR NEW.replaced_by_evidence_id IS DISTINCT FROM OLD.replaced_by_evidence_id)
       AND coalesce(current_setting('cm.evlm_apply', true), '') <> 'on' THEN
      RAISE EXCEPTION 'validity_status can only be changed via change_validity()';
    END IF;
    IF NEW.case_id <> OLD.case_id OR NEW.ref <> OLD.ref
       OR NEW.evidence_type <> OLD.evidence_type OR NEW.source <> OLD.source
       OR NEW.evidence_timestamp IS DISTINCT FROM OLD.evidence_timestamp THEN
      RAISE EXCEPTION 'Evidence identity/provenance fields are immutable; supersede the record instead';
    END IF;
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER trg_validate_evidence
BEFORE INSERT OR UPDATE ON evidence
FOR EACH ROW EXECUTE FUNCTION validate_evidence();

-- Append-only guard (CON-005): no DELETE, and no UPDATE on event/log tables.
CREATE OR REPLACE FUNCTION forbid_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% on % is not allowed (append-only / history-preserving)', TG_OP, TG_TABLE_NAME;
END $$;

CREATE TRIGGER trg_evidence_no_delete   BEFORE DELETE ON evidence
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_findings_no_delete   BEFORE DELETE ON findings
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_vevents_immutable    BEFORE UPDATE OR DELETE ON evidence_validity_events
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_audit_immutable      BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- ---------- change_validity(): the single entry point ----------
CREATE OR REPLACE FUNCTION change_validity(
  p_case_id               bigint,
  p_evidence_id           bigint,
  p_new_status            validity_status,
  p_trigger               validity_trigger,
  p_reason                validity_reason,
  p_justification         text   DEFAULT NULL,
  p_triggering_evidence_id bigint DEFAULT NULL,
  p_actor                 text   DEFAULT NULL
) RETURNS bigint                      -- the new validity event_id
LANGUAGE plpgsql AS $$
DECLARE
  v_actor   text := coalesce(nullif(btrim(p_actor), ''), current_actor());
  v_user    users%ROWTYPE;
  v_current validity_status;
  v_rule    evlm_transition_rules%ROWTYPE;
  v_event   bigint;
BEGIN
  -- Actor must be an active user with access to this case.
  SELECT * INTO v_user FROM users WHERE username = v_actor AND is_active;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Unknown or inactive actor: %', v_actor;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM user_case_access
                 WHERE user_id = v_user.user_id AND case_id = p_case_id) THEN
    RAISE EXCEPTION 'Actor % has no access to case %', v_actor, p_case_id;
  END IF;

  -- Lock the evidence row so concurrent changes serialize.
  SELECT validity_status INTO v_current
  FROM evidence WHERE evidence_id = p_evidence_id AND case_id = p_case_id
  FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Evidence % not found in case %', p_evidence_id, p_case_id;
  END IF;

  SELECT * INTO v_rule FROM evlm_transition_rules
  WHERE current_status = v_current AND trigger_code = p_trigger AND new_status = p_new_status;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Transition % -> % via % is not permitted by the EVLM rules',
      v_current, p_new_status, p_trigger;
  END IF;
  IF NOT (p_reason = ANY (v_rule.allowed_reasons)) THEN
    RAISE EXCEPTION 'Reason % is not valid for % -> % via %',
      p_reason, v_current, p_new_status, p_trigger;
  END IF;

  IF (v_rule.requires_triggering_evidence OR p_reason = 'CONTRADICTED_BY_STRONGER_SOURCE')
     AND p_triggering_evidence_id IS NULL THEN
    RAISE EXCEPTION 'This transition requires a triggering evidence record';
  END IF;
  IF p_triggering_evidence_id IS NOT NULL THEN
    IF p_triggering_evidence_id = p_evidence_id THEN
      RAISE EXCEPTION 'Evidence cannot be its own triggering evidence';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM evidence
                   WHERE evidence_id = p_triggering_evidence_id AND case_id = p_case_id) THEN
      RAISE EXCEPTION 'Triggering evidence % not found in case %', p_triggering_evidence_id, p_case_id;
    END IF;
  END IF;

  IF p_trigger = 'MANUAL_OVERRIDE' THEN
    IF v_user.role NOT IN ('SUPERVISOR','ADMINISTRATOR') THEN
      RAISE EXCEPTION 'Manual override requires SUPERVISOR or ADMINISTRATOR (actor % is %)',
        v_actor, v_user.role;
    END IF;
    IF p_justification IS NULL OR length(btrim(p_justification)) < 10 THEN
      RAISE EXCEPTION 'Manual override requires a written justification (>= 10 characters)';
    END IF;
  END IF;

  INSERT INTO evidence_validity_events
    (case_id, evidence_id, previous_status, new_status, trigger_code,
     triggering_evidence_id, reason_code, justification, changed_by)
  VALUES
    (p_case_id, p_evidence_id, v_current, p_new_status, p_trigger,
     p_triggering_evidence_id, p_reason, p_justification, v_actor)
  RETURNING event_id INTO v_event;
  -- AFTER INSERT trigger below applies the status and propagates impact.
  RETURN v_event;
END $$;

-- ---------- apply status + propagate impact (FR-040..FR-047) ----------
CREATE OR REPLACE FUNCTION apply_validity_event() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  f record;
BEGIN
  PERFORM set_config('cm.evlm_apply', 'on', true);          -- transaction-local
  UPDATE evidence
     SET validity_status = NEW.new_status,
         replaced_by_evidence_id =
           CASE WHEN NEW.new_status = 'SUPERSEDED' THEN NEW.triggering_evidence_id END
   WHERE evidence_id = NEW.evidence_id AND case_id = NEW.case_id;
  PERFORM set_config('cm.evlm_apply', 'off', true);

  -- Findings whose LIVE version rests on this evidence.
  FOR f IN
    SELECT fi.finding_id, fi.finding_key, fi.status
    FROM finding_evidence_links l
    JOIN findings fi ON fi.finding_id = l.finding_id AND fi.case_id = l.case_id
    WHERE l.evidence_id = NEW.evidence_id
      AND l.case_id = NEW.case_id
      AND fi.status <> 'OUTDATED'
  LOOP
    INSERT INTO finding_impact_log
      (case_id, validity_event_id, affected_finding_id, status_before)
    VALUES (NEW.case_id, NEW.event_id, f.finding_id, f.status);

    UPDATE findings SET status = 'RECOMPUTE_REQUIRED'
     WHERE finding_id = f.finding_id AND status = 'CURRENT';

    -- Hypotheses that cite any version of this finding.
    UPDATE hypotheses h SET needs_review = true, updated_at = now()
     WHERE h.case_id = NEW.case_id
       AND h.hypothesis_id IN (
         SELECT hf.hypothesis_id
         FROM hypothesis_findings hf
         JOIN findings fx ON fx.finding_id = hf.finding_id AND fx.case_id = hf.case_id
         WHERE hf.case_id = NEW.case_id AND fx.finding_key = f.finding_key);
  END LOOP;

  -- Hypotheses that cite this evidence directly.
  UPDATE hypotheses h SET needs_review = true, updated_at = now()
   WHERE h.case_id = NEW.case_id
     AND h.hypothesis_id IN (SELECT hypothesis_id FROM hypothesis_evidence
                             WHERE evidence_id = NEW.evidence_id AND case_id = NEW.case_id);
  RETURN NULL;
END $$;

CREATE TRIGGER trg_apply_validity_event
AFTER INSERT ON evidence_validity_events
FOR EACH ROW EXECUTE FUNCTION apply_validity_event();

-- ---------- recomputation: next finding version (FR-045..FR-047) ----------
CREATE OR REPLACE FUNCTION record_recomputation(
  p_case_id        bigint,
  p_old_finding_id bigint,
  p_statement      text,
  p_classification text,
  p_generated_by   text,
  p_method         text,
  p_evidence_ids   bigint[]
) RETURNS bigint                       -- new finding_id
LANGUAGE plpgsql AS $$
DECLARE
  v_old   findings%ROWTYPE;
  v_new   bigint;
  v_eid   bigint;
  v_bad   bigint;
BEGIN
  SELECT * INTO v_old FROM findings
   WHERE finding_id = p_old_finding_id AND case_id = p_case_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Finding % not found in case %', p_old_finding_id, p_case_id; END IF;
  IF v_old.status = 'OUTDATED' THEN
    RAISE EXCEPTION 'Finding % is already outdated; recompute the live version', p_old_finding_id;
  END IF;
  IF p_evidence_ids IS NULL OR cardinality(p_evidence_ids) = 0 THEN
    RAISE EXCEPTION 'A recomputed finding must cite at least one supporting evidence record';
  END IF;

  -- Only currently SUPPORTED evidence may back a new version.
  SELECT e INTO v_bad
  FROM unnest(p_evidence_ids) e
  WHERE NOT EXISTS (SELECT 1 FROM evidence ev
                    WHERE ev.evidence_id = e AND ev.case_id = p_case_id
                      AND ev.validity_status = 'SUPPORTED')
  LIMIT 1;
  IF v_bad IS NOT NULL THEN
    RAISE EXCEPTION 'Evidence % is not SUPPORTED in case %; it cannot back a finding', v_bad, p_case_id;
  END IF;

  UPDATE findings SET status = 'OUTDATED' WHERE finding_id = v_old.finding_id;   -- frees the live slot

  INSERT INTO findings
    (case_id, finding_key, version, statement, classification, status, generated_by, method)
  VALUES
    (p_case_id, v_old.finding_key, v_old.version + 1, p_statement, p_classification,
     'CURRENT', p_generated_by, p_method)
  RETURNING finding_id INTO v_new;

  FOREACH v_eid IN ARRAY p_evidence_ids LOOP
    INSERT INTO finding_evidence_links (case_id, finding_id, evidence_id)
    VALUES (p_case_id, v_new, v_eid) ON CONFLICT DO NOTHING;
  END LOOP;

  UPDATE finding_impact_log
     SET recomputed_finding_id = v_new, recomputed_at = clock_timestamp()
   WHERE affected_finding_id = v_old.finding_id AND recomputed_at IS NULL;

  RETURN v_new;
END $$;

-- A human clears the review flag; the system never does it automatically.
CREATE OR REPLACE FUNCTION clear_hypothesis_review(p_case_id bigint, p_hypothesis_id bigint)
RETURNS void LANGUAGE sql AS $$
  UPDATE hypotheses SET needs_review = false, updated_at = now()
   WHERE case_id = p_case_id AND hypothesis_id = p_hypothesis_id;
$$;

-- ---------- get_current_belief(): replayable status as of a moment (FR-050..FR-055) ----------
-- as_of NULL => now. Status = last validity event at/before as_of, else the initial SUPPORTED.
CREATE OR REPLACE FUNCTION get_current_belief(p_case_id bigint, p_as_of timestamptz DEFAULT NULL)
RETURNS TABLE (
  evidence_id       bigint,
  ref               text,
  evidence_type     text,
  source            text,
  validity_status   validity_status,
  reliability_score numeric,
  counts_as_support boolean,
  last_changed_at   timestamptz
)
LANGUAGE sql STABLE AS $$
  SELECT e.evidence_id, e.ref, e.evidence_type, e.source,
         coalesce(le.new_status, 'SUPPORTED'::validity_status),
         e.reliability_score,
         coalesce(le.new_status, 'SUPPORTED'::validity_status) = 'SUPPORTED',
         le.changed_at
  FROM evidence e
  LEFT JOIN LATERAL (
    SELECT v.new_status, v.changed_at
    FROM evidence_validity_events v
    WHERE v.evidence_id = e.evidence_id
      AND v.changed_at <= coalesce(p_as_of, 'infinity'::timestamptz)
    ORDER BY v.changed_at DESC, v.event_id DESC
    LIMIT 1
  ) le ON true
  WHERE e.case_id = p_case_id
    AND e.created_at <= coalesce(p_as_of, 'infinity'::timestamptz)
  ORDER BY e.ref
$$;

-- Live findings with a health summary of their evidence base.
CREATE OR REPLACE VIEW v_finding_health AS
SELECT fi.case_id, fi.finding_id, fi.finding_key, fi.version, fi.statement,
       fi.classification, fi.status,
       count(*)                                                    AS evidence_total,
       count(*) FILTER (WHERE e.validity_status = 'SUPPORTED')     AS evidence_supported,
       count(*) FILTER (WHERE e.validity_status <> 'SUPPORTED')    AS evidence_not_supported
FROM findings fi
JOIN finding_evidence_links l ON l.finding_id = fi.finding_id AND l.case_id = fi.case_id
JOIN evidence e               ON e.evidence_id = l.evidence_id AND e.case_id = l.case_id
WHERE fi.status <> 'OUTDATED'
GROUP BY fi.case_id, fi.finding_id, fi.finding_key, fi.version, fi.statement, fi.classification, fi.status;

-- Open work queue: impacts not yet recomputed.
CREATE OR REPLACE VIEW v_open_impacts AS
SELECT i.case_id, i.impact_id, i.affected_finding_id, f.finding_key, f.statement,
       v.evidence_id, v.new_status AS evidence_new_status, v.reason_code, i.logged_at
FROM finding_impact_log i
JOIN findings f ON f.finding_id = i.affected_finding_id AND f.case_id = i.case_id
JOIN evidence_validity_events v ON v.event_id = i.validity_event_id
WHERE i.recomputed_at IS NULL;
