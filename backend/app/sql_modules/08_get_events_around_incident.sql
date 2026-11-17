-- @module M8
-- @version 1.1
-- @description Activity before / after / around a specified incident event.
-- @variant before
SELECT a.occurred_at, a.item_type, a.ref AS record_ref, e.ref AS entity_ref, e.display_name AS entity_name,
       a.description, l.ref AS location_ref, l.display_name AS location_name,
       a.evidence_ref, a.validity_status::text AS validity_status
FROM events inc
JOIN v_activity a ON a.case_id = inc.case_id
 AND a.occurred_at >= inc.occurred_at - make_interval(mins => coalesce(%(window_minutes)s::int, 60))
 AND a.occurred_at <  inc.occurred_at
JOIN entities e ON e.case_id = a.case_id AND e.entity_id = a.entity_id AND e.entity_type = 'PERSON'
LEFT JOIN entities l ON l.case_id = a.case_id AND l.entity_id = a.location_id
WHERE inc.case_id = %(case_id)s::bigint AND inc.event_id = %(event_id)s::bigint
  AND (%(include_historical)s::boolean OR a.validity_status = 'SUPPORTED')
  AND a.ref <> inc.ref
ORDER BY a.occurred_at DESC, a.ref
LIMIT coalesce(%(result_limit)s::int, 300)
-- @variant after
SELECT a.occurred_at, a.item_type, a.ref AS record_ref, e.ref AS entity_ref, e.display_name AS entity_name,
       a.description, l.ref AS location_ref, l.display_name AS location_name,
       a.evidence_ref, a.validity_status::text AS validity_status
FROM events inc
JOIN v_activity a ON a.case_id = inc.case_id
 AND a.occurred_at >  inc.occurred_at
 AND a.occurred_at <= inc.occurred_at + make_interval(mins => coalesce(%(window_minutes)s::int, 60))
JOIN entities e ON e.case_id = a.case_id AND e.entity_id = a.entity_id AND e.entity_type = 'PERSON'
LEFT JOIN entities l ON l.case_id = a.case_id AND l.entity_id = a.location_id
WHERE inc.case_id = %(case_id)s::bigint AND inc.event_id = %(event_id)s::bigint
  AND (%(include_historical)s::boolean OR a.validity_status = 'SUPPORTED')
  AND a.ref <> inc.ref
ORDER BY a.occurred_at, a.ref
LIMIT coalesce(%(result_limit)s::int, 300)
-- @variant around
SELECT e.entity_id, e.ref AS entity_ref, e.display_name,
       coalesce(bool_or(a.location_id = inc.location_entity_id), false) AS recorded_at_incident_location,
       count(*) AS record_count, min(a.occurred_at) AS first_record, max(a.occurred_at) AS last_record,
       array_agg(DISTINCT a.ref ORDER BY a.ref) AS record_refs,
       array_remove(array_agg(DISTINCT a.evidence_ref), NULL) AS evidence_refs
FROM events inc
JOIN v_activity a ON a.case_id = inc.case_id
 AND a.occurred_at BETWEEN inc.occurred_at - make_interval(mins => coalesce(%(window_minutes)s::int, 60))
                       AND inc.occurred_at + make_interval(mins => coalesce(%(window_minutes)s::int, 60))
JOIN entities e ON e.case_id = a.case_id AND e.entity_id = a.entity_id AND e.entity_type = 'PERSON'
WHERE inc.case_id = %(case_id)s::bigint AND inc.event_id = %(event_id)s::bigint
  AND (%(include_historical)s::boolean OR a.validity_status = 'SUPPORTED')
  AND a.ref <> inc.ref
GROUP BY e.entity_id, e.ref, e.display_name
ORDER BY recorded_at_incident_location DESC, record_count DESC
LIMIT coalesce(%(result_limit)s::int, 200)
