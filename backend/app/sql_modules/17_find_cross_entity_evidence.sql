-- @module M17
-- @version 1.0
-- @description Evidence connecting multiple entities; entities with independent evidence; independent corroboration.
-- @variant multi_entity
SELECT ev.ref AS evidence_ref, ev.evidence_type, ev.source, ev.validity_status::text AS validity_status,
       count(DISTINCT ee.entity_id) AS entity_count,
       array_agg(DISTINCT en.ref ORDER BY en.ref) AS entity_refs,
       array_agg(DISTINCT en.display_name ORDER BY en.display_name) AS entity_names
FROM evidence ev
JOIN evidence_entities ee ON ee.case_id = ev.case_id AND ee.evidence_id = ev.evidence_id
JOIN entities en ON en.case_id = ee.case_id AND en.entity_id = ee.entity_id
WHERE ev.case_id = %(case_id)s::bigint
  AND (%(include_historical)s::boolean OR ev.validity_status = 'SUPPORTED')
GROUP BY ev.ref, ev.evidence_type, ev.source, ev.validity_status
HAVING count(DISTINCT ee.entity_id) >= 2
ORDER BY entity_count DESC, ev.ref
LIMIT coalesce(%(result_limit)s::int, 200)
-- @variant multi_type
SELECT en.entity_id, en.ref AS entity_ref, en.display_name,
       count(DISTINCT ev.evidence_type) AS evidence_type_count,
       count(DISTINCT coalesce(ev.provenance->>'origin_root', ev.source)) AS independent_source_count,
       array_agg(DISTINCT ev.evidence_type ORDER BY ev.evidence_type) AS evidence_types,
       array_agg(DISTINCT ev.ref ORDER BY ev.ref) AS evidence_refs,
       array_agg(DISTINCT coalesce(ev.provenance->>'origin_root', ev.source)
                 ORDER BY coalesce(ev.provenance->>'origin_root', ev.source)) AS origins
FROM evidence_entities ee
JOIN evidence ev ON ev.case_id = ee.case_id AND ev.evidence_id = ee.evidence_id
JOIN entities en ON en.case_id = ee.case_id AND en.entity_id = ee.entity_id AND en.entity_type = 'PERSON'
WHERE ee.case_id = %(case_id)s::bigint
  AND (%(include_historical)s::boolean OR ev.validity_status = 'SUPPORTED')
GROUP BY en.entity_id, en.ref, en.display_name
HAVING count(DISTINCT ev.evidence_type) >= coalesce(%(min_count)s::int, 2)
ORDER BY independent_source_count DESC, evidence_type_count DESC, en.ref
LIMIT coalesce(%(result_limit)s::int, 100)
-- @variant corroborating
SELECT en.ref AS entity_ref, en.display_name AS entity_name,
       a.ref AS evidence_ref_a, a.evidence_type AS type_a, coalesce(a.provenance->>'origin_root', a.source) AS origin_a,
       b.ref AS evidence_ref_b, b.evidence_type AS type_b, coalesce(b.provenance->>'origin_root', b.source) AS origin_b
FROM evidence_entities ea
JOIN evidence_entities eb ON eb.case_id = ea.case_id AND eb.entity_id = ea.entity_id AND eb.evidence_id > ea.evidence_id
JOIN evidence a ON a.case_id = ea.case_id AND a.evidence_id = ea.evidence_id
JOIN evidence b ON b.case_id = eb.case_id AND b.evidence_id = eb.evidence_id
JOIN entities en ON en.case_id = ea.case_id AND en.entity_id = ea.entity_id
WHERE ea.case_id = %(case_id)s::bigint
  AND (%(entity_id)s::bigint IS NULL OR ea.entity_id = %(entity_id)s::bigint)
  AND coalesce(a.provenance->>'origin_root', a.source) <> coalesce(b.provenance->>'origin_root', b.source)
  AND (%(include_historical)s::boolean OR (a.validity_status = 'SUPPORTED' AND b.validity_status = 'SUPPORTED'))
ORDER BY en.ref, a.ref, b.ref
LIMIT coalesce(%(result_limit)s::int, 300)
