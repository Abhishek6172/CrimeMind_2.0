# SQL investigation modules (M1–M18)

Generated from `backend/app/sql_modules/*.sql` and `backend/app/registry.py`; oracle coverage from run `P7-20261102T053251Z-766b7f1`. Every module is read-only, case-scoped (`case_id` comes from the authorised case context), uses bind parameters only, and by default returns only evidence in `SUPPORTED` state (`include_historical` widens this).

## M1 — get recent contacts  (v1.0)

Recent contacts: who communicated with an entity, how often, when.

File: `backend/app/sql_modules/01_get_recent_contacts.sql`

| Variant | Questions | Required parameters | Optional parameters | Oracle comparisons (match / total) |
|---|---|---|---|---|
| `contacts` | Q1 | entity_id | end_time, include_historical, result_limit, start_time | 96 / 96 |
| `frequency` | Q3 | entity_id | end_time, include_historical, result_limit, start_time | 96 / 96 |
| `pairs` | Q4 | – | end_time, include_historical, min_count, result_limit, start_time | 96 / 96 |

## M2 — get communication between entities  (v1.0)

Communications between two specified entities.

File: `backend/app/sql_modules/02_get_communication_between_entities.sql`

| Variant | Questions | Required parameters | Optional parameters | Oracle comparisons (match / total) |
|---|---|---|---|---|
| `default` | Q2 | entity_id_1, entity_id_2 | end_time, include_historical, result_limit, start_time | 96 / 96 |

## M3 — find entities near location  (v1.0)

Entities recorded at a location; co-presence between entities.

File: `backend/app/sql_modules/03_find_entities_near_location.sql`

| Variant | Questions | Required parameters | Optional parameters | Oracle comparisons (match / total) |
|---|---|---|---|---|
| `present` | Q5 | end_time, location_id, start_time | include_historical, result_limit | 96 / 96 |
| `copresence` | Q8 | – | end_time, include_historical, location_id, result_limit, start_time, window_minutes | 96 / 96 |

## M4 — find common locations  (v1.0)

Locations visited by two entities; visit frequency per entity and location.

File: `backend/app/sql_modules/04_find_common_locations.sql`

| Variant | Questions | Required parameters | Optional parameters | Oracle comparisons (match / total) |
|---|---|---|---|---|
| `shared` | Q9 | entity_id_1, entity_id_2 | end_time, include_historical, result_limit, start_time | 96 / 96 |
| `frequency` | Q10 | – | end_time, entity_id, include_historical, location_id, result_limit, start_time | 96 / 96 |

## M5 — get entity location history  (v1.0)

Chronological and aggregated location history of an entity.

File: `backend/app/sql_modules/05_get_entity_location_history.sql`

| Variant | Questions | Required parameters | Optional parameters | Oracle comparisons (match / total) |
|---|---|---|---|---|
| `history` | Q6 | entity_id | end_time, include_historical, result_limit, start_time | 96 / 96 |
| `frequency` | Q7 | entity_id | end_time, include_historical, result_limit, start_time | 96 / 96 |

## M6 — get entity timeline  (v1.0)

Chronological timeline of everything recorded for an entity.

File: `backend/app/sql_modules/06_get_entity_timeline.sql`

| Variant | Questions | Required parameters | Optional parameters | Oracle comparisons (match / total) |
|---|---|---|---|---|
| `default` | Q11, Q12 | end_time, entity_id, start_time | end_time, include_historical, result_limit, start_time | 96 / 96 |

## M7 — find timeline gaps  (v1.0)

Gaps between recorded observations of an entity. A gap is an ABSENCE OF RECORDS, not proof of inactivity.

File: `backend/app/sql_modules/07_find_timeline_gaps.sql`

| Variant | Questions | Required parameters | Optional parameters | Oracle comparisons (match / total) |
|---|---|---|---|---|
| `default` | Q13 | entity_id | end_time, gap_minutes, include_historical, result_limit, start_time | 96 / 96 |

## M8 — get events around incident  (v1.1)

Activity before / after / around a specified incident event.

File: `backend/app/sql_modules/08_get_events_around_incident.sql`

| Variant | Questions | Required parameters | Optional parameters | Oracle comparisons (match / total) |
|---|---|---|---|---|
| `before` | Q14 | event_id | include_historical, result_limit, window_minutes | 96 / 96 |
| `after` | Q15 | event_id | include_historical, result_limit, window_minutes | 96 / 96 |
| `around` | Q16 | event_id | include_historical, result_limit, window_minutes | 96 / 96 |

## M9 — get direct relationships  (v1.0)

Explicitly recorded relationships of an entity (FACT).

File: `backend/app/sql_modules/09_get_direct_relationships.sql`

| Variant | Questions | Required parameters | Optional parameters | Oracle comparisons (match / total) |
|---|---|---|---|---|
| `default` | Q17 | entity_id | include_historical, result_limit | 96 / 96 |

## M10 — get relationship between entities  (v1.0)

Directly recorded relationship(s) between two entities.

File: `backend/app/sql_modules/10_get_relationship_between_entities.sql`

| Variant | Questions | Required parameters | Optional parameters | Oracle comparisons (match / total) |
|---|---|---|---|---|
| `default` | Q18 | entity_id_1, entity_id_2 | include_historical | 96 / 96 |

## M11 — find indirect connections  (v1.0)

Indirect connection paths between two entities over recorded relationships, communications and transactions.

