-- @module M6
-- @version 1.0
-- @description Chronological timeline of everything recorded for an entity.
-- @variant default
SELECT a.occurred_at, a.item_type, a.ref AS record_ref, a.description,
       o.ref AS other_entity_ref, o.display_name AS other_entity_name,
       l.ref AS location_ref, l.display_name AS location_name,
       a.evidence_ref, a.validity_status::text AS validity_status
FROM v_activity a
LEFT JOIN entities o ON o.case_id = a.case_id AND o.entity_id = a.other_entity_id
LEFT JOIN entities l ON l.case_id = a.case_id AND l.entity_id = a.location_id
WHERE a.case_id = %(case_id)s::bigint AND a.entity_id = %(entity_id)s::bigint
  AND (%(include_historical)s::boolean OR a.validity_status = 'SUPPORTED')
  AND (%(start_time)s::timestamptz IS NULL OR a.occurred_at >= %(start_time)s::timestamptz)
  AND (%(end_time)s::timestamptz   IS NULL OR a.occurred_at <= %(end_time)s::timestamptz)
ORDER BY a.occurred_at, a.ref
LIMIT coalesce(%(result_limit)s::int, 500)
