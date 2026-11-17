"""Generate docs/SQL_MODULES.md from the module files + registry (single source of truth) and the oracle coverage from stored results."""
import json
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1]
ROOT = R.parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "backend"))
from app.registry import QUESTIONS, load_modules   # noqa: E402

latest = (R / "results" / "LATEST.txt").read_text().strip()
summ = json.load(open(R / "results" / latest / "oracle_summary.json"))
mods = load_modules()
out = ["# SQL investigation modules (M1–M18)", "",
       f"Generated from `backend/app/sql_modules/*.sql` and `backend/app/registry.py`; oracle coverage from run `{latest}`. Every module is read-only, case-scoped (`case_id` comes from the authorised case context), uses bind parameters only, and by default returns only evidence in `SUPPORTED` state (`include_historical` widens this).", ""]
for mid in sorted(mods, key=lambda m: int(m[1:])):
    m = mods[mid]
    sql_file = next(Path(ROOT / "backend/app/sql_modules").glob(f"{int(mid[1:]):02d}_*.sql"))
    desc = re.search(r"@description (.*)", sql_file.read_text()).group(1)
    out += [f"## {mid} — {sql_file.stem[3:].replace('_', ' ')}  (v{m['version']})", "", desc, "", f"File: `backend/app/sql_modules/{sql_file.name}`", "",
            "| Variant | Questions | Required parameters | Optional parameters | Oracle comparisons (match / total) |", "|---|---|---|---|---|"]
    for v in m["variants"]:
        qs = [q for q in QUESTIONS if q["module_id"] == mid and q["variant"] == v]
        s = summ.get(f"{mid}.{v}")
        cov = f"{s['matches']} / {s['comparisons']}" if s else ("Q40: see `q40_vs_python.json`" if mid == "M18" and v == "overall" else "no independent oracle (not covered)")
        out.append(f"| `{v}` | {', '.join(q['question_id'] for q in qs)} | {', '.join(sorted({p for q in qs for p in q['required_params']})) or '–'} | {', '.join(sorted({p for q in qs for p in q['optional_params']})) or '–'} | {cov} |")
    out.append("")
out += ["## Common behaviour", "", "- Validation (`sql_engine.validate_params`): only registry-defined parameters; presence, type and range checks; identifiers must resolve inside the authorised case; `start_time <= end_time`; identifier strings bounded to 200 characters and NUL-free (added after Phase 7 finding SEC-10).",
        "- Execution: `SET LOCAL statement_timeout`, one transaction, query audit row written in a separate transaction even on failure.",
        "- Results are recorded facts or correlations, never conclusions of guilt; empty results carry an explicit \"does not establish that the event did not occur\" warning.", ""]
(R / "docs" / "SQL_MODULES.md").write_text("\n".join(out), encoding="utf-8")
print("ok")
