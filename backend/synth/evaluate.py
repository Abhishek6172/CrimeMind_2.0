"""Evaluation against isolated ground truth (SRS 6.12, 17.7). Admin connection only — the app never reads `gt`.

Metrics: Precision@K / Recall@K of Q40 (suspect-prioritisation) vs gt.expected_leads, red-herring rank,
event-based lifecycle metrics (synth/lifecycle.py), and a stale-fact check (no CURRENT finding may rely on non-SUPPORTED evidence).
Usage: python -m synth.evaluate [--db crimemind] [--case CASE-2026-001] [--k 3]
"""
import argparse
import json
import os

import psycopg
from psycopg.rows import dict_row

from .lifecycle import evaluate_events, history_integrity, ranked_q40 as _ranked_q40

BASE = os.environ.get("CM_ADMIN_URL_BASE", "postgresql://postgres:postgres@localhost:5432")


def ranked_q40(conn, case):
    return _ranked_q40(conn, case)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="crimemind")
    ap.add_argument("--case", default="CASE-2026-001")
    ap.add_argument("--k", type=int, default=3)
    a = ap.parse_args()
    with psycopg.connect(f"{BASE}/{a.db}", row_factory=dict_row) as conn:
        case = conn.execute("SELECT case_id, case_ref FROM cases WHERE case_ref=%s", (a.case,)).fetchone()
        conn.execute("SELECT set_config('app.user','system.evaluate',false)")
        expected = {r["entity_ref"] for r in conn.execute("SELECT entity_ref FROM gt.expected_leads WHERE case_ref=%s", (a.case,))}
        herring = {r["entity_ref"] for r in conn.execute("SELECT entity_ref FROM gt.entity_roles WHERE case_ref=%s AND role='RED_HERRING'", (a.case,))}
        ranking = ranked_q40(conn, case)
        topk = ranking[:a.k]
        hits = len(expected & set(topk))
        ev = evaluate_events(conn, a.case)
        stale = conn.execute(
            """SELECT count(DISTINCT f.finding_id) n FROM findings f JOIN finding_evidence_links l ON l.finding_id=f.finding_id AND l.case_id=f.case_id
               JOIN evidence e ON e.evidence_id=l.evidence_id AND e.case_id=l.case_id
               WHERE f.case_id=%s AND f.status='CURRENT' AND e.validity_status<>'SUPPORTED'""", (case["case_id"],)).fetchone()["n"]
        report = {
            "case": a.case, "k": a.k, "ranking_top": topk,
            "precision_at_k": round(hits / max(len(topk), 1), 3), "recall_at_k": round(hits / max(len(expected), 1), 3),
            "red_herring_ranks": {h: (ranking.index(h) + 1 if h in ranking else None) for h in herring},
            "lifecycle": ev["summary"], "lifecycle_steps": ev["steps"],
            "history_integrity": history_integrity(conn, case["case_id"]),
            "stale_current_findings": stale,
            "note": ("Lifecycle metrics are EVENT-BASED: each scripted step is matched to the validity event it should have produced, "
                     "so intermediate states are no longer compared with final states. Steps not yet applied are reported as such "
                     "(run `python -m synth.scenario next`). Ties in the Q40 ranking are broken by entity ref."),
        }
        print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
