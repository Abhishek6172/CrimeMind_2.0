"""Parameterised investigation storylines for the research datasets (Phase 2).

Unlike the scripted demo case in generator.py, everything that defines the "truth" of a case is drawn from the seed:
who the perpetrator/accomplices are (and how strong their evidence trail is), how many red herrings there are and what
kind (high communication, high proximity, mixed), who is merely near the scene, which witnesses help or mislead, and
which evidence-evolution steps occur. Roles are given to randomly chosen members of the background population, so a
person's reference (P-0xx) carries no information about their role.

The generator records its own plan (who was planted where, which evidence supports or contradicts whom). That plan is
the ground truth; it never reads the ranking, correlation or lifecycle logic of the application.

Only the structure of the story is parameterised. Thresholds used by the application's rules (60 minutes, 150 m) are
respected when planting scene presence, and each planted "claim" (a person near the incident) is recorded with its
supporting evidence so lifecycle expectations can be derived from the plan rather than from the system's own lineage.
"""
import random
from collections import defaultdict
from datetime import timedelta

from .generator import World, background, build_city, ts

DAY = 2
WORKPLACES = [("Orbit Software Park", ""), ("City Bank HQ", ""), ("Mercy Hospital", ""), ("Sunrise School", ""),
              ("Central Municipal Office", ""), ("Harbor Logistics", ""), ("Lotus Textiles", ""), ("Apex Insurance", "")]
PUBLICS = [("City Mall", ""), ("Metro Station", ""), ("Cafe Aroma", ""), ("Riverside Walk", ""), ("Central Market", ""),
           ("Night Bazaar", ""), ("Stadium Road Ground", ""), ("Fuel Station NH-5", ""), ("Sector 4 ATM Kiosk", ""),
           ("Parking Lot P2", ""), ("Temple Square", ""), ("Botanical Garden Entrance", "")]
SPECIALS = [("L-GP1", "Lakeview Pavilion", "PUBLIC", 20.30500, 85.82400),
            ("L-GP2", "Lakeview East Gate", "PUBLIC", 20.30548, 85.82400),      # ~55 m from the pavilion
            ("L-GP3", "Lakeview Jogging Track", "PUBLIC", 20.30900, 85.82900)]  # ~700 m away
MERCHANTS = ["FreshMart", "Metro Pharmacy", "Urban Fuel", "BookNook", "Spice Route Kitchen", "Gadget Hub"]
RULE_WINDOW_MIN = 60     # INCIDENT_PROXIMITY_001 time threshold (backend/app/correlation/rules.py)


def _draw(rng, lo_hi):
    return rng.randint(lo_hi[0], lo_hi[1])


