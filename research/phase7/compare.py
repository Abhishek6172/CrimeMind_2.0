"""Run a module variant against PostgreSQL and compare it with its independent oracle."""
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "backend"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
from app.registry import load_modules   # noqa: E402
from app.sql_engine import ALL_PARAMS   # noqa: E402
from research.phase7.oracles.oracles import ORACLES, ORDERED_LIST_KEYS   # noqa: E402

MODULES = load_modules()


def run_sql(conn, module, variant, case_id, params):
    full = {k: None for k in ALL_PARAMS}
    full.update(include_historical=False)
    full.update(params)
    full["case_id"] = case_id
    cur = conn.execute(MODULES[module]["variants"][variant], full)
    return [dict(r) for r in cur.fetchall()]


def norm(v, ordered=False):
    if isinstance(v, datetime):
        return (v if v.tzinfo else v.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()
    if isinstance(v, (Decimal, float)):
        return round(float(v), 6)
    if isinstance(v, (list, tuple)):
        xs = [norm(x) for x in v]
        return tuple(xs) if ordered else tuple(sorted(xs, key=lambda x: (x is None, str(x))))
    return v


def canon(row, keys):
    return tuple((k, norm(row.get(k), k in ORDERED_LIST_KEYS)) for k in keys)


def compare(d, conn, module, variant, params):
    """Returns dict(match, n_sql, n_oracle, problems[]). Rows are compared as multisets over the oracle's output columns;
    the SQL ordering is checked against the oracle's order key (ties may appear in any order)."""
    rows_o, okey = ORACLES[module](d, variant, params)
    rows_s = run_sql(conn, module, variant, d.case_id, params)
    probs = []
    keys = [k for k in (rows_o[0].keys() if rows_o else (rows_s[0].keys() if rows_s else [])) if not k.startswith("_")]
    if rows_o:
        missing = [k for k in keys if rows_s and k not in rows_s[0]]
        if missing:
            probs.append(f"SQL result lacks columns {missing}")
            keys = [k for k in keys if k not in missing]
    co = sorted(canon(r, keys) for r in rows_o) if keys else []
    cs = sorted(canon(r, keys) for r in rows_s) if keys else []
    if len(rows_o) != len(rows_s):
        probs.append(f"row count: sql={len(rows_s)} oracle={len(rows_o)}")
    if co != cs:
        from collections import Counter
        a, b = Counter(co), Counter(cs)
        only_o, only_s = list((a - b).elements())[:2], list((b - a).elements())[:2]
        probs.append(f"content differs; only-in-oracle={only_o} only-in-sql={only_s}")
    # ordering: look each SQL row up in the oracle's rows (by compared content) and check the oracle order key is non-decreasing
    if not probs:
        lookup = {canon(r, keys): okey(r) for r in rows_o}
        seq = [lookup[canon(r, keys)] for r in rows_s]
        if any(seq[i] > seq[i + 1] for i in range(len(seq) - 1)):
            probs.append("SQL row order violates the specified ordering")
    return dict(match=not probs, n_sql=len(rows_s), n_oracle=len(rows_o), problems=probs)
