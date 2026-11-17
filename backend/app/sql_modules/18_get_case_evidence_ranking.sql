-- @module M18
-- @version 1.0
-- @description Evidence ranking and cross-domain analysis. Scores are approved heuristics, not probabilities of guilt.
-- @variant reliability
SELECT ev.ref AS evidence_ref, ev.evidence_type, ev.source, ev.reliability_score,
       ev.validity_status::text AS validity_status, ev.description
FROM evidence ev
WHERE ev.case_id = %(case_id)s::bigint
  AND (%(include_historical)s::boolean OR ev.validity_status = 'SUPPORTED')
ORDER BY ev.reliability_score DESC NULLS LAST, ev.ref
LIMIT coalesce(%(result_limit)s::int, 25)
-- @variant evidence_strength
WITH per_origin AS (
  SELECT ee.entity_id, coalesce(ev.provenance->>'origin_root', ev.source) AS origin,
         max(ev.reliability_score) AS best_reliability,
         array_agg(DISTINCT ev.ref) AS refs, array_agg(DISTINCT ev.evidence_type) AS types
  FROM evidence_entities ee
  JOIN evidence ev ON ev.case_id = ee.case_id AND ev.evidence_id = ee.evidence_id
  WHERE ee.case_id = %(case_id)s::bigint
    AND (%(include_historical)s::boolean OR ev.validity_status = 'SUPPORTED')
  GROUP BY ee.entity_id, coalesce(ev.provenance->>'origin_root', ev.source)
)
SELECT en.entity_id, en.ref AS entity_ref, en.display_name,
       count(*) AS independent_source_count,
       round(sum(po.best_reliability), 2) AS evidence_strength,
       array_agg(DISTINCT r ORDER BY r) AS evidence_refs
FROM per_origin po
JOIN entities en ON en.case_id = %(case_id)s::bigint AND en.entity_id = po.entity_id AND en.entity_type = 'PERSON'
CROSS JOIN LATERAL unnest(po.refs) AS r
GROUP BY en.entity_id, en.ref, en.display_name
ORDER BY evidence_strength DESC, en.ref
LIMIT coalesce(%(result_limit)s::int, 25)
-- @variant connected_both
WITH links AS (
  SELECT CASE WHEN sender_id = %(entity_id)s::bigint THEN receiver_id ELSE sender_id END AS pid,
         'COMMUNICATION'::text AS domain, ref
  FROM v_comms WHERE case_id = %(case_id)s::bigint AND (sender_id = %(entity_id)s::bigint OR receiver_id = %(entity_id)s::bigint)
    AND (%(include_historical)s::boolean OR validity_status = 'SUPPORTED')
  UNION ALL
  SELECT CASE WHEN from_entity_id = %(entity_id)s::bigint THEN to_entity_id ELSE from_entity_id END, 'TRANSACTION', ref
  FROM v_txns WHERE case_id = %(case_id)s::bigint AND (from_entity_id = %(entity_id)s::bigint OR to_entity_id = %(entity_id)s::bigint)
    AND (%(include_historical)s::boolean OR validity_status = 'SUPPORTED')
  UNION ALL
  SELECT CASE WHEN entity_a = %(entity_id)s::bigint THEN entity_b ELSE entity_a END, 'RELATIONSHIP', ref
  FROM v_rels WHERE case_id = %(case_id)s::bigint AND (entity_a = %(entity_id)s::bigint OR entity_b = %(entity_id)s::bigint)
    AND rel_type NOT IN ('OWNS','USES') AND (%(include_historical)s::boolean OR validity_status = 'SUPPORTED')
), at_loc AS (
  SELECT subject_entity_id AS pid, array_agg(DISTINCT ref ORDER BY ref) AS refs
  FROM v_obs WHERE case_id = %(case_id)s::bigint AND location_entity_id = %(location_id)s::bigint
    AND (%(include_historical)s::boolean OR validity_status = 'SUPPORTED')
    AND (%(start_time)s::timestamptz IS NULL OR observed_to   >= %(start_time)s::timestamptz)
    AND (%(end_time)s::timestamptz   IS NULL OR observed_from <= %(end_time)s::timestamptz)
  GROUP BY subject_entity_id
)
SELECT p.entity_id, p.ref AS entity_ref, p.display_name,
       (SELECT array_agg(DISTINCT l.domain ORDER BY l.domain) FROM links l WHERE l.pid = p.entity_id) AS connection_types,
       (SELECT array_agg(DISTINCT l.ref ORDER BY l.ref) FROM links l WHERE l.pid = p.entity_id) AS connection_record_refs,
       a.refs AS location_record_refs
