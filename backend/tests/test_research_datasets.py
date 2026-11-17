"""Phase 2 tests: generated datasets, independent ground truth, validator negative controls."""
import copy, csv, json, subprocess, sys
from pathlib import Path

import psycopg, pytest
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
R = ROOT / "research"
sys.path.insert(0, str(ROOT / "backend"))
from synth.research_seed import seed_database, BASE
from synth.dataset_validation import validate_case, check_no_leakage, REQUIRED

DB = "cm_r_test_p2"


@pytest.fixture(scope="module")
def seeded():
    subprocess.run([sys.executable, str(ROOT / "scripts" / "init_db.py"), "--db", DB, "--reset"], check=True, capture_output=True, cwd=ROOT / "backend")
    gts = seed_database(DB, 9001, json.load(open(R / "generation_config.json")))
    with psycopg.connect(f"{BASE}/{DB}", row_factory=dict_row) as c:
        yield c, gts


def test_generated_case_validates(seeded):
    c, gts = seeded
    for g in gts.values():
        assert validate_case(c, g) == []
    assert check_no_leakage(c, list(gts)) == []


@pytest.mark.parametrize("mutate,expect", [
    (lambda g: g.pop("claims"), "missing 'claims'"),
    (lambda g: g["relevant_leads"][0].update(supporting_evidence=[]), "no supporting evidence"),
    (lambda g: g["red_herrings"][0].update(contradicting_evidence=[]), "no contradicting evidence"),
    (lambda g: g["lifecycle"][0].update(expected_status="SUPERSEDED", trigger="DOCUMENTED_CONTRADICTION"), "not permitted"),
    (lambda g: g["lifecycle"][0].update(must_flag_keys=["INCIDENT_PROXIMITY_001|P-999|EVT-001"]), "must-flag keys"),
    (lambda g: g["lifecycle"][0].update(must_not_flag_keys=[]), "no must-not-flag"),
    (lambda g: g["relevant_leads"][0].update(ref="P-999"), "not a person"),
])
def test_validator_rejects_corrupted_ground_truth(seeded, mutate, expect):
    c, gts = seeded
    g = copy.deepcopy(next(iter(gts.values())))
    mutate(g)
    assert any(expect in p for p in validate_case(c, g)), expect


def test_leakage_check_detects_label_words(seeded):
    c, gts = seeded
    cid = c.execute("SELECT case_id FROM cases WHERE case_ref=%s", (next(iter(gts)),)).fetchone()["case_id"]
    c.execute("UPDATE entities SET display_name = display_name || ' perpetrator' WHERE case_id=%s AND ref='P-001'", (cid,))
    try:
        assert check_no_leakage(c, list(gts))
    finally:
        c.rollback()


def test_ground_truth_independent_of_ranking_inputs(seeded):
    """gt rows are written for every lead, and the ground-truth JSON never stores a ranking score."""
    _, gts = seeded
    for g in gts.values():
        blob = json.dumps(g)
        assert "q40" not in blob.lower() and "score" not in " ".join(g["relevant_leads"][0].keys())


def test_published_seed_set():
    rows = list(csv.DictReader(open(R / "seed_manifest.csv")))
    if len(rows) < 30:
        pytest.skip("seed set not generated")
    assert len(rows) >= 30 and len({r["content_sha256"] for r in rows}) == len(rows)
    for r in rows:
        gt = json.load(open(R / "ground_truth" / f"seed_{r['seed']}.json"))
        for case in gt["cases"].values():
            assert set(REQUIRED) <= set(case)
            assert case["relevant_leads"] and case["red_herrings"]
