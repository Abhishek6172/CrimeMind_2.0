from .base import RankingAlgorithm, assign_ranks


def build_graph(case, as_of=None, exclude_types=()):
    """Undirected relationship graph over non-location entities. Edge = SUPPORTED relationship valid at as_of.
    Returns (nodes, weights{(a,b):w}). Parallel relationships between the same pair keep the maximum strength."""
    as_of = as_of or case.as_of
    nodes = sorted(e for e, t in case.ent_type.items() if t != "LOCATION")
    ns = set(nodes)
    w = {}
    for r in case.active(case.rels):
        if r["type"] in exclude_types or r["a"] not in ns or r["b"] not in ns or r["a"] == r["b"]:
            continue
        if r["valid_from"] and r["valid_from"] > as_of or r["valid_to"] and r["valid_to"] < as_of:
            continue
        k = tuple(sorted((r["a"], r["b"])))
        w[k] = max(w.get(k, 0.0), r["strength"] or 0.0)
    return nodes, w


def degree_centrality(nodes, w):
    nb = {n: set() for n in nodes}
    for (a, b) in w:
        nb[a].add(b); nb[b].add(a)
    d = max(len(nodes) - 1, 1)
    return {n: len(nb[n]) / d for n in nodes}


def pagerank(nodes, w, damping=0.85, tol=1e-10, max_iter=200, teleport=None):
    """Weighted PageRank by power iteration on an undirected graph. Isolated nodes are dangling: their mass is
    redistributed according to the teleport vector (uniform by default), so disconnected components are handled by
    teleportation. Optional personalised teleport vector (dict node->mass summing to 1)."""
    n = len(nodes)
    if n == 0:
        return {}
    tp = teleport or {x: 1.0 / n for x in nodes}
    adj = {x: {} for x in nodes}
    for (a, b), wt in w.items():
        wt = wt if wt > 0 else 1e-9
        adj[a][b] = wt; adj[b][a] = wt
    out = {x: sum(adj[x].values()) for x in nodes}
    pr = {x: 1.0 / n for x in nodes}
    for _ in range(max_iter):
        dangling = sum(pr[x] for x in nodes if out[x] == 0)
        new = {x: (1 - damping) * tp[x] + damping * dangling * tp[x] for x in nodes}
        for x in nodes:
            if out[x]:
                share = damping * pr[x] / out[x]
                for y, wt in adj[x].items():
                    new[y] += share * wt
        delta = sum(abs(new[x] - pr[x]) for x in nodes)
        pr = new
        if delta < tol:
            break
    return pr


class DegreeCentrality(RankingAlgorithm):
    """Incident-agnostic structural baseline: degree centrality in the relationship graph valid at the evaluation time."""
    name = "degree_centrality"

    def rank(self, dataset_id, case, config):
        nodes, w = build_graph(case)
        dc = degree_centrality(nodes, w)
        scores = {p: dc.get(p, 0.0) for p in case.candidates}
        return assign_ranks(dataset_id, case.case_ref, scores, {p: {"degree_centrality": scores[p]} for p in scores},
                            lambda r, s, f: f"degree centrality {s:.4f} (isolated nodes score 0)", self.name, self.config_version)


class PageRankBaseline(RankingAlgorithm):
    """Incident-agnostic PageRank (uniform teleport) on the same graph."""
    name = "pagerank"

    def rank(self, dataset_id, case, config):
        g = config["graph"]
        nodes, w = build_graph(case)
        pr = pagerank(nodes, w, g["pagerank_damping"], g["pagerank_tol"], g["pagerank_max_iter"])
        scores = {p: pr.get(p, 0.0) for p in case.candidates}
        return assign_ranks(dataset_id, case.case_ref, scores, {p: {"pagerank": scores[p]} for p in scores},
                            lambda r, s, f: f"PageRank {s:.6f}", self.name, self.config_version)


class PersonalizedPageRank(RankingAlgorithm):
    """Extra (not required) victim-anchored PageRank: teleport mass concentrated on the victim(s); ranks closeness in the
    relationship graph to the victim."""
    name = "pagerank_victim_personalised"

    def rank(self, dataset_id, case, config):
        g = config["graph"]
        nodes, w = build_graph(case)
        vs = [v for v in case.victims if v in set(nodes)]
        tp = {x: (1.0 / len(vs) if x in vs else 0.0) for x in nodes} if vs else None
        pr = pagerank(nodes, w, g["pagerank_damping"], g["pagerank_tol"], g["pagerank_max_iter"], tp)
        scores = {p: pr.get(p, 0.0) for p in case.candidates}
        return assign_ranks(dataset_id, case.case_ref, scores, {p: {"ppr": scores[p]} for p in scores},
                            lambda r, s, f: f"victim-personalised PageRank {s:.6f}", self.name, self.config_version)
