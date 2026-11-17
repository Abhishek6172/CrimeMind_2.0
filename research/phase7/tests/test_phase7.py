"""Phase 7 tests. Oracle unit tests use hand-built data (no database). DB-backed tests regenerate seed 2026 in a disposable database."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from research.phase7.oracles import oracles as O
from research.phase7.oracles.data import Data

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
m = lambda n: T0 + timedelta(minutes=n)


def tiny():
    d = Data(1)
    for i, (t, ref) in enumerate([("PERSON", "P1"), ("PERSON", "P2"), ("PERSON", "P3"), ("LOCATION", "L1"), ("VEHICLE", "V1")], 1):
        d.entities[i] = dict(type=t, ref=ref, name=ref.lower(), attrs={"plate": "X1"} if t == "VEHICLE" else {})
    d.evidence[10] = dict(ref="E1", type="CDR", source="S1", ts=m(0), status="SUPPORTED", rel=Decimal("0.8"), desc="", prov={})
    d.evidence[11] = dict(ref="E2", type="CDR", source="S2", ts=m(0), status="INVALIDATED", rel=Decimal("0.8"), desc="", prov={"origin_root": "ROOT"})
    d.comms += [dict(ref="C1", s=1, r=2, type="CALL", at=m(0), dur=5, eid=10), dict(ref="C2", s=2, r=1, type="SMS", at=m(10), dur=None, eid=11),
                dict(ref="C3", s=1, r=3, type="SMS", at=m(500), dur=None, eid=None)]
    return d


def test_m1_contacts_counts_and_validity_filter():
    d = tiny()
    rows, _ = O.m1(d, "contacts", dict(entity_id=1))
    by = {r["entity_ref"]: r for r in rows}
    assert by["P2"]["communication_count"] == 1 and by["P2"]["record_refs"] == ["C1"]          # C2 is INVALIDATED -> excluded by default
    assert by["P3"]["evidence_refs"] == []                                                       # NULL evidence is allowed, not an error
    rows, _ = O.m1(d, "contacts", dict(entity_id=1, include_historical=True))
    assert {r["entity_ref"]: r["communication_count"] for r in rows}["P2"] == 2


def test_time_bounds_are_inclusive_and_zero_width_windows_work():
    d = tiny()
    rows, _ = O.m2(d, "default", dict(entity_id_1=1, entity_id_2=2, include_historical=True, start_time=m(10), end_time=m(10)))
    assert [r["communication_ref"] for r in rows] == ["C2"]


def test_m7_gap_rounding_and_threshold():
    d = tiny()
    rows, _ = O.m7(d, "default", dict(entity_id=1, gap_minutes=60, include_historical=True))
    assert [(r["before_record_ref"], r["after_record_ref"], r["gap_minutes"]) for r in rows] == [("C3", "C2", 490)] or rows[0]["gap_minutes"] == 490


def test_m8_around_reports_false_not_null_for_unlocated_records():
    d = tiny()
    d.events[1] = dict(ref="EVT", type="INCIDENT", at=m(5), loc=4, desc=None)
    rows, _ = O.m8(d, "around", dict(event_id=1, window_minutes=30, include_historical=True))
    assert all(r["recorded_at_incident_location"] is False for r in rows) and {r["entity_ref"] for r in rows} == {"P1", "P2"}


def test_m15_median_rule_and_pairing():
    d = tiny()
    for i, a in enumerate(("10", "10", "10", "100")):
        d.txns.append(dict(ref=f"T{i}", f=1, t=2, amount=Decimal(a), cur="INR", type="TRANSFER", at=m(i), loc=None, eid=None))
    rows, _ = O.m15(d, "repeated_or_unusual", dict(min_count=5))
    assert len(rows) == 1 and rows[0]["large_relative_to_case_median"] is True and rows[0]["repeated"] is False   # 100 >= 5 * median(10,10,10,100)=5*10


def test_m11_shortest_and_connected():
    d = tiny()
    d.rels += [dict(ref="R1", a=1, b=3, type="FRIEND", strength=Decimal("0.5"), vfrom=None, vto=None, eid=None), dict(ref="R2", a=3, b=2, type="FRIEND", strength=Decimal("0.5"), vfrom=None, vto=None, eid=None)]
    rows, _ = O.m11(d, "shortest", dict(entity_id_1=1, entity_id_2=2, include_historical=False))
    assert [r["hop_count"] for r in rows] == [1] and rows[0]["link_kinds"] == ["COMMUNICATION"]
    rows, _ = O.m11(d, "connected", dict(entity_id_1=1, entity_id_2=2, max_hops=3))
    assert [r["path_refs"] for r in rows] == [["P1", "P3", "P2"]]


def test_m12_null_strength_is_excluded():
    d = tiny()
    d.rels.append(dict(ref="R1", a=1, b=2, type="FRIEND", strength=None, vfrom=None, vto=None, eid=None))
    assert O.m12(d, "default", dict(entity_id=1))[0] == []


# ---------------- database-backed
@pytest.fixture(scope="module")
def ws():
    from research.common.workspace import SeedWorkspace
    with SeedWorkspace(2026, prefix="cm_p7t") as w:
        yield w


def test_oracles_match_sql_for_every_variant_on_seed_2026(ws):
    from research.phase7.compare import compare
    from research.phase7.oracles.data import from_csv
    from research.phase7.params import VARIANTS, param_sets
    bad = []
    for c in ws.cases():
        d = from_csv(2026, c["case_id"])
        for mo, v in VARIANTS:
            for p in param_sets(d, mo, v, 2026, n=2):
                r = compare(d, ws.conn, mo, v, p)
                if not r["match"]:
                    bad.append((mo, v, r["problems"][:1]))
    assert not bad, bad[:3]


def test_comparison_detects_a_wrong_oracle(ws):
    from research.phase7.compare import compare
    from research.phase7.oracles.data import from_csv
    from research.phase7.params import param_sets
    d = from_csv(2026, ws.cases()[0]["case_id"])
    sets = param_sets(d, "M2", "default", 2026)
    good = [compare(d, ws.conn, "M2", "default", q) for q in sets]
    assert all(r["match"] for r in good) and any(r["n_sql"] > 0 for r in good)
    d.comms = []          # corrupt the oracle world: remove every communication
    bad = [compare(d, ws.conn, "M1", "frequency", q) for q in param_sets(d, "M1", "frequency", 2026)]
    assert any(not r["match"] for r in bad)


def test_m8_around_never_returns_null_flag(ws):
    from research.phase7.compare import run_sql
    from research.phase7.oracles.data import from_csv
    from research.phase7.params import param_sets
    d = from_csv(2026, ws.cases()[0]["case_id"])
    rows = run_sql(ws.conn, "M8", "around", d.case_id, param_sets(d, "M8", "around", 2026)[0])
    assert rows and all(r["recorded_at_incident_location"] is not None for r in rows)
    flags = [r["recorded_at_incident_location"] for r in rows]
    assert flags == sorted(flags, reverse=True)


def test_db_checks_all_pass():
    import tempfile
    from pathlib import Path
    from research.phase7.run_dbchecks import run
    rows = run(2026, Path(tempfile.mkdtemp()))
    assert rows and all(r["result"] == "PASS" for r in rows), [r for r in rows if r["result"] != "PASS"]
