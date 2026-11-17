-- =====================================================================
-- CrimeMind — 007_activity_view.sql
-- A single normalized, current-belief-aware activity stream used by the
-- timeline, gap and incident modules (M6, M7, M8).
-- Each communication / transaction appears once per participant so
-- "everything entity X did" is a single predicate.
-- =====================================================================
CREATE OR REPLACE VIEW v_activity AS
  SELECT case_id, 'OBSERVATION'::text AS item_type, ref, observed_from AS occurred_at,
         subject_entity_id AS entity_id, NULL::bigint AS other_entity_id,
         location_entity_id AS location_id,
         (source_kind || ' observation from ' || source) AS description,
         evidence_ref, validity_status
  FROM v_obs
  UNION ALL
  SELECT case_id, 'COMMUNICATION', ref, occurred_at, sender_id, receiver_id, NULL::bigint,
         (comm_type || ' sent'), evidence_ref, validity_status
  FROM v_comms
  UNION ALL
  SELECT case_id, 'COMMUNICATION', ref, occurred_at, receiver_id, sender_id, NULL::bigint,
         (comm_type || ' received'), evidence_ref, validity_status
  FROM v_comms
  UNION ALL
  SELECT case_id, 'TRANSACTION', ref, occurred_at, from_entity_id, to_entity_id, location_entity_id,
         (txn_type || ' sent ' || amount::text || ' ' || currency), evidence_ref, validity_status
  FROM v_txns
  UNION ALL
  SELECT case_id, 'TRANSACTION', ref, occurred_at, to_entity_id, from_entity_id, location_entity_id,
         (txn_type || ' received ' || amount::text || ' ' || currency), evidence_ref, validity_status
  FROM v_txns
  UNION ALL
  SELECT ev.case_id, 'EVENT', ev.ref, ev.occurred_at, ee.entity_id, NULL::bigint, ev.location_entity_id,
         coalesce(ev.description, ev.event_type), NULL::text, 'SUPPORTED'::validity_status
  FROM events ev
  JOIN event_entities ee ON ee.case_id = ev.case_id AND ee.event_id = ev.event_id
  WHERE ev.occurred_at IS NOT NULL;

GRANT SELECT ON v_activity TO cm_app;