def build_case(conn, rng: random.Random, admin_id: int, case_ref: str, title: str, cfg: dict, size: str) -> dict:
    w = World(conn, case_ref, title, rng, admin_id)
    big = size == "primary"
    res, wrk, pub = build_city(w, 20 if big else 8, WORKPLACES if big else WORKPLACES[:3], PUBLICS if big else PUBLICS[:6], SPECIALS)
    merchants = []
    for i, nm in enumerate(MERCHANTS[:6 if big else 3], 1):
        w.entity("ORGANIZATION", f"O-{i:02d}", nm, {"synthetic": True})
        merchants.append(f"O-{i:02d}")
    n_bg = _draw(rng, cfg["background_persons"][size])
    people, home, gps, cdr, bank = background(w, n_bg, res, wrk, pub, days=range(0, 4), merchants=merchants)

    # ---------------------------------------------------------------- storyline parameters (all seed-driven)
    n_leads = _draw(rng, cfg["n_true_leads"])
    n_rh = _draw(rng, cfg["n_red_herrings"])
    n_by = _draw(rng, cfg["n_bystanders"])
    chosen = rng.sample(people, 1 + n_leads + n_rh + 2 + n_by)
    victim, leads = chosen[0], chosen[1:1 + n_leads]
    rhs = chosen[1 + n_leads:1 + n_leads + n_rh]
    wit1, wit2 = chosen[1 + n_leads + n_rh], chosen[2 + n_leads + n_rh]
    bys = chosen[3 + n_leads + n_rh:]
    perp, accs = leads[0], leads[1:]
    sv = cfg["lead_strengths"]
    strength = {p: rng.choices(list(sv), weights=list(sv.values()))[0] for p in leads}
    decoy = {p: rng.choice(cfg["decoy_types"]) for p in rhs}
    wit2_contradicts = rng.random() < cfg["witness_contradiction_probability"]
    incident_h = rng.randint(*cfg["incident"]["hour_range"])
    T = ts(cfg["incident"]["day"], incident_h, rng.randint(0, 59))
    assert cfg["incident"]["day"] == DAY

    # people in a story have no routine on the evening of the incident (their story evidence is the only record)
    core = set(chosen)
    core_ids = {w.ent[p] for p in core}
    w.obs_rows = [r for r in w.obs_rows if not (r[2] in core_ids and r[5] > ts(DAY, 16) and r[4] < ts(DAY + 1, 0))]

    def at(minutes):
        return T + timedelta(minutes=minutes)

    sup, con, claims = defaultdict(set), defaultdict(set), {}
    counter = {"d": 0}

    def E(etype, source, when, desc, ents, origin=None):
        return w.evidence(etype, source, when, desc, origin or source, ents)

    def presence(p, loc, a, b, kind, source, evref):
        w.obs(p, loc, at(a), at(b), kind, source, evref)
        if loc in ("L-GP1", "L-GP2") and a <= RULE_WINDOW_MIN and b >= -RULE_WINDOW_MIN:
            claims.setdefault(f"INCIDENT_PROXIMITY_001|{p}|EVT-001", {"subject": p, "supporting": set()})["supporting"].add(evref)

    N = lambda p: w.names[p]
    cam = "CAM-05"
    vehicle_used = False
    scene_ev = {}            # person -> dedicated scene-presence evidence refs, in planting order

    # ---------------------------------------------------------------- victim and incident
    v_gps = E("GPS", f"GPS:{victim}:D{DAY}", at(-60), f"GPS extract for {N(victim)}, day {DAY}", [victim])
    w.obs(victim, "L-GP1", at(-40), at(0), "GPS", f"GPS:{victim}:D{DAY}", v_gps)

    # ---------------------------------------------------------------- vehicle (owned by an accomplice, used by the perpetrator)
    cctv_in = cctv_out = rto = nb = None
    if accs and rng.random() < 0.85:
        vehicle_used = True
        w.entity("VEHICLE", "V-01", "White cargo van", {"colour": "white", "synthetic": True})
        owner = accs[0]
        cctv_in = E("CCTV", cam, at(-15), f"{cam} East Gate: white cargo van arrives, plate partially legible", ["V-01", "L-GP2"])
        cctv_out = E("CCTV", cam, at(10), f"{cam} East Gate: white cargo van departs", ["V-01", "L-GP2"])
        presence("V-01", "L-GP2", -15, -14, "CCTV", cam, cctv_in)
        presence("V-01", "L-GP2", 10, 11, "CCTV", cam, cctv_out)
        rto = E("DOCUMENT", "RTO:REG", ts(-90, 0), f"Vehicle registration: registered to {N(owner)}", [owner, "V-01"])
        nb = E("WITNESS_STATEMENT", "WIT:NB", ts(DAY + 1, 10), f"Neighbour statement: {N(perp)} regularly borrows {N(owner)}'s white van.", [perp, "V-01"])
        w.rel(owner, "V-01", "OWNS", 1.0, rto)
        w.rel(perp, "V-01", "USES", 0.7, nb)
        for p in (owner, perp):
            sup[p].update({rto, nb})

    # ---------------------------------------------------------------- witnesses
    t_w = -rng.randint(1, 10)
    wit_ev = E("WITNESS_STATEMENT", f"WIT:{wit1}", ts(DAY, 22), f"Statement of {N(wit1)}: saw a white van parked near the East Gate at about {at(t_w):%H:%M}.",
               [wit1] + (["V-01"] if vehicle_used else []))
    if vehicle_used:
        presence("V-01", "L-GP2", t_w, t_w + 1, "WITNESS", f"WIT:{wit1}", wit_ev)
        for p in (accs[0], perp):
            sup[p].add(wit_ev)
    if wit2_contradicts:
        w2 = E("WITNESS_STATEMENT", f"WIT:{wit2}", ts(DAY, 22, 30), f"Statement of {N(wit2)}: saw {N(perp)} at the market around {at(-20):%H:%M}.",
               [wit2, perp])
        con[perp].add(w2)
    else:
        w2 = E("WITNESS_STATEMENT", f"WIT:{wit2}", ts(DAY, 22, 30), f"Statement of {N(wit2)}: heard raised voices from the park at about {at(-5):%H:%M}.", [wit2])

    # ---------------------------------------------------------------- true leads
    for p in leads:
        s, is_perp = strength[p], p == perp
        # perpetrator: strong = GPS + camera + calls + payment + tie; medium = GPS (+ camera half the time) + calls; weak = camera + calls
        # accomplice: strong = GPS + camera; medium = camera; weak = no scene presence (calls and payments with the perpetrator only)
        has_gps = (is_perp and s in ("strong", "medium")) or (not is_perp and s == "strong")
        has_cctv = (is_perp and (s in ("strong", "weak") or (s == "medium" and rng.random() < 0.5))) or (not is_perp and s in ("strong", "medium"))
        if has_gps:
            g = E("GPS", f"GPS:{p}:D{DAY}", at(-30), f"GPS extract for {N(p)}, day {DAY}", [p])
            presence(p, "L-GP1", -rng.randint(10, 25), rng.randint(5, 20), "GPS", f"GPS:{p}:D{DAY}", g)
            scene_ev.setdefault(p, []).append(g)
            sup[p].add(g)
        if has_cctv:
            c = E("CCTV", cam, at(-12), f"{cam} East Gate footage extract: {N(p)} walking towards the park", [p, "L-GP2"])
            presence(p, "L-GP2", -rng.randint(8, 15), rng.randint(10, 25), "CCTV", cam, c)
            scene_ev.setdefault(p, []).append(c)
            sup[p].add(c)
        if is_perp:
            for _ in range(rng.randint(1, 3)):
                w.comm(p, victim, at(-rng.randint(20, 240)), "CALL", rng.randint(30, 400), cdr[p])
            sup[p].add(cdr[p])
            if s == "strong":
                w.txn(p, victim, rng.choice([20000, 50000, 90000]), ts(rng.choice([0, 1]), 14), "TRANSFER", None, bank[p])
                w.rel(victim, p, "ASSOCIATE", 0.5)
                sup[p].add(bank[p])
        else:
            for _ in range(rng.randint(2, 4)):
                a_, b_ = (p, perp) if rng.random() < 0.5 else (perp, p)
                w.comm(a_, b_, at(-rng.randint(10, 150)), "CALL", rng.randint(20, 300), cdr[a_])
                sup[p].add(cdr[a_])
            w.rel(p, perp, "ASSOCIATE", 0.6)
            if s != "weak":
                w.txn(perp, p, rng.choice([5000, 10000, 30000]), ts(1, 15), "TRANSFER", None, bank[perp])
                sup[p].add(bank[perp])
    # make sure each lead has at least one supporting record even for weak trails
    for p in leads:
        if not sup[p]:
            sup[p].add(cdr[p])

    # ---------------------------------------------------------------- red herrings
    tips = {}
    rh_gps, alibi, device = {}, {}, {}
    for i, p in enumerate(rhs):
        kind = decoy[p]
        wp = rng.choice(wrk)
        if kind in ("HIGH_COMMUNICATION", "MIXED"):
            k = rng.randint(10, 20) if kind == "HIGH_COMMUNICATION" else rng.randint(6, 12)
            for _ in range(k):
                a, b = (p, victim) if rng.random() < 0.5 else (victim, p)
                w.comm(a, b, ts(rng.choice([0, 1, 2]), rng.randint(8, 18), rng.randint(0, 59)), rng.choice(["CALL", "SMS", "CHAT"]), rng.randint(20, 500), cdr[a])
            w.txn(p, victim, rng.choice([1500, 3000, 8000]), ts(rng.choice([0, 1]), 12), "TRANSFER", None, bank[p])
            w.rel(p, victim, "ASSOCIATE", 0.7)
            sup[p].update({cdr[p], bank[p]})
        if kind in ("HIGH_PROXIMITY", "MIXED"):
            src = f"GPS-{rng.randint(10, 99)}"
            dref = f"D-{src}"
            w.entity("DEVICE", dref, f"Phone GPS unit {src}", {"synthetic": True})
            g = E("GPS", src, at(-20), f"{src} trace for {N(p)}: at Lakeview Pavilion", [p, dref], origin=f"GPS:{src}")
            presence(p, "L-GP1", -rng.randint(10, 18), rng.randint(8, 18), "GPS", f"GPS:{src}", g)
            rh_gps[p], device[p] = g, (src, dref)
            scene_ev.setdefault(p, []).append(g)
            sup[p].add(g)
        # independent alibi: workplace access log covering the incident time
        a = E("ACCESS_LOG", f"ACCESS:{wp}:{p}", at(30), f"Access-control log: {N(p)} badge in {at(-150):%H:%M}, out {at(90):%H:%M}", [p, wp])
        w.obs(p, wp, at(-150), at(90), "ACCESS_LOG", f"ACCESS:{wp}:{p}", a)
        alibi[p] = (a, wp)
        con[p].add(a)
        if i == 0:
            tip = E("DOCUMENT", "TIP:ANON", ts(DAY, 23), f"Anonymous tip: {N(p)} was seen arguing with {N(victim)} last week.", [p, victim])
            tips[p] = tip
            sup[p].add(tip)

    # ---------------------------------------------------------------- bystanders near the scene (irrelevant, hard negatives)
    passersby, near = 0, []
    for i, p in enumerate(bys):
        kind = ["guard", "jogger"][i] if i < 2 else rng.choice(["guard", "jogger", "passerby", "passerby"])
        if kind == "passerby" and passersby >= cfg["max_passersby_at_scene"]:
            kind = "jogger"
        if kind == "guard":
            c = E("CCTV", cam, at(-120), f"{cam} East Gate booth: {N(p)} on duty", [p, "L-GP2"])
            presence(p, "L-GP2", -120, 120, "CCTV", cam, c)
        elif kind == "jogger":
            c = E("CCTV", "CAM-06", at(-40), f"CAM-06 Jogging Track: {N(p)} jogging", [p, "L-GP3"])
            presence(p, "L-GP3", -40, -5, "CCTV", "CAM-06", c)
        else:
            passersby += 1
            c = E("GPS", f"GPS:{p}:D{DAY}", at(-10), f"GPS extract for {N(p)}, day {DAY}", [p])
            presence(p, "L-GP1", -rng.randint(3, 8), rng.randint(3, 8), "GPS", f"GPS:{p}:D{DAY}", c)
        near.append({"ref": p, "kind": kind, "evidence": c})

    # ---------------------------------------------------------------- the incident record
    ev_for_event = [v_gps] + ([cctv_in, cctv_out] if vehicle_used else []) + [wit_ev]
    w.event("INCIDENT", "L-GP1", T, f"{N(victim)} found fatally injured at Lakeview Pavilion (incident under investigation)",
            [(victim, "VICTIM")], ev_for_event)
    w.flush()

    # ---------------------------------------------------------------- evidence-evolution script (drawn from the plan)
    ev_cfg = cfg["evolution"]

    def arrive(etype, source, desc, ents, observations=None):
        counter["d"] += 1
        ref = f"E-D{counter['d']:03d}"
        pl = {"evidence": {"ref": ref, "evidence_type": etype, "source": source, "description": desc, "entities": ents}}
        if observations:
            pl["observations"] = observations
        return ref, pl

    steps = []

    def step(sid, n, desc, target, status, trig, reason, trig_ref, payload=None):
        steps.append(dict(scenario_id=sid, step=n, case_ref=case_ref, description=desc, evidence_ref=target, triggering=trig_ref,
                          expected_status=status, trigger=trig, reason=reason, payload=payload or {}))

    prox_rh = next((p for p in rhs if p in rh_gps), None)
    if prox_rh and rng.random() < ev_cfg["device_fault"]:
        src, dref = device[prox_rh]
        d, pl = arrive("DEVICE_DIAGNOSTIC", f"DIAG:{src}", f"Manufacturer diagnostic: unit {src} logged a position/clock fault; positions unreliable.", [prox_rh, dref])
        step("SC-DEVICE-FAULT", 1, "Diagnostic report arrives; the trace is challenged.", rh_gps[prox_rh], "CHALLENGED", "DOCUMENTED_CONTRADICTION", "DEVICE_FAULT", d, pl)
        step("SC-DEVICE-FAULT", 2, "Fault confirmed; the trace is invalidated (history preserved).", rh_gps[prox_rh], "INVALIDATED", "CONFIRMED_INVALIDITY", "DEVICE_FAULT", d)
    if tips and rng.random() < ev_cfg["tip_retraction"]:
        step("SC-TIP-RETRACTED", 1, "The anonymous tipster retracts the claim.", next(iter(tips.values())), "INVALIDATED", "CONFIRMED_INVALIDITY", "SOURCE_RETRACTION", None)
    if rng.random() < ev_cfg["witness_challenge_reinstate"]:
        d1, p1 = arrive("CCTV", "CAM-05-AUDIT", "Camera clock audit: footage times are accurate; no van visible at the reported time.", [])
        d2, p2 = arrive("CCTV", "CAM-05-ENH", "Enhanced footage shows a van at the East Gate at the reported time.", [])
        step("SC-WITNESS", 1, "A camera audit contradicts the witness timing; the statement is challenged.", wit_ev, "CHALLENGED", "DOCUMENTED_CONTRADICTION", "CONTRADICTED_BY_STRONGER_SOURCE", d1, p1)
        step("SC-WITNESS", 2, "Enhanced footage corroborates the statement; it returns to SUPPORTED.", wit_ev, "SUPPORTED", "CORROBORATION", "CORROBORATED", d2, p2)
    if alibi and rng.random() < ev_cfg["alibi_correction"]:
        p0 = rhs[0]
        a_ref, wp = alibi[p0]
        d, pl = arrive("ACCESS_LOG", f"ACCESS:{wp}:R2:{p0}", f"Corrected access-control log: {N(p0)} badge in {at(-140):%H:%M}, out {at(100):%H:%M}.", [p0],
                       [{"subject": p0, "location": wp, "from": at(-140).isoformat(), "to": at(100).isoformat(), "kind": "ACCESS_LOG", "source": f"ACCESS:{wp}:R2:{p0}"}])
        step("SC-ALIBI-CORRECTED", 1, "A corrected access log is issued; the original is superseded.", a_ref, "SUPERSEDED", "REPLACEMENT_RECORD", "CORRECTED_RECORD", d, pl)
    cctv_lead = next((p for p in leads if len(scene_ev.get(p, [])) >= 2), None)
    if cctv_lead and rng.random() < ev_cfg["lead_cctv_timestamp_error"]:
        target = scene_ev[cctv_lead][-1]            # the secondary (camera) record of a lead with two independent scene records
        d, pl = arrive("CCTV", "CAM-05-AUDIT2", "Camera clock audit: the camera clock was offset on the incident day; timestamps unreliable.", [cctv_lead])
        step("SC-LEAD-TIMESTAMP", 1, "Camera audit shows a clock offset; the lead's camera record is challenged.", target, "CHALLENGED", "DOCUMENTED_CONTRADICTION", "TIMESTAMP_ERROR", d, pl)
        step("SC-LEAD-TIMESTAMP", 2, "Offset confirmed; the camera record is invalidated.", target, "INVALIDATED", "CONFIRMED_INVALIDITY", "TIMESTAMP_ERROR", d)

    ranks = {perp: 1}
    for i, a in enumerate(accs, 2):
        ranks[a] = i
    return {
        "w": w, "case_ref": case_ref, "size": size, "T": T, "persons": list(people), "victim": victim,
        "leads": [{"ref": p, "role": "PERPETRATOR" if p == perp else "ACCOMPLICE", "grade": 3 if p == perp else 2, "rank_hint": ranks[p],
                   "strength": strength[p], "supporting_evidence": sorted(sup[p]), "contradicting_evidence": sorted(con[p]),
                   "scene_evidence": scene_ev.get(p, [])} for p in leads],
        "red_herrings": [{"ref": p, "type": decoy[p], "supporting_evidence": sorted(sup[p]), "contradicting_evidence": sorted(con[p]),
                          "scene_evidence": scene_ev.get(p, [])} for p in rhs],
        "witnesses": [wit1, wit2], "witness2_contradicts_a_lead": wit2_contradicts, "bystanders_near_scene": near,
        "bystanders": bys, "claims": {k: {"subject": v["subject"], "supporting": sorted(v["supporting"])} for k, v in claims.items()},
        "steps": steps, "params": {"n_leads": n_leads, "n_red_herrings": n_rh, "n_bystanders": n_by, "n_background": n_bg,
                                   "lead_strengths": {p: strength[p] for p in leads}, "decoy_types": decoy,
                                   "vehicle_used": vehicle_used, "incident_time": T.isoformat()},
    }
