# Phase 7 Report: SQL Module Verification, Database Correctness, Security and Scalability

Run ID: `P7-20261102T053251Z-766b7f1` (git `766b7f1`). PostgreSQL 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1); all databases are disposable research databases regenerated from committed seeds; the application database was never touched. Synthetic data only.

## 1. Status

| Component | Status |
|---|---|
| SQL module documentation (docs/SQL_MODULES.md, generated) | EXECUTED |
| Independent Python oracles M1–M17 (all variants) and M18.reliability | EXECUTED |
| M18.overall (Q40) vs independent Python re-implementation | EXECUTED |
| M18.evidence_strength / connected_both / multi_domain oracles | NOT IMPLEMENTED (no independent oracle) |
| Database correctness, isolation, security, concurrency checks | EXECUTED |
| Scalability 1x/2x/5x/10x + EXPLAIN ANALYZE + index experiment | EXECUTED (synthetic replication model) |
| HTTP-level authentication/authorisation tests | Covered by backend/tests/test_security.py (73 backend tests pass); not re-run as an experiment |

## 2. Oracle comparison

3360 comparisons over 35 module variants: **3360 matched, 0 mismatched** (after the fixes in section 5). 2600 of 3360 (77%) had a non-empty expected result; the remaining comparisons check that SQL and oracle agree on emptiness. Rows are compared as multisets over the oracle's output columns (timestamps normalised to UTC, decimals to 6 places, aggregate arrays as sets) and the SQL ordering is checked against the specified order key (ties in any order).

| Source | Comparisons | Matches |
|---|---|---|
| dataset_csv | 1680 | 1680 |
| edge_mutated | 1680 | 1680 |

`dataset_csv`: 4 committed datasets (seeds 2026, 2040, 2055, 2075), both cases each, oracle reads the CSV files only. `edge_mutated`: seeds 2026, 2060 after the mutations below; oracle reads the raw base tables.

| Variant | Comparisons | Matches | Mismatches |
|---|---|---|---|
| M1.contacts | 96 | 96 | 0 |
| M1.frequency | 96 | 96 | 0 |
| M1.pairs | 96 | 96 | 0 |
| M2.default | 96 | 96 | 0 |
| M3.present | 96 | 96 | 0 |
| M3.copresence | 96 | 96 | 0 |
| M4.shared | 96 | 96 | 0 |
| M4.frequency | 96 | 96 | 0 |
| M5.history | 96 | 96 | 0 |
| M5.frequency | 96 | 96 | 0 |
| M6.default | 96 | 96 | 0 |
| M7.default | 96 | 96 | 0 |
| M8.before | 96 | 96 | 0 |
| M8.after | 96 | 96 | 0 |
| M8.around | 96 | 96 | 0 |
| M9.default | 96 | 96 | 0 |
| M10.default | 96 | 96 | 0 |
| M11.connected | 96 | 96 | 0 |
| M11.shortest | 96 | 96 | 0 |
| M12.default | 96 | 96 | 0 |
| M13.default | 96 | 96 | 0 |
| M14.near_location | 96 | 96 | 0 |
| M14.associated_entities | 96 | 96 | 0 |
| M14.repeated | 96 | 96 | 0 |
| M15.entity | 96 | 96 | 0 |
| M15.between | 96 | 96 | 0 |
| M15.top_amounts | 96 | 96 | 0 |
| M15.patterns | 96 | 96 | 0 |
| M15.repeated_or_unusual | 96 | 96 | 0 |
| M16.entity | 96 | 96 | 0 |
| M16.event | 96 | 96 | 0 |
| M17.multi_entity | 96 | 96 | 0 |
| M17.multi_type | 96 | 96 | 0 |
| M17.corroborating | 96 | 96 | 0 |
| M18.reliability | 96 | 96 | 0 |

### Edge-case mutations (disposable DB)

