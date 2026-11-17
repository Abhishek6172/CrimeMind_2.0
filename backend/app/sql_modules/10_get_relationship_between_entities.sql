-- @module M10
-- @version 1.0
-- @description Directly recorded relationship(s) between two entities.
-- @variant default
SELECT r.ref AS relationship_ref, r.rel_type, a.ref AS entity_a_ref, a.display_name AS entity_a_name,
       b.ref AS entity_b_ref, b.display_name AS entity_b_name, r.strength, r.valid_from, r.valid_to,
       r.evidence_ref, r.validity_status::text AS validity_status
FROM v_rels r
JOIN entities a ON a.case_id = r.case_id AND a.entity_id = r.entity_a
JOIN entities b ON b.case_id = r.case_id AND b.entity_id = r.entity_b
WHERE r.case_id = %(case_id)s::bigint
  AND ((r.entity_a = %(entity_id_1)s::bigint AND r.entity_b = %(entity_id_2)s::bigint)
    OR (r.entity_a = %(entity_id_2)s::bigint AND r.entity_b = %(entity_id_1)s::bigint))
  AND (%(include_historical)s::boolean OR r.validity_status = 'SUPPORTED')
ORDER BY r.ref
