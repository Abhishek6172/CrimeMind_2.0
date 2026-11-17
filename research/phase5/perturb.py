"""Controlled, seeded perturbations of a CaseView (never of the stored database, never using ground truth).

Every perturbation draws from random.Random(sha256(seed|case|kind|level)) so a run is exactly reproducible. `p` is the
perturbation level. Records and evidence are copied before modification; the input view is untouched."""
import dataclasses
import hashlib
import random
from datetime import timedelta

SHIFT_MIN, SHIFT_MAX = 30, 240


def _copy(view):
    return dataclasses.replace(view, obs=[dict(x) for x in view.obs], comms=[dict(x) for x in view.comms], txns=[dict(x) for x in view.txns],
                               rels=[dict(x) for x in view.rels], evidence={k: dict(v) for k, v in view.evidence.items()}, activity=list(view.activity))


def rng_for(seed, case_ref, kind, level):
    return random.Random(int(hashlib.sha256(f"{seed}|{case_ref}|{kind}|{level}".encode()).hexdigest()[:16], 16))


def _records(v):
    return v.obs, v.comms, v.txns, v.rels


def missing_evidence(v, p, rng):
    drop = {e for e in sorted(v.evidence) if rng.random() < p}
    for name in ("obs", "comms", "txns", "rels"):
        rows = getattr(v, name)
        setattr(v, name, [r for r in rows if not ((r["evidence"] in drop) or (r["evidence"] is None and rng.random() < p))])
    v.evidence = {k: e for k, e in v.evidence.items() if k not in drop}


def noisy_location(v, p, rng):
    locs = sorted(v.locations)
    for o in v.obs:
        if rng.random() < p:
            o["location"] = rng.choice([l for l in locs if l != o["location"]])


def incorrect_timestamps(v, p, rng):
    for r in v.obs:
        if rng.random() < p:
            d = timedelta(minutes=rng.choice([-1, 1]) * rng.uniform(SHIFT_MIN, SHIFT_MAX))
            r["t_from"], r["t_to"] = r["t_from"] + d, r["t_to"] + d
    for r in v.comms + v.txns:
        if rng.random() < p:
            r["t"] = r["t"] + timedelta(minutes=rng.choice([-1, 1]) * rng.uniform(SHIFT_MIN, SHIFT_MAX))


def duplicate_evidence(v, p, rng):
    """Duplicate records keep the SAME evidence ref and origin (a re-ingested copy of one source), new record ref."""
    for name in ("obs", "comms", "txns"):
        rows = getattr(v, name)
        extra = []
        for r in rows:
            if rng.random() < p:
                d = dict(r); d["ref"] = r["ref"] + "-DUP"; extra.append(d)
        rows.extend(extra)


def contradictory_records(v, p, rng):
    """Random persons (independent of any role) receive a far-away location record from a DIFFERENT origin overlapping the incident."""
    locs = sorted(v.locations)
    far = [l for l in locs if l != v.incident_location]
    for i, c in enumerate(v.candidates):
        if rng.random() < p:
            ref = f"E-NOISE-{i}"
            v.evidence[ref] = dict(type="ACCESS_LOG", source=f"ACCESS:noise-{i}", origin=f"ACCESS:noise-{i}", reliability=0.8, status="SUPPORTED",
                                   timestamp=v.incident_time, entities=[c])
            v.obs.append(dict(ref=f"OBS-NOISE-{i}", subject=c, location=rng.choice(far), t_from=v.incident_time - timedelta(minutes=20),
                              t_to=v.incident_time + timedelta(minutes=20), source_kind="ACCESS", evidence=ref, status="SUPPORTED", origin=f"ACCESS:noise-{i}"))


def reduced_communication(v, p, rng):
    v.comms = [c for c in v.comms if rng.random() >= p]


def reduced_graph(v, p, rng):
    v.rels = [r for r in v.rels if rng.random() >= p]


def low_reliability(v, p, rng):
    for e in v.evidence.values():
        if e["reliability"] is not None:
            e["reliability"] = e["reliability"] * (1 - p)


def delayed_evidence(v, p, rng):
    """The latest fraction p of evidence (by evidence timestamp) has not arrived yet."""
    order = sorted(v.evidence, key=lambda k: (v.evidence[k]["timestamp"], k))
    late = set(order[len(order) - int(round(p * len(order))):]) if p > 0 else set()
    for name in ("obs", "comms", "txns", "rels"):
        setattr(v, name, [r for r in getattr(v, name) if r["evidence"] not in late])
    v.evidence = {k: e for k, e in v.evidence.items() if k not in late}


def _set_status(v, p, rng, status):
    chosen = {e for e in sorted(v.evidence) if rng.random() < p}
    for e in chosen:
        v.evidence[e]["status"] = status
    for name in ("obs", "comms", "txns", "rels"):
        for r in getattr(v, name):
            if r["evidence"] in chosen:
                r["status"] = status


def invalidation(v, p, rng): _set_status(v, p, rng, "INVALIDATED")
def challenge(v, p, rng): _set_status(v, p, rng, "CHALLENGED")
def update_superseded(v, p, rng): _set_status(v, p, rng, "SUPERSEDED")


def mixed_quality(v, L, rng):
    missing_evidence(v, L / 2, rng); incorrect_timestamps(v, L / 2, rng); low_reliability(v, L / 2, rng)
    duplicate_evidence(v, L / 2, rng); invalidation(v, L / 4, rng)


KINDS = {"missing_evidence": missing_evidence, "noisy_location": noisy_location, "incorrect_timestamps": incorrect_timestamps,
         "duplicate_evidence": duplicate_evidence, "contradictory_records": contradictory_records, "reduced_communication": reduced_communication,
         "reduced_graph": reduced_graph, "low_reliability": low_reliability, "delayed_evidence": delayed_evidence, "invalidation": invalidation,
         "challenge": challenge, "update_superseded": update_superseded, "mixed_quality": mixed_quality}


def perturb(view, kind, level, seed):
    v = _copy(view)
    KINDS[kind](v, level, rng_for(seed, view.case_ref, kind, level))
    return v
