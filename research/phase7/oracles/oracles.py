"""Independent Python oracles for SQL modules M1-M17 (M18/Q40 is verified against its own Python re-implementation in run_phase7).
Written from the module *specifications* (docs/SQL_MODULES.md), not by translating SQL line by line. Each oracle returns
(rows, order_key) where rows are dicts using the SQL output column names that are compared, and order_key(row) must be non-decreasing
in the SQL output."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import median

NEG = lambda v: -v


def _ok(d, p, eid):
    return bool(p.get("include_historical")) or d.status(eid) == "SUPPORTED"


def _after(t, bound):      # t >= bound; a missing timestamp never satisfies a supplied bound (SQL NULL semantics)
    return True if bound is None else (t is not None and t >= bound)


def _before(t, bound):
    return True if bound is None else (t is not None and t <= bound)


def _overlaps(o, p):
    return _after(o["to"], p.get("start_time")) and _before(o["frm"], p.get("end_time"))


def _ts(t):
    return t.timestamp() if t else float("-inf")


def _lim(rows, p, default):
    n = p.get("result_limit") or default
    return rows[:n]


def _refs(vals):
    return sorted({v for v in vals if v is not None})


# ---------------- M1 communications
def m1(d, variant, p):
    rows, hist = [], p
    cs = [c for c in d.comms if _ok(d, p, c["eid"]) and _after(c["at"], p.get("start_time")) and _before(c["at"], p.get("end_time"))]
    if variant in ("contacts", "frequency"):
        e = p["entity_id"]
        g = {}
        for c in cs:
            if e not in (c["s"], c["r"]):
                continue
            o = c["r"] if c["s"] == e else c["s"]
            g.setdefault(o, []).append(c)
        for o, L in g.items():
            r = dict(entity_ref=d.ref(o), display_name=d.entities[o]["name"], communication_count=len(L), first_at=min(c["at"] for c in L), last_at=max(c["at"] for c in L),
                     record_refs=_refs(c["ref"] for c in L), evidence_refs=_refs(d.ev_ref(c["eid"]) for c in L))
            if variant == "contacts":
                r["validity_states"] = sorted({d.status(c["eid"]) for c in L})
            rows.append(r)
        key = (lambda r: (-_ts(r["last_at"]),)) if variant == "contacts" else (lambda r: (-r["communication_count"], -_ts(r["last_at"])))
    else:  # pairs
        g = {}
        for c in cs:
            g.setdefault((min(c["s"], c["r"]), max(c["s"], c["r"])), []).append(c)
        for (a, b), L in g.items():
            if len(L) >= (p.get("min_count") or 3):
                rows.append(dict(entity_a_ref=d.ref(a), entity_b_ref=d.ref(b), communication_count=len(L), first_at=min(c["at"] for c in L), last_at=max(c["at"] for c in L),
                                 record_refs=_refs(c["ref"] for c in L), evidence_refs=_refs(d.ev_ref(c["eid"]) for c in L)))
        key = lambda r: (-r["communication_count"],)
    return rows, key


def m2(d, variant, p):
    a, b = p["entity_id_1"], p["entity_id_2"]
    rows = []
    for c in d.comms:
        if (c["s"], c["r"]) in ((a, b), (b, a)):
            if _ok(d, p, c["eid"]) and _after(c["at"], p.get("start_time")) and _before(c["at"], p.get("end_time")):
                rows.append(dict(communication_ref=c["ref"], sender_ref=d.ref(c["s"]), receiver_ref=d.ref(c["r"]), comm_type=c["type"], occurred_at=c["at"], duration_sec=c["dur"],
                                 evidence_ref=d.ev_ref(c["eid"]), validity_status=d.status(c["eid"])))
    return rows, lambda r: (_ts(r["occurred_at"]),)


# ---------------- M3 / M4 / M5 observations
def _obs_ok(d, p, o):
    return _ok(d, p, o["eid"]) and _overlaps(o, p)


def m3(d, variant, p):
    rows = []
    if variant == "present":
        g = {}
        for o in d.obs:
            if o["loc"] == p["location_id"] and d.entities[o["subj"]]["type"] == "PERSON" and _obs_ok(d, p, o):
                g.setdefault(o["subj"], []).append(o)
        for s, L in g.items():
            rows.append(dict(entity_ref=d.ref(s), first_seen=min(o["frm"] for o in L), last_seen=max(o["to"] for o in L if o["to"]) if any(o["to"] for o in L) else None,
                             observation_count=len(L), sources=_refs(o["source"] for o in L), record_refs=_refs(o["ref"] for o in L), evidence_refs=_refs(d.ev_ref(o["eid"]) for o in L)))
        return rows, lambda r: (_ts(r["first_seen"]),)
    w = timedelta(minutes=p.get("window_minutes") or 0)
    for oa in d.obs:
        if d.entities[oa["subj"]]["type"] != "PERSON" or (p.get("location_id") and oa["loc"] != p["location_id"]):
            continue
        if not (_after(oa["to"], p.get("start_time")) and _before(oa["frm"], p.get("end_time"))):
            continue
        for ob in d.obs:
            if ob["loc"] != oa["loc"] or ob["subj"] <= oa["subj"] or d.entities[ob["subj"]]["type"] != "PERSON":
                continue
            if None in (oa["frm"], oa["to"], ob["frm"], ob["to"]):
                continue
            if not (oa["frm"] <= ob["to"] + w and ob["frm"] <= oa["to"] + w):
                continue
            if not (p.get("include_historical") or (d.status(oa["eid"]) == "SUPPORTED" and d.status(ob["eid"]) == "SUPPORTED")):
                continue
            rows.append(dict(entity_a_ref=d.ref(oa["subj"]), entity_b_ref=d.ref(ob["subj"]), location_ref=d.ref(oa["loc"]), overlap_start=max(oa["frm"], ob["frm"]),
                             overlap_end=min(oa["to"], ob["to"]), record_ref_a=oa["ref"], record_ref_b=ob["ref"], evidence_ref_a=d.ev_ref(oa["eid"]), evidence_ref_b=d.ev_ref(ob["eid"])))
    return rows, lambda r: (_ts(r["overlap_start"]),)


def m4(d, variant, p):
    rows = []
    if variant == "shared":
        e1, e2 = p["entity_id_1"], p["entity_id_2"]
        g = {}
        for o in d.obs:
            if o["subj"] in (e1, e2) and _obs_ok(d, p, o):
                g.setdefault(o["loc"], []).append(o)
        for l, L in g.items():
            if len({o["subj"] for o in L}) == 2:
                rows.append(dict(location_ref=d.ref(l), visits_entity_1=sum(o["subj"] == e1 for o in L), visits_entity_2=sum(o["subj"] == e2 for o in L),
                                 record_refs=_refs(o["ref"] for o in L), evidence_refs=_refs(d.ev_ref(o["eid"]) for o in L), _n=len(L)))
        return rows, lambda r: (-r["_n"],)
    g = {}
    for o in d.obs:
        if d.entities[o["subj"]]["type"] != "PERSON" or not _obs_ok(d, p, o):
            continue
        if p.get("entity_id") and o["subj"] != p["entity_id"]:
            continue
        if p.get("location_id") and o["loc"] != p["location_id"]:
            continue
        g.setdefault((o["subj"], o["loc"]), []).append(o)
    for (s, l), L in g.items():
        rows.append(dict(entity_ref=d.ref(s), location_ref=d.ref(l), visit_count=len(L), first_seen=min(o["frm"] for o in L), last_seen=max(o["to"] for o in L), record_refs=_refs(o["ref"] for o in L)))
    return rows, lambda r: (-r["visit_count"], r["entity_ref"])


def m5(d, variant, p):
    L = [o for o in d.obs if o["subj"] == p["entity_id"] and _obs_ok(d, p, o)]
    if variant == "history":
        rows = [dict(record_ref=o["ref"], location_ref=d.ref(o["loc"]), observed_from=o["frm"], observed_to=o["to"], source_kind=o["kind"], source=o["source"],
                     evidence_ref=d.ev_ref(o["eid"]), validity_status=d.status(o["eid"])) for o in L]
        return rows, lambda r: (_ts(r["observed_from"]),)
    g = {}
    for o in L:
        g.setdefault(o["loc"], []).append(o)
    rows = [dict(location_ref=d.ref(l), visit_count=len(x), first_seen=min(o["frm"] for o in x), last_seen=max(o["to"] for o in x), record_refs=_refs(o["ref"] for o in x)) for l, x in g.items()]
    return rows, lambda r: (-r["visit_count"], -_ts(r["last_seen"]))


# ---------------- activity (M6/M7/M8): the union of everything recorded about an entity
def activity(d):
    A = []
    for o in d.obs:
        A.append(dict(at=o["frm"], type="OBSERVATION", ref=o["ref"], ent=o["subj"], other=None, loc=o["loc"], desc=f"{o['kind']} observation from {o['source']}", eid=o["eid"], status=d.status(o["eid"])))
    for c in d.comms:
        A.append(dict(at=c["at"], type="COMMUNICATION", ref=c["ref"], ent=c["s"], other=c["r"], loc=None, desc=f"{c['type']} sent", eid=c["eid"], status=d.status(c["eid"])))
        A.append(dict(at=c["at"], type="COMMUNICATION", ref=c["ref"], ent=c["r"], other=c["s"], loc=None, desc=f"{c['type']} received", eid=c["eid"], status=d.status(c["eid"])))
    for t in d.txns:
        A.append(dict(at=t["at"], type="TRANSACTION", ref=t["ref"], ent=t["f"], other=t["t"], loc=t["loc"], desc=f"{t['type']} sent {t['amount']} {t['cur']}", eid=t["eid"], status=d.status(t["eid"])))
        A.append(dict(at=t["at"], type="TRANSACTION", ref=t["ref"], ent=t["t"], other=t["f"], loc=t["loc"], desc=f"{t['type']} received {t['amount']} {t['cur']}", eid=t["eid"], status=d.status(t["eid"])))
    for eid_, ev in d.events.items():
        if ev["at"] is None:
            continue
        for e2, ent in d.event_entities:
            if e2 == eid_:
                A.append(dict(at=ev["at"], type="EVENT", ref=ev["ref"], ent=ent, other=None, loc=ev["loc"], desc=ev["desc"] or ev["type"], eid=None, status="SUPPORTED", noev=True))
    return A


def _okA(d, p, a):
    return bool(p.get("include_historical")) or a["status"] == "SUPPORTED"


def m6(d, variant, p):
    rows = []
    for a in activity(d):
        if a["ent"] == p["entity_id"] and _okA(d, p, a) and _after(a["at"], p.get("start_time")) and _before(a["at"], p.get("end_time")):
            rows.append(dict(occurred_at=a["at"], item_type=a["type"], record_ref=a["ref"], description=a["desc"], other_entity_ref=d.ref(a["other"]) if a["other"] else None,
                             location_ref=d.ref(a["loc"]) if a["loc"] else None, evidence_ref=None if a.get("noev") else d.ev_ref(a["eid"]), validity_status=a["status"]))
    return rows, lambda r: (_ts(r["occurred_at"]),)


def m7(d, variant, p):
    seen = {}
    for a in activity(d):
        if a["ent"] == p["entity_id"] and _okA(d, p, a) and _after(a["at"], p.get("start_time")) and _before(a["at"], p.get("end_time")):
            seen.setdefault((a["at"], a["ref"]), a)
    ks = sorted(seen)
    thr = timedelta(minutes=p.get("gap_minutes") or 120)
    rows = []
    for (t0, r0), (t1, r1) in zip(ks, ks[1:]):
        if t1 - t0 >= thr:
            secs = Decimal(str((t1 - t0).total_seconds()))
            rows.append(dict(gap_start=t0, gap_end=t1, gap_minutes=int((secs / 60 + Decimal("0.5")).to_integral_value(rounding="ROUND_FLOOR")), before_record_ref=r0, after_record_ref=r1))
    return rows, lambda r: (-r["gap_minutes"], _ts(r["gap_start"]))


def m8(d, variant, p):
    inc = d.events[p["event_id"]]
    w = timedelta(minutes=60 if p.get("window_minutes") is None else p["window_minutes"])
    t0 = inc["at"]
    sel = []
    for a in activity(d):
        if a["ref"] == inc["ref"] or d.entities[a["ent"]]["type"] != "PERSON" or not _okA(d, p, a) or a["at"] is None:
            continue
        if variant == "before" and t0 - w <= a["at"] < t0 or variant == "after" and t0 < a["at"] <= t0 + w or variant == "around" and t0 - w <= a["at"] <= t0 + w:
            sel.append(a)
    if variant == "around":
        g = {}
        for a in sel:
            g.setdefault(a["ent"], []).append(a)
        rows = [dict(entity_ref=d.ref(e), recorded_at_incident_location=any(x["loc"] is not None and x["loc"] == inc["loc"] for x in L), record_count=len(L),
                     first_record=min(x["at"] for x in L), last_record=max(x["at"] for x in L), record_refs=_refs(x["ref"] for x in L),
                     evidence_refs=_refs(None if x.get("noev") else d.ev_ref(x["eid"]) for x in L)) for e, L in g.items()]
        return rows, lambda r: (-int(r["recorded_at_incident_location"]), -r["record_count"])
    rows = [dict(occurred_at=a["at"], item_type=a["type"], record_ref=a["ref"], entity_ref=d.ref(a["ent"]), description=a["desc"], location_ref=d.ref(a["loc"]) if a["loc"] else None,
                 evidence_ref=None if a.get("noev") else d.ev_ref(a["eid"]), validity_status=a["status"]) for a in sel]
    return rows, (lambda r: (-_ts(r["occurred_at"]),)) if variant == "before" else (lambda r: (_ts(r["occurred_at"]),))


# ---------------- relationships
def _rok(d, p, r):
    return _ok(d, p, r["eid"])


def m9(d, variant, p):
    e = p["entity_id"]
    rows = []
    for r in d.rels:
        if e in (r["a"], r["b"]) and _rok(d, p, r):
            o = r["b"] if r["a"] == e else r["a"]
            rows.append(dict(relationship_ref=r["ref"], rel_type=r["type"], other_entity_ref=d.ref(o), entity_is_subject=(r["a"] == e), strength=r["strength"], valid_from=r["vfrom"], valid_to=r["vto"],
                             evidence_ref=d.ev_ref(r["eid"]), validity_status=d.status(r["eid"])))
    return rows, lambda r: (1 if r["strength"] is None else 0, -(r["strength"] or 0), r["relationship_ref"])


def m10(d, variant, p):
    a, b = p["entity_id_1"], p["entity_id_2"]
    rows = [dict(relationship_ref=r["ref"], rel_type=r["type"], entity_a_ref=d.ref(r["a"]), entity_b_ref=d.ref(r["b"]), strength=r["strength"], valid_from=r["vfrom"], valid_to=r["vto"],
                 evidence_ref=d.ev_ref(r["eid"]), validity_status=d.status(r["eid"])) for r in d.rels if (r["a"], r["b"]) in ((a, b), (b, a)) and _rok(d, p, r)]
    return rows, lambda r: (r["relationship_ref"],)


def m12(d, variant, p):
    e, mn = p["entity_id"], Decimal(str(p.get("minimum_strength") or 0))
    rows = []
    for r in d.rels:
        if e in (r["a"], r["b"]) and r["strength"] is not None and r["strength"] >= mn and _rok(d, p, r):
            rows.append(dict(other_entity_ref=d.ref(r["b"] if r["a"] == e else r["a"]), rel_type=r["type"], strength=r["strength"], relationship_ref=r["ref"], evidence_ref=d.ev_ref(r["eid"]), validity_status=d.status(r["eid"])))
    return rows, lambda r: (-r["strength"], r["relationship_ref"])


def m11(d, variant, p):
    kinds = {}
    def add(a, b, k):
        kinds.setdefault((a, b), set()).add(k); kinds.setdefault((b, a), set()).add(k)
    for r in d.rels:
        if r["type"] not in ("OWNS", "USES") and _rok(d, p, r):
            add(r["a"], r["b"], "RELATIONSHIP")
    for c in d.comms:
        if _ok(d, p, c["eid"]):
            add(c["s"], c["r"], "COMMUNICATION")
    for t in d.txns:
        if _ok(d, p, t["eid"]):
            add(t["f"], t["t"], "TRANSACTION")
    adj = {}
    for (a, b) in kinds:
        adj.setdefault(a, []).append(b)
    src, dst = p["entity_id_1"], p["entity_id_2"]
    mx = min(p.get("max_hops") or (3 if variant == "connected" else 4), 4)
    found = []
    def walk(path, kp):
        last = path[-1]
        if last == dst:
            found.append((list(path), list(kp)))
            return
        if len(path) - 1 >= mx:
            return
        for n in adj.get(last, []):
            if n not in path:
                walk(path + [n], kp + ["+".join(sorted(kinds[(last, n)]))])
    walk([src], [])
    if variant == "connected":
        found = [f for f in found if len(f[0]) - 1 >= 2]
    elif found:
        h = min(len(f[0]) - 1 for f in found)
        found = [f for f in found if len(f[0]) - 1 == h]
    rows = [dict(hop_count=len(pa) - 1, path_refs=[d.ref(x) for x in pa], link_kinds=kp) for pa, kp in found]
    return rows, (lambda r: (r["hop_count"],)) if variant == "connected" else (lambda r: (0,))


# ---------------- vehicles
def m13(d, variant, p):
    now = datetime.now(timezone.utc)
    rows = []
    for r in d.rels:
        if r["a"] == p["entity_id"] and r["type"] in ("OWNS", "USES") and d.entities[r["b"]]["type"] == "VEHICLE" and _rok(d, p, r):
            rows.append(dict(vehicle_ref=d.ref(r["b"]), plate=d.entities[r["b"]]["attrs"].get("plate"), rel_type=r["type"], valid_from=r["vfrom"], valid_to=r["vto"],
                             is_current=(r["vto"] is None or r["vto"] > now), relationship_ref=r["ref"], evidence_ref=d.ev_ref(r["eid"]), validity_status=d.status(r["eid"])))
    return rows, lambda r: (-int(r["is_current"]), _ts(r["valid_from"]))


def m14(d, variant, p):
    rows = []
    if variant == "associated_entities":
        for r in d.rels:
            if r["b"] == p["vehicle_id"] and r["type"] in ("OWNS", "USES") and d.entities[r["a"]]["type"] == "PERSON" and _rok(d, p, r):
                if (p.get("start_time") is None or r["vto"] is None or r["vto"] >= p["start_time"]) and (p.get("end_time") is None or r["vfrom"] is None or r["vfrom"] <= p["end_time"]):
                    rows.append(dict(entity_ref=d.ref(r["a"]), rel_type=r["type"], valid_from=r["vfrom"], valid_to=r["vto"], relationship_ref=r["ref"], evidence_ref=d.ev_ref(r["eid"]), validity_status=d.status(r["eid"])))
        return rows, lambda r: (_ts(r["valid_from"]),)
    g = {}
    for o in d.obs:
        if d.entities[o["subj"]]["type"] != "VEHICLE" or not _obs_ok(d, p, o):
            continue
        if variant == "near_location" and o["loc"] != p["location_id"]:
            continue
        if variant == "repeated" and p.get("location_id") and o["loc"] != p["location_id"]:
            continue
        g.setdefault(o["subj"], []).append(o)
    if variant == "near_location":
        rows = [dict(vehicle_ref=d.ref(v), plate=d.entities[v]["attrs"].get("plate"), first_seen=min(o["frm"] for o in L), last_seen=max(o["to"] for o in L), observation_count=len(L),
                     record_refs=_refs(o["ref"] for o in L), evidence_refs=_refs(d.ev_ref(o["eid"]) for o in L)) for v, L in g.items()]
        return rows, lambda r: (_ts(r["first_seen"]),)
    rows = [dict(vehicle_ref=d.ref(v), observation_count=len(L), distinct_locations=len({o["loc"] for o in L}), first_seen=min(o["frm"] for o in L), last_seen=max(o["to"] for o in L),
                 record_refs=_refs(o["ref"] for o in L)) for v, L in g.items() if len(L) >= (p.get("min_count") or 2)]
    return rows, lambda r: (-r["observation_count"],)


# ---------------- transactions
def _tx(d, p):
    return [t for t in d.txns if _ok(d, p, t["eid"]) and _after(t["at"], p.get("start_time")) and _before(t["at"], p.get("end_time"))]


def _trow(d, t):
    return dict(transaction_ref=t["ref"], from_ref=d.ref(t["f"]), to_ref=d.ref(t["t"]), amount=t["amount"], currency=t["cur"], txn_type=t["type"], occurred_at=t["at"], evidence_ref=d.ev_ref(t["eid"]), validity_status=d.status(t["eid"]))


def m15(d, variant, p):
    T = _tx(d, p)
    if variant == "entity":
        return [_trow(d, t) for t in T if p["entity_id"] in (t["f"], t["t"])], lambda r: (_ts(r["occurred_at"]),)
    if variant == "between":
        a, b = p["entity_id_1"], p["entity_id_2"]
        return [_trow(d, t) for t in T if (t["f"], t["t"]) in ((a, b), (b, a))], lambda r: (_ts(r["occurred_at"]),)
    if variant == "top_amounts":
        g = {}
        for t in T:
            for e in {t["f"], t["t"]}:
                x = g.setdefault(e, dict(sent=Decimal(0), recv=Decimal(0), n=0, refs=[]))
                x["sent"] += t["amount"] if t["f"] == e else 0
                x["recv"] += t["amount"] if t["t"] == e else 0
                x["n"] += 1; x["refs"].append(t["ref"])
        rows = [dict(entity_ref=d.ref(e), total_sent=x["sent"], total_received=x["recv"], transaction_count=x["n"], record_refs=_refs(x["refs"]), _m=max(x["sent"], x["recv"])) for e, x in g.items()]
        return rows, lambda r: (-r["_m"],)
    if variant == "patterns":
        g = {}
        for t in T:
            if p.get("entity_id") and p["entity_id"] not in (t["f"], t["t"]):
                continue
            g.setdefault((t["f"], t["t"]), []).append(t)
        rows = [dict(from_ref=d.ref(f), to_ref=d.ref(to), transaction_count=len(L), total_amount=sum(t["amount"] for t in L), average_amount=(sum(t["amount"] for t in L) / len(L)).quantize(Decimal("0.01"), rounding="ROUND_HALF_UP"),
                     first_at=min(t["at"] for t in L), last_at=max(t["at"] for t in L), record_refs=_refs(t["ref"] for t in L)) for (f, to), L in g.items()]
        return rows, lambda r: (-r["total_amount"],)
    # repeated_or_unusual: median over ALL case transactions that pass the validity filter (not the time window)
    allv = [t["amount"] for t in d.txns if _ok(d, p, t["eid"])]
    med = Decimal(str(median(allv))) if allv else Decimal(0)
    g = {}
    for t in T:
        g.setdefault((t["f"], t["t"]), []).append(t)
    mc = p.get("min_count") or 2
    rows = []
    for (f, to), L in g.items():
        big = max(t["amount"] for t in L) >= 5 * med
        if len(L) >= mc or big:
            rows.append(dict(from_ref=d.ref(f), to_ref=d.ref(to), transaction_count=len(L), total_amount=sum(t["amount"] for t in L), largest_amount=max(t["amount"] for t in L),
                             repeated=len(L) >= mc, large_relative_to_case_median=big, record_refs=_refs(t["ref"] for t in L)))
    return rows, lambda r: (-r["total_amount"],)


# ---------------- evidence
def _evok(d, p, e):
    return bool(p.get("include_historical")) or d.evidence[e]["status"] == "SUPPORTED"


def _evrow(d, e):
    x = d.evidence[e]
    return dict(evidence_ref=x["ref"], evidence_type=x["type"], source=x["source"], evidence_timestamp=x["ts"], validity_status=x["status"], reliability_score=x["rel"], description=x["desc"], origin=d.origin(e))


def m16(d, variant, p):
    pairs = d.evidence_entities if variant == "entity" else d.evidence_events
    key = p["entity_id"] if variant == "entity" else p["event_id"]
    ids = sorted({e for e, k in pairs if k == key and e in d.evidence and _evok(d, p, e)})
    rows = [_evrow(d, e) for e in ids]
    return rows, lambda r: (_ts(r["evidence_timestamp"]) if r["evidence_timestamp"] else float("inf"), r["evidence_ref"])


def m17(d, variant, p):
    by_ent = {}
    for e, k in set(d.evidence_entities):
        if e in d.evidence and _evok(d, p, e):
            by_ent.setdefault(k, set()).add(e)
    if variant == "multi_entity":
        by_ev = {}
        for k, es in by_ent.items():
            for e in es:
                by_ev.setdefault(e, set()).add(k)
        rows = [dict(evidence_ref=d.evidence[e]["ref"], evidence_type=d.evidence[e]["type"], source=d.evidence[e]["source"], validity_status=d.evidence[e]["status"], entity_count=len(ks),
                     entity_refs=_refs(d.ref(k) for k in ks)) for e, ks in by_ev.items() if len(ks) >= 2]
        return rows, lambda r: (-r["entity_count"], r["evidence_ref"])
    if variant == "multi_type":
        rows = []
        for k, es in by_ent.items():
            if d.entities[k]["type"] != "PERSON":
                continue
            types = {d.evidence[e]["type"] for e in es}
            origins = {d.origin(e) for e in es}
            if len(types) >= (p.get("min_count") or 2):
                rows.append(dict(entity_ref=d.ref(k), evidence_type_count=len(types), independent_source_count=len(origins), evidence_types=sorted(types), evidence_refs=_refs(d.evidence[e]["ref"] for e in es), origins=sorted(origins)))
        return rows, lambda r: (-r["independent_source_count"], -r["evidence_type_count"], r["entity_ref"])
    rows = []
    for k, es in by_ent.items():
        if p.get("entity_id") and k != p["entity_id"]:
            continue
        ids = sorted(es)
        # SQL joins evidence_entities on ea.evidence_id < eb.evidence_id, and filters validity of both sides (unless historical)
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                if d.origin(a) != d.origin(b):
                    rows.append(dict(entity_ref=d.ref(k), evidence_ref_a=d.evidence[a]["ref"], type_a=d.evidence[a]["type"], origin_a=d.origin(a), evidence_ref_b=d.evidence[b]["ref"], type_b=d.evidence[b]["type"], origin_b=d.origin(b)))
    return rows, lambda r: (r["entity_ref"],)


def m18(d, variant, p):
    if variant != "reliability":
        raise NotImplementedError(f"no independent oracle for M18.{variant}")
    rows = [dict(evidence_ref=e["ref"], evidence_type=e["type"], source=e["source"], reliability_score=e["rel"], validity_status=e["status"], description=e["desc"])
            for e in d.evidence.values() if bool(p.get("include_historical")) or e["status"] == "SUPPORTED"]
    return rows, lambda r: (1 if r["reliability_score"] is None else 0, -(r["reliability_score"] or 0), r["evidence_ref"])


ORACLES = {"M18": m18, "M1": m1, "M2": m2, "M3": m3, "M4": m4, "M5": m5, "M6": m6, "M7": m7, "M8": m8, "M9": m9, "M10": m10, "M11": m11, "M12": m12, "M13": m13, "M14": m14, "M15": m15, "M16": m16, "M17": m17}
ORDERED_LIST_KEYS = {"path_refs", "link_kinds"}
