"""Build the golden question benchmark from the generator's ground truth plus the raw dataset tables.

Independence: expected answers, supporting evidence and source records come from (a) the generator's plan
(research/ground_truth/seed_<n>.json) and (b) direct reads of the exported dataset CSVs. NOTHING is taken from retrieval, the
AI layer, the correlation engine or any ranking output. Deterministic: same seeds -> identical file.

  python -m research.phase6.benchmark.build_benchmark [--seeds 2026-2045]"""
import argparse
import csv
import gzip
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from research.generate_datasets import parse_seeds   # noqa: E402

OUT = Path(__file__).resolve().parent / "golden_questions.jsonl"
CATS = ["entity_identification", "evidence_lookup", "timeline_reconstruction", "relationship_analysis", "contradiction_analysis", "missing_information",
        "investigation_summary", "evidence_lifecycle", "sql_investigation", "multi_hop", "unanswerable"]
TYPE_WORDS = {"GPS": "GPS location", "CCTV": "CCTV", "CDR": "phone call", "TRANSACTION_RECORD": "bank transaction", "ACCESS_LOG": "access-control log"}


def table(seed, name):
    return list(csv.DictReader(gzip.open(ROOT / "research/datasets" / f"seed_{seed}" / f"{name}.csv.gz", "rt")))


def case_questions(seed, case_ref, gt, T):
    case_id = None
    ents = {e["entity_id"]: e for e in T["entities"] if e["case_id"] == str(T["case_ids"][case_ref])}
    cid = str(T["case_ids"][case_ref])
    by_ref = {e["ref"]: e for e in ents.values()}
    ev = {e["evidence_id"]: e for e in T["evidence"] if e["case_id"] == cid}
    ev_by_ref = {e["ref"]: e for e in ev.values()}
    ee = defaultdict(set)
    for r in T["evidence_entities"]:
        if r["case_id"] == cid:
            ee[ents[r["entity_id"]]["ref"]].add(ev[r["evidence_id"]]["ref"])
    name = lambda ref: by_ref[ref]["display_name"]
    rng = random.Random(f"bench-{seed}-{case_ref}")
    victim = gt["incident"]["victim"]
    loc_name = by_ref[gt["incident"]["location"]]["display_name"]
    leads = gt["relevant_leads"]
    qs = []

    def add(cat, q, answerable, expected_answer, rel_ev=(), exp_entities=(), source_records=(), criteria=None, state="initial", extra=None):
        qs.append({"question_id": f"Q-{seed}-{case_ref[-3:]}-{len(qs) + 1:02d}", "dataset_id": f"seed_{seed}", "case_id": case_ref, "category": cat,
                   "question": q, "answerability": answerable, "expected_answer": expected_answer, "supporting_evidence": sorted(set(rel_ev)),
                   "expected_entities": sorted(set(exp_entities)), "expected_source_records": sorted(set(source_records)), "state": state,
                   "evaluation_criteria": criteria or {}, **(extra or {})})

    # 1 entity identification: everyone with recorded scene presence (leads, decoys, bystanders) from the generator plan
    scene = {l["ref"]: l["scene_evidence"] for l in leads if l["scene_evidence"]}
    scene.update({r["ref"]: r["scene_evidence"] for r in gt["red_herrings"] if r["scene_evidence"]})
    scene.update({b["ref"]: [b["evidence"]] for b in gt["near_scene_irrelevant"]})
    if scene:
        add("entity_identification", f"Which people were recorded near {loc_name} around the time of the incident?", "answerable",
            f"People recorded near the scene in the incident window: {', '.join(f'{p} ({name(p)})' for p in sorted(scene))}.",
            [e for v in scene.values() for e in v], scene, [], {"must_mention_entities": sorted(scene)})
    # 2 evidence lookup
    for l in rng.sample(leads, min(2, len(leads))):
        types = sorted({ev_by_ref[e]["evidence_type"] for e in ee[l["ref"]]} & set(TYPE_WORDS))
        if not types:
            continue
        t = rng.choice(types)
        rel = [e for e in ee[l["ref"]] if ev_by_ref[e]["evidence_type"] == t]
        add("evidence_lookup", f"Show the {TYPE_WORDS[t]} records for {name(l['ref'])}.", "answerable", f"{len(rel)} {t} record(s): {', '.join(sorted(rel))}.", rel, [l["ref"]],
            [], {"must_cite_all": True}, extra={"evidence_type": t})
    # 3 timeline
    lead = leads[0]
    add("timeline_reconstruction", f"What was {name(lead['ref'])} recorded doing around the incident?", "answerable",
        f"Records for {lead['ref']} around the incident: {', '.join(lead['supporting_evidence'])}.", lead["supporting_evidence"], [lead["ref"]])
    # 4 relationship (relationships are not in the evidence index: retrieval excluded, answer evaluated on records)
    for l in leads:
        recs = [r["ref"] for r in T["relationships"] if r["case_id"] == cid and {ents[r["entity_a"]]["ref"], ents[r["entity_b"]]["ref"]} == {l["ref"], victim}]
        if recs:
            add("relationship_analysis", f"How is {name(l['ref'])} connected to the victim, {name(victim)}?", "answerable",
                f"A recorded relationship exists between {l['ref']} and {victim} ({', '.join(recs)}).", [], [l["ref"], victim], recs,
                {"retrieval_applicable": False, "note": "relationship records are not in the evidence index"})
            break
    # 5 contradiction
    for r in gt["red_herrings"][:1]:
        add("contradiction_analysis", f"Is there evidence that contradicts {name(r['ref'])} having been near the scene?", "answerable",
            f"Yes: contradicting record(s) {', '.join(r['contradicting_evidence'])} place {r['ref']} elsewhere.", r["contradicting_evidence"], [r["ref"]],
            [], {"must_cite_contradicting": r["contradicting_evidence"]})
    # 6 missing information: person with NO CCTV evidence linked
    nocctv = [p for p in sorted(gt["eligible_entities"]) if not any(ev_by_ref[e]["evidence_type"] == "CCTV" for e in ee[p])]
    if nocctv:
        p = rng.choice(nocctv)
        add("missing_information", f"What CCTV footage is recorded for {name(p)}?", "answerable_negative", f"None: no CCTV evidence is linked to {p}.", [], [],
            [], {"must_state_absence": True})
    # 7 summary
    l = leads[min(1, len(leads) - 1)]
    add("investigation_summary", f"Summarise the recorded evidence concerning {name(l['ref'])}.", "answerable", f"Evidence concerning {l['ref']}: {', '.join(l['supporting_evidence'])}.",
        l["supporting_evidence"], [l["ref"]])
    # 8 lifecycle (evolved state): final status of the changed evidence per the generator plan
    final = {}
    for s in gt["lifecycle"]:
        final[s["evidence_ref"]] = s["expected_status"]
    for e, st in list(sorted(final.items()))[:2]:
        add("evidence_lifecycle", f"What is the current validity status of evidence {e}?", "answerable", f"{e} is currently {st}.", [e], [], [],
            {"expected_status": st}, state="evolved", extra={"expected_status": st})
    # 9 sql-style questions from raw tables
    comm = [c for c in T["communications"] if c["case_id"] == cid and victim in (ents[c["sender_id"]]["ref"], ents[c["receiver_id"]]["ref"])]
    if comm:
        people = {ents[c["sender_id"]]["ref"] if ents[c["receiver_id"]]["ref"] == victim else ents[c["receiver_id"]]["ref"] for c in comm}
        add("sql_investigation", f"Who communicated with the victim, {name(victim)}?", "answerable", f"Communication partners of {victim}: {', '.join(sorted(people))}.",
            [ev[c["evidence_id"]]["ref"] for c in comm if c["evidence_id"] in ev], people, [c["ref"] for c in comm])
    # 10 multi-hop: contacts of people recorded at the scene
    sp = set(scene)
    hop = defaultdict(set)
    for c in T["communications"]:
        if c["case_id"] != cid:
            continue
        a, b = ents[c["sender_id"]]["ref"], ents[c["receiver_id"]]["ref"]
        for me, other in ((a, b), (b, a)):
            if other in sp and me not in sp and me != victim and c["evidence_id"] in ev:
                hop[me].add(ev[c["evidence_id"]]["ref"])
    if hop:
        add("multi_hop", f"Who communicated with people who were recorded near {loc_name} at the incident time?", "answerable",
            f"Contacts of scene-present people: {', '.join(sorted(hop))}.", [e for v in hop.values() for e in v], hop, [],
            {"note": "two hops: scene presence, then communication"})
    # 11 unanswerable
    p = rng.choice(sorted(gt["eligible_entities"]))
    add("unanswerable", f"What did the DNA analysis show about {name(p)}?", "unanswerable", "No DNA analysis exists in the case records; the system should say so.", [], [], [],
        {"must_refuse": True})
    p = rng.choice(sorted(gt["eligible_entities"]))
    add("unanswerable", f"Where was {name(p)} on 1 January 2025?", "unanswerable", "The case records do not cover that date; the system should say so.", [], [], [], {"must_refuse": True})
    return qs


