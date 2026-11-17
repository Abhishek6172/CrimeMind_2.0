-- @module M13
-- @version 1.0
-- @description Vehicles recorded as owned/used by an entity, with validity period (historical vs current).
-- @variant default
SELECT v.entity_id AS vehicle_id, v.ref AS vehicle_ref, v.display_name AS vehicle_name,
       v.attributes->>'plate' AS plate, r.rel_type, r.valid_from, r.valid_to,
       (r.valid_to IS NULL OR r.valid_to > now()) AS is_current,
       r.ref AS relationship_ref, r.evidence_ref, r.validity_status::text AS validity_status
FROM v_rels r
JOIN entities v ON v.case_id = r.case_id AND v.entity_id = r.entity_b AND v.entity_type = 'VEHICLE'
WHERE r.case_id = %(case_id)s::bigint AND r.entity_a = %(entity_id)s::bigint
  AND r.rel_type IN ('OWNS','USES')
  AND (%(include_historical)s::boolean OR r.validity_status = 'SUPPORTED')
ORDER BY is_current DESC, r.valid_from NULLS FIRST