FROM entities p
JOIN at_loc a ON a.pid = p.entity_id
WHERE p.case_id = %(case_id)s::bigint AND p.entity_type = 'PERSON' AND p.entity_id <> %(entity_id)s::bigint
  AND EXISTS (SELECT 1 FROM links l WHERE l.pid = p.entity_id)
ORDER BY p.ref
LIMIT coalesce(%(result_limit)s::int, 100)
-- @variant multi_domain
WITH d(pid, domain, ref) AS (
  SELECT CASE WHEN sender_id = %(entity_id)s::bigint THEN receiver_id ELSE sender_id END, 'COMMUNICATION', ref
  FROM v_comms WHERE case_id = %(case_id)s::bigint AND (sender_id = %(entity_id)s::bigint OR receiver_id = %(entity_id)s::bigint)
    AND (%(include_historical)s::boolean OR validity_status = 'SUPPORTED')
  UNION ALL
  SELECT CASE WHEN from_entity_id = %(entity_id)s::bigint THEN to_entity_id ELSE from_entity_id END, 'TRANSACTION', ref
  FROM v_txns WHERE case_id = %(case_id)s::bigint AND (from_entity_id = %(entity_id)s::bigint OR to_entity_id = %(entity_id)s::bigint)
    AND (%(include_historical)s::boolean OR validity_status = 'SUPPORTED')
  UNION ALL
  SELECT CASE WHEN entity_a = %(entity_id)s::bigint THEN entity_b ELSE entity_a END, 'RELATIONSHIP', ref
  FROM v_rels WHERE case_id = %(case_id)s::bigint AND (entity_a = %(entity_id)s::bigint OR entity_b = %(entity_id)s::bigint)
    AND rel_type NOT IN ('OWNS','USES') AND (%(include_historical)s::boolean OR validity_status = 'SUPPORTED')
  UNION ALL
  SELECT r2.entity_a, 'SHARED_VEHICLE', r1.ref || '/' || r2.ref
  FROM v_rels r1 JOIN v_rels r2 ON r2.case_id = r1.case_id AND r2.entity_b = r1.entity_b AND r2.entity_a <> r1.entity_a
  WHERE r1.case_id = %(case_id)s::bigint AND r1.entity_a = %(entity_id)s::bigint
    AND r1.rel_type IN ('OWNS','USES') AND r2.rel_type IN ('OWNS','USES')
    AND (%(include_historical)s::boolean OR (r1.validity_status = 'SUPPORTED' AND r2.validity_status = 'SUPPORTED'))
  UNION ALL
  SELECT b.subject_entity_id, 'CO_LOCATION', a.ref || '/' || b.ref
  FROM v_obs a JOIN v_obs b ON b.case_id = a.case_id AND b.location_entity_id = a.location_entity_id
    AND b.subject_entity_id <> a.subject_entity_id
    AND a.observed_from <= b.observed_to   + make_interval(mins => coalesce(%(window_minutes)s::int, 30))
    AND b.observed_from <= a.observed_to   + make_interval(mins => coalesce(%(window_minutes)s::int, 30))
  JOIN entities pb ON pb.case_id = b.case_id AND pb.entity_id = b.subject_entity_id AND pb.entity_type = 'PERSON'
  WHERE a.case_id = %(case_id)s::bigint AND a.subject_entity_id = %(entity_id)s::bigint
    AND (%(include_historical)s::boolean OR (a.validity_status = 'SUPPORTED' AND b.validity_status = 'SUPPORTED'))
  UNION ALL
  SELECT e2.entity_id, 'SHARED_EVIDENCE', ev.ref
  FROM evidence_entities e1
  JOIN evidence_entities e2 ON e2.case_id = e1.case_id AND e2.evidence_id = e1.evidence_id AND e2.entity_id <> e1.entity_id
  JOIN evidence ev ON ev.case_id = e1.case_id AND ev.evidence_id = e1.evidence_id
  WHERE e1.case_id = %(case_id)s::bigint AND e1.entity_id = %(entity_id)s::bigint
    AND (%(include_historical)s::boolean OR ev.validity_status = 'SUPPORTED')
)
SELECT p.entity_id, p.ref AS entity_ref, p.display_name,
       count(DISTINCT d.domain) AS domain_count,
       array_agg(DISTINCT d.domain ORDER BY d.domain) AS domains,
       array_agg(DISTINCT d.ref ORDER BY d.ref) AS record_refs
