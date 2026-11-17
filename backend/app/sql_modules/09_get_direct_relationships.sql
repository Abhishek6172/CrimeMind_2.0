-- @module M9
-- @version 1.0
-- @description Explicitly recorded relationships of an entity (FACT).
-- @variant default
SELECT r.ref AS relationship_ref, r.rel_type,
       o.entity_id AS other_entity_id, o.ref AS other_entity_ref, o.display_name AS other_entity_name,
       (r.entity_a = %(entity_id)s::bigint) AS entity_is_subject,
       r.strength, r.valid_from, r.valid_to,
       r.evidence_ref, r.validity_status::text AS validity_status
FROM v_rels r
JOIN entities o ON o.case_id = r.case_id
 AND o.entity_id = CASE WHEN r.entity_a = %(entity_id)s::bigint THEN r.entity_b ELSE r.entity_a END
WHERE r.case_id = %(case_id)s::bigint
  AND (r.entity_a = %(entity_id)s::bigint OR r.entity_b = %(entity_id)s::bigint)
  AND (%(include_historical)s::boolean OR r.validity_status = 'SUPPORTED')
ORDER BY r.strength DESC NULLS LAST, r.ref
LIMIT coalesce(%(result_limit)s::int, 200)
