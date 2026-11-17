# Phase 2 completion report: multi-seed datasets with independent ground truth

## Delivered
- `backend/synth/storylines.py`: parameterised storyline builder (leads of strong/medium/weak evidence, red herrings with an independent alibi, near-scene bystanders, witnesses, optional contradicting witness, vehicle trail, five evidence-evolution scripts). Original generator (`generator.py`, `seed.py`) is untouched.
- `backend/synth/research_seed.py`: seeds one DB per seed (two cases), writes ground truth to the isolated `gt` schema and JSON.
- `backend/synth/dataset_validation.py`: rejects incomplete/inconsistent ground truth, invalid EVLM chains, label-word leakage, and checks `gt` unreadable by the app role.
- `research/generate_datasets.py`, `research/generation_config.json`, `research/seed_manifest.csv`, `research/datasets/seed_<n>/` (10 deterministic CSV.gz tables + manifest), `research/ground_truth/seed_<n>.json`.
- Tests: `backend/tests/test_research_datasets.py` (7 new; suite 71 passed).

## Results (actually run)
- Seeds 2026-2075 (50), 2 cases each, 0 failures, about 52 s with 3 workers.
- Persons per primary case 86-115; 2-4 true leads, 1-2 red herrings; 4-14 lifecycle steps per seed.
- Determinism: seed 2030 regenerated with `--force` gave an identical content hash. 50 distinct content hashes across seeds.
- Lead position in the entity-ref order: mean 0.53, sd 0.29 (uniform is 0.50/0.29), so refs carry no role information.
- All planted claims exist as CURRENT findings; every lifecycle step has non-empty must-not-flag sets.

## Ground-truth independence
Leads, red herrings, claims and supporting/contradicting evidence come from the generator's plan, not from any ranking. Lifecycle tiers: must_flag (planted claims citing the changed evidence), must_not_flag (findings with no entity touched by records citing it), indeterminate (reported, never counted as error). `finding_evidence_links` is not used to define expectations.

## Limitations
- Synthetic data only; claims about real-world performance are not supported.
- must_not_flag is conservative; it does not test stability of findings that share an entity with the changed evidence.
- Storylines share one template family; 50 seeds vary structure and size, not scenario type.
- Some steps have empty must_flag (e.g. alibi/tip retraction affect no planted claim); recall there is vacuous and is reported as such.
- Generated datasets are not hand-verified beyond automated validation.

## Preserved
`research/results/baseline/` and Phase 1 results unchanged; original seed-2026 generator output unchanged.
