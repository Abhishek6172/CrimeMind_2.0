-- @module M15
-- @version 1.0
-- @description Structured financial transaction analysis (records, not interpretations).
-- @variant entity
SELECT t.ref AS transaction_ref, f.ref AS from_ref, f.display_name AS from_name,
       tt.ref AS to_ref, tt.display_name AS to_name, t.amount, t.currency, t.txn_type, t.occurred_at,
       t.evidence_ref, t.validity_status::text AS validity_status
FROM v_txns t
JOIN entities f  ON f.case_id = t.case_id AND f.entity_id = t.from_entity_id
JOIN entities tt ON tt.case_id = t.case_id AND tt.entity_id = t.to_entity_id
WHERE t.case_id = %(case_id)s::bigint
  AND (t.from_entity_id = %(entity_id)s::bigint OR t.to_entity_id = %(entity_id)s::bigint)
  AND (%(include_historical)s::boolean OR t.validity_status = 'SUPPORTED')
  AND (%(start_time)s::timestamptz IS NULL OR t.occurred_at >= %(start_time)s::timestamptz)
  AND (%(end_time)s::timestamptz   IS NULL OR t.occurred_at <= %(end_time)s::timestamptz)
ORDER BY t.occurred_at
LIMIT coalesce(%(result_limit)s::int, 500)
-- @variant between
SELECT t.ref AS transaction_ref, f.ref AS from_ref, f.display_name AS from_name,
       tt.ref AS to_ref, tt.display_name AS to_name, t.amount, t.currency, t.txn_type, t.occurred_at,
       t.evidence_ref, t.validity_status::text AS validity_status
FROM v_txns t
JOIN entities f  ON f.case_id = t.case_id AND f.entity_id = t.from_entity_id
JOIN entities tt ON tt.case_id = t.case_id AND tt.entity_id = t.to_entity_id
WHERE t.case_id = %(case_id)s::bigint
  AND ((t.from_entity_id = %(entity_id_1)s::bigint AND t.to_entity_id = %(entity_id_2)s::bigint)
    OR (t.from_entity_id = %(entity_id_2)s::bigint AND t.to_entity_id = %(entity_id_1)s::bigint))
  AND (%(include_historical)s::boolean OR t.validity_status = 'SUPPORTED')
  AND (%(start_time)s::timestamptz IS NULL OR t.occurred_at >= %(start_time)s::timestamptz)
  AND (%(end_time)s::timestamptz   IS NULL OR t.occurred_at <= %(end_time)s::timestamptz)
ORDER BY t.occurred_at
LIMIT coalesce(%(result_limit)s::int, 500)
-- @variant top_amounts
SELECT e.entity_id, e.ref AS entity_ref, e.display_name,
       sum(CASE WHEN t.from_entity_id = e.entity_id THEN t.amount ELSE 0 END) AS total_sent,
       sum(CASE WHEN t.to_entity_id   = e.entity_id THEN t.amount ELSE 0 END) AS total_received,
       count(*) AS transaction_count,
       array_agg(DISTINCT t.ref ORDER BY t.ref) AS record_refs
FROM v_txns t
JOIN entities e ON e.case_id = t.case_id AND e.entity_id IN (t.from_entity_id, t.to_entity_id)
WHERE t.case_id = %(case_id)s::bigint
  AND (%(include_historical)s::boolean OR t.validity_status = 'SUPPORTED')
  AND (%(start_time)s::timestamptz IS NULL OR t.occurred_at >= %(start_time)s::timestamptz)
  AND (%(end_time)s::timestamptz   IS NULL OR t.occurred_at <= %(end_time)s::timestamptz)
GROUP BY e.entity_id, e.ref, e.display_name
ORDER BY GREATEST(sum(CASE WHEN t.from_entity_id = e.entity_id THEN t.amount ELSE 0 END),
                  sum(CASE WHEN t.to_entity_id   = e.entity_id THEN t.amount ELSE 0 END)) DESC
LIMIT coalesce(%(result_limit)s::int, 25)
-- @variant patterns
SELECT f.ref AS from_ref, f.display_name AS from_name, tt.ref AS to_ref, tt.display_name AS to_name,
       count(*) AS transaction_count, sum(t.amount) AS total_amount, round(avg(t.amount), 2) AS average_amount,
       min(t.occurred_at) AS first_at, max(t.occurred_at) AS last_at,
       array_agg(DISTINCT t.ref ORDER BY t.ref) AS record_refs
FROM v_txns t
JOIN entities f  ON f.case_id = t.case_id AND f.entity_id = t.from_entity_id
JOIN entities tt ON tt.case_id = t.case_id AND tt.entity_id = t.to_entity_id
WHERE t.case_id = %(case_id)s::bigint
  AND (%(entity_id)s::bigint IS NULL OR %(entity_id)s::bigint IN (t.from_entity_id, t.to_entity_id))
  AND (%(include_historical)s::boolean OR t.validity_status = 'SUPPORTED')
  AND (%(start_time)s::timestamptz IS NULL OR t.occurred_at >= %(start_time)s::timestamptz)
  AND (%(end_time)s::timestamptz   IS NULL OR t.occurred_at <= %(end_time)s::timestamptz)
GROUP BY f.ref, f.display_name, tt.ref, tt.display_name
ORDER BY total_amount DESC
LIMIT coalesce(%(result_limit)s::int, 100)
-- @variant repeated_or_unusual
WITH med AS (
  SELECT coalesce(percentile_cont(0.5) WITHIN GROUP (ORDER BY amount), 0) AS median_amount
  FROM v_txns WHERE case_id = %(case_id)s::bigint AND (%(include_historical)s::boolean OR validity_status = 'SUPPORTED')
)
SELECT f.ref AS from_ref, f.display_name AS from_name, tt.ref AS to_ref, tt.display_name AS to_name,
       count(*) AS transaction_count, sum(t.amount) AS total_amount, max(t.amount) AS largest_amount,
       (count(*) >= coalesce(%(min_count)s::int, 2)) AS repeated,
       (max(t.amount) >= 5 * med.median_amount) AS large_relative_to_case_median,
       array_agg(DISTINCT t.ref ORDER BY t.ref) AS record_refs,
       'Observed characteristics only; not a classification of anyone as criminal.'::text AS note
FROM v_txns t
CROSS JOIN med
JOIN entities f  ON f.case_id = t.case_id AND f.entity_id = t.from_entity_id
JOIN entities tt ON tt.case_id = t.case_id AND tt.entity_id = t.to_entity_id
WHERE t.case_id = %(case_id)s::bigint
  AND (%(include_historical)s::boolean OR t.validity_status = 'SUPPORTED')
  AND (%(start_time)s::timestamptz IS NULL OR t.occurred_at >= %(start_time)s::timestamptz)
  AND (%(end_time)s::timestamptz   IS NULL OR t.occurred_at <= %(end_time)s::timestamptz)
GROUP BY f.ref, f.display_name, tt.ref, tt.display_name, med.median_amount
HAVING count(*) >= coalesce(%(min_count)s::int, 2) OR max(t.amount) >= 5 * med.median_amount
ORDER BY total_amount DESC
LIMIT coalesce(%(result_limit)s::int, 100)
