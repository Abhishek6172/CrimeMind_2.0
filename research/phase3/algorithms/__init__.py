from .base import RankedLead, RankingAlgorithm, assign_ranks
from .comm_frequency import CommunicationFrequency
from .graph_centrality import DegreeCentrality, PageRankBaseline, PersonalizedPageRank
from .q40_adapter import Q40Frozen
from .random_baseline import RandomBaseline
from .spatial_proximity import SpatialProximity

PHASE3_METHODS = ["random", "communication_frequency", "spatial_proximity", "degree_centrality", "pagerank", "q40"]
EXTRA_METHODS = ["pagerank_victim_personalised"]


def make(name: str, **kw):
    return {"random": RandomBaseline, "communication_frequency": CommunicationFrequency, "spatial_proximity": SpatialProximity,
            "degree_centrality": DegreeCentrality, "pagerank": PageRankBaseline, "pagerank_victim_personalised": PersonalizedPageRank,
            "q40": Q40Frozen}[name](**kw)
