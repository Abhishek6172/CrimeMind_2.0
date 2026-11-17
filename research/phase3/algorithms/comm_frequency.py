import math
from datetime import timedelta

from research.common.casedata import CaseView
from .base import RankingAlgorithm, assign_ranks, normalise


class CommunicationFrequency(RankingAlgorithm):
    """Communication-activity baseline. Uses only SUPPORTED communications with occurred_at <= case.as_of (no future records).

    Features per candidate p (all min-max normalised across candidates, then combined with equal weights from the config):
      count            number of communications p sent or received
      unique_partners  number of distinct counterparties
      pre_week         communications in the N days before the incident (relevant frequency)
      recency          mean over p's communications of exp(-ln2 * |t_incident - t| / half_life)  (closeness in time to the incident)
    No victim- or location-specific logic and no labels are used: this is a pure 'who talks most / most recently' baseline.
    """
    name = "communication_frequency"

    def rank(self, dataset_id, case: CaseView, config):
        cfg = config["communication"]
        cand = set(case.candidates)
        comms = [c for c in case.active(case.comms) if c["t"] <= case.as_of]
        T = case.incident_time
        pre = timedelta(days=cfg["pre_incident_days"])
        hl = cfg["recency_half_life_hours"] * 3600
        f = {p: {"count": 0, "partners": set(), "pre_week": 0, "rec": []} for p in cand}
        for c in comms:
            for me, other in ((c["a"], c["b"]), (c["b"], c["a"])):
                if me in f:
                    f[me]["count"] += 1
                    f[me]["partners"].add(other)
                    if T - pre <= c["t"] <= T:
                        f[me]["pre_week"] += 1
                    f[me]["rec"].append(math.exp(-math.log(2) * abs((T - c["t"]).total_seconds()) / hl))
        raw = {p: {"count": v["count"], "unique_partners": len(v["partners"]), "pre_week": v["pre_week"],
                   "recency": (sum(v["rec"]) / len(v["rec"])) if v["rec"] else 0.0} for p, v in f.items()}
        norm = {k: normalise({p: raw[p][k] for p in cand}) for k in ("count", "unique_partners", "pre_week", "recency")}
        w = cfg["weights"]
        scores = {p: w["count"] * norm["count"][p] + w["unique_partners"] * norm["unique_partners"][p]
                  + w["pre_incident_week_frequency"] * norm["pre_week"][p] + w["recency"] * norm["recency"][p] for p in cand}
        return assign_ranks(dataset_id, case.case_ref, scores, raw,
                            lambda r, s, fx: f"{fx['count']} communications, {fx['unique_partners']} partners, {fx['pre_week']} in the week before the incident", self.name, self.config_version)
