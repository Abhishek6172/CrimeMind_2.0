-- @module M16
-- @version 1.0
-- @description Evidence associated with an entity or an event, with provenance, validity and reliability.
-- @variant entity
SELECT ev.ref AS evidence_ref, ev.evidence_type, ev.source, ev.evidence_timestamp,
       ev.validity_status::text AS validity_status, ev.reliability_score, ev.description,
       coalesce(ev.provenance->>'origin_root', ev.source) AS origin
FROM evidence_entities ee
JOIN evidence ev ON ev.case_id = ee.case_id AND ev.evidence_id = ee.evidence_id
WHERE ee.case_id = %(case_id)s::bigint AND ee.entity_id = %(entity_id)s::bigint
  AND (%(include_historical)s::boolean OR ev.validity_status = 'SUPPORTED')
ORDER BY ev.evidence_timestamp NULLS LAST, ev.ref
LIMIT coalesce(%(result_limit)s::int, 300)
-- @variant event
SELECT ev.ref AS evidence_ref, ev.evidence_type, ev.source, ev.evidence_timestamp,
       ev.validity_status::text AS validity_status, ev.reliability_score, ev.description,
       coalesce(ev.provenance->>'origin_root', ev.source) AS origin
FROM evidence_events ee
JOIN evidence ev ON ev.case_id = ee.case_id AND ev.evidence_id = ee.evidence_id
WHERE ee.case_id = %(case_id)s::bigint AND ee.event_id = %(event_id)s::bigint
  AND (%(include_historical)s::boolean OR ev.validity_status = 'SUPPORTED')
ORDER BY ev.evidence_timestamp NULLS LAST, ev.ref
LIMIT coalesce(%(result_limit)s::int, 300)
