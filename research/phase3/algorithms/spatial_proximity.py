from datetime import timedelta

from research.common.casedata import CaseView, haversine_m
from .base import RankingAlgorithm, assign_ranks


class SpatialProximity(RankingAlgorithm):
    """Spatial baseline: how close was the candidate to the incident location during +/- window of the incident?

    Distance: great-circle (haversine, R = 6371 km) between the observation's LOCATION entity and the incident location,
    from the entities' lat/lon attributes. Relevant observations: SUPPORTED, interval overlapping [T - w, T + w].
    score = 1 / (1 + d_min / scale) with d_min the smallest such distance. Missing data: a candidate with no relevant
    observation scores 0 (absence of observation is not evidence of absence; coverage is reported in the explanation).
    Coverage = fraction of the window covered by the candidate's relevant observations (diagnostic only).
    """
    name = "spatial_proximity"

    def rank(self, dataset_id, case: CaseView, config):
        scale = config["spatial"]["proximity_scale_m"]
        w = timedelta(minutes=config["window_minutes"])
        T = case.incident_time
        target = case.locations[case.incident_location]
        best, cover = {}, {}
        for o in case.active(case.obs):
            if o["t_to"] < T - w or o["t_from"] > T + w or o["t_from"] > case.as_of:
                continue
            loc = case.locations.get(o["location"])
            if loc is None:
                continue
            d = haversine_m(target, loc)
            s = o["subject"]
            best[s] = min(best.get(s, 1e18), d)
            lo, hi = max(o["t_from"], T - w), min(o["t_to"], T + w)
            cover[s] = cover.get(s, 0.0) + max(0.0, (hi - lo).total_seconds())
        scores, fx = {}, {}
        for p in case.candidates:
            d = best.get(p)
            scores[p] = 0.0 if d is None else 1.0 / (1.0 + d / scale)
            fx[p] = {"d_min_m": None if d is None else round(d, 1), "coverage": round(min(1.0, cover.get(p, 0.0) / (2 * w.total_seconds())), 3)}
        return assign_ranks(dataset_id, case.case_ref, scores, fx,
                            lambda r, s, f: "no location observation in the window" if f["d_min_m"] is None else f"closest observed {f['d_min_m']} m from the incident location (coverage {f['coverage']})",
                            self.name, self.config_version)
