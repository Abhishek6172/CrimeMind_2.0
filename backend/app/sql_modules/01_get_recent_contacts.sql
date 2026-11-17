-- @module M1
-- @version 1.0
-- @description Recent contacts: who communicated with an entity, how often, when.
-- @variant contacts
SELECT e.entity_id, e.ref AS entity_ref, e.display_name,
       count(*) AS communication_count,
       min(c.occurred_at) AS first_at, max(c.occurred_at) AS last_at,
       array_agg(DISTINCT c.ref ORDER BY c.ref) AS record_refs,
       array_remove(array_agg(DISTINCT c.evidence_ref), NULL) AS evidence_refs,
       array_agg(DISTINCT c.validity_status::text) AS validity_states
FROM v_comms c
JOIN entities e ON e.case_id = c.case_id
 AND e.entity_id = CASE WHEN c.sender_id = %(entity_id)s::bigint THEN c.receiver_id ELSE c.sender_id END
WHERE c.case_id = %(case_id)s::bigint
  AND (c.sender_id = %(entity_id)s::bigint OR c.receiver_id = %(entity_id)s::bigint)
  AND (%(include_historical)s::boolean OR c.validity_status = 'SUPPORTED')
  AND (%(start_time)s::timestamptz IS NULL OR c.occurred_at >= %(start_time)s::timestamptz)
  AND (%(end_time)s::timestamptz   IS NULL OR c.occurred_at <= %(end_time)s::timestamptz)
GROUP BY e.entity_id, e.ref, e.display_name
ORDER BY last_at DESC
LIMIT coalesce(%(result_limit)s::int, 200)
-- @variant frequency
SELECT e.entity_id, e.ref AS entity_ref, e.display_name,
       count(*) AS communication_count,
       min(c.occurred_at) AS first_at, max(c.occurred_at) AS last_at,
       array_agg(DISTINCT c.ref ORDER BY c.ref) AS record_refs,
       array_remove(array_agg(DISTINCT c.evidence_ref), NULL) AS evidence_refs
FROM v_comms c
JOIN entities e ON e.case_id = c.case_id
 AND e.entity_id = CASE WHEN c.sender_id = %(entity_id)s::bigint THEN c.receiver_id ELSE c.sender_id END
WHERE c.case_id = %(case_id)s::bigint
  AND (c.sender_id = %(entity_id)s::bigint OR c.receiver_id = %(entity_id)s::bigint)
  AND (%(include_historical)s::boolean OR c.validity_status = 'SUPPORTED')
  AND (%(start_time)s::timestamptz IS NULL OR c.occurred_at >= %(start_time)s::timestamptz)
  AND (%(end_time)s::timestamptz   IS NULL OR c.occurred_at <= %(end_time)s::timestamptz)
GROUP BY e.entity_id, e.ref, e.display_name
ORDER BY communication_count DESC, last_at DESC
LIMIT coalesce(%(result_limit)s::int, 200)
-- @variant pairs
SELECT a.ref AS entity_a_ref, a.display_name AS entity_a_name,
       b.ref AS entity_b_ref, b.display_name AS entity_b_name,
       count(*) AS communication_count,
       min(c.occurred_at) AS first_at, max(c.occurred_at) AS last_at,
       array_agg(DISTINCT c.ref ORDER BY c.ref) AS record_refs,
       array_remove(array_agg(DISTINCT c.evidence_ref), NULL) AS evidence_refs
FROM v_comms c
JOIN entities a ON a.case_id = c.case_id AND a.entity_id = LEAST(c.sender_id, c.receiver_id)
JOIN entities b ON b.case_id = c.case_id AND b.entity_id = GREATEST(c.sender_id, c.receiver_id)
WHERE c.case_id = %(case_id)s::bigint
  AND (%(include_historical)s::boolean OR c.validity_status = 'SUPPORTED')
  AND (%(start_time)s::timestamptz IS NULL OR c.occurred_at >= %(start_time)s::timestamptz)
  AND (%(end_time)s::timestamptz   IS NULL OR c.occurred_at <= %(end_time)s::timestamptz)
GROUP BY a.ref, a.display_name, b.ref, b.display_name
HAVING count(*) >= coalesce(%(min_count)s::int, 3)
ORDER BY communication_count DESC
LIMIT coalesce(%(result_limit)s::int, 200)
