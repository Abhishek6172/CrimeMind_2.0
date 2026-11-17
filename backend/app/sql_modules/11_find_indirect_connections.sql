-- @module M11
-- @version 1.0
-- @description Indirect connection paths between two entities over recorded relationships, communications and transactions.
-- @variant connected
WITH RECURSIVE raw AS (
  SELECT entity_a AS a, entity_b AS b, 'RELATIONSHIP' AS kind, ref FROM v_rels
   WHERE case_id = %(case_id)s::bigint AND (%(include_historical)s::boolean OR validity_status = 'SUPPORTED')
     AND rel_type NOT IN ('OWNS','USES')
  UNION ALL SELECT sender_id, receiver_id, 'COMMUNICATION', ref FROM v_comms
   WHERE case_id = %(case_id)s::bigint AND (%(include_historical)s::boolean OR validity_status = 'SUPPORTED')
  UNION ALL SELECT from_entity_id, to_entity_id, 'TRANSACTION', ref FROM v_txns
   WHERE case_id = %(case_id)s::bigint AND (%(include_historical)s::boolean OR validity_status = 'SUPPORTED')
), edges AS (
  SELECT a, b, array_agg(DISTINCT kind) AS kinds FROM (
    SELECT a, b, kind FROM raw UNION ALL SELECT b, a, kind FROM raw) u
  GROUP BY a, b
), walk(path, kinds_path, last_id, hops) AS (
  SELECT ARRAY[%(entity_id_1)s::bigint], ARRAY[]::text[], %(entity_id_1)s::bigint, 0
  UNION ALL
  SELECT w.path || e.b, w.kinds_path || array_to_string(e.kinds, '+'), e.b, w.hops + 1
  FROM walk w JOIN edges e ON e.a = w.last_id
  WHERE NOT (e.b = ANY (w.path)) AND w.hops < LEAST(coalesce(%(max_hops)s::int, 3), 4)
    AND w.last_id <> %(entity_id_2)s::bigint
), found AS (
  SELECT * FROM walk WHERE last_id = %(entity_id_2)s::bigint AND hops >= 2
)
SELECT f.hops AS hop_count,
       (SELECT array_agg(en.ref ORDER BY x.ord) FROM unnest(f.path) WITH ORDINALITY x(id, ord)
          JOIN entities en ON en.case_id = %(case_id)s::bigint AND en.entity_id = x.id) AS path_refs,
       (SELECT array_agg(en.display_name ORDER BY x.ord) FROM unnest(f.path) WITH ORDINALITY x(id, ord)
          JOIN entities en ON en.case_id = %(case_id)s::bigint AND en.entity_id = x.id) AS path_names,
       f.kinds_path AS link_kinds
FROM found f
ORDER BY f.hops, path_refs
LIMIT coalesce(%(result_limit)s::int, 50)
-- @variant shortest
WITH RECURSIVE raw AS (
  SELECT entity_a AS a, entity_b AS b, 'RELATIONSHIP' AS kind, ref FROM v_rels
   WHERE case_id = %(case_id)s::bigint AND (%(include_historical)s::boolean OR validity_status = 'SUPPORTED')
     AND rel_type NOT IN ('OWNS','USES')
  UNION ALL SELECT sender_id, receiver_id, 'COMMUNICATION', ref FROM v_comms
   WHERE case_id = %(case_id)s::bigint AND (%(include_historical)s::boolean OR validity_status = 'SUPPORTED')
  UNION ALL SELECT from_entity_id, to_entity_id, 'TRANSACTION', ref FROM v_txns
   WHERE case_id = %(case_id)s::bigint AND (%(include_historical)s::boolean OR validity_status = 'SUPPORTED')
), edges AS (
  SELECT a, b, array_agg(DISTINCT kind) AS kinds FROM (
    SELECT a, b, kind FROM raw UNION ALL SELECT b, a, kind FROM raw) u
  GROUP BY a, b
), walk(path, kinds_path, last_id, hops) AS (
  SELECT ARRAY[%(entity_id_1)s::bigint], ARRAY[]::text[], %(entity_id_1)s::bigint, 0
  UNION ALL
  SELECT w.path || e.b, w.kinds_path || array_to_string(e.kinds, '+'), e.b, w.hops + 1
  FROM walk w JOIN edges e ON e.a = w.last_id
  WHERE NOT (e.b = ANY (w.path)) AND w.hops < LEAST(coalesce(%(max_hops)s::int, 4), 4)
    AND w.last_id <> %(entity_id_2)s::bigint
), found AS (
  SELECT * FROM walk WHERE last_id = %(entity_id_2)s::bigint
), best AS (SELECT min(hops) AS h FROM found)
SELECT f.hops AS hop_count,
       (SELECT array_agg(en.ref ORDER BY x.ord) FROM unnest(f.path) WITH ORDINALITY x(id, ord)
          JOIN entities en ON en.case_id = %(case_id)s::bigint AND en.entity_id = x.id) AS path_refs,
       (SELECT array_agg(en.display_name ORDER BY x.ord) FROM unnest(f.path) WITH ORDINALITY x(id, ord)
          JOIN entities en ON en.case_id = %(case_id)s::bigint AND en.entity_id = x.id) AS path_names,
       f.kinds_path AS link_kinds
FROM found f, best
WHERE f.hops = best.h
ORDER BY path_refs
LIMIT coalesce(%(result_limit)s::int, 20)
