"""RAEER - Reliability-Aware Evidence Evolution Ranking (operational definition: research/phase4/docs/RAEER_DEFINITION.md).

For candidate p, with rho(record) = reliability x lifecycle-status factor, origin(record) = provenance root,
tau-weighting t(record) = exp(-gap / tau) (gap between the observation interval and the incident time):

  f_spatial(p)   = 1 - prod_{o in origins} (1 - max_{records of o at the scene within +/-W} rho * t)        [scene = within R metres]
  f_temporal(p)  = 1 - prod_{o} (1 - max_{any activity of o within +/-W} rho * t)
  f_comm(p)      = 1 - prod_{o} (1 - max rho)  over communications with the victim or a scene person
  f_fin(p)       = same for transactions
  f_rel(p)       = 1 - prod_{o} (1 - max rho * strength) over non-OWNS/USES relationships with the victim or a scene person
  f_corr(p)      = min(1, (f_spatial + f_comm + f_fin + f_rel) / 3)        (strength of independent supporting domains)
  C(p)           = max over conflicting location-record pairs (A at the scene, B > D metres away, overlapping, different origin) of rho_B / (rho_A + rho_B)
  score(p)       = ( w_s f_spatial (1 - gamma C) + w_t f_temporal + w_c f_comm + w_f f_fin + w_r f_rel + w_k f_corr )      in [0, 1]

Heuristic ranking score, NOT a probability. A contradiction lowers the spatial feature by at most the factor (1 - gamma) and never
removes it (contradiction is not proof of innocence or guilt)."""
import math

from research.common.casedata import CaseView, haversine_m
from research.phase3.algorithms.base import RankingAlgorithm, assign_ranks
from .common import Rel, best_per_origin, noisy_or, window


