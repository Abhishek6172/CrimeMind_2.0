"""Common ranking interface. Algorithms see a CaseView (no ground truth) and return RankedLead rows."""
import hashlib
from dataclasses import dataclass, field


@dataclass
class RankedLead:
    lead_id: str
    rank: int
    raw_score: float
    normalised_score: float | None
    factors: dict
    explanation: str
    algorithm: str
    config_version: str


def tie_key(dataset_id: str, case_ref: str, ref: str) -> str:
    return hashlib.sha256(f"{dataset_id}|{case_ref}|{ref}".encode()).hexdigest()


def normalise(scores: dict) -> dict:
    """min-max to [0,1]; constant vectors map to 0.0."""
    if not scores:
        return {}
    lo, hi = min(scores.values()), max(scores.values())
    return {k: (0.0 if hi == lo else (v - lo) / (hi - lo)) for k, v in scores.items()}


def assign_ranks(dataset_id, case_ref, scores: dict, factors: dict, explain, algorithm: str, config_version: str) -> list[RankedLead]:
    order = sorted(scores, key=lambda r: (-scores[r], tie_key(dataset_id, case_ref, r)))
    nrm = normalise(scores)
    return [RankedLead(r, i + 1, float(scores[r]), nrm[r], factors.get(r, {}), explain(r, scores[r], factors.get(r, {})), algorithm, config_version)
            for i, r in enumerate(order)]


class RankingAlgorithm:
    name = "base"
    config_version = "p3-1.0"

    def rank(self, dataset_id: str, case, config: dict) -> list[RankedLead]:   # pragma: no cover - interface
        raise NotImplementedError
