import hashlib
import random

from .base import RankingAlgorithm, assign_ranks


class RandomBaseline(RankingAlgorithm):
    """Uniformly random order of the eligible candidates; deterministic given (dataset, case, repetition)."""
    name = "random"

    def __init__(self, repetition: int = 0):
        self.repetition = repetition

    def rank(self, dataset_id, case, config):
        seed = int(hashlib.sha256(f"{dataset_id}|{case.case_ref}|{self.repetition}".encode()).hexdigest()[:16], 16)
        rng = random.Random(seed)
        scores = {c: rng.random() for c in case.candidates}
        return assign_ranks(dataset_id, case.case_ref, scores, {c: {"rng_seed": seed} for c in scores},
                            lambda r, s, f: f"random draw {s:.4f} (rng seed {f['rng_seed']})", self.name, self.config_version)
