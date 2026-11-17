"""Q40-R: Q40 with evidence reliability. Same six signals, same weights, same window, same population as Q40; each
binary signal 1[present] is replaced by sigma_s = max over its supporting records of rho(record), where
rho = reliability(evidence) * status_factor(evidence). With reliability off and all records SUPPORTED, Q40-R == Q40 exactly
(unit-tested against the frozen SQL).

score(p) = sum_s w_s sigma_s(p) + w_e * min(1, sum_{origins o} max rho / 3)      in [0, 1]. A heuristic, NOT a probability."""
from datetime import timedelta

from research.common.casedata import CaseView
from research.phase3.algorithms.base import RankingAlgorithm, assign_ranks
from .common import Rel, best_per_origin, window


class Q40R(RankingAlgorithm):
    name = "q40_r"
    config_version = "p4-1.0"

    def __init__(self, features=None, name=None, status_factor=None):
        self.features = features or {}
        self.status_factor = status_factor
        if name:
            self.name = name

    def rank(self, dataset_id, case: CaseView, config):
        cfg = config["q40r"] if "q40r" in config else config
        top = {**config, "status_factor": self.status_factor} if self.status_factor else config
        flags = {**cfg["features"], **self.features}
        rel = Rel(case, top, use_reliability=flags["reliability"])
        lo, hi = window(case, top["window_minutes"])
        w = cfg["weights"]
        victims = set(case.victims)
        cand = case.candidates

        def ok(r):
            return rel.rho(r) > 0

        def best(d, p, v):
            d[p] = max(d.get(p, 0.0), v)

        spatial, temporal = {}, {}
        for o in case.obs:
            if not ok(o):
                continue
            r = rel.rho(o)
            if o["location"] == case.incident_location and o["t_to"] >= lo and o["t_from"] <= hi:
                best(spatial, o["subject"], r)
            if lo <= o["t_from"] <= hi:
                best(temporal, o["subject"], r)
        for c in case.comms:
            if ok(c) and lo <= c["t"] <= hi:
                best(temporal, c["a"], rel.rho(c)); best(temporal, c["b"], rel.rho(c))
        for t in case.txns:
            if ok(t) and lo <= t["t"] <= hi:
                best(temporal, t["a"], rel.rho(t)); best(temporal, t["b"], rel.rho(t))
        scene = set(spatial)
        comm, fin, relsig = {}, {}, {}
        for c in case.comms:
            if not ok(c):
                continue
            for me, other in ((c["a"], c["b"]), (c["b"], c["a"])):
                if other in victims or other in scene:
                    best(comm, me, rel.rho(c))
        for t in case.txns:
            if not ok(t):
                continue
            for me, other in ((t["a"], t["b"]), (t["b"], t["a"])):
                if other in victims or other in scene:
                    best(fin, me, rel.rho(t))
        for r in case.rels:
            if r["type"] in ("OWNS", "USES") or not ok(r):
                continue
            for me, other in ((r["a"], r["b"]), (r["b"], r["a"])):
                if other in victims:
                    best(relsig, me, rel.rho(r))
        ev_items = {}
        for ref, e in case.evidence.items():
            rr = {"evidence": ref, "status": e["status"], "ref": ref, "origin": e["origin"]}
            if rel.rho(rr) <= 0:
                continue
            for p in e["entities"]:
                ev_items.setdefault(p, []).append((rel.origin(rr), rel.rho(rr)))
        scores, fx = {}, {}
        for p in cand:
            origins = best_per_origin(ev_items.get(p, []))
            ev = min(1.0, sum(origins.values()) / cfg["evidence_divisor"])
            sig = {"spatial": spatial.get(p, 0.0), "temporal": temporal.get(p, 0.0), "communication": comm.get(p, 0.0),
                   "financial": fin.get(p, 0.0), "relational": relsig.get(p, 0.0), "evidence": ev}
            scores[p] = round(sum(w[k] * v for k, v in sig.items()), 6)
            fx[p] = {**{k: round(v, 4) for k, v in sig.items()}, "independent_origins": len(origins)}
        return assign_ranks(dataset_id, case.case_ref, scores, fx,
                            lambda r, s, f: f"Q40-R score {s:.3f} = reliability-weighted signals " + ", ".join(f"{k} {f[k]:.2f}" for k in ("spatial", "temporal", "communication", "financial", "relational", "evidence")) + " (heuristic, not a probability)",
                            self.name, self.config_version)
