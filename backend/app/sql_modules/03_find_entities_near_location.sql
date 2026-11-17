-- @module M3
-- @version 1.0
-- @description Entities recorded at a location; co-presence between entities.
-- @variant present
SELECT e.entity_id, e.ref AS entity_ref, e.display_name,
       min(o.observed_from) AS first_seen, max(o.observed_to) AS last_seen,
       count(*) AS observation_count,
       array_agg(DISTINCT o.source ORDER BY o.source) AS sources,
       array_agg(DISTINCT o.ref ORDER BY o.ref) AS record_refs,
       array_remove(array_agg(DISTINCT o.evidence_ref), NULL) AS evidence_refs
FROM v_obs o
JOIN entities e ON e.case_id = o.case_id AND e.entity_id = o.subject_entity_id AND e.entity_type = 'PERSON'
WHERE o.case_id = %(case_id)s::bigint
  AND o.location_entity_id = %(location_id)s::bigint
  AND (%(include_historical)s::boolean OR o.validity_status = 'SUPPORTED')
  AND (%(start_time)s::timestamptz IS NULL OR o.observed_to   >= %(start_time)s::timestamptz)
  AND (%(end_time)s::timestamptz   IS NULL OR o.observed_from <= %(end_time)s::timestamptz)
GROUP BY e.entity_id, e.ref, e.display_name
ORDER BY first_seen
LIMIT coalesce(%(result_limit)s::int, 200)
-- @variant copresence
SELECT a.ref AS entity_a_ref, a.display_name AS entity_a_name,
       b.ref AS entity_b_ref, b.display_name AS entity_b_name,
       l.ref AS location_ref, l.display_name AS location_name,
       GREATEST(oa.observed_from, ob.observed_from) AS overlap_start,
       LEAST(oa.observed_to, ob.observed_to) AS overlap_end,
       oa.ref AS record_ref_a, ob.ref AS record_ref_b,
       oa.evidence_ref AS evidence_ref_a, ob.evidence_ref AS evidence_ref_b
FROM v_obs oa
JOIN v_obs ob ON ob.case_id = oa.case_id AND ob.location_entity_id = oa.location_entity_id
  AND ob.subject_entity_id > oa.subject_entity_id
  AND oa.observed_from <= ob.observed_to   + make_interval(mins => coalesce(%(window_minutes)s::int, 0))
  AND ob.observed_from <= oa.observed_to   + make_interval(mins => coalesce(%(window_minutes)s::int, 0))
JOIN entities a ON a.case_id = oa.case_id AND a.entity_id = oa.subject_entity_id AND a.entity_type = 'PERSON'
JOIN entities b ON b.case_id = ob.case_id AND b.entity_id = ob.subject_entity_id AND b.entity_type = 'PERSON'
JOIN entities l ON l.case_id = oa.case_id AND l.entity_id = oa.location_entity_id
WHERE oa.case_id = %(case_id)s::bigint
  AND (%(location_id)s::bigint IS NULL OR oa.location_entity_id = %(location_id)s::bigint)
  AND (%(include_historical)s::boolean OR (oa.validity_status = 'SUPPORTED' AND ob.validity_status = 'SUPPORTED'))
  AND (%(start_time)s::timestamptz IS NULL OR oa.observed_to >= %(start_time)s::timestamptz)
  AND (%(end_time)s::timestamptz   IS NULL OR oa.observed_from <= %(end_time)s::timestamptz)
ORDER BY overlap_start, a.ref, b.ref
LIMIT coalesce(%(result_limit)s::int, 300)
