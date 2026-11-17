-- =====================================================================
-- CrimeMind — 003_audit.sql
-- Write-audit triggers (SRS 5.29, 20.3). Read-access auditing is NOT done
-- here; it belongs in FastAPI middleware or pgAudit.
-- =====================================================================
CREATE OR REPLACE FUNCTION audit_row_change() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  v_new jsonb := CASE WHEN TG_OP <> 'DELETE' THEN to_jsonb(NEW) END;
  v_old jsonb := CASE WHEN TG_OP <> 'INSERT' THEN to_jsonb(OLD) END;
  v_row jsonb := coalesce(v_new, v_old);
BEGIN
  INSERT INTO audit_log (actor, case_id, action_type, object_type, object_id, old_data, new_data)
  VALUES (current_actor(),
          nullif(v_row->>'case_id','')::bigint,
          TG_OP, TG_TABLE_NAME,
          v_row->>TG_ARGV[0],            -- primary-key column name
          v_old, v_new);
  RETURN NULL;
END $$;

CREATE TRIGGER trg_audit_cases      AFTER INSERT OR UPDATE OR DELETE ON cases
  FOR EACH ROW EXECUTE FUNCTION audit_row_change('case_id');
CREATE TRIGGER trg_audit_evidence   AFTER INSERT OR UPDATE OR DELETE ON evidence
  FOR EACH ROW EXECUTE FUNCTION audit_row_change('evidence_id');
CREATE TRIGGER trg_audit_vevents    AFTER INSERT ON evidence_validity_events
  FOR EACH ROW EXECUTE FUNCTION audit_row_change('event_id');
CREATE TRIGGER trg_audit_findings   AFTER INSERT OR UPDATE ON findings
  FOR EACH ROW EXECUTE FUNCTION audit_row_change('finding_id');
CREATE TRIGGER trg_audit_hypotheses AFTER INSERT OR UPDATE ON hypotheses
  FOR EACH ROW EXECUTE FUNCTION audit_row_change('hypothesis_id');
CREATE TRIGGER trg_audit_access     AFTER INSERT OR DELETE ON user_case_access
  FOR EACH ROW EXECUTE FUNCTION audit_row_change('user_id');
