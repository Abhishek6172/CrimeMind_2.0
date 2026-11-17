"""Deterministic investigative analytics over CURRENT BELIEF records (SUPPORTED evidence only). No language model.

Each function is a transparent rule with visible parameters. Outputs are leads and measurements for an investigator to
review; none of them establishes intent, guilt or responsibility.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from itertools import combinations
from statistics import mean, pstdev

from .correlation.engine import CaseData, haversine_m

IST = timezone(timedelta(hours=5, minutes=30))
NOTE = "Rule-based lead for review. It does not establish intent, guilt or responsibility."


def _persons(d: CaseData):
    return [i for i, e in d.ents.items() if e["entity_type"] == "PERSON"]


def _lab(d: CaseData, i):
    return {"ref": d.ref_of[i], "name": d.name_of[i]}


# ------------------------------------------------------------------ 1. impossible movement
def impossible_jumps(d: CaseData, max_speed_kmh: float = 120.0, min_distance_m: float = 300.0) -> dict:
    by_subj = defaultdict(list)
    for o in d.obs:
        if o["location_entity_id"] in d.coord:
            by_subj[o["subject_entity_id"]].append(o)
    flags, per_source = [], defaultdict(lambda: {"flagged_pairs": 0, "subjects": set()})
    for subj, obs in by_subj.items():
        obs.sort(key=lambda o: (o["observed_from"], o["observed_to"]))
        for a, b in zip(obs, obs[1:]):
            if a["location_entity_id"] == b["location_entity_id"]:
                continue
            dist = haversine_m(d.coord[a["location_entity_id"]], d.coord[b["location_entity_id"]])
            if dist < min_distance_m:
                continue
            gap = (b["observed_from"] - a["observed_to"]).total_seconds()
            simultaneous = gap <= 0
            speed = float("inf") if simultaneous else (dist / 1000.0) / (gap / 3600.0)
            if not (simultaneous or speed > max_speed_kmh):
                continue
            srcs = sorted({a["source"], b["source"]})
            for s in srcs:
                per_source[s]["flagged_pairs"] += 1
                per_source[s]["subjects"].add(d.ref_of[subj])
            flags.append({
                "kind": "SIMULTANEOUS_PRESENCE" if simultaneous else "IMPOSSIBLE_SPEED",
                "subject": _lab(d, subj), "distance_m": round(dist),
                "gap_minutes": None if simultaneous else round(gap / 60, 1),
                "required_speed_kmh": None if simultaneous else round(speed, 1),
                "from": {"obs": a["ref"], "location": d.ref_of[a["location_entity_id"]], "source": a["source"], "source_kind": a["source_kind"],
                         "start": a["observed_from"], "end": a["observed_to"], "evidence_ref": a.get("evidence_ref")},
                "to": {"obs": b["ref"], "location": d.ref_of[b["location_entity_id"]], "source": b["source"], "source_kind": b["source_kind"],
                       "start": b["observed_from"], "end": b["observed_to"], "evidence_ref": b.get("evidence_ref")},
                "summary": (f"{d.name_of[subj]} is recorded {round(dist)} m apart at overlapping times by {srcs[0]} and {srcs[-1]}" if simultaneous else
                            f"{d.name_of[subj]} would need ≈{round(speed)} km/h to get between two recorded positions {round(dist)} m apart in {round(gap / 60, 1)} min"),
                "possible_explanations": ["A device fault or timestamp error in one source", "A shared or lent device", "Imprecise location data",
                                          "Genuinely two different people or vehicles mislabelled"],
            })
    flags.sort(key=lambda f: (f["kind"] != "SIMULTANEOUS_PRESENCE", -(f["distance_m"])))
    sources = sorted(({"source": s, "flagged_pairs": v["flagged_pairs"], "subjects": sorted(v["subjects"])} for s, v in per_source.items()),
                     key=lambda x: -x["flagged_pairs"])
    return {"parameters": {"max_speed_kmh": max_speed_kmh, "min_distance_m": min_distance_m}, "flags": flags[:200], "total": len(flags),
            "sources_in_conflicts": sources[:20],
            "interpretation": "A source that keeps appearing in conflicts is a candidate for a device or timestamp check (use the evidence-change process if confirmed).",
            "notice": NOTE}


# ------------------------------------------------------------------ 2. alibi checker
def alibi(d: CaseData, person: int, start: datetime, end: datetime, target: int, radius_m: float = 150.0) -> dict:
    inside, elsewhere = [], []
    covered = []
    for o in d.obs:
        if o["subject_entity_id"] != person or o["observed_to"] < start or o["observed_from"] > end:
            continue
        lid = o["location_entity_id"]
        dist = d.dist(lid, target)
        row = {"obs": o["ref"], "location": d.ref_of[lid], "location_name": d.name_of[lid], "source": o["source"], "source_kind": o["source_kind"],
               "from": o["observed_from"], "to": o["observed_to"], "distance_to_target_m": None if dist == float("inf") else round(dist),
               "evidence_ref": o.get("evidence_ref"), "origin": o.get("origin_key")}
        covered.append((max(o["observed_from"], start), min(o["observed_to"], end)))
        (inside if dist <= radius_m else elsewhere).append(row)
    covered.sort()
    total, cur_s, cur_e = 0.0, None, None
    for s, e in covered:
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += (cur_e - cur_s).total_seconds()
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += (cur_e - cur_s).total_seconds()
    window = max((end - start).total_seconds(), 1.0)
    if inside and elsewhere:
        verdict = "CONFLICTING"
        text = "Records place this person both at the location and elsewhere during the window. Check device and timestamp reliability."
    elif inside:
        verdict = "PLACED_AT_LOCATION"
        text = "Records place this person at or near the location during the window."
    elif elsewhere:
        verdict = "RECORDED_ELSEWHERE"
        text = "Records place this person elsewhere during the window. Absence from the location is not proven by gaps in the records."
    else:
        verdict = "NO_DATA"
        text = "No current, supported location records cover this window. This is not evidence of presence or absence."
    comms = [{"ref": c["ref"], "at": c["occurred_at"], "type": c["comm_type"]} for c in d.comms
             if person in (c["sender_id"], c["receiver_id"]) and start <= c["occurred_at"] <= end][:30]
    txns = [{"ref": t["ref"], "at": t["occurred_at"], "type": t["txn_type"], "amount": float(t["amount"])} for t in d.txns
            if person in (t["from_entity_id"], t["to_entity_id"]) and start <= t["occurred_at"] <= end][:30]
    origins = {r["origin"] for r in inside + elsewhere if r["origin"]}
    return {"person": _lab(d, person), "target": _lab(d, target), "window": {"start": start, "end": end}, "radius_m": radius_m,
            "verdict": verdict, "explanation": text, "coverage_percent": round(min(100.0, 100.0 * total / window), 1),
            "independent_sources": len(origins), "at_location": inside[:50], "elsewhere": elsewhere[:50], "communications_in_window": comms,
            "transactions_in_window": txns, "excluded_unsupported_records": d.excluded["observations"], "notice": NOTE}


# ------------------------------------------------------------------ 3. network metrics
def _graph(d: CaseData, domains: set[str]):
    w = defaultdict(float)
    pers = set(_persons(d))
    def add(a, b, x):
        if a != b and a in pers and b in pers:
            w[tuple(sorted((a, b)))] += x
    if "communication" in domains:
        for c in d.comms:
            add(c["sender_id"], c["receiver_id"], 1.0)
    if "transaction" in domains:
        for t in d.txns:
            add(t["from_entity_id"], t["to_entity_id"], 2.0)
    if "relationship" in domains:
        for r in d.rels:
            if r["rel_type"] not in ("OWNS", "USES", "ACCOUNT_OF"):
                add(r["entity_a"], r["entity_b"], 1.0)
    return pers, w


def network(d: CaseData, domains: set[str] | None = None) -> dict:
    domains = domains or {"communication", "transaction", "relationship"}
    pers, w = _graph(d, domains)
    adj = defaultdict(dict)
    for (a, b), x in w.items():
        adj[a][b] = x
        adj[b][a] = x
    nodes = sorted(n for n in pers if adj[n])
    # betweenness (Brandes, unweighted, deterministic)
    bc = {n: 0.0 for n in nodes}
    for s in nodes:
        stack, pred, sigma, dist = [], {n: [] for n in nodes}, dict.fromkeys(nodes, 0), dict.fromkeys(nodes, -1)
        sigma[s], dist[s], q = 1, 0, [s]
        for v in q:
            stack.append(v)
            for u in sorted(adj[v]):
                if dist[u] < 0:
                    dist[u] = dist[v] + 1
                    q.append(u)
                if dist[u] == dist[v] + 1:
                    sigma[u] += sigma[v]
                    pred[u].append(v)
        delta = dict.fromkeys(nodes, 0.0)
        while stack:
            v = stack.pop()
            for p in pred[v]:
                delta[p] += sigma[p] / sigma[v] * (1 + delta[v])
            if v != s:
                bc[v] += delta[v]
    n = len(nodes)
    norm = 1.0 / ((n - 1) * (n - 2)) if n > 2 else 1.0
    bc = {k: v * norm for k, v in bc.items()}   # undirected pairs counted twice: this is the standard directed normalisation
    # PageRank (weighted)
    pr = {v: 1.0 / max(n, 1) for v in nodes}
    for _ in range(60):
        new = {}
        for v in nodes:
            new[v] = 0.15 / n + 0.85 * sum(pr[u] * adj[u][v] / sum(adj[u].values()) for u in adj[v])
        pr = new
    # communities: deterministic label propagation
    label = {v: v for v in nodes}
    for _ in range(20):
        changed = False
        for v in nodes:
            score = defaultdict(float)
            for u, x in adj[v].items():
                score[label[u]] += x
            best = max(sorted(score), key=lambda l: (score[l], -l))
            if best != label[v]:
                label[v], changed = best, True
        if not changed:
            break
    comm_ids = {l: i + 1 for i, l in enumerate(sorted(set(label.values())))}
    sizes = defaultdict(int)
    for v in nodes:
        sizes[comm_ids[label[v]]] += 1
    top_bc = sorted(bc.values(), reverse=True)[max(0, n // 10 - 1)] if n >= 10 else float("inf")
    victims = {r["entity_id"] for ev in d.incidents for r in d.event_people[ev["event_id"]] if r["role"] == "VICTIM"}
    rows = []
    for v in nodes:
        nbr_comms = {comm_ids[label[u]] for u in adj[v]}
        rows.append({**_lab(d, v), "degree": len(adj[v]), "weighted_degree": round(sum(adj[v].values()), 1), "betweenness": round(bc[v], 4),
                     "pagerank": round(pr[v], 4), "community": comm_ids[label[v]], "bridges_communities": len(nbr_comms) >= 2 and bc[v] >= top_bc,
                     "connected_to_victim": bool(set(adj[v]) & victims), "is_victim": v in victims})
    rows.sort(key=lambda r: (-r["betweenness"], -r["pagerank"], r["ref"]))
    return {"domains": sorted(domains), "people": rows, "communities": [{"id": i, "size": s} for i, s in sorted(sizes.items())], "people_count": n,
            "metrics_note": "Betweenness = how often a person lies on shortest paths between others (a go-between). PageRank = connectedness weighted by the importance of contacts. "
                            "Both describe the recorded network structure, not roles in any crime.", "notice": NOTE}


# ------------------------------------------------------------------ 4. anomaly flags
def anomalies(d: CaseData) -> dict:
    flags = []
    pers = _persons(d)
    # large / round transactions
    amts = [float(t["amount"]) for t in d.txns]
    if len(amts) >= 10:
        mu, sd = mean(amts), pstdev(amts)
        thr = mu + 3 * sd
        for t in d.txns:
            a = float(t["amount"])
            if a > thr:
                flags.append({"rule": "LARGE_TRANSACTION", "severity": "MEDIUM", "subjects": [d.ref_of[t["from_entity_id"]], d.ref_of[t["to_entity_id"]]],
                              "summary": f"{t['txn_type']} of {a:,.0f} {t['currency']} is more than 3 standard deviations above the case average ({mu:,.0f})",
                              "records": [t["ref"]], "evidence": [t["evidence_ref"]] if t.get("evidence_ref") else [], "parameters": {"threshold": round(thr), "mean": round(mu)}})
    # structuring: many transfers from one sender within 24h
    by_sender = defaultdict(list)
    for t in d.txns:
        by_sender[t["from_entity_id"]].append(t)
    for s, lst in by_sender.items():
        lst.sort(key=lambda t: t["occurred_at"])
        for i, t in enumerate(lst):
            win = [x for x in lst[i:] if x["occurred_at"] - t["occurred_at"] <= timedelta(hours=24)]
            if len(win) >= 3 and len({x["to_entity_id"] for x in win}) <= 2 and sum(float(x["amount"]) for x in win) >= 3000:
                flags.append({"rule": "SPLIT_TRANSFERS", "severity": "MEDIUM", "subjects": [d.ref_of[s]],
                              "summary": f"{d.name_of[s]} made {len(win)} transfers within 24 h totalling {sum(float(x['amount']) for x in win):,.0f}, to at most two recipients",
                              "records": [x["ref"] for x in win], "evidence": sorted({x["evidence_ref"] for x in win if x.get("evidence_ref")}),
                              "parameters": {"min_count": 3, "window_hours": 24}})
                break
    # silence around incident
    for inc in d.incidents:
        lo, hi = inc["occurred_at"] - timedelta(hours=6), inc["occurred_at"] + timedelta(hours=2)
        for p in pers:
            mine = [c["occurred_at"] for c in d.comms if p in (c["sender_id"], c["receiver_id"])]
            if len(mine) < 6:
                continue
            span_days = max((max(mine) - min(mine)).total_seconds() / 86400, 1.0)
            rate = len(mine) / span_days
            if rate >= 3 and not any(lo <= t <= hi for t in mine):
                flags.append({"rule": "SILENT_AROUND_INCIDENT", "severity": "LOW", "subjects": [d.ref_of[p]],
                              "summary": f"{d.name_of[p]} averages {rate:.1f} communications/day but has none from 6 h before to 2 h after incident {inc['ref']}",
                              "records": [], "evidence": [], "parameters": {"window": "-6h/+2h", "min_rate_per_day": 3}})
    # communication burst: a day far above the person's own baseline
    perday = defaultdict(lambda: defaultdict(int))
    for c in d.comms:
        for p in (c["sender_id"], c["receiver_id"]):
            perday[p][c["occurred_at"].astimezone(IST).date()] += 1
    for p, days in perday.items():
        if len(days) < 4:
            continue
        for day, n in days.items():
            others = [v for k, v in days.items() if k != day]
            mu, sd = mean(others), pstdev(others)
            if n >= 8 and n > mu + 3 * max(sd, 1.0):
                flags.append({"rule": "COMMUNICATION_BURST", "severity": "LOW", "subjects": [d.ref_of[p]],
                              "summary": f"{d.name_of[p]} had {n} communications on {day}, far above their usual {mu:.1f}/day",
                              "records": [], "evidence": [], "parameters": {"day": str(day), "baseline": round(mu, 1)}})
    # night-time presence (00:00-05:00 IST) away from residence
    for o in d.obs:
        if d.etype(o["subject_entity_id"]) != "PERSON" or d.loc_kind.get(o["location_entity_id"]) in ("RESIDENCE", "WORKPLACE"):
            continue
        h = o["observed_from"].astimezone(IST).hour
        if 0 <= h < 5:
            flags.append({"rule": "NIGHT_PRESENCE", "severity": "LOW", "subjects": [d.ref_of[o["subject_entity_id"]]],
                          "summary": f"{d.name_of[o['subject_entity_id']]} recorded at {d.name_of[o['location_entity_id']]} at {o['observed_from'].astimezone(IST):%H:%M} IST",
                          "records": [o["ref"]], "evidence": [o["evidence_ref"]] if o.get("evidence_ref") else [], "parameters": {"hours_ist": "00:00-05:00"}})
    order = {"MEDIUM": 0, "LOW": 1}
    flags.sort(key=lambda f: (order[f["severity"]], f["rule"], f["subjects"]))
    counts = defaultdict(int)
    for f in flags:
        counts[f["rule"]] += 1
    return {"flags": flags[:300], "total": len(flags), "by_rule": dict(counts),
            "rules": {"LARGE_TRANSACTION": "amount > mean + 3σ", "SPLIT_TRANSFERS": "≥3 transfers in 24 h to ≤2 recipients, total ≥ 3000",
                      "SILENT_AROUND_INCIDENT": "usual rate ≥ 3/day but silent −6h/+2h", "COMMUNICATION_BURST": "a day > baseline + 3σ and ≥ 8",
                      "NIGHT_PRESENCE": "recorded away from home/work between 00:00 and 05:00 IST"},
            "notice": "Statistical flags describe unusual activity, which is often innocent. " + NOTE}


# ------------------------------------------------------------------ 5. money trail
def money_trail(d: CaseData, start: int, direction: str = "forward", max_hops: int = 4, min_amount: float = 0.0, max_paths: int = 60) -> dict:
    out_edges = defaultdict(list)
    for t in d.txns:
        if float(t["amount"]) < min_amount:
            continue
        a, b = (t["from_entity_id"], t["to_entity_id"]) if direction == "forward" else (t["to_entity_id"], t["from_entity_id"])
        out_edges[a].append((b, t))
    paths = []

    def walk(node, path, seen, last_time):
        if len(paths) >= max_paths * 3:
            return
        for nxt, t in sorted(out_edges.get(node, []), key=lambda x: x[1]["occurred_at"]):
            if nxt in seen:
                continue
            ok = last_time is None or (t["occurred_at"] >= last_time if direction == "forward" else t["occurred_at"] <= last_time)
            if not ok:
                continue
            p = path + [(node, nxt, t)]
            paths.append(p)
            if len(p) < max_hops:
                walk(nxt, p, seen | {nxt}, t["occurred_at"])

    walk(start, [], {start}, None)
    paths.sort(key=lambda p: (-len(p), -sum(float(h[2]["amount"]) for h in p)))
    res = []
    for p in paths[:max_paths]:
        res.append({"hops": len(p), "end": _lab(d, p[-1][1]), "total_moved": round(sum(float(h[2]["amount"]) for h in p), 2),
                    "steps": [{"from": d.ref_of[a], "to": d.ref_of[b], "txn": t["ref"], "amount": float(t["amount"]), "currency": t["currency"],
                               "at": t["occurred_at"], "evidence_ref": t.get("evidence_ref")} for a, b, t in p]})
    # pass-through nodes: receive and forward ≥80% within 48h
    passthrough = []
    incoming = defaultdict(list)
    for t in d.txns:
        incoming[t["to_entity_id"]].append(t)
    for node, ins in incoming.items():
        outs = [t for t in d.txns if t["from_entity_id"] == node]
        for i in ins:
            fwd = sum(float(o["amount"]) for o in outs if timedelta(0) <= o["occurred_at"] - i["occurred_at"] <= timedelta(hours=48))
            if float(i["amount"]) >= 1000 and fwd >= 0.8 * float(i["amount"]):
                passthrough.append({"entity": _lab(d, node), "received": {"txn": i["ref"], "amount": float(i["amount"])}, "forwarded_within_48h": round(fwd, 2)})
    return {"start": _lab(d, start), "direction": direction, "parameters": {"max_hops": max_hops, "min_amount": min_amount}, "paths": res,
            "total_paths_found": len(paths), "pass_through": passthrough[:30],
            "notice": "Paths follow recorded transactions in time order. A path shows where money moved, not why. " + NOTE}


# ------------------------------------------------------------------ 6. meeting detection
def meetings(d: CaseData, window_minutes: int = 30, radius_m: float = 100.0, comm_minutes: int = 60) -> dict:
    ignore = ("RESIDENCE", "WORKPLACE")
    obs = [o for o in d.obs if d.etype(o["subject_entity_id"]) == "PERSON" and d.loc_kind.get(o["location_entity_id"]) not in ignore]
    by_loc = defaultdict(list)
    for o in obs:
        by_loc[o["location_entity_id"]].append(o)
    pairs = defaultdict(list)
    locs = list(by_loc)
    near = {a: [b for b in locs if d.dist(a, b) <= radius_m] for a in locs}
    seen = set()
    w = timedelta(minutes=window_minutes)
    for a in locs:
        cand = [o for b in near[a] for o in by_loc[b]]
        for x, y in combinations(sorted(cand, key=lambda o: o["observed_from"]), 2):
            if x["subject_entity_id"] == y["subject_entity_id"] or (x["ref"], y["ref"]) in seen:
                continue
            if x["observed_from"] <= y["observed_to"] + w and y["observed_from"] <= x["observed_to"] + w:
                seen.add((x["ref"], y["ref"]))
                pairs[tuple(sorted((x["subject_entity_id"], y["subject_entity_id"])))].append((x, y))
    comm_by_pair = defaultdict(list)
    for c in d.comms:
        comm_by_pair[tuple(sorted((c["sender_id"], c["receiver_id"])))].append(c)
    out = []
    for pair, ev in pairs.items():
        days = {max(x["observed_from"], y["observed_from"]).astimezone(IST).date() for x, y in ev}
        contacts = []
        for x, y in ev:
            t0 = max(x["observed_from"], y["observed_from"])
            for c in comm_by_pair.get(pair, []):
                if abs((c["occurred_at"] - t0).total_seconds()) <= comm_minutes * 60:
                    contacts.append(c["ref"])
        contacts = sorted(set(contacts))
        if len(days) >= 2 or contacts:
            x, y = ev[0]
            out.append({"people": [_lab(d, pair[0]), _lab(d, pair[1])], "occasions": len(days), "co_presences": len(ev),
                        "first_place": d.name_of[x["location_entity_id"]], "linked_communications": contacts[:10],
                        "pattern": "REPEATED_AND_CONTACT" if len(days) >= 2 and contacts else "REPEATED" if len(days) >= 2 else "CONTACT_AROUND_MEETING",
                        "observations": sorted({o["ref"] for pr in ev[:6] for o in pr}), "evidence": sorted({o["evidence_ref"] for pr in ev[:6] for o in pr if o.get("evidence_ref")})})
    order = {"REPEATED_AND_CONTACT": 0, "REPEATED": 1, "CONTACT_AROUND_MEETING": 2}
    out.sort(key=lambda r: (order[r["pattern"]], -r["occasions"], r["people"][0]["ref"]))
    return {"parameters": {"window_minutes": window_minutes, "radius_m": radius_m, "contact_minutes": comm_minutes}, "meetings": out[:150], "total": len(out),
            "notice": "Being at the same place at similar times is not proof of meeting. Homes and workplaces are excluded. " + NOTE}


# ------------------------------------------------------------------ 7. map data
def map_data(d: CaseData, person: int | None = None) -> dict:
    locs = [{"ref": d.ref_of[i], "name": d.name_of[i], "lat": lat, "lon": lon, "kind": d.loc_kind.get(i, "")} for i, (lat, lon) in d.coord.items()]
    incidents = [{"ref": e["ref"], "at": e["occurred_at"], "description": e["description"], "location": d.ref_of.get(e["location_entity_id"])} for e in d.incidents]
    trail = []
    if person is not None:
        for o in sorted((o for o in d.obs if o["subject_entity_id"] == person and o["location_entity_id"] in d.coord), key=lambda o: o["observed_from"]):
            lat, lon = d.coord[o["location_entity_id"]]
            trail.append({"obs": o["ref"], "location": d.ref_of[o["location_entity_id"]], "lat": lat, "lon": lon, "from": o["observed_from"], "to": o["observed_to"],
                          "source": o["source"], "source_kind": o["source_kind"], "evidence_ref": o.get("evidence_ref")})
    return {"locations": locs, "incidents": incidents, "person": _lab(d, person) if person else None, "trail": trail}
