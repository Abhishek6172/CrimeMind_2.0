"""Render PHASE_7_REPORT.md from stored results only."""
import json
from pathlib import Path

R = Path(__file__).resolve().parents[1]
res = R / "results"
run = (res / "LATEST.txt").read_text().strip()
D = res / run
man = json.load(open(D / "run_manifest.json"))
S = json.load(open(D / "oracle_summary.json"))
Q = json.load(open(D / "q40_vs_python.json"))
C = json.load(open(D / "db_security_checks.json"))
P = json.load(open(D / "scalability.json"))
E = json.load(open(D / "edge_mutation_log.json"))
PRE = json.load(open(res / "bugevidence_M8_prefix" / "oracle_summary.json"))
import csv
rows = list(csv.DictReader(open(D / "oracle_comparisons.csv")))
tbl = lambda h, rs: "\n".join(["| " + " | ".join(h) + " |", "|" + "---|" * len(h)] + ["| " + " | ".join(map(str, r)) + " |" for r in rs])
tot = sum(v["comparisons"] for v in S.values()); mm = sum(v["mismatches"] for v in S.values())
nonempty = sum(1 for r in rows if int(r["n_oracle"] or 0) > 0)
by_src = {}
for r in rows:
    by_src.setdefault(r["source"], [0, 0])[0] += 1; by_src[r["source"]][1] += r["match"] == "True"
acc = {}
for l in E:
    for m in l["mutations"]:
        k = m["mutation"].split(" #")[0].split(" amount")[0]
        a = acc.setdefault(k, [0, 0, m.get("reason", "")]); a[0 if m["accepted"] else 1] += 1
        if not m["accepted"]: a[2] = m["reason"][:90]
o = [f"# Phase 7 Report: SQL Module Verification, Database Correctness, Security and Scalability\n",
     f"Run ID: `{run}` (git `{run.split('-')[-1]}`). PostgreSQL {man['environment'].get('postgresql') or P['config']['postgres']}; all databases are disposable research databases regenerated from committed seeds; the application database was never touched. Synthetic data only.\n",
     "## 1. Status\n", tbl(["Component", "Status"], [["SQL module documentation (docs/SQL_MODULES.md, generated)", "EXECUTED"], ["Independent Python oracles M1–M17 (all variants) and M18.reliability", "EXECUTED"],
        ["M18.overall (Q40) vs independent Python re-implementation", "EXECUTED"], ["M18.evidence_strength / connected_both / multi_domain oracles", "NOT IMPLEMENTED (no independent oracle)"],
        ["Database correctness, isolation, security, concurrency checks", "EXECUTED"], ["Scalability 1x/2x/5x/10x + EXPLAIN ANALYZE + index experiment", "EXECUTED (synthetic replication model)"], ["HTTP-level authentication/authorisation tests", "Covered by backend/tests/test_security.py (73 backend tests pass); not re-run as an experiment"]]), "",
     "## 2. Oracle comparison\n",
     f"{tot} comparisons over {len(S)} module variants: **{tot - mm} matched, {mm} mismatched** (after the fixes in section 5). {nonempty} of {tot} ({100*nonempty/tot:.0f}%) had a non-empty expected result; the remaining comparisons check that SQL and oracle agree on emptiness. Rows are compared as multisets over the oracle's output columns (timestamps normalised to UTC, decimals to 6 places, aggregate arrays as sets) and the SQL ordering is checked against the specified order key (ties in any order).\n",
     tbl(["Source", "Comparisons", "Matches"], [[k, v[0], v[1]] for k, v in by_src.items()]), "",
     "`dataset_csv`: 4 committed datasets (seeds " + ", ".join(map(str, man["config"]["oracle_seeds"])) + "), both cases each, oracle reads the CSV files only. `edge_mutated`: seeds " + ", ".join(map(str, man["config"]["edge_seeds"])) + " after the mutations below; oracle reads the raw base tables.\n",
     tbl(["Variant", "Comparisons", "Matches", "Mismatches"], [[k, v["comparisons"], v["matches"], v["mismatches"]] for k, v in S.items()]), "",
     "### Edge-case mutations (disposable DB)\n", tbl(["Mutation", "Accepted", "Rejected by DB", "Rejection reason"], [[k, v[0], v[1], v[2] if v[1] else ""] for k, v in acc.items()]),
     "\nRejected inserts are documented behaviour (constraints), not oracle gaps. Mixed validity states (CHALLENGED, INVALIDATED, SUPERSEDED, applied through `change_validity()`) were exercised with `include_historical` on and off, together with duplicates, NULL evidence, NULL strength, contradictory relationships, empty entities, vehicles with open and ended ownership, and zero-width time windows equal to a record's timestamp.\n",
     "### Q40 (M18 `overall`)\n", tbl(["Seed", "Case", "Candidates", "Max |score difference|", "Same candidate set"], [[q["seed"], q["case"], q["candidates"], q["max_abs_score_diff"], q["same_candidate_set"]] for q in Q]),
     "\nThe frozen Q40 SQL is unchanged; `q40_py` is an independent Python statement of the same scoring.\n",
     "## 3. Database correctness, isolation and security checks\n", f"{sum(c['result']=='PASS' for c in C)} of {len(C)} checks passed.\n",
     tbl(["ID", "Area", "Check", "Result", "Observed"], [[c["id"], c["area"], c["check"], c["result"], c["observed"][:110].replace("|", "/")] for c in C]), "",
     "## 4. Scalability\n",
     "Model: the case's data is replicated k times inside one case (disjoint copies). Entity-scoped queries stay roughly constant; case-wide queries grow with k. Parameter sets are fixed from the original data. "
     f"Hardware: 2 vCPU, 8 GB RAM, PostgreSQL {P['config']['postgres']}, shared_buffers={P['config'].get('shared_buffers')}, work_mem={P['config'].get('work_mem')} (default configuration, no tuning). "
     f"{man['config']['perf']['repetitions']} repetitions per query after a first (cache-warming) execution is included in the percentiles; p99 on 20 samples equals the maximum.\n"]
