"""Adapter around the FROZEN Q40 SQL (module M18, variant 'overall'). Q40 itself is not modified or re-implemented.

Q40 returns only entities with association_score > 0 (descending). The adapter gives every other candidate raw score 0.0
so all methods rank the same candidate set. Ranks are then assigned by the common tie rule (see base.assign_ranks); the
native Q40 order (score DESC, entity ref ASC) is preserved in the factors as `native_rank` for the sensitivity analysis."""
from app.sql_engine import execute_question

from .base import RankingAlgorithm, assign_ranks


class Q40Frozen(RankingAlgorithm):
    name = "q40"
    config_version = "q40-frozen-research-baseline-v1"

    def raw(self, case, config):
        conn = case.db
        conn.execute("SELECT set_config('app.user','system.research',false)")
        res = execute_question(conn, "system.research", {"case_id": case.case_meta["case_id"], "case_ref": case.case_ref}, "Q40",
                               {"event_id": case.incident_ref, "window_minutes": config["q40"]["window_minutes"],
                                "result_limit": config["q40"]["result_limit"]})
        return res.get("rows") or res.get("results") or []

    def rank(self, dataset_id, case, config):
        rows = self.raw(case, config)
        if rows and len(rows) >= config["q40"]["result_limit"]:
            raise RuntimeError("Q40 result truncated by result_limit; raise the limit")
        got = {r["entity_ref"]: r for r in rows}
        cand = case.candidates
        scores = {p: float(got[p]["association_score"]) if p in got else 0.0 for p in cand}
        fx = {p: {"signals": got[p]["contributing_signals"] if p in got else [], "native_rank": (list(got).index(p) + 1) if p in got else None,
                  "independent_sources": got[p]["independent_evidence_sources"] if p in got else 0} for p in cand}
        return assign_ranks(dataset_id, case.case_ref, scores, fx,
                            lambda r, s, f: f"Q40 association score {s:.2f}; signals: {', '.join(f['signals']) or 'none'} (heuristic, not a probability)",
                            self.name, self.config_version)
