"""Result aggregation: one index of every experiment run actually used (CSV / JSON / Markdown) plus headline tables.
Reads stored results only. Nothing is recomputed or typed by hand."""
import csv
import hashlib
import json
from pathlib import Path

R = Path(__file__).resolve().parents[1]
PHASE_DIRS = {"phase3": R / "phase3" / "results", "phase4": R / "phase4" / "results", "phase5": R / "phase5" / "results", "phase6": R / "phase6" / "results", "phase7": R / "phase7" / "results"}


def latest(phase: str) -> Path:
    d = PHASE_DIRS[phase]
    return d / (d / "LATEST.txt").read_text().strip()


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(phase, name):
    return json.load(open(latest(phase) / name))


def index_rows():
    rows = []
    for ph in PHASE_DIRS:
        d = latest(ph)
        m = json.load(open(d / "run_manifest.json"))
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.suffix in (".csv", ".json", ".jsonl"):
                rows.append(dict(phase=ph, run_id=m.get("run_id", d.name), git_commit=m.get("git_commit") or m.get("environment", {}).get("git_commit"), file=str(f.relative_to(R.parent)), bytes=f.stat().st_size, sha256=sha(f)))
    return rows


def headline_ranking():
    """method -> metrics (mean, ci) from Phase 3 + Phase 4 aggregate tables (50 seeds)."""
    out = {}
    for ph in ("phase3", "phase4"):
        for r in csv.DictReader(open(latest(ph) / "aggregate_metrics.csv")):
            out.setdefault(r["method"], {})[r["metric"]] = dict(mean=float(r["mean"]), lo=float(r["ci95_low"]), hi=float(r["ci95_high"]), n=int(r["n_seeds"]))
    return out


def write_index(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    rows = index_rows()
    with open(out / "results_index.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    json.dump(rows, open(out / "results_index.json", "w"), indent=1)
    md = ["# Results index", "", "Every stored result file behind the final report (latest run of each phase). SHA-256 lets a reader confirm a file is the one cited.", "",
          "| Phase | Run ID | Git | File | Bytes | SHA-256 (first 16) |", "|---|---|---|---|---|---|"]
    md += [f"| {r['phase']} | {r['run_id']} | {r['git_commit']} | `{r['file']}` | {r['bytes']} | {r['sha256'][:16]} |" for r in rows]
    (out / "results_index.md").write_text("\n".join(md), encoding="utf-8")
    hr = headline_ranking()
    with open(out / "headline_ranking.csv", "w", newline="", encoding="utf-8") as f:
        mets = sorted({m for v in hr.values() for m in v})
        w = csv.writer(f); w.writerow(["method"] + [f"{m}_{s}" for m in mets for s in ("mean", "ci_low", "ci_high")])
        for k, v in hr.items():
            w.writerow([k] + [x for m in mets for x in ((round(v[m]["mean"], 4), round(v[m]["lo"], 4), round(v[m]["hi"], 4)) if m in v else ("", "", ""))])
    return rows