File: `backend/app/sql_modules/11_find_indirect_connections.sql`

| Variant | Questions | Required parameters | Optional parameters | Oracle comparisons (match / total) |
|---|---|---|---|---|
| `connected` | Q19 | entity_id_1, entity_id_2 | include_historical, max_hops, result_limit | 96 / 96 |
| `shortest` | Q20 | entity_id_1, entity_id_2 | include_historical, max_hops, result_limit | 96 / 96 |

## M12 — get strong entity relationships  (v1.0)

Strongest recorded direct relationships of an entity (strength is an approved heuristic, not guilt or priority).

File: `backend/app/sql_modules/12_get_strong_entity_relationships.sql`

| Variant | Questions | Required parameters | Optional parameters | Oracle comparisons (match / total) |
|---|---|---|---|---|
| `default` | Q21 | entity_id | include_historical, minimum_strength, result_limit | 96 / 96 |

## M13 — get entity vehicles  (v1.0)

Vehicles recorded as owned/used by an entity, with validity period (historical vs current).

File: `backend/app/sql_modules/13_get_entity_vehicles.sql`

| Variant | Questions | Required parameters | Optional parameters | Oracle comparisons (match / total) |
|---|---|---|---|---|
| `default` | Q22 | entity_id | include_historical | 96 / 96 |

## M14 — find vehicles near location  (v1.0)

Vehicle observations at locations; entities associated with a vehicle; repeated vehicle presence.

File: `backend/app/sql_modules/14_find_vehicles_near_location.sql`

| Variant | Questions | Required parameters | Optional parameters | Oracle comparisons (match / total) |
|---|---|---|---|---|
| `near_location` | Q23 | end_time, location_id, start_time | include_historical, result_limit | 96 / 96 |
| `associated_entities` | Q24 | vehicle_id | end_time, include_historical, start_time | 96 / 96 |
| `repeated` | Q25 | – | end_time, include_historical, location_id, min_count, result_limit, start_time | 96 / 96 |

## M15 — get entity transactions  (v1.0)

Structured financial transaction analysis (records, not interpretations).

File: `backend/app/sql_modules/15_get_entity_transactions.sql`

| Variant | Questions | Required parameters | Optional parameters | Oracle comparisons (match / total) |
|---|---|---|---|---|
| `entity` | Q26 | entity_id | end_time, include_historical, result_limit, start_time | 96 / 96 |
| `between` | Q27 | entity_id_1, entity_id_2 | end_time, include_historical, result_limit, start_time | 96 / 96 |
| `top_amounts` | Q28 | end_time, start_time | include_historical, result_limit | 96 / 96 |
| `patterns` | Q29 | – | end_time, entity_id, include_historical, result_limit, start_time | 96 / 96 |
| `repeated_or_unusual` | Q30 | – | end_time, include_historical, min_count, result_limit, start_time | 96 / 96 |

## M16 — get entity evidence  (v1.0)

Evidence associated with an entity or an event, with provenance, validity and reliability.

File: `backend/app/sql_modules/16_get_entity_evidence.sql`

| Variant | Questions | Required parameters | Optional parameters | Oracle comparisons (match / total) |
|---|---|---|---|---|
| `entity` | Q31 | entity_id | include_historical, result_limit | 96 / 96 |
| `event` | Q32 | event_id | include_historical, result_limit | 96 / 96 |

## M17 — find cross entity evidence  (v1.0)

Evidence connecting multiple entities; entities with independent evidence; independent corroboration.

File: `backend/app/sql_modules/17_find_cross_entity_evidence.sql`

| Variant | Questions | Required parameters | Optional parameters | Oracle comparisons (match / total) |
|---|---|---|---|---|
| `multi_entity` | Q33 | – | include_historical, result_limit | 96 / 96 |
| `multi_type` | Q36 | – | include_historical, min_count, result_limit | 96 / 96 |
| `corroborating` | Q37 | – | entity_id, include_historical, result_limit | 96 / 96 |

## M18 — get case evidence ranking  (v1.0)

Evidence ranking and cross-domain analysis. Scores are approved heuristics, not probabilities of guilt.

File: `backend/app/sql_modules/18_get_case_evidence_ranking.sql`

| Variant | Questions | Required parameters | Optional parameters | Oracle comparisons (match / total) |
|---|---|---|---|---|
| `reliability` | Q34 | – | include_historical, result_limit | 96 / 96 |
| `evidence_strength` | Q35 | – | include_historical, result_limit | no independent oracle (not covered) |
| `connected_both` | Q38 | entity_id, location_id | end_time, include_historical, result_limit, start_time | no independent oracle (not covered) |
| `multi_domain` | Q39 | entity_id | include_historical, min_count, result_limit, window_minutes | no independent oracle (not covered) |
| `overall` | Q40 | event_id | include_historical, result_limit, window_minutes | Q40: see `q40_vs_python.json` |

## Common behaviour

- Validation (`sql_engine.validate_params`): only registry-defined parameters; presence, type and range checks; identifiers must resolve inside the authorised case; `start_time <= end_time`; identifier strings bounded to 200 characters and NUL-free (added after Phase 7 finding SEC-10).
- Execution: `SET LOCAL statement_timeout`, one transaction, query audit row written in a separate transaction even on failure.
- Results are recorded facts or correlations, never conclusions of guilt; empty results carry an explicit "does not establish that the event did not occur" warning.