| Mutation | Accepted | Rejected by DB | Rejection reason |
|---|---|---|---|
| insert entity with no records | 4 | 0 |  |
| insert second person for duplicate/null cases | 4 | 0 |  |
| duplicate communication | 8 | 0 |  |
| communication with NULL evidence and NULL duration | 4 | 0 |  |
| self-communication | 0 | 4 | CheckViolation: new row for relation "communications" violates check constraint "communica |
| duplicate zero-length observation | 8 | 0 |  |
| observation with NULL observed_to | 0 | 4 | NotNullViolation: null value in column "observed_to" of relation "location_observations" v |
| observation ending before it starts | 0 | 4 | CheckViolation: new row for relation "location_observations" violates check constraint "lo |
| transaction | 16 | 4 | CheckViolation: new row for relation "transactions" violates check constraint "transaction |
| relationship with NULL strength | 4 | 0 |  |
| contradictory relationship (same pair, other type) | 4 | 0 |  |
| self relationship | 0 | 4 | CheckViolation: new row for relation "relationships" violates check constraint "relationsh |
| relationship strength out of range | 0 | 4 | CheckViolation: new row for relation "relationships" violates check constraint "relationsh |
| insert vehicle | 4 | 0 |  |
| vehicle OWNS (open-ended) | 4 | 0 |  |
| vehicle USES (ended in the past) | 4 | 0 |  |
| vehicle observation | 0 | 12 | CheckViolation: new row for relation "location_observations" violates check constraint "lo |
| validity CHALLENGED | 40 | 0 |  |
| validity INVALIDATED | 40 | 0 |  |
| validity SUPERSEDED | 40 | 0 |  |

Rejected inserts are documented behaviour (constraints), not oracle gaps. Mixed validity states (CHALLENGED, INVALIDATED, SUPERSEDED, applied through `change_validity()`) were exercised with `include_historical` on and off, together with duplicates, NULL evidence, NULL strength, contradictory relationships, empty entities, vehicles with open and ended ownership, and zero-width time windows equal to a record's timestamp.

### Q40 (M18 `overall`)

| Seed | Case | Candidates | Max |score difference| | Same candidate set |
|---|---|---|---|---|
| 2026 | CASE-2026-001 | 109 | 0.0 | True |
| 2026 | CASE-2026-002 | 47 | 0.0 | True |
| 2040 | CASE-2040-001 | 95 | 0.0 | True |
| 2040 | CASE-2040-002 | 37 | 0.0 | True |
| 2055 | CASE-2055-001 | 107 | 0.0 | True |
| 2055 | CASE-2055-002 | 54 | 0.0 | True |
| 2075 | CASE-2075-001 | 107 | 0.0 | True |
| 2075 | CASE-2075-002 | 49 | 0.0 | True |

The frozen Q40 SQL is unchanged; `q40_py` is an independent Python statement of the same scoring.

## 3. Database correctness, isolation and security checks

27 of 27 checks passed.

