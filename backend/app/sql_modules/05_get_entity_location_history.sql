-- @module M5
-- @version 1.0
-- @description Chronological and aggregated location history of an entity.
-- @variant history
SELECT o.ref AS record_ref, l.ref AS location_ref, l.display_name AS location_name,
       o.observed_from, o.observed_to, o.source_kind, o.source,
       o.evidence_ref, o.validity_status::text AS validity_status
FROM v_obs o
JOIN entities l ON l.case_id = o.case_id AND l.entity_id = o.location_entity_id
WHERE o.case_id = %(case_id)s::bigint AND o.subject_entity_id = %(entity_id)s::bigint
  AND (%(include_historical)s::boolean OR o.validity_status = 'SUPPORTED')
  AND (%(start_time)s::timestamptz IS NULL OR o.observed_to   >= %(start_time)s::timestamptz)
  AND (%(end_time)s::timestamptz   IS NULL OR o.observed_from <= %(end_time)s::timestamptz)
ORDER BY o.observed_from
LIMIT coalesce(%(result_limit)s::int, 500)
-- @variant frequency
SELECT l.entity_id AS location_id, l.ref AS location_ref, l.display_name AS location_name,
       count(*) AS visit_count, min(o.observed_from) AS first_seen, max(o.observed_to) AS last_seen,
       array_agg(DISTINCT o.ref ORDER BY o.ref) AS record_refs
FROM v_obs o
JOIN entities l ON l.case_id = o.case_id AND l.entity_id = o.location_entity_id
WHERE o.case_id = %(case_id)s::bigint AND o.subject_entity_id = %(entity_id)s::bigint
  AND (%(include_historical)s::boolean OR o.validity_status = 'SUPPORTED')
  AND (%(start_time)s::timestamptz IS NULL OR o.observed_to   >= %(start_time)s::timestamptz)
  AND (%(end_time)s::timestamptz   IS NULL OR o.observed_from <= %(end_time)s::timestamptz)
GROUP BY l.entity_id, l.ref, l.display_name
ORDER BY visit_count DESC, last_seen DESC
LIMIT coalesce(%(result_limit)s::int, 200)
