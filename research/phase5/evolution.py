"""Evidence-evolution experiment. For each scripted lifecycle step: capture the ranking, apply the step through the system's own
change_validity() (which writes the append-only evidence_validity_events), run the system's own recomputation, recompute every
method's ranking, and compare. Expected outcomes come from the generator's ground truth (must_flag / must_not_flag /
indeterminate), NOT from correlation_evidence lineage. History is verified from evidence_validity_events, not from the
current status alone."""
import time
from collections import defaultdict

import numpy as np
from scipy import stats as sps

from app.correlation.engine import recompute_pending
from research.common.casedata import load_case_view
from research.phase3.algorithms.base import tie_key
from research.phase3.metrics.ranking_metrics import evaluate_ranking
from research.phase5.algorithms import make
from synth import scenario
from synth.lifecycle import evaluate_events, history_integrity

EPS = 1e-9


def _scores(view, methods, cfg, dataset_id):
    out = {}
    for m in methods:
        res = make(m).rank(dataset_id, view, cfg)
        out[m] = {"order": [r.lead_id for r in sorted(res, key=lambda r: r.rank)], "score": {r.lead_id: r.raw_score for r in res}}
    return out


def rank_change_metrics(prev, cur, k=5):
    pos0 = {p: i for i, p in enumerate(prev["order"], 1)}
    pos1 = {p: i for i, p in enumerate(cur["order"], 1)}
    ids = sorted(pos0)
    a, b = [pos0[i] for i in ids], [pos1[i] for i in ids]
    disp = [abs(x - y) for x, y in zip(a, b)]
    if len(set(b)) < 2 or a == b:
        tau = 1.0 if a == b else float(sps.kendalltau(a, b).statistic)
        rho = 1.0 if a == b else float(sps.spearmanr(a, b).statistic)
    else:
        tau, rho = float(sps.kendalltau(a, b).statistic), float(sps.spearmanr(a, b).statistic)
    return {"kendall_tau": tau, "spearman_rho": rho, "top_k_overlap": len(set(prev["order"][:k]) & set(cur["order"][:k])) / k,
            "mean_rank_displacement": float(np.mean(disp)), "max_rank_displacement": int(max(disp))}


def person_tokens(keys):
    return {t for k in keys for t in k.split("|")[1:] if t.startswith("P-")}


def run_evolution(conn, case_ref, gt_case, cfg, evo_cfg, dataset_id, user_cfg=None):
    case = dict(conn.execute("SELECT case_id, case_ref FROM cases WHERE case_ref=%s", (case_ref,)).fetchone())
    methods = evo_cfg["methods"]
    grades = gt_case["relevance_grades"]
    gt_steps = {(s["scenario_id"], s["step"]): s for s in gt_case["lifecycle"]}
    view = load_case_view(conn, case_ref)
    state = _scores(view, methods, cfg, dataset_id)
    initial_metrics = {m: evaluate_ranking(state[m]["order"], grades) for m in methods}
    steps, order_applied = [], []
    prev_events = conn.execute("SELECT count(*) n FROM evidence_validity_events WHERE case_id=%s", (case["case_id"],)).fetchone()["n"]
    while True:
        pend = [r for r in scenario.pending(conn) if r["case_ref"] == case_ref]
        if not pend:
            break
        s = pend[0]
        sid = s["scenario_id"].split("@")[0]
        gts = gt_steps[(sid, s["step"])]
        t0 = time.perf_counter()
        res = scenario.apply_step(conn, s["scenario_id"], s["step"])
        t_apply = time.perf_counter() - t0
        t1 = time.perf_counter()
        recompute_pending(conn, case, "system.research")
        conn.commit()
        t_recompute = time.perf_counter() - t1
        flagged = set(res["flagged_findings"])
        must, neg, indet = set(gts["must_flag_keys"]), set(gts["must_not_flag_keys"]), set(gts["indeterminate_keys"])
        t2 = time.perf_counter()
        view = load_case_view(conn, case_ref)
        cur = _scores(view, methods, cfg, dataset_id)
        t_rank = (time.perf_counter() - t2) / len(methods)
        touched = set(gts["touched_entities"])
        expected_people = person_tokens(must)
        row = {"scenario": sid, "step": s["step"], "evidence_ref": s["evidence_ref"], "new_status": s["expected_status"],
               "flagged": len(flagged), "flagged_keys": sorted(flagged), "must_keys": sorted(must), "must_flag": len(must), "must_not_flag": len(neg), "indeterminate": len(indet),
               "detected_expected": len(flagged & must), "missed_expected": len(must - flagged), "false_alarm_must_not": len(flagged & neg),
               "flagged_indeterminate": len(flagged & indet), "flagged_unclassified": len(flagged - must - neg - indet),
               "apply_ms": t_apply * 1000, "recompute_ms": t_recompute * 1000, "rank_ms_per_method": t_rank * 1000, "methods": {}}
        for m in methods:
            ds = {p: cur[m]["score"][p] - state[m]["score"][p] for p in cur[m]["score"]}
            changed = {p for p, d in ds.items() if abs(d) > EPS}
            row["methods"][m] = {**rank_change_metrics(state[m], cur[m], evo_cfg["top_k_overlap"]),
                                 "n_score_changes": len(changed), "unnecessary_changes": len(changed - touched),
                                 "changes_on_touched": len(changed & touched), "expected_people": len(expected_people),
                                 "expected_people_updated": len(expected_people & changed), "missed_expected_updates": len(expected_people - changed),
                                 **{f"after_{k}": v for k, v in evaluate_ranking(cur[m]["order"], grades).items() if k in ("MRR", "AP", "nDCG@5", "P@3", "R@5")}}
        steps.append(row)
        state = cur
        order_applied.append((sid, s["step"]))
    ev = evaluate_events(conn, case_ref)
    hist = history_integrity(conn, case["case_id"])
    rows = conn.execute("""SELECT evidence_id, event_id, changed_at FROM evidence_validity_events WHERE case_id=%s ORDER BY event_id""", (case["case_id"],)).fetchall()
    times = [r["changed_at"] for r in rows]
    unique = len({r["event_id"] for r in rows}) == len(rows)
    final_metrics = {m: evaluate_ranking(state[m]["order"], grades) for m in methods}
    return {"case_ref": case_ref, "steps": steps, "event_eval": ev["summary"], "event_checks_failed": sum(1 for x in ev["steps"] if x.get("applied") and not x.get("transition_ok")),
            "history_ok": hist["ok"], "history_problems": hist["problems"], "events_total": len(rows) - prev_events,
            "event_ids_unique": unique, "event_times_monotonic": times == sorted(times),
            "initial_metrics": initial_metrics, "final_metrics": final_metrics, "final_view": view}