FROM d
JOIN entities p ON p.case_id = %(case_id)s::bigint AND p.entity_id = d.pid AND p.entity_type = 'PERSON'
GROUP BY p.entity_id, p.ref, p.display_name
HAVING count(DISTINCT d.domain) >= coalesce(%(min_count)s::int, 2)
ORDER BY domain_count DESC, p.ref
LIMIT coalesce(%(result_limit)s::int, 100)
-- @variant overall
WITH inc AS (
  SELECT * FROM events WHERE case_id = %(case_id)s::bigint AND event_id = %(event_id)s::bigint
), w AS (SELECT make_interval(mins => coalesce(%(window_minutes)s::int, 60)) AS span),
victims AS (
  SELECT ee.entity_id FROM event_entities ee, inc WHERE ee.case_id = inc.case_id AND ee.event_id = inc.event_id AND ee.role = 'VICTIM'
), spatial AS (
  SELECT o.subject_entity_id AS pid, array_agg(DISTINCT o.ref) AS refs
  FROM v_obs o, inc, w
  WHERE o.case_id = inc.case_id AND o.location_entity_id = inc.location_entity_id
    AND o.observed_to >= inc.occurred_at - w.span AND o.observed_from <= inc.occurred_at + w.span
    AND (%(include_historical)s::boolean OR o.validity_status = 'SUPPORTED')
  GROUP BY o.subject_entity_id
), temporal AS (
  SELECT a.entity_id AS pid, array_agg(DISTINCT a.ref) AS refs
  FROM v_activity a, inc, w
  WHERE a.case_id = inc.case_id AND a.occurred_at BETWEEN inc.occurred_at - w.span AND inc.occurred_at + w.span
    AND a.ref <> inc.ref AND (%(include_historical)s::boolean OR a.validity_status = 'SUPPORTED')
  GROUP BY a.entity_id
), comm AS (
  SELECT x.pid, array_agg(DISTINCT x.ref) AS refs FROM (
    SELECT c.sender_id AS pid, c.ref, c.receiver_id AS other FROM v_comms c
     WHERE c.case_id = %(case_id)s::bigint AND (%(include_historical)s::boolean OR c.validity_status = 'SUPPORTED')
    UNION ALL
    SELECT c.receiver_id, c.ref, c.sender_id FROM v_comms c
     WHERE c.case_id = %(case_id)s::bigint AND (%(include_historical)s::boolean OR c.validity_status = 'SUPPORTED')
  ) x
  WHERE x.other IN (SELECT entity_id FROM victims) OR x.other IN (SELECT pid FROM spatial)
  GROUP BY x.pid
), fin AS (
  SELECT x.pid, array_agg(DISTINCT x.ref) AS refs FROM (
    SELECT t.from_entity_id AS pid, t.ref, t.to_entity_id AS other FROM v_txns t
     WHERE t.case_id = %(case_id)s::bigint AND (%(include_historical)s::boolean OR t.validity_status = 'SUPPORTED')
    UNION ALL
    SELECT t.to_entity_id, t.ref, t.from_entity_id FROM v_txns t
     WHERE t.case_id = %(case_id)s::bigint AND (%(include_historical)s::boolean OR t.validity_status = 'SUPPORTED')
  ) x
  WHERE x.other IN (SELECT entity_id FROM victims) OR x.other IN (SELECT pid FROM spatial)
  GROUP BY x.pid
), rel AS (
  SELECT x.pid, array_agg(DISTINCT x.ref) AS refs FROM (
    SELECT r.entity_a AS pid, r.ref, r.entity_b AS other FROM v_rels r
     WHERE r.case_id = %(case_id)s::bigint AND r.rel_type NOT IN ('OWNS','USES') AND (%(include_historical)s::boolean OR r.validity_status = 'SUPPORTED')
    UNION ALL
    SELECT r.entity_b, r.ref, r.entity_a FROM v_rels r
     WHERE r.case_id = %(case_id)s::bigint AND r.rel_type NOT IN ('OWNS','USES') AND (%(include_historical)s::boolean OR r.validity_status = 'SUPPORTED')
  ) x
  WHERE x.other IN (SELECT entity_id FROM victims)
  GROUP BY x.pid
), evid AS (
  SELECT ee.entity_id AS pid, count(DISTINCT coalesce(ev.provenance->>'origin_root', ev.source)) AS sources,
         array_agg(DISTINCT ev.ref) AS refs
  FROM evidence_entities ee JOIN evidence ev ON ev.case_id = ee.case_id AND ev.evidence_id = ee.evidence_id
  WHERE ee.case_id = %(case_id)s::bigint AND (%(include_historical)s::boolean OR ev.validity_status = 'SUPPORTED')
  GROUP BY ee.entity_id
), scored AS (
  SELECT p.entity_id, p.ref, p.display_name,
         (s.pid IS NOT NULL) AS spatial_signal, (t.pid IS NOT NULL) AS temporal_signal,
         (c.pid IS NOT NULL) AS communication_signal, (f.pid IS NOT NULL) AS financial_signal,
         (r.pid IS NOT NULL) AS relational_signal, coalesce(e.sources, 0) AS independent_evidence_sources,
         round((0.35 * (s.pid IS NOT NULL)::int + 0.10 * (t.pid IS NOT NULL)::int
              + 0.15 * (c.pid IS NOT NULL)::int + 0.15 * (f.pid IS NOT NULL)::int
              + 0.10 * (r.pid IS NOT NULL)::int + 0.15 * LEAST(1.0, coalesce(e.sources, 0) / 3.0))::numeric, 2) AS association_score,
         coalesce(s.refs, '{}') || coalesce(c.refs, '{}') || coalesce(f.refs, '{}') || coalesce(r.refs, '{}') AS supporting_record_refs,
         coalesce(e.refs, '{}') AS evidence_refs
  FROM entities p
  LEFT JOIN spatial s ON s.pid = p.entity_id LEFT JOIN temporal t ON t.pid = p.entity_id
  LEFT JOIN comm c ON c.pid = p.entity_id    LEFT JOIN fin f ON f.pid = p.entity_id
  LEFT JOIN rel r ON r.pid = p.entity_id     LEFT JOIN evid e ON e.pid = p.entity_id
  WHERE p.case_id = %(case_id)s::bigint AND p.entity_type = 'PERSON'
    AND p.entity_id NOT IN (SELECT entity_id FROM victims)
)
SELECT entity_id, ref AS entity_ref, display_name, association_score,
       ARRAY_REMOVE(ARRAY[CASE WHEN spatial_signal THEN 'SPATIAL' END, CASE WHEN temporal_signal THEN 'TEMPORAL' END,
                          CASE WHEN communication_signal THEN 'COMMUNICATION' END, CASE WHEN financial_signal THEN 'FINANCIAL' END,
                          CASE WHEN relational_signal THEN 'RELATIONAL' END,
                          CASE WHEN independent_evidence_sources > 0 THEN 'EVIDENCE' END], NULL) AS contributing_signals,
       independent_evidence_sources, supporting_record_refs, evidence_refs,
       'Heuristic association score (weights: spatial .35, temporal .10, communication .15, financial .15, relational .10, evidence .15). Not a probability of guilt.'::text AS scoring_note
FROM scored
WHERE association_score > 0
ORDER BY association_score DESC, ref
LIMIT coalesce(%(result_limit)s::int, 25)