class RAEER(RankingAlgorithm):
    name = "raeer"
    config_version = "p4-1.0"

    def __init__(self, features=None, name=None, weights=None, override=None):
        self.features = features or {}
        self.override = override or {}
        self.weights = weights
        if name:
            self.name = name

    def rank(self, dataset_id, case: CaseView, config):
        cfg = {**config["raeer"], **{k: ({**config["raeer"][k], **v} if isinstance(v, dict) and isinstance(config["raeer"].get(k), dict) else v) for k, v in self.override.items()}}
        fl = {**cfg["features"], **self.features}
        W = {**cfg["weights"], **(self.weights or {})}
        rel = Rel(case, config, use_reliability=fl["reliability"], use_lifecycle=fl["lifecycle"], use_provenance=fl["provenance"])
        if not fl["independence"]:
            rel.use_prov = False          # every record counts as its own source
        lo, hi = window(case, config["window_minutes"])
        T = case.incident_time
        tau = cfg["temporal_tau_minutes"] * 60.0
        victims, cand = set(case.victims), case.candidates
        target = case.locations[case.incident_location]
        R = cfg["scene_radius_m"]

        def tw(t_from, t_to):
            if not fl["temporal"]:
                return 1.0
            gap = 0.0 if t_from <= T <= t_to else min(abs((t_from - T).total_seconds()), abs((t_to - T).total_seconds()))
            return math.exp(-gap / tau)

        def collect():
            return {}

        def add(d, p, origin, v):
            m = d.setdefault(p, {})
            m[origin] = max(m.get(origin, 0.0), v)

        spatial, temporal, scene_obs = {}, {}, {}
        for o in case.obs:
            r = rel.rho(o)
            if r <= 0:
                continue
            org = rel.origin(o)
            in_win = o["t_to"] >= lo and o["t_from"] <= hi
            loc = case.locations.get(o["location"])
            at_scene = loc is not None and haversine_m(target, loc) <= R
            if in_win and at_scene:
                add(spatial, o["subject"], org, r * tw(o["t_from"], o["t_to"]))
                scene_obs.setdefault(o["subject"], []).append((o, r))
            if in_win:
                add(temporal, o["subject"], org, r * tw(o["t_from"], o["t_to"]))
        for c in case.comms:
            r = rel.rho(c)
            if r > 0 and lo <= c["t"] <= hi:
                for p in (c["a"], c["b"]):
                    add(temporal, p, rel.origin(c), r * tw(c["t"], c["t"]))
        for t in case.txns:
            r = rel.rho(t)
            if r > 0 and lo <= t["t"] <= hi:
                for p in (t["a"], t["b"]):
                    add(temporal, p, rel.origin(t), r * tw(t["t"], t["t"]))
        scene = set(spatial)
        comm, fin, relf = {}, {}, {}
        for c in case.comms:
            r = rel.rho(c)
            if r <= 0:
                continue
            for me, other in ((c["a"], c["b"]), (c["b"], c["a"])):
                if other in victims or other in scene:
                    add(comm, me, rel.origin(c), r)
        for t in case.txns:
            r = rel.rho(t)
            if r <= 0:
                continue
            for me, other in ((t["a"], t["b"]), (t["b"], t["a"])):
                if other in victims or other in scene:
                    add(fin, me, rel.origin(t), r)
        if fl["relational"]:
            for e in case.rels:
                r = rel.rho(e)
                if e["type"] in ("OWNS", "USES") or r <= 0:
                    continue
                for me, other in ((e["a"], e["b"]), (e["b"], e["a"])):
                    if other in victims or other in scene:
                        add(relf, me, rel.origin(e), r * (e["strength"] or 0.0))
        # contradictions: scene presence vs a conflicting location record from a different origin (CONTRADICTION_001 semantics)
        C = {}
        if fl["contradiction"]:
            by_subj = {}
            for o in case.obs:
                if rel.rho(o) > 0:
                    by_subj.setdefault(o["subject"], []).append(o)
            D = cfg["contradiction"]["distance_m"]
            for p, pairs in scene_obs.items():
                for a, ra in pairs:
                    la = case.locations.get(a["location"])
                    for b in by_subj.get(p, []):
                        lb = case.locations.get(b["location"])
                        if b is a or lb is None or rel.origin(b) == rel.origin(a):
                            continue
                        if b["t_from"] <= a["t_to"] and a["t_from"] <= b["t_to"] and haversine_m(la, lb) > D:
                            rb = rel.rho(b)
                            C[p] = max(C.get(p, 0.0), rb / (ra + rb) if (ra + rb) > 0 else 0.0)
        gamma = cfg["contradiction"]["gamma"]
        scores, fx = {}, {}
        for p in cand:
            f = {"spatial": noisy_or(spatial.get(p, {}).values()), "temporal": noisy_or(temporal.get(p, {}).values()),
                 "communication": noisy_or(comm.get(p, {}).values()), "financial": noisy_or(fin.get(p, {}).values()),
                 "relational": noisy_or(relf.get(p, {}).values())}
            if not fl["temporal"]:
                f["temporal"] = 0.0                  # temporal reasoning removed entirely (decay AND the activity feature)
            f["spatial_after_contradiction"] = f["spatial"] * (1 - gamma * C.get(p, 0.0))
            # corroboration: independent supporting DOMAINS (spatial, communication, financial, relational) weighted by their strength
            f["corroboration"] = min(1.0, sum(f[d] for d in ("spatial", "communication", "financial", "relational")) / cfg["corroboration_domains_cap"]) if fl["corroboration"] else 0.0
            score = (W["spatial"] * f["spatial_after_contradiction"] + W["temporal"] * f["temporal"] + W["communication"] * f["communication"]
                     + W["financial"] * f["financial"] + W["relational"] * f["relational"] + W["corroboration"] * f["corroboration"])
            scores[p] = round(score, 9)
            fx[p] = {**{k: round(v, 4) for k, v in f.items()}, "contradiction_strength": round(C.get(p, 0.0), 4)}
        return assign_ranks(dataset_id, case.case_ref, scores, fx,
                            lambda r, s, f: f"RAEER {s:.3f}: spatial {f['spatial_after_contradiction']:.2f} (raw {f['spatial']:.2f}, contradiction {f['contradiction_strength']:.2f}), "
                                            f"communication {f['communication']:.2f}, financial {f['financial']:.2f}, relational {f['relational']:.2f}, temporal {f['temporal']:.2f}, corroboration {f['corroboration']:.2f} (heuristic, not a probability)",
                            self.name, self.config_version)
