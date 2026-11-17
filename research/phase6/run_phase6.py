"""Phase 6: retrieval evaluation (ablated variants) and answer evaluation (offline template provider) on the golden benchmark.
  python -m research.phase6.run_phase6 [--workers 3]
Live LLM providers are handled by research/phase6/provider_eval.py (NOT RUN when no credentials)."""
import argparse
import json
import random
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "backend"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
from research.common import runmeta   # noqa: E402
from research.common.workspace import SeedWorkspace   # noqa: E402
from research.phase3.statistical_analysis.stats import summarise   # noqa: E402
from research.phase6.metrics import answer_metrics, retrieval_metrics   # noqa: E402

BENCH = ROOT / "research/phase6/benchmark/golden_questions.jsonl"
OUT = ROOT / "research/phase6/results"
VARIANTS = {"full": {}, "bm25_only": {"entity_boost": False, "ref_boost": False, "typo": False}, "no_entity_boost": {"entity_boost": False},
            "no_ref_boost": {"ref_boost": False}, "no_typo": {"typo": False}}


def load_questions():
    return [json.loads(l) for l in BENCH.read_text().splitlines() if l.strip()]


def seed_task(a):
    seed, qs = a
    try:
        from app.ai.context import build_context
        from app.ai.providers import OfflineTemplateProvider
        from app.ai.validator import validate
        from app.retrieval import search_evidence
        from synth import scenario
        rows = []
        prov = OfflineTemplateProvider()
        with SeedWorkspace(seed, prefix="cm_p6") as w:
            cases = {c["case_ref"]: c for c in w.cases()}

            def evaluate(group):
                for q in group:
                    case = cases[q["case_id"]]
                    rel = set(q["supporting_evidence"])
                    row = {"question_id": q["question_id"], "seed": seed, "category": q["category"], "state": q["state"]}
                    ents = {}
                    for r in w.conn.execute("""SELECT e.ref, array_agg(n.ref) AS ents FROM evidence e JOIN evidence_entities ee ON ee.case_id=e.case_id AND ee.evidence_id=e.evidence_id
                                               JOIN entities n ON n.case_id=ee.case_id AND n.entity_id=ee.entity_id WHERE e.case_id=%s GROUP BY e.ref""", (case["case_id"],)):
                        ents[r["ref"]] = r["ents"]
                    applicable = rel and q["evaluation_criteria"].get("retrieval_applicable", True)
                    row["retrieval"] = {}
                    if applicable:
                        all_refs = sorted(ents)
                        for name, kw in VARIANTS.items():
                            res = search_evidence(w.conn, case["case_id"], q["question"], k=50, **kw)
                            row["retrieval"][name] = retrieval_metrics([h["ref"] for h in res["hits"]], rel, ents, q["expected_entities"])
                        rng = random.Random(f"{q['question_id']}")
                        shuffled = rng.sample(all_refs, len(all_refs))
                        row["retrieval"]["random"] = retrieval_metrics(shuffled, rel, ents, q["expected_entities"])
                    else:
                        res = search_evidence(w.conn, case["case_id"], q["question"], k=8)
                        row["hits_returned_full"] = len(res["hits"])
                    ctx = build_context(w.conn, {"case_id": case["case_id"], "case_ref": q["case_id"]}, q["question"])
                    out = prov.generate(ctx, q["question"])
                    problems = validate(out, ctx)
                    names = {r["ref"]: r["display_name"] for r in w.conn.execute("SELECT ref, display_name FROM entities WHERE case_id=%s", (case["case_id"],))}
                    row["answer"] = answer_metrics(q, out, {e["id"] for e in ctx["evidence"]}, problems, names)
                    row["problems"] = problems[:3]
                    rows.append(row)

            evaluate([q for q in qs if q["state"] == "initial"])
            ev = [q for q in qs if q["state"] == "evolved"]
            if ev:
                while True:
                    pend = scenario.pending(w.conn)
                    if not pend:
                        break
                    scenario.apply_step(w.conn, pend[0]["scenario_id"], pend[0]["step"])
                evaluate(ev)
        return {"seed": seed, "rows": rows, "error": None}
    except Exception as e:
        import traceback
        return {"seed": seed, "rows": [], "error": f"{type(e).__name__}: {e} | {traceback.format_exc()[-500:]}"}


def aggregate(rows):
    """Seed = unit: per-seed means per category, then summarised across seeds."""
    cats = sorted({r["category"] for r in rows}) + ["ALL"]
    out = {"retrieval": {}, "answer": {}, "error_attribution": {}}
    for cat in cats:
        sel = [r for r in rows if cat == "ALL" or r["category"] == cat]
        for v in list(VARIANTS) + ["random"]:
            have = [r for r in sel if v in r["retrieval"]]
            if not have:
                continue
            metrics = defaultdict(lambda: defaultdict(list))
            for r in have:
                for k, x in r["retrieval"][v].items():
                    metrics[k][r["seed"]].append(x)
            out["retrieval"].setdefault(cat, {})[v] = {"n_questions": len(have), **{k: summarise([sum(vs) / len(vs) for vs in by.values()]) for k, by in metrics.items()}}
        am = defaultdict(lambda: defaultdict(list))
        for r in sel:
            for k, x in r["answer"].items():
                if isinstance(x, (int, float)) and x is not None:
                    am[k][r["seed"]].append(x)
        out["answer"][cat] = {"n_questions": len(sel), **{k: dict(summarise([sum(vs) / len(vs) for vs in by.values()]), n_questions=sum(len(vs) for vs in by.values())) for k, by in am.items()}}
        et = defaultdict(int)
        for r in sel:
            if "error_type" in r["answer"]:
                et[r["answer"]["error_type"]] += 1
        out["error_attribution"][cat] = dict(et)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    qs = load_questions()
    by_seed = defaultdict(list)
    for q in qs:
        by_seed[int(q["dataset_id"].split("_")[1])].append(q)
    run_id = a.run_id or runmeta.new_run_id("P6")
    outdir = Path(a.out) / run_id
    outdir.mkdir(parents=True, exist_ok=False)
    rows, errors = [], []
    with ProcessPoolExecutor(a.workers) as ex:
        for res in ex.map(seed_task, sorted(by_seed.items())):
            (errors.append({"seed": res["seed"], "error": res["error"]}) if res["error"] else rows.extend(res["rows"]))
            print(res["seed"], "FAILED " + res["error"][:300] if res["error"] else "ok", flush=True)
    json.dump(rows, open(outdir / "per_question_results.json", "w"), indent=0, default=str)
    json.dump(aggregate(rows), open(outdir / "analysis.json", "w"), indent=1, default=str)
    runmeta.write_manifest(outdir, run_id, phase=6, benchmark=json.load(open(BENCH.parent / "benchmark_manifest.json")), status="COMPLETED" if not errors else "COMPLETED_WITH_ERRORS",
                           errors=errors, questions_evaluated=len(rows), provider="offline-template (deterministic, no LLM)", variants=list(VARIANTS) + ["random"])
    if not errors:
        (Path(a.out) / "LATEST.txt").write_text(run_id)
    print("run", run_id, "questions", len(rows), "errors", len(errors))


if __name__ == "__main__":
    main()
