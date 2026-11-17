"""Common-link analysis (SRS 9.23-9.31): returns the concrete shared objects, not just 'A and B are connected'."""
from collections import defaultdict

from .engine import CaseData


def common_links(data: CaseData, a: int, b: int, window_minutes: int = 30) -> dict:
    d = data
    nm = d.name_of
    out = {"entity_a": d.ref_of[a], "entity_b": d.ref_of[b], "links": [], "uncertainties": []}

    def add(kind, cls, summary, records, evidence=()):
        out["links"].append({"domain": kind, "classification": cls, "summary": summary,
                             "source_records": records, "evidence_refs": sorted({e for e in evidence if e})})

    nbr = defaultdict(lambda: defaultdict(list))
    for c in d.comms:
        for x, y in ((c["sender_id"], c["receiver_id"]), (c["receiver_id"], c["sender_id"])):
            nbr[x][y].append(("communication", c["ref"], c["evidence_ref"]))
    for t in d.txns:
        for x, y in ((t["from_entity_id"], t["to_entity_id"]), (t["to_entity_id"], t["from_entity_id"])):
            nbr[x][y].append(("transaction", t["ref"], t["evidence_ref"]))
    for r in d.rels:
        if r["rel_type"] not in ("OWNS", "USES"):
            for x, y in ((r["entity_a"], r["entity_b"]), (r["entity_b"], r["entity_a"])):
                nbr[x][y].append(("relationship", r["ref"], r["evidence_ref"]))
    direct = nbr[a].get(b, [])
    if direct:
        add("DIRECT", "FACT", f"{nm[a]} and {nm[b]} have {len(direct)} directly recorded link(s)",
            [{"type": t, "ref": r} for t, r, _ in direct[:30]], [e for _, _, e in direct])
    for c in sorted(set(nbr[a]) & set(nbr[b]) - {a, b}):
        if d.etype(c) != "PERSON":
            continue
        recs = nbr[a][c] + nbr[b][c]
        add("COMMON_PERSON", "FACT", f"Both are recorded as linked to {nm[c]} (a common intermediary does not establish coordination)",
            [{"type": t, "ref": r} for t, r, _ in recs[:30]], [e for _, _, e in recs])
    la, lb = defaultdict(list), defaultdict(list)
    for o in d.obs:
        if o["subject_entity_id"] == a:
            la[o["location_entity_id"]].append(o)
        elif o["subject_entity_id"] == b:
            lb[o["location_entity_id"]].append(o)
    for loc in sorted(set(la) & set(lb)):
        if d.loc_kind.get(loc) in ("RESIDENCE",):
            continue
        best = None
        for x in la[loc]:
            for y in lb[loc]:
                gap = max(0, (max(x["observed_from"], y["observed_from"]) - min(x["observed_to"], y["observed_to"])).total_seconds() / 60)
                if best is None or gap < best[0]:
                    best = (gap, x, y)
        gap, x, y = best
        cls = "CORRELATED" if gap <= window_minutes else "FACT"
        add("COMMON_LOCATION", cls, f"Both recorded at {nm[loc]} ({'within ' + str(int(gap)) + ' min' if gap else 'overlapping times'}"
            f"{'' if gap <= window_minutes else '; outside the co-presence threshold'})",
            [{"type": "observation", "ref": x["ref"]}, {"type": "observation", "ref": y["ref"]}], [x["evidence_ref"], y["evidence_ref"]])
    va = {r["entity_b"]: r for r in d.rels if r["entity_a"] == a and r["rel_type"] in ("OWNS", "USES")}
    vb = {r["entity_b"]: r for r in d.rels if r["entity_a"] == b and r["rel_type"] in ("OWNS", "USES")}
    for v in sorted(set(va) & set(vb)):
        add("COMMON_VEHICLE", "CORRELATED", f"Both are recorded as owner/user of {nm[v]}",
            [{"type": "relationship", "ref": va[v]["ref"]}, {"type": "relationship", "ref": vb[v]["ref"]}],
            [va[v]["evidence_ref"], vb[v]["evidence_ref"]])
    shared = [e for eid, e in d.evidence.items() if {a, b} <= d.ev_entities.get(eid, set()) and e["validity_status"] == "SUPPORTED"]
    for e in shared:
        add("COMMON_EVIDENCE", "INFERRED", f"Evidence {e['ref']} ({e['evidence_type']}) is linked to both",
            [{"type": "evidence", "ref": e["ref"]}], [e["ref"]])
    ea = {ev["event_id"] for ev in d.incidents if any(p["entity_id"] == a for p in d.event_people[ev["event_id"]])}
    if not out["links"]:
        out["uncertainties"].append("No supported link was found under the current constraints; this does not prove there is no connection.")
    out["uncertainties"].append("Links are recorded or rule-derived relationships; they do not establish intent, cooperation or responsibility.")
    out["excluded_records"] = d.excluded
    return out
