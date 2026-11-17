# Synthetic generator and ground-truth format

Code: `backend/synth/generator.py` (world), `seed.py` (database seeding, ground truth, scenarios), `scenario.py` (evolution runner), `evaluate.py` (metrics).
All identities are fictional. Command: `python -m synth.seed --db <name> --seed <int>` (default seed 2026; database created first with `scripts/init_db.py --db <name> --reset`).

## What is random and what is scripted

| Element | Source |
|---|---|
| Background persons (~100 in CASE-2026-001, ~25 in CASE-2026-002): names, homes, workplaces, friend groups | `random.Random(seed)` |
| Background routines: observations, communications, transactions, CCTV sightings | `random.Random(seed)` |
| The incident (EVT-001 "Green Park Incident"), victim Meera Kulkarni (P-001), and 8 reserved named characters | scripted, identical in every seed |
| Planted evidence trails for perpetrator, accomplice, red herring, witnesses | scripted, identical in every seed |
| Evolution scenarios (6 steps, 4 scenario ids) | scripted |

Verified at baseline: same seed gives byte-identical evidence (md5 of ref/type/source/description equal across two runs); a different seed changes counts (seed 2026: 1304 observations, 1211 communications; seed 7: 1321, 1321) while the ground-truth leads stay P-002, P-003.

## Ground-truth schema (`gt`, readable only by the admin role; the application role `cm_app` has no access)

| Table | Columns | Content for CASE-2026-001 |
|---|---|---|
| `gt.entity_roles` | case_ref, entity_ref, role (VICTIM, PERPETRATOR, ACCOMPLICE, RED_HERRING, WITNESS, BYSTANDER), notes | P-001 victim; P-002 perpetrator; P-003 accomplice; P-004 red herring; witness and 3 bystanders |
| `gt.expected_leads` | case_ref, entity_ref, rank_hint | P-002 (1), P-003 (2) |
| `gt.scenario_events` | scenario_id, step, case_ref, description, evidence_ref, payload (new records that arrive), triggering_evidence_ref, expected_status, trigger_code, reason_code, expected_affected_finding_keys | 6 rows: SC-GPS17-FAULT 1-2, SC-ACCESS-CORRECTED 1, SC-WITNESS 1-2, SC-TIP-RETRACTED 1 |

Scenario steps are applied through the system's own `change_validity()`; the runner never edits findings. `expected_affected_finding_keys` is currently derived from `correlation_evidence` (see status doc, caveat 3).

## Metrics implemented today (`synth/evaluate.py`)

Precision@K and Recall@K of Q40 vs `gt.expected_leads`, red-herring rank, scenario steps at expected validity status, and stale-CURRENT-findings count. Not yet implemented: F1, MRR, nDCG, confidence intervals, baselines, per-seed aggregation.

## What the ground truth does not contain yet

Per-lead supporting and contradicting evidence lists; findings that should become invalid vs merely recomputed; graded relevance; multiple storylines.
