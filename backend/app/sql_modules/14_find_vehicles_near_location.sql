-- @module M14
-- @version 1.0
-- @description Vehicle observations at locations; entities associated with a vehicle; repeated vehicle presence.
-- @variant near_location
SELECT v.entity_id AS vehicle_id, v.ref AS vehicle_ref, v.display_name AS vehicle_name,
       v.attributes->>'plate' AS plate,
       min(o.observed_from) AS first_seen, max(o.observed_to) AS last_seen, count(*) AS observation_count,
       array_agg(DISTINCT o.ref ORDER BY o.ref) AS record_refs,
       array_remove(array_agg(DISTINCT o.evidence_ref), NULL) AS evidence_refs
FROM v_obs o
JOIN entities v ON v.case_id = o.case_id AND v.entity_id = o.subject_entity_id AND v.entity_type = 'VEHICLE'
WHERE o.case_id = %(case_id)s::bigint AND o.location_entity_id = %(location_id)s::bigint
  AND (%(include_historical)s::boolean OR o.validity_status = 'SUPPORTED')
  AND (%(start_time)s::timestamptz IS NULL OR o.observed_to   >= %(start_time)s::timestamptz)
  AND (%(end_time)s::timestamptz   IS NULL OR o.observed_from <= %(end_time)s::timestamptz)
GROUP BY v.entity_id, v.ref, v.display_name, v.attributes
ORDER BY first_seen
LIMIT coalesce(%(result_limit)s::int, 200)
-- @variant associated_entities
SELECT p.entity_id, p.ref AS entity_ref, p.display_name, r.rel_type, r.valid_from, r.valid_to,
       r.ref AS relationship_ref, r.evidence_ref, r.validity_status::text AS validity_status
FROM v_rels r
JOIN entities p ON p.case_id = r.case_id AND p.entity_id = r.entity_a AND p.entity_type = 'PERSON'
WHERE r.case_id = %(case_id)s::bigint AND r.entity_b = %(vehicle_id)s::bigint
  AND r.rel_type IN ('OWNS','USES')
  AND (%(include_historical)s::boolean OR r.validity_status = 'SUPPORTED')
  AND (%(start_time)s::timestamptz IS NULL OR r.valid_to   IS NULL OR r.valid_to   >= %(start_time)s::timestamptz)
  AND (%(end_time)s::timestamptz   IS NULL OR r.valid_from IS NULL OR r.valid_from <= %(end_time)s::timestamptz)
ORDER BY r.valid_from NULLS FIRST
-- @variant repeated
SELECT v.entity_id AS vehicle_id, v.ref AS vehicle_ref, v.display_name AS vehicle_name,
       count(*) AS observation_count, count(DISTINCT o.location_entity_id) AS distinct_locations,
       min(o.observed_from) AS first_seen, max(o.observed_to) AS last_seen,
       array_agg(DISTINCT o.ref ORDER BY o.ref) AS record_refs,
       'Repeated presence is not by itself suspicious.'::text AS note
FROM v_obs o
JOIN entities v ON v.case_id = o.case_id AND v.entity_id = o.subject_entity_id AND v.entity_type = 'VEHICLE'
WHERE o.case_id = %(case_id)s::bigint
  AND (%(location_id)s::bigint IS NULL OR o.location_entity_id = %(location_id)s::bigint)
  AND (%(include_historical)s::boolean OR o.validity_status = 'SUPPORTED')
  AND (%(start_time)s::timestamptz IS NULL OR o.observed_to   >= %(start_time)s::timestamptz)
  AND (%(end_time)s::timestamptz   IS NULL OR o.observed_from <= %(end_time)s::timestamptz)
GROUP BY v.entity_id, v.ref, v.display_name
HAVING count(*) >= coalesce(%(min_count)s::int, 2)
ORDER BY observation_count DESC
LIMIT coalesce(%(result_limit)s::int, 100)
