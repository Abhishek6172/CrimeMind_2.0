-- @module M2
-- @version 1.0
-- @description Communications between two specified entities.
-- @variant default
SELECT c.ref AS communication_ref, s.ref AS sender_ref, s.display_name AS sender_name,
       r.ref AS receiver_ref, r.display_name AS receiver_name,
       c.comm_type, c.occurred_at, c.duration_sec,
       c.evidence_ref, c.validity_status::text AS validity_status
FROM v_comms c
JOIN entities s ON s.case_id = c.case_id AND s.entity_id = c.sender_id
JOIN entities r ON r.case_id = c.case_id AND r.entity_id = c.receiver_id
WHERE c.case_id = %(case_id)s::bigint
  AND ((c.sender_id = %(entity_id_1)s::bigint AND c.receiver_id = %(entity_id_2)s::bigint)
    OR (c.sender_id = %(entity_id_2)s::bigint AND c.receiver_id = %(entity_id_1)s::bigint))
  AND (%(include_historical)s::boolean OR c.validity_status = 'SUPPORTED')
  AND (%(start_time)s::timestamptz IS NULL OR c.occurred_at >= %(start_time)s::timestamptz)
  AND (%(end_time)s::timestamptz   IS NULL OR c.occurred_at <= %(end_time)s::timestamptz)
ORDER BY c.occurred_at
LIMIT coalesce(%(result_limit)s::int, 500)