| ID | Area | Check | Result | Observed |
|---|---|---|---|---|
| DB-01 | constraints | duplicate (case, ref) on entities is rejected | PASS | UniqueViolation: duplicate key value violates unique constraint "entities_case_id_ref_key" |
| DB-02 | constraints | unknown entity type is rejected (FK) | PASS | ForeignKeyViolation: insert or update on table "entities" violates foreign key constraint "entities_entity_typ |
| DB-03 | constraints | communication referencing an entity of ANOTHER case is rejected | PASS | ForeignKeyViolation: insert or update on table "communications" violates foreign key constraint "communication |
| DB-04 | constraints | relationship strength > 1 is rejected | PASS | CheckViolation: new row for relation "relationships" violates check constraint "relationships_strength_check" |
| DB-05 | constraints | self relationship is rejected | PASS | CheckViolation: new row for relation "relationships" violates check constraint "relationships_check" |
| DB-06 | constraints | observation ending before it starts is rejected | PASS | CheckViolation: new row for relation "location_observations" violates check constraint "location_observations_ |
| DB-07 | constraints | new evidence must start SUPPORTED | PASS | RaiseException: New evidence must start SUPPORTED; use change_validity() for later changes |
| DB-08 | constraints | event referencing a location of ANOTHER case is rejected | PASS | ForeignKeyViolation: insert or update on table "events" violates foreign key constraint "events_case_id_locati |
| DB-10 | lifecycle | validity_status cannot be updated directly | PASS | RaiseException: validity_status can only be changed via change_validity() |
| DB-11 | lifecycle | evidence rows cannot be deleted | PASS | RaiseException: DELETE on evidence is not allowed (append-only / history-preserving) |
| DB-12 | lifecycle | evidence identity fields are immutable | PASS | RaiseException: Evidence identity/provenance fields are immutable; supersede the record instead |
| DB-13 | lifecycle | audit_log is append-only (UPDATE) | PASS | RaiseException: UPDATE on audit_log is not allowed (append-only / history-preserving) |
| DB-14 | lifecycle | audit_log is append-only (DELETE) | PASS | RaiseException: DELETE on audit_log is not allowed (append-only / history-preserving) |
| DB-16 | lifecycle | evidence.validity_status equals the newest validity event for every evidence row | PASS | 0 evidence rows disagree with their latest validity event |
| DB-15 | lifecycle | evidence_validity_events is append-only (UPDATE, once rows exist) | PASS | RaiseException: UPDATE on evidence_validity_events is not allowed (append-only / history-preserving) |
| DB-17 | audit | every validity event is mirrored in the audit log | PASS | audit rows for validity events=1, events=1 |
| DB-18 | transactions | failed change_validity (unknown actor) leaves no event and no status change | PASS | events 1->1, status INVALIDATED |
| DB-19 | concurrency | 8 concurrent change_validity calls on one evidence row: final status equals the newest event, one event per accepted call | PASS | accepted=2 rejected=6 events=2 final status=INVALIDATED latest event=INVALIDATED; rejections: ['Transition INV |
| SEC-01 | privilege | cm_app cannot read the ground-truth schema | PASS | InsufficientPrivilege: permission denied for schema gt |
| SEC-02 | privilege | cm_app cannot write the ground-truth schema | PASS | InsufficientPrivilege: permission denied for schema gt |
| SEC-03 | privilege | cm_app cannot UPDATE evidence directly | PASS | InsufficientPrivilege: permission denied for table evidence |
| SEC-04 | privilege | cm_app cannot DELETE evidence | PASS | InsufficientPrivilege: permission denied for table evidence |
| SEC-05 | privilege | cm_app cannot modify the audit log | PASS | InsufficientPrivilege: permission denied for table audit_log |
| SEC-06 | privilege | cm_app cannot create or drop tables | PASS | InsufficientPrivilege: permission denied for schema public |
| SEC-10 | injection | hostile values in entity_id/start_time/result_limit are rejected as invalid parameters; evidence table intact | PASS | accepted=[] unexpected_exceptions=[] evidence_rows_intact=550 |
| SEC-11 | isolation | an entity identifier belonging to another case cannot be resolved | PASS | numeric id from another case rejected |
| DB-20 | isolation | validity changes in case 1 create no events in case 2 | PASS | case-2 validity events after case-1 changes = 0 |

## 4. Scalability

Model: the case's data is replicated k times inside one case (disjoint copies). Entity-scoped queries stay roughly constant; case-wide queries grow with k. Parameter sets are fixed from the original data. Hardware: 2 vCPU, 8 GB RAM, PostgreSQL 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1), shared_buffers=163848kB, work_mem=4096kB (default configuration, no tuning). 20 repetitions per query after a first (cache-warming) execution is included in the percentiles; p99 on 20 samples equals the maximum.

| Table | 1x | 2x | 5x | 10x |
|---|---|---|---|---|
| entities | 162 | 324 | 810 | 1620 |
| evidence | 373 | 746 | 1865 | 3730 |
| communications | 1276 | 2552 | 6380 | 12760 |
| location_observations | 1265 | 2530 | 6325 | 12650 |
| relationships | 462 | 924 | 2310 | 4620 |
| transactions | 242 | 484 | 1210 | 2420 |
| events | 1 | 2 | 5 | 10 |
| evidence_entities | 392 | 784 | 1960 | 3920 |

p95 latency in ms (all variants, slowest first at the largest scale):

| Query | p95 1x | p95 2x | p95 5x | p95 10x | p50 10x | p99 10x | growth 10x/1x |
|---|---|---|---|---|---|---|---|
| M11.connected | 27.38 | 39.75 | 59.85 | 110.92 | 78.18 | 111.87 | 4.1 |
| M11.shortest | 23.62 | 28.61 | 52.77 | 84.0 | 64.99 | 85.0 | 3.6 |
| M18.overall | 22.86 | 27.28 | 54.1 | 79.12 | 66.47 | 82.29 | 3.5 |
| M1.pairs | 12.7 | 23.16 | 46.71 | 78.13 | 51.84 | 85.84 | 6.2 |
| M8.after | 7.77 | 15.07 | 13.62 | 77.4 | 49.94 | 81.57 | 10.0 |
| M8.before | 7.69 | 15.63 | 12.91 | 74.71 | 64.35 | 75.38 | 9.7 |
| M8.around | 8.66 | 15.98 | 19.36 | 63.91 | 53.37 | 68.85 | 7.4 |
| M15.top_amounts | 4.53 | 5.03 | 10.6 | 22.55 | 21.02 | 22.61 | 5.0 |
| M17.multi_entity | 5.46 | 4.14 | 9.94 | 20.1 | 18.25 | 20.41 | 3.7 |
| M18.evidence_strength | 4.0 | 4.0 | 7.18 | 19.61 | 14.11 | 19.64 | 4.9 |
| M3.copresence | 15.88 | 19.41 | 14.58 | 15.64 | 13.38 | 15.7 | 1.0 |
| M15.repeated_or_unusual | 32.32 | 4.5 | 9.76 | 15.63 | 13.17 | 16.32 | 0.5 |
| M17.multi_type | 2.85 | 5.07 | 6.75 | 15.2 | 10.95 | 17.82 | 5.3 |
| M18.reliability | 1.32 | 0.91 | 1.25 | 3.35 | 3.04 | 4.86 | 2.5 |
| M18.multi_domain | 8.91 | 5.86 | 3.56 | 3.15 | 1.46 | 5.34 | 0.4 |
| M7.default | 3.45 | 1.05 | 2.1 | 2.15 | 0.6 | 2.36 | 0.6 |
| M17.corroborating | 2.33 | 0.52 | 0.98 | 1.98 | 1.65 | 4.12 | 0.8 |
| M6.default | 2.95 | 1.24 | 1.77 | 1.58 | 1.37 | 2.76 | 0.5 |
| M15.patterns | 1.62 | 0.43 | 1.37 | 1.37 | 1.23 | 1.51 | 0.8 |
| M14.repeated | 1.15 | 0.36 | 0.74 | 1.3 | 0.63 | 2.03 | 1.1 |
| M1.contacts | 2.69 | 1.58 | 1.01 | 1.18 | 0.55 | 1.52 | 0.4 |
| M3.present | 1.71 | 1.16 | 1.07 | 0.88 | 0.65 | 1.4 | 0.5 |
| M1.frequency | 2.32 | 0.85 | 0.59 | 0.82 | 0.58 | 1.4 | 0.4 |
| M12.default | 1.16 | 0.48 | 0.45 | 0.71 | 0.33 | 1.36 | 0.6 |
| M15.entity | 1.37 | 0.31 | 0.31 | 0.69 | 0.19 | 1.17 | 0.5 |
| M2.default | 1.25 | 0.76 | 0.48 | 0.65 | 0.26 | 1.14 | 0.5 |
| M4.frequency | 1.1 | 0.96 | 0.59 | 0.65 | 0.43 | 0.7 | 0.6 |
| M4.shared | 1.78 | 1.12 | 0.34 | 0.56 | 0.21 | 1.12 | 0.3 |
| M18.connected_both | 4.51 | 2.63 | 0.77 | 0.54 | 0.37 | 2.41 | 0.1 |
| M5.frequency | 0.93 | 0.96 | 0.26 | 0.53 | 0.3 | 1.01 | 0.6 |
| M9.default | 1.3 | 0.64 | 0.9 | 0.44 | 0.22 | 1.2 | 0.3 |
| M14.near_location | 1.15 | 0.29 | 1.92 | 0.38 | 0.22 | 1.12 | 0.3 |
| M15.between | 1.76 | 0.31 | 0.7 | 0.36 | 0.18 | 1.14 | 0.2 |
| M13.default | 1.19 | 0.3 | 0.57 | 0.32 | 0.19 | 1.04 | 0.3 |
| M16.entity | 1.0 | 0.56 | 0.72 | 0.31 | 0.14 | 0.91 | 0.3 |
| M5.history | 1.06 | 0.59 | 0.29 | 0.29 | 0.17 | 1.23 | 0.3 |
| M16.event | 1.11 | 0.25 | 0.52 | 0.27 | 0.15 | 0.7 | 0.2 |
| M14.associated_entities | 1.78 | 0.48 | 0.32 | 0.26 | 0.13 | 0.9 | 0.1 |
| M10.default | 1.05 | 0.55 | 0.24 | 0.23 | 0.11 | 0.83 | 0.2 |

### EXPLAIN (ANALYZE, BUFFERS) for the six slowest queries at the largest scale

| Query | Execution ms | Planning ms | Seq scans (relation, ms, rows) |
|---|---|---|---|
| M11.connected | 99.493 | 0.781 | [['relationships', 0.7, 4600], ['evidence', 0.5, 3730], ['communications', 1.1, 12760], ['evidence', 0.5, 3730], ['transactions', 0.2, 2420], ['evidence', 0.4, 3730], ['entities', 2.3, 1620], ['entities', 2.1, 1620]] |
| M11.shortest | 94.784 | 0.853 | [['relationships', 0.7, 4600], ['evidence', 0.5, 3730], ['communications', 1.8, 12760], ['evidence', 0.5, 3730], ['transactions', 0.3, 2420], ['evidence', 0.8, 3730], ['entities', 0.2, 1620], ['entities', 0.1, 1620]] |
| M18.overall | 84.055 | 3.827 | [['events', 0.0, 1], ['event_entities', 0.0, 11], ['location_observations', 1.9, 13203], ['evidence', 0.9, 3907], ['communications', 6.0, 13283], ['evidence', 1.0, 3907], ['communications', 1.3, 13283], ['evidence', 0.4, 3907], ['transactions', 0.2, 2523], ['evidence', 0.5, 3907], ['transactions', 0.2, 2523], ['evidence', 0.6, 3907], ['event_entities', 0.0, 11], ['events', 0.0, 11], ['communications', 1.3, 12760], ['evidence', 0.6, 3730], ['communications', 1.2, 12760], ['evidence', 0.6, 3730], ['transactions', 0.3, 2420], ['evidence', 0.5, 3730], ['transactions', 0.3, 2420], ['evidence', 0.5, 3730], ['relationships', 0.7, 4600], ['evidence', 0.5, 3730], ['relationships', 0.6, 4600], ['evidence', 0.5, 3730], ['evidence_entities', 0.3, 3920], ['evidence', 0.5, 3730]] |
| M1.pairs | 60.224 | 0.472 | [['communications', 1.5, 12760], ['evidence', 0.5, 3730]] |
| M8.after | 71.265 | 1.297 | [['location_observations', 1.7, 12650], ['evidence', 0.7, 3730], ['communications', 5.7, 12760], ['evidence', 0.7, 3730], ['communications', 1.4, 12760], ['evidence', 0.5, 3730], ['transactions', 0.2, 2420], ['evidence', 0.6, 3730], ['transactions', 0.3, 2420], ['evidence', 0.8, 3730], ['event_entities', 0.0, 10], ['events', 0.0, 10], ['events', 0.0, 1]] |
| M8.before | 56.636 | 1.702 | [['location_observations', 5.7, 12650], ['evidence', 0.7, 3730], ['communications', 1.9, 12760], ['evidence', 0.6, 3730], ['communications', 1.9, 12760], ['evidence', 0.9, 3730], ['transactions', 0.4, 2420], ['evidence', 0.9, 3730], ['transactions', 0.4, 2420], ['evidence', 1.0, 3730], ['event_entities', 0.0, 10], ['events', 0.0, 10], ['events', 0.0, 1]] |

### Index experiment (measured before adding anything)

Queries slower than 50 ms (p95) at the largest scale: M1.pairs, M8.before, M8.after, M8.around, M11.connected, M11.shortest, M18.overall. Each candidate index was created on its own, the queries re-measured, and the index dropped.

| Candidate index | Query | p95 before | p95 after |
|---|---|---|---|
| idx_cand_obs_loc_subj | M1.pairs | 78.13 | 67.31 |
| idx_cand_obs_loc_subj | M8.before | 74.71 | 76.75 |
| idx_cand_obs_loc_subj | M8.after | 77.4 | 63.72 |
| idx_cand_obs_loc_subj | M8.around | 63.91 | 70.12 |
| idx_cand_obs_loc_subj | M11.connected | 110.92 | 94.51 |
| idx_cand_obs_loc_subj | M11.shortest | 84.0 | 98.59 |
| idx_cand_obs_loc_subj | M18.overall | 79.12 | 84.87 |
| idx_cand_evid_ent_ev | M1.pairs | 78.13 | 69.13 |
| idx_cand_evid_ent_ev | M8.before | 74.71 | 67.49 |
| idx_cand_evid_ent_ev | M8.after | 77.4 | 84.71 |
| idx_cand_evid_ent_ev | M8.around | 63.91 | 81.61 |
| idx_cand_evid_ent_ev | M11.connected | 110.92 | 106.1 |
| idx_cand_evid_ent_ev | M11.shortest | 84.0 | 71.91 |
| idx_cand_evid_ent_ev | M18.overall | 79.12 | 66.24 |
| idx_cand_event_ent | M1.pairs | 78.13 | 88.09 |
| idx_cand_event_ent | M8.before | 74.71 | 55.98 |
| idx_cand_event_ent | M8.after | 77.4 | 69.16 |
| idx_cand_event_ent | M8.around | 63.91 | 72.52 |
| idx_cand_event_ent | M11.connected | 110.92 | 113.14 |
| idx_cand_event_ent | M11.shortest | 84.0 | 98.12 |
| idx_cand_event_ent | M18.overall | 79.12 | 84.15 |
| idx_cand_comm_time | M1.pairs | 78.13 | 83.63 |
| idx_cand_comm_time | M8.before | 74.71 | 60.39 |
| idx_cand_comm_time | M8.after | 77.4 | 54.85 |
| idx_cand_comm_time | M8.around | 63.91 | 68.72 |
| idx_cand_comm_time | M11.connected | 110.92 | 96.12 |
| idx_cand_comm_time | M11.shortest | 84.0 | 96.26 |
| idx_cand_comm_time | M18.overall | 79.12 | 82.96 |
| idx_cand_obs_time | M1.pairs | 78.13 | 87.77 |
| idx_cand_obs_time | M8.before | 74.71 | 66.08 |
| idx_cand_obs_time | M8.after | 77.4 | 70.03 |
| idx_cand_obs_time | M8.around | 63.91 | 70.43 |
| idx_cand_obs_time | M11.connected | 110.92 | 79.78 |
| idx_cand_obs_time | M11.shortest | 84.0 | 91.97 |
| idx_cand_obs_time | M18.overall | 79.12 | 96.09 |

**Reading:** `M1.pairs` reads only `communications`, yet its p95 moved between 67.31 and 88.09 ms (baseline 78.13) when indexes on unrelated tables were created. That spread is the measurement noise floor on this shared 2-vCPU machine. Changes inside that band are not evidence of benefit, so **no index was added** and no migration changed. A proper index study would need many more repetitions on dedicated hardware.

## 5. Defects found by this phase and fixed

1. **M8 `around` ranked unknown above confirmed (SQL defect).** `bool_or(location = incident_location)` is NULL when none of an entity's records has a location, and `ORDER BY ... DESC` puts NULLs first, so entities with no located records were listed *above* entities confirmed at the incident location. Before the fix 90 of 96 oracle comparisons for this variant disagreed (evidence preserved in `results/bugevidence_M8_prefix/`; that earlier trial also contained harness errors for other variants that were fixed in the harness, not the SQL). Fix: `coalesce(bool_or(...), false)`; module version 1.0 → 1.1. After the fix: 96/96 match.
2. **NUL byte / oversized identifier raised an unhandled driver error (SEC-10).** `P-001\x00` as `entity_id` surfaced as a `DataError` instead of a 422 validation error. Fix in `sql_engine.resolve_entity/resolve_event`; regression test `test_nul_and_oversized_identifiers_are_validation_errors_not_server_errors`.

## 6. Limitations
- Oracles were written by the same author as the SQL, from the module specification; independence is procedural (separate data path, no shared code), not organisational. A shared misreading of the specification would pass both.
- Oracles exist for M1–M17 and M18.reliability and Q40; M18 `evidence_strength`, `connected_both` and `multi_domain` have none.
- Datasets contain few vehicles (some seeds none); vehicle modules are exercised mainly through the injected edge-case vehicle.
- Scalability replicates one synthetic case; real data would have different skew. Machine: 2 vCPU container; latencies are indicative, not benchmarks. Cold-cache behaviour was not measured separately.
- Concurrency was checked for `change_validity()` on one row with 8 threads (one run); it shows no corruption in that run, not proof of freedom from races.
- Authentication/authorisation at the HTTP layer is covered by the backend test-suite, not by a Phase 7 experiment; audit-log integrity is checked at the database level (append-only, mirrored validity events).

## 7. Reproduce
`python -m research.phase7.run_phase7` (stages: `--stages oracles q40 db perf`; `--quick` for a smoke run), then `python research/phase7/reports/make_docs.py` and `python research/phase7/reports/make_report.py`. Tests: `python -m pytest research/phase7/tests`.
