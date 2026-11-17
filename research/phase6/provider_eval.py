"""LLM provider evaluation harness. Runs a sample of the golden benchmark through each CONFIGURED provider and scores the answers with
the same deterministic metrics as the offline provider. A provider without credentials is reported NOT_RUN, never simulated.

  python -m research.phase6.provider_eval [--sample 20] [--out research/phase6/results/providers]
Environment: GEMINI_API_KEY / GEMINI_MODEL, ANTHROPIC_API_KEY / ANTHROPIC_MODEL (keys are read from the environment or .env and never logged)."""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "backend"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def configured_providers(transport=None):
    from app import config
    from app.ai.providers import AnthropicProvider, GeminiProvider
    out = {}
    out["gemini"] = (GeminiProvider(config.GEMINI_API_KEY, config.GEMINI_MODEL, transport), config.GEMINI_MODEL) if config.GEMINI_API_KEY else (None, "GEMINI_API_KEY is not set")
    out["anthropic"] = (AnthropicProvider(config.ANTHROPIC_API_KEY, config.ANTHROPIC_MODEL, transport), config.ANTHROPIC_MODEL) if config.ANTHROPIC_API_KEY else (None, "ANTHROPIC_API_KEY is not set")
    return out


def run_provider(provider, questions, conn_for_case):
    """questions: benchmark dicts; conn_for_case(q) -> (conn, case dict). Returns per-question rows with call statistics."""
    from app.ai.context import build_context
    from app.ai.providers import ProviderUnavailable
    from app.ai.validator import validate
    from research.phase6.metrics import answer_metrics
    rows = []
    for q in questions:
        conn, case = conn_for_case(q)
        ctx = build_context(conn, case, q["question"])
        t0 = time.perf_counter()
        rec = {"question_id": q["question_id"], "category": q["category"]}
        try:
            out = provider.generate(ctx, q["question"])
            problems = validate(out, ctx)
            rec.update(status="OK" if not problems else "INVALID", problems=problems[:3], answer=answer_metrics(q, out, {e["id"] for e in ctx["evidence"]}, problems))
        except ProviderUnavailable as e:
            rec.update(status="UNAVAILABLE", error=str(e))
        except (ValueError, KeyError, TypeError) as e:
            rec.update(status="INVALID", error=type(e).__name__)
        rec["wall_ms"] = (time.perf_counter() - t0) * 1000
        rec["call"] = getattr(provider, "last_call", None)
        rows.append(rec)
    return rows


def summarise(rows):
    ok = [r for r in rows if r["status"] == "OK"]
    lat = sorted(r["wall_ms"] for r in rows)
    tok = [r["call"]["usage"] for r in rows if r.get("call") and r["call"].get("usage")]
    return {"questions": len(rows), "ok": len(ok), "invalid": sum(r["status"] == "INVALID" for r in rows), "unavailable": sum(r["status"] == "UNAVAILABLE" for r in rows),
            "retries": sum(max(0, (r.get("call") or {}).get("attempts", 1) - 1) for r in rows), "p50_ms": lat[len(lat) // 2] if lat else None,
            "p95_ms": lat[int(0.95 * (len(lat) - 1))] if lat else None, "usage_records": len(tok), "usage_example": tok[0] if tok else None}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=20)
    ap.add_argument("--out", default=str(ROOT / "research/phase6/results/providers"))
    a = ap.parse_args(argv)
    from research.common import runmeta
    from research.common.workspace import SeedWorkspace
    qs = [json.loads(l) for l in (ROOT / "research/phase6/benchmark/golden_questions.jsonl").read_text().splitlines()]
    qs = [q for q in qs if q["state"] == "initial"]
    qs = qs[:: max(1, len(qs) // a.sample)][: a.sample]
    run_id = runmeta.new_run_id("P6PROV")
    outdir = Path(a.out) / run_id
    outdir.mkdir(parents=True, exist_ok=True)
    report = {"offline-template": {"status": "EXECUTED", "note": "deterministic template, not an LLM; evaluated on the full benchmark by research/phase6/run_phase6.py"}}
    for name, (prov, info) in configured_providers().items():
        if prov is None:
            report[name] = {"status": "NOT_RUN", "reason": info}
            continue
        seeds = sorted({int(q["dataset_id"].split("_")[1]) for q in qs})
        rows = []
        for sd in seeds:
            with SeedWorkspace(sd, prefix="cm_p6p") as w:
                cases = {c["case_ref"]: c for c in w.cases()}
                rows += run_provider(prov, [q for q in qs if q["dataset_id"] == f"seed_{sd}"], lambda q: (w.conn, {"case_id": cases[q["case_id"]]["case_id"], "case_ref": q["case_id"]}))
        report[name] = {"status": "EXECUTED", "model": info, "summary": summarise(rows)}
        json.dump(rows, open(outdir / f"{name}_rows.json", "w"), indent=1, default=str)
    json.dump(report, open(outdir / "provider_report.json", "w"), indent=1)
    runmeta.write_manifest(outdir, run_id, phase=6, kind="provider_evaluation", providers=report)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