def build(seeds):
    out = []
    for seed in seeds:
        gts = json.load(open(ROOT / "research/ground_truth" / f"seed_{seed}.json"))["cases"]
        T = {n: table(seed, n) for n in ("entities", "evidence", "evidence_entities", "communications", "relationships")}
        cases = {}
        # case ids: entity rows carry case_id; map case_ref by order (case 1 = -001, case 2 = -002)
        ids = sorted({e["case_id"] for e in T["entities"]}, key=int)
        for i, ref in enumerate(sorted(gts)):
            cases[ref] = ids[i]
        T["case_ids"] = cases
        for ref in sorted(gts):
            out += case_questions(seed, ref, gts[ref], T)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="2026-2045")
    a = ap.parse_args()
    qs = build(parse_seeds(a.seeds))
    OUT.write_text("\n".join(json.dumps(q, sort_keys=True) for q in qs) + "\n")
    cnt = defaultdict(int)
    for q in qs:
        cnt[q["category"]] += 1
    man = {"questions": len(qs), "seeds": a.seeds, "by_category": dict(cnt), "sha256": hashlib.sha256(OUT.read_bytes()).hexdigest(),
           "annotation_source": "generator ground truth + raw dataset CSVs (never system output)"}
    (OUT.parent / "benchmark_manifest.json").write_text(json.dumps(man, indent=1))
    print(man)
