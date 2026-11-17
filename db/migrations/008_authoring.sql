-- =====================================================================
-- CrimeMind — 008_authoring.sql
-- Case creation / access management (definer functions: cm_app cannot write
-- cases or user_case_access directly), case notes, and a data-change log so
-- correlation staleness also notices new records that carry no evidence row.
-- =====================================================================

CREATE TABLE case_data_log (
  log_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id    bigint NOT NULL REFERENCES cases(case_id),
  kind       text   NOT NULL,
  ref        text,
  changed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX idx_case_data_log ON case_data_log(case_id, changed_at);
CREATE TRIGGER trg_case_data_log_immutable BEFORE UPDATE OR DELETE ON case_data_log
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

CREATE TABLE case_notes (
  note_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id     bigint NOT NULL REFERENCES cases(case_id),
  target_type text   NOT NULL CHECK (target_type IN ('CASE','ENTITY','EVIDENCE','FINDING','HYPOTHESIS')),
  target_ref  text   NOT NULL,
  body        text   NOT NULL CHECK (length(btrim(body)) BETWEEN 1 AND 4000),
  tags        text[] NOT NULL DEFAULT '{}',
  bookmarked  boolean NOT NULL DEFAULT false,
  author      text   NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_case_notes ON case_notes(case_id, target_type, target_ref);
-- Notes are part of the investigation record: append-only (corrections are new notes).
CREATE TRIGGER trg_case_notes_immutable BEFORE UPDATE OR DELETE ON case_notes
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- ---------- case creation and access (supervisor / administrator only) ----------
CREATE OR REPLACE FUNCTION _acting_user() RETURNS users
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public AS $$
DECLARE u users;
BEGIN
  SELECT * INTO u FROM users WHERE username = current_setting('app.user', true) AND is_active;
  IF NOT FOUND THEN RAISE EXCEPTION 'No authenticated acting user'; END IF;
  RETURN u;
END $$;

CREATE OR REPLACE FUNCTION create_case(p_title text) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE u users; n int; v_id bigint; v_ref text;
BEGIN
  u := _acting_user();
  IF u.role NOT IN ('SUPERVISOR','ADMINISTRATOR') THEN RAISE EXCEPTION 'Only a supervisor or administrator can create a case'; END IF;
  IF p_title IS NULL OR length(btrim(p_title)) < 3 OR length(p_title) > 200 THEN RAISE EXCEPTION 'Title must be 3-200 characters'; END IF;
  LOCK TABLE cases IN SHARE ROW EXCLUSIVE MODE;
  SELECT coalesce(max(substring(case_ref from '(\d+)$')::int), 0) + 1 INTO n
    FROM cases WHERE case_ref LIKE 'CASE-' || extract(year FROM now())::int || '-%';
  v_ref := format('CASE-%s-%s', extract(year FROM now())::int, lpad(n::text, 3, '0'));
  INSERT INTO cases(case_ref, title, created_by) VALUES (v_ref, btrim(p_title), u.user_id) RETURNING case_id INTO v_id;
  INSERT INTO user_case_access(user_id, case_id) VALUES (u.user_id, v_id);
  RETURN v_ref;
END $$;

CREATE OR REPLACE FUNCTION grant_case_access(p_case_ref text, p_username text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE u users; t users; c cases;
BEGIN
  u := _acting_user();
  IF u.role NOT IN ('SUPERVISOR','ADMINISTRATOR') THEN RAISE EXCEPTION 'Only a supervisor or administrator can manage case access'; END IF;
  SELECT cs.* INTO c FROM cases cs JOIN user_case_access a ON a.case_id = cs.case_id AND a.user_id = u.user_id WHERE cs.case_ref = p_case_ref;
  IF NOT FOUND THEN RAISE EXCEPTION 'No such case, or you do not have access to it'; END IF;
  SELECT * INTO t FROM users WHERE username = p_username AND is_active;
  IF NOT FOUND THEN RAISE EXCEPTION 'No such active user'; END IF;
  INSERT INTO user_case_access(user_id, case_id) VALUES (t.user_id, c.case_id) ON CONFLICT DO NOTHING;
END $$;

CREATE OR REPLACE FUNCTION revoke_case_access(p_case_ref text, p_username text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE u users; t users; c cases;
BEGIN
  u := _acting_user();
  IF u.role NOT IN ('SUPERVISOR','ADMINISTRATOR') THEN RAISE EXCEPTION 'Only a supervisor or administrator can manage case access'; END IF;
  SELECT cs.* INTO c FROM cases cs JOIN user_case_access a ON a.case_id = cs.case_id AND a.user_id = u.user_id WHERE cs.case_ref = p_case_ref;
  IF NOT FOUND THEN RAISE EXCEPTION 'No such case, or you do not have access to it'; END IF;
  SELECT * INTO t FROM users WHERE username = p_username;
  IF NOT FOUND THEN RAISE EXCEPTION 'No such user'; END IF;
  IF t.user_id = u.user_id THEN RAISE EXCEPTION 'You cannot revoke your own access'; END IF;
  DELETE FROM user_case_access WHERE user_id = t.user_id AND case_id = c.case_id;
END $$;

REVOKE ALL ON FUNCTION _acting_user(), create_case(text), grant_case_access(text,text), revoke_case_access(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION create_case(text), grant_case_access(text,text), revoke_case_access(text,text) TO cm_app;
GRANT INSERT ON case_notes, case_data_log TO cm_app;
GRANT SELECT ON case_notes, case_data_log TO cm_app;
