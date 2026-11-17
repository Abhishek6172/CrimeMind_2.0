"""Shared reliability machinery for Q40-R and RAEER (feature-flag aware so ablations change exactly one component)."""
import math
from datetime import timedelta

from research.common.casedata import CaseView, haversine_m


class Rel:
    """Per-record trust: rho(record) = reliability(evidence) * status_factor(evidence)."""

    def __init__(self, case: CaseView, cfg: dict, use_reliability=True, use_lifecycle=True, use_provenance=True):
        self.case, self.cfg = case, cfg
        self.use_reliability, self.use_lifecycle, self.use_prov = use_reliability, use_lifecycle, use_provenance

    def rho(self, rec) -> float:
        ev = self.case.evidence.get(rec.get("evidence")) if rec.get("evidence") else None
        base = self.cfg["missing_reliability"] if (ev is None or ev["reliability"] is None) else ev["reliability"]
        if not self.use_reliability:
            base = 1.0
        status = rec["status"] if ev is None else ev["status"]
        if self.use_lifecycle:
            phi = self.cfg["status_factor"].get(status, 0.0)
        else:
            phi = 1.0                      # lifecycle-blind: treat every record as current
        return base * phi

    def origin(self, rec) -> str:
        """Independence unit. With provenance: the evidence's origin root (duplicates of one source collapse).
        Without: every record is its own origin (duplicates are double counted)."""
        return rec.get("origin") if self.use_prov and rec.get("origin") else f"REC:{rec['ref']}"


def best_per_origin(items):
    """items: [(origin, value)] -> {origin: max value}: duplicated records of one origin are not independent corroboration."""
    d = {}
    for o, v in items:
        d[o] = max(d.get(o, 0.0), v)
    return d


def noisy_or(values):
    p = 1.0
    for v in values:
        p *= (1.0 - min(1.0, max(0.0, v)))
    return 1.0 - p


def window(case, minutes):
    w = timedelta(minutes=minutes)
    return case.incident_time - w, case.incident_time + w
