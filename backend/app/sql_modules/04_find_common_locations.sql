-- @module M4
-- @version 1.0
-- @description Locations visited by two entities; visit frequency per entity and location.
-- @variant shared
SELECT l.entity_id AS location_id, l.ref AS location_ref, l.display_name AS location_name,
       count(*) FILTER (WHERE o.subject_entity_id = %(entity_id_1)s::bigint) AS visits_entity_1,
       count(*) FILTER (WHERE o.subject_entity_id = %(entity_id_2)s::bigint) AS visits_entity_2,
       array_agg(DISTINCT o.ref ORDER BY o.ref) AS record_refs,
       array_remove(array_agg(DISTINCT o.evidence_ref), NULL) AS evidence_refs
FROM v_obs o
JOIN entities l ON l.case_id = o.case_id AND l.entity_id = o.location_entity_id
WHERE o.case_id = %(case_id)s::bigint
  AND o.subject_entity_id IN (%(entity_id_1)s::bigint, %(entity_id_2)s::bigint)
  AND (%(include_historical)s::boolean OR o.validity_status = 'SUPPORTED')
  AND (%(start_time)s::timestamptz IS NULL OR o.observed_to   >= %(start_time)s::timestamptz)
  AND (%(end_time)s::timestamptz   IS NULL OR o.observed_from <= %(end_time)s::timestamptz)
GROUP BY l.entity_id, l.ref, l.display_name
HAVING count(DISTINCT o.subject_entity_id) = 2
ORDER BY (count(*)) DESC
LIMIT coalesce(%(result_limit)s::int, 200)
-- @variant frequency
SELECT p.entity_id, p.ref AS entity_ref, p.display_name,
       l.ref AS location_ref, l.display_name AS location_name,
       count(*) AS visit_count, min(o.observed_from) AS first_seen, max(o.observed_to) AS last_seen,
       array_agg(DISTINCT o.ref ORDER BY o.ref) AS record_refs
FROM v_obs o
JOIN entities p ON p.case_id = o.case_id AND p.entity_id = o.subject_entity_id AND p.entity_type = 'PERSON'
JOIN entities l ON l.case_id = o.case_id AND l.entity_id = o.location_entity_id
WHERE o.case_id = %(case_id)s::bigint
  AND (%(entity_id)s::bigint IS NULL OR o.subject_entity_id = %(entity_id)s::bigint)
  AND (%(location_id)s::bigint IS NULL OR o.location_entity_id = %(location_id)s::bigint)
  AND (%(include_historical)s::boolean OR o.validity_status = 'SUPPORTED')
  AND (%(start_time)s::timestamptz IS NULL OR o.observed_to   >= %(start_time)s::timestamptz)
  AND (%(end_time)s::timestamptz   IS NULL OR o.observed_from <= %(end_time)s::timestamptz)
GROUP BY p.entity_id, p.ref, p.display_name, l.ref, l.display_name
ORDER BY visit_count DESC, p.ref
LIMIT coalesce(%(result_limit)s::int, 200)
