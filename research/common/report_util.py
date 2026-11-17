"""Helpers that render result files into Markdown. Numbers in reports come from result files, never typed by hand."""
import csv
import json
from pathlib import Path


def md_table(header, rows):
    out = ["| " + " | ".join(map(str, header)) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(map(str, r)) + " |" for r in rows]
    return "\n".join(out)


def f3(x):
    return "n/a" if x is None else f"{float(x):.3f}"


def fp(p):
    p = float(p)
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def agg_table(agg, methods, metrics):
    rows = []
    for m in methods:
        rows.append([m] + [f"{f3(agg[m][k]['mean'])} [{f3(agg[m][k]['ci95_low'])}, {f3(agg[m][k]['ci95_high'])}]" for k in metrics])
    return md_table(["method"] + [f"{k} mean [95% CI]" for k in metrics], rows)


def pair_rows(pairs, metric, focal=None):
    rows = []
    for r in pairs[metric]:
        if focal and focal not in (r["A"], r["B"]):
            continue
        a, b, d = r["A"], r["B"], r["mean_diff"]
        if focal and b == focal:      # orient as focal - other
            a, b, d = b, a, -d
            lo, hi = -r["ci95_high"], -r["ci95_low"]
            w, l = r["losses"], r["wins"]
            rb = -r["rank_biserial"]
        else:
            lo, hi, w, l, rb = r["ci95_low"], r["ci95_high"], r["wins"], r["losses"], r["rank_biserial"]
        rows.append([f"{a} − {b}", f3(d), f"[{f3(lo)}, {f3(hi)}]", fp(r["wilcoxon_p"]), fp(r["p_holm"]), "yes" if r["p_holm"] < 0.05 else "no", f3(rb), f"{w}/{l}/{r['ties']}"])
    return md_table(["comparison", "mean diff", "95% CI", "p (Wilcoxon)", "p (Holm)", "sig. @0.05", "rank-biserial r", "wins/losses/ties (seeds)"], rows)


def latest_run(resdir: Path) -> Path:
    return resdir / (resdir / "LATEST.txt").read_text().strip()


def load_analysis(rundir: Path):
    return json.load(open(rundir / "analysis.json")), json.load(open(rundir / "run_manifest.json"))
