"""Deterministic parameter-set generation per (dataset case, module variant). Uses only the plain-Python Data model."""
import random
from datetime import timedelta

from research.phase7.oracles.oracles import activity

VARIANTS = [("M1", "contacts"), ("M1", "frequency"), ("M1", "pairs"), ("M2", "default"), ("M3", "present"), ("M3", "copresence"), ("M4", "shared"), ("M4", "frequency"),
            ("M5", "history"), ("M5", "frequency"), ("M6", "default"), ("M7", "default"), ("M8", "before"), ("M8", "after"), ("M8", "around"), ("M9", "default"),
            ("M10", "default"), ("M11", "connected"), ("M11", "shortest"), ("M12", "default"), ("M13", "default"), ("M14", "near_location"), ("M14", "associated_entities"),
            ("M14", "repeated"), ("M15", "entity"), ("M15", "between"), ("M15", "top_amounts"), ("M15", "patterns"), ("M15", "repeated_or_unusual"), ("M16", "entity"),
            ("M16", "event"), ("M17", "multi_entity"), ("M17", "multi_type"), ("M17", "corroborating"), ("M18", "reliability")]
LIMIT = 1_000_000


def _pick(rng, xs, k):
    xs = sorted(xs)
    return rng.sample(xs, min(k, len(xs))) if xs else []


def targets(d):
    """Data-driven targets so pair/vehicle/location-keyed modules are exercised on non-empty inputs where the data allow it."""
    from collections import Counter
    pc = Counter((min(c["s"], c["r"]), max(c["s"], c["r"])) for c in d.comms if c["s"] != c["r"])
    tc = Counter((min(t["f"], t["t"]), max(t["f"], t["t"])) for t in d.txns)
    rp = [(min(r["a"], r["b"]), max(r["a"], r["b"])) for r in d.rels if d.entities[r["a"]]["type"] == "PERSON" and d.entities[r["b"]]["type"] == "PERSON"]
    byloc = {}
    for o in d.obs:
        if d.entities[o["subj"]]["type"] == "PERSON":
            byloc.setdefault(o["loc"], set()).add(o["subj"])
    sh = Counter()
    for l, ss in byloc.items():
        ss = sorted(ss)
        for i, a in enumerate(ss[:12]):
            for b in ss[i + 1:12]:
                sh[(a, b)] += 1
    own = [(r["a"], r["b"]) for r in d.rels if r["type"] in ("OWNS", "USES") and d.entities[r["b"]]["type"] == "VEHICLE"]
    vloc = Counter((o["subj"], o["loc"]) for o in d.obs if d.entities[o["subj"]]["type"] == "VEHICLE")
    top = lambda c: [k for k, _ in c.most_common(3)]
    return dict(comm=top(pc), txn=top(tc), rel=sorted(set(rp))[:3], shared=top(sh), own=own[:3], vloc=[k for k, _ in vloc.most_common(3)])


def param_sets(d, module, variant, seed, n=3):
    rng = random.Random(f"{seed}|{d.case_id}|{module}|{variant}")
    persons = [i for i, e in d.entities.items() if e["type"] == "PERSON"]
    locs = [i for i, e in d.entities.items() if e["type"] == "LOCATION"]
    vehs = [i for i, e in d.entities.items() if e["type"] == "VEHICLE"]
    busy = lambda ids, key: sorted(ids, key=lambda i: -key(i))[:6]
    act = {}
    for a in activity(d):
        act[a["ent"]] = act.get(a["ent"], 0) + 1
    P = busy(persons, lambda i: act.get(i, 0))
    times = sorted(a["at"] for a in activity(d) if a["at"])
    t_lo, t_mid, t_hi = (times[0], times[len(times) // 2], times[-1]) if times else (None, None, None)
    wins = [dict(), dict(start_time=t_lo + (t_hi - t_lo) / 4, end_time=t_lo + 3 * (t_hi - t_lo) / 4) if times else {}, dict(start_time=t_mid, end_time=t_mid)]   # all / middle / zero-width boundary
    ent_ids = _pick(rng, P, 3)
    base = []
    for w in wins[:n]:
        pr = dict(w, result_limit=LIMIT)
        e = ent_ids[len(base) % len(ent_ids)] if ent_ids else None
        e2 = ent_ids[(len(base) + 1) % len(ent_ids)] if len(ent_ids) > 1 else e
        loc = _pick(rng, locs, 1)[0] if locs else None
        # use most-observed location for location-keyed modules
        cnt = {}
        for o in d.obs:
            cnt[o["loc"]] = cnt.get(o["loc"], 0) + 1
        loc = max(cnt, key=cnt.get) if cnt and len(base) == 0 else (rng.choice(sorted(cnt)) if cnt else loc)
        inc = sorted(i for i, ev in d.events.items() if ev["type"] == "INCIDENT") or sorted(d.events)
        veh = max({o["subj"] for o in d.obs if o["subj"] in vehs} or set(vehs) or {None}, key=lambda v: (v is not None, v))
        base.append(dict(pr, entity_id=e, entity_id_1=e, entity_id_2=e2, location_id=loc, event_id=inc[0] if inc else None, vehicle_id=veh))
    out = []
    for pr in base:
        q = dict(pr)
        if variant in ("copresence",):
            q["window_minutes"] = 30
        if variant in ("before", "after", "around"):
            q["window_minutes"] = 120
        if variant == "pairs":
            q["min_count"] = 2
        if module == "M7":
            q["gap_minutes"] = 60
        if variant in ("between", "shared", "default") and module in ("M2", "M10", "M4", "M11") and q["entity_id_1"] == q["entity_id_2"] and len(P) > 1:
            q["entity_id_2"] = P[1] if P[0] == q["entity_id_1"] else P[0]
        T = targets(d)
        i = len([o for o in out]) // 2           # which of the n base sets this is
        pick = lambda lst: lst[i % len(lst)] if lst else None
        if (module, variant) in (("M2", "default"),) and pick(T["comm"]):
            q["entity_id_1"], q["entity_id_2"] = pick(T["comm"])
        if (module, variant) in (("M15", "between"),) and pick(T["txn"]):
            q["entity_id_1"], q["entity_id_2"] = pick(T["txn"])
        if (module, variant) in (("M10", "default"), ("M11", "connected"), ("M11", "shortest")) and pick(T["rel"]):
            q["entity_id_1"], q["entity_id_2"] = pick(T["rel"])
        if (module, variant) == ("M4", "shared") and pick(T["shared"]):
            q["entity_id_1"], q["entity_id_2"] = pick(T["shared"])
        if module == "M13" and pick(T["own"]):
            q["entity_id"] = pick(T["own"])[0]
        if (module, variant) == ("M14", "associated_entities") and pick(T["own"]):
            q["vehicle_id"] = pick(T["own"])[1]
        if (module, variant) == ("M14", "near_location") and pick(T["vloc"]):
            q["location_id"] = pick(T["vloc"])[1]
        if module == "M11":
            q["max_hops"] = 3
        if variant == "repeated" and module == "M14":
            q["location_id"] = None
        if module in ("M12",):
            q["minimum_strength"] = 0.3
        for hist in (False, True):
            r = dict(q, include_historical=hist)
            # drop time window for modules that reject it / ignore it harmlessly: pass anyway (SQL ignores undefined ones only if used)
            out.append(r)
    return out
