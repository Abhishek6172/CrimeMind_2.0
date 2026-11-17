-- @module M7
-- @version 1.0
-- @description Gaps between recorded observations of an entity. A gap is an ABSENCE OF RECORDS, not proof of inactivity.
-- @variant default
WITH t AS (
  SELECT a.occurred_at, a.ref, a.item_type,
         lead(a.occurred_at) OVER w AS next_at, lead(a.ref) OVER w AS next_ref
  FROM (SELECT DISTINCT ON (occurred_at, ref) occurred_at, ref, item_type
        FROM v_activity
        WHERE case_id = %(case_id)s::bigint AND entity_id = %(entity_id)s::bigint
          AND (%(include_historical)s::boolean OR validity_status = 'SUPPORTED')
          AND (%(start_time)s::timestamptz IS NULL OR occurred_at >= %(start_time)s::timestamptz)
          AND (%(end_time)s::timestamptz   IS NULL OR occurred_at <= %(end_time)s::timestamptz)
        ORDER BY occurred_at, ref) a
  WINDOW w AS (ORDER BY a.occurred_at, a.ref)
)
SELECT t.occurred_at AS gap_start, t.next_at AS gap_end,
       round(extract(epoch FROM (t.next_at - t.occurred_at)) / 60)::int AS gap_minutes,
       t.ref AS before_record_ref, t.next_ref AS after_record_ref,
       'No records between these two observations; this is not evidence that nothing happened.'::text AS note
FROM t
WHERE t.next_at IS NOT NULL
  AND t.next_at - t.occurred_at >= make_interval(mins => coalesce(%(gap_minutes)s::int, 120))
ORDER BY gap_minutes DESC, gap_start
LIMIT coalesce(%(result_limit)s::int, 200)