sc = sorted(P["scales"], key=int)
hdr = ["Table", *[f"{k}x" for k in sc]]
o += [tbl(hdr, [[t, *[P["scales"][k]["table_rows"][t] for k in sc]] for t in P["scales"][sc[0]]["table_rows"]]), ""]
names = sorted(P["scales"][sc[-1]]["latency"], key=lambda n: -P["scales"][sc[-1]]["latency"][n].get("p95_ms", 0))
o += ["p95 latency in ms (all variants, slowest first at the largest scale):\n", tbl(["Query", *[f"p95 {k}x" for k in sc], f"p50 {sc[-1]}x", f"p99 {sc[-1]}x", f"growth {sc[-1]}x/1x"],
      [[n, *[P["scales"][k]["latency"][n].get("p95_ms", "ERR") for k in sc], P["scales"][sc[-1]]["latency"][n].get("p50_ms"), P["scales"][sc[-1]]["latency"][n].get("p99_ms"),
        round(P["scales"][sc[-1]]["latency"][n]["p95_ms"] / max(P["scales"][sc[0]]["latency"][n]["p95_ms"], .01), 1)] for n in names]), "",
      "### EXPLAIN (ANALYZE, BUFFERS) for the six slowest queries at the largest scale\n", tbl(["Query", "Execution ms", "Planning ms", "Seq scans (relation, ms, rows)"], [[k, v["execution_ms"], v["planning_ms"], v["seq_scans"]] for k, v in P["plans"].items()]), "",
      "### Index experiment (measured before adding anything)\n"]
ie = P["index_experiment"]
o += [f"Queries slower than {ie['threshold_ms']} ms (p95) at the largest scale: {', '.join(ie['queries_over_threshold']) or 'none'}. Each candidate index was created on its own, the queries re-measured, and the index dropped.\n"]
rowsx = [[n, q, c["before_p95"], c["after_p95"]] for n, qs in ie["candidates"].items() for q, c in qs.items()]
o += [tbl(["Candidate index", "Query", "p95 before", "p95 after"], rowsx), "",
      f"**Reading:** `M1.pairs` reads only `communications`, yet its p95 moved between {min(ie['candidates'][n]['M1.pairs']['after_p95'] for n in ie['candidates'] if n != 'idx_cand_comm_time')} and {max(ie['candidates'][n]['M1.pairs']['after_p95'] for n in ie['candidates'] if n != 'idx_cand_comm_time')} ms (baseline {ie['candidates']['idx_cand_comm_time']['M1.pairs']['before_p95']}) when indexes on unrelated tables were created. That spread is the measurement noise floor on this shared 2-vCPU machine. Changes inside that band are not evidence of benefit, so **no index was added** and no migration changed. A proper index study would need many more repetitions on dedicated hardware.\n",
      "## 5. Defects found by this phase and fixed\n",
      f"1. **M8 `around` ranked unknown above confirmed (SQL defect).** `bool_or(location = incident_location)` is NULL when none of an entity's records has a location, and `ORDER BY ... DESC` puts NULLs first, so entities with no located records were listed *above* entities confirmed at the incident location. Before the fix {PRE['M8.around']['mismatches']} of {PRE['M8.around']['comparisons']} oracle comparisons for this variant disagreed (evidence preserved in `results/bugevidence_M8_prefix/`; that earlier trial also contained harness errors for other variants that were fixed in the harness, not the SQL). Fix: `coalesce(bool_or(...), false)`; module version 1.0 → 1.1. After the fix: {S['M8.around']['matches']}/{S['M8.around']['comparisons']} match.",
      "2. **NUL byte / oversized identifier raised an unhandled driver error (SEC-10).** `P-001\\x00` as `entity_id` surfaced as a `DataError` instead of a 422 validation error. Fix in `sql_engine.resolve_entity/resolve_event`; regression test `test_nul_and_oversized_identifiers_are_validation_errors_not_server_errors`.", "",
      "## 6. Limitations\n- Oracles were written by the same author as the SQL, from the module specification; independence is procedural (separate data path, no shared code), not organisational. A shared misreading of the specification would pass both.",
      "- Oracles exist for M1–M17 and M18.reliability and Q40; M18 `evidence_strength`, `connected_both` and `multi_domain` have none.",
      "- Datasets contain few vehicles (some seeds none); vehicle modules are exercised mainly through the injected edge-case vehicle.",
      "- Scalability replicates one synthetic case; real data would have different skew. Machine: 2 vCPU container; latencies are indicative, not benchmarks. Cold-cache behaviour was not measured separately.",
      "- Concurrency was checked for `change_validity()` on one row with 8 threads (one run); it shows no corruption in that run, not proof of freedom from races.",
      "- Authentication/authorisation at the HTTP layer is covered by the backend test-suite, not by a Phase 7 experiment; audit-log integrity is checked at the database level (append-only, mirrored validity events).", "",
      "## 7. Reproduce\n`python -m research.phase7.run_phase7` (stages: `--stages oracles q40 db perf`; `--quick` for a smoke run), then `python research/phase7/reports/make_docs.py` and `python research/phase7/reports/make_report.py`. Tests: `python -m pytest research/phase7/tests`.\n"]
(R / "PHASE_7_REPORT.md").write_text("\n".join(o), encoding="utf-8")
print("ok")
