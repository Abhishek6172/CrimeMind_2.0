"""Dataset Service for Research Platform.
Loads, validates, caches, and prepares CaseView structures from research/datasets/.
"""
import csv
from datetime import datetime
import gzip
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from research.common.casedata import CaseView
from research.phase5 import perturb

log = logging.getLogger("crimemind.research")

ROOT = Path(__file__).resolve().parents[3]
DATASETS_DIR = ROOT / "research" / "datasets"
GROUND_TRUTH_DIR = ROOT / "research" / "ground_truth"


class DatasetService:
    """Manages synthetic research datasets and in-memory CaseView conversions."""

    def __init__(self):
        self._case_view_cache: Dict[str, Dict[str, CaseView]] = {}
        self._ground_truth_cache: Dict[int, Dict[str, Any]] = {}

    def list_available_datasets(self) -> List[Dict[str, Any]]:
        """Returns catalog of all available research dataset seeds."""
        items = []
        if not DATASETS_DIR.exists():
            return items

        for p in sorted(DATASETS_DIR.glob("seed_*")):
            if not p.is_dir():
                continue
            try:
                seed_num = int(p.name.replace("seed_", ""))
                manifest_path = p / "dataset_manifest.json"
                manifest = {}
                if manifest_path.exists():
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                
                items.append({
                    "seed": seed_num,
                    "dataset_id": f"seed_{seed_num}",
                    "cases": manifest.get("cases", ["CASE-2026-001", "CASE-2026-002"]),
                    "content_sha256": manifest.get("summary", {}).get("content_sha256", "UNKNOWN"),
                    "evidence_count": manifest.get("summary", {}).get("evidence_rows", 0),
                    "persons_count": manifest.get("summary", {}).get("persons", 0),
                })
            except Exception as e:
                log.warning(f"Error parsing dataset directory {p.name}: {e}")

        return items

    def get_ground_truth(self, seed: int) -> Dict[str, Any]:
        """Loads ground truth for a given seed, cached in memory."""
        if seed in self._ground_truth_cache:
            return self._ground_truth_cache[seed]

        gt_file = GROUND_TRUTH_DIR / f"seed_{seed}.json"
        if not gt_file.exists():
            raise FileNotFoundError(f"Ground truth file missing for seed {seed}: {gt_file}")

        with open(gt_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            cases = data.get("cases", {})
            self._ground_truth_cache[seed] = cases
            return cases

    def load_seed_cases(
        self,
        seed: int,
        target_cases: Optional[List[str]] = None,
        perturbation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, CaseView]:
        """Loads and constructs CaseView instances for a seed.
        Applies caching and optional in-memory perturbation.
        """
        # If no perturbation, check cache
        cache_key = f"seed_{seed}"
        if not perturbation and cache_key in self._case_view_cache:
            all_views = self._case_view_cache[cache_key]
            if target_cases:
                return {k: v for k, v in all_views.items() if k in target_cases}
            return dict(all_views)

        seed_dir = DATASETS_DIR / f"seed_{seed}"
        if not seed_dir.exists():
            raise FileNotFoundError(f"Dataset directory missing for seed {seed}: {seed_dir}")

        views = self._build_case_views_from_seed_dir(seed, seed_dir)
        self._case_view_cache[cache_key] = views

        selected_views = dict(views)
        if target_cases:
            selected_views = {k: v for k, v in selected_views.items() if k in target_cases}

        # If perturbation requested, apply seeded in-memory transformations
        if perturbation:
            perturbed_views = {}
            p_kind = perturbation.get("type", "none")
            p_level = float(perturbation.get("level", 0.0))
            for case_ref, orig_view in selected_views.items():
                copy_view = perturb._copy(orig_view)
                if p_level > 0.0:
                    rng = perturb.rng_for(seed, case_ref, p_kind, p_level)
                    if hasattr(perturb, p_kind):
                        fn = getattr(perturb, p_kind)
                        fn(copy_view, p_level, rng)
                perturbed_views[case_ref] = copy_view
            return perturbed_views

        return selected_views

    def _build_case_views_from_seed_dir(self, seed: int, seed_dir: Path) -> Dict[str, CaseView]:
        """Parses CSV gzip files and builds exact CaseView instances."""
        def read_gz_csv(filename: str) -> List[Dict[str, Any]]:
            filepath = seed_dir / filename
            if not filepath.exists():
                return []
            with gzip.open(filepath, "rt", encoding="utf-8") as f:
                return list(csv.DictReader(f))

        entities = read_gz_csv("entities.csv.gz")
        events = read_gz_csv("events.csv.gz")
        event_entities = read_gz_csv("event_entities.csv.gz")
        evidence = read_gz_csv("evidence.csv.gz")
        evidence_entities = read_gz_csv("evidence_entities.csv.gz")
        obs = read_gz_csv("location_observations.csv.gz")
        comms = read_gz_csv("communications.csv.gz")
        txns = read_gz_csv("transactions.csv.gz")
        rels = read_gz_csv("relationships.csv.gz")

        # Discover all unique cases
        unique_case_ids = sorted({int(e["case_id"]) for e in entities if e.get("case_id")})
        case_map: Dict[int, str] = {1: "CASE-2026-001", 2: "CASE-2026-002"}

        manifest_path = seed_dir / "dataset_manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                m = json.load(f)
                for idx, c_ref in enumerate(m.get("cases", []), start=1):
                    case_map[idx] = c_ref

        views = {}

        for cid in unique_case_ids:
            case_ref = case_map.get(cid, f"CASE-2026-{cid:03d}")
            ents_in_case = [e for e in entities if int(e["case_id"]) == cid]
            ents_by_id = {int(e["entity_id"]): e["ref"] for e in ents_in_case}
            ents_map = {e["ref"]: e for e in ents_in_case}

            # Find primary incident event
            case_events = [e for e in events if int(e["case_id"]) == cid]
            ev = next((e for e in case_events if e["ref"] == "EVT-001"), None)
            if not ev and case_events:
                ev = case_events[0]
            if not ev:
                continue

            loc_entity = ents_map.get(ents_by_id.get(int(ev["location_entity_id"]))) if ev.get("location_entity_id") else None
            incident_loc_ref = loc_entity["ref"] if loc_entity else "L-GP1"

            # Victims
            victims = [
                ents_by_id[int(r["entity_id"])]
                for r in event_entities
                if int(r["case_id"]) == cid
                and int(r["event_id"]) == int(ev["event_id"])
                and r.get("role") == "VICTIM"
                and int(r["entity_id"]) in ents_by_id
            ]

            persons = {e["ref"]: e["display_name"] for e in ents_in_case if e.get("entity_type") == "PERSON"}
            locations = {}
            for e in ents_in_case:
                if e.get("entity_type") == "LOCATION" and e.get("attributes"):
                    try:
                        attr = json.loads(e["attributes"]) if isinstance(e["attributes"], str) else e["attributes"]
                        if "lat" in attr and "lon" in attr:
                            locations[e["ref"]] = (float(attr["lat"]), float(attr["lon"]))
                    except Exception:
                        pass

            ent_types = {e["ref"]: e.get("entity_type", "UNKNOWN") for e in ents_in_case}

            def parse_dt(ts: Optional[str]) -> Optional[datetime]:
                if not ts:
                    return None
                ts_clean = ts.replace(" ", "T")
                if ts_clean.endswith("+00:00"):
                    ts_clean = ts_clean[:-6] + "Z"
                return datetime.fromisoformat(ts_clean.replace("Z", "+00:00"))

            view = CaseView(
                case_ref=case_ref,
                case_id=cid,
                incident_ref=ev["ref"],
                incident_time=parse_dt(ev["occurred_at"]) or datetime(2026, 8, 14, 22, 14),
                incident_location=incident_loc_ref,
                victims=victims,
                persons=persons,
                locations=locations,
                ent_type=ent_types,
            )

            # Build Evidence lookup
            ev_dict = {}
            for row in evidence:
                if int(row["case_id"]) != cid:
                    continue
                try:
                    prov = json.loads(row["provenance"]) if row.get("provenance") else {}
                except Exception:
                    prov = {}
                rel_score = float(row["reliability_score"]) if row.get("reliability_score") else None
                ev_dict[row["ref"]] = {
                    "type": row.get("evidence_type", "DOCUMENT"),
                    "source": row.get("source", "UNKNOWN"),
                    "origin": prov.get("origin_root", row.get("source", "UNKNOWN")),
                    "reliability": rel_score,
                    "status": row.get("validity_status", "SUPPORTED"),
                    "timestamp": parse_dt(row.get("evidence_timestamp")),
                    "entities": [],
                }

            ev_by_id = {int(r["evidence_id"]): r["ref"] for r in evidence if int(r["case_id"]) == cid}

            for ee in evidence_entities:
                if int(ee["case_id"]) != cid:
                    continue
                ev_ref = ev_by_id.get(int(ee["evidence_id"]))
                if ev_ref and ev_ref in ev_dict:
                    ent_ref = ents_by_id.get(int(ee["entity_id"]))
                    if ent_ref:
                        ev_dict[ev_ref]["entities"].append(ent_ref)

            view.evidence = ev_dict

            # Observations
            for r in obs:
                if int(r["case_id"]) != cid:
                    continue
                ev_id = int(r["evidence_id"]) if r.get("evidence_id") else None
                ev_item = ev_dict.get(ev_by_id.get(ev_id)) if ev_id else None
                v_status = ev_item["status"] if ev_item else "SUPPORTED"
                origin_key = ev_item["origin"] if ev_item else f"RECORD:{r['ref']}"
                subj = ents_by_id.get(int(r["subject_entity_id"]))
                loc_ref = ents_by_id.get(int(r["location_entity_id"]))
                if subj and loc_ref:
                    view.obs.append({
                        "ref": r["ref"],
                        "subject": subj,
                        "location": loc_ref,
                        "t_from": parse_dt(r["observed_from"]),
                        "t_to": parse_dt(r["observed_to"]),
                        "source_kind": r.get("source_kind", "OBS"),
                        "evidence": ev_by_id.get(ev_id),
                        "status": v_status,
                        "origin": origin_key,
                    })

            # Communications
            for c in comms:
                if int(c["case_id"]) != cid:
                    continue
                ev_id = int(c["evidence_id"]) if c.get("evidence_id") else None
                ev_item = ev_dict.get(ev_by_id.get(ev_id)) if ev_id else None
                v_status = ev_item["status"] if ev_item else "SUPPORTED"
                origin_key = ev_item["origin"] if ev_item else f"RECORD:{c['ref']}"
                sender = ents_by_id.get(int(c["sender_id"]))
                receiver = ents_by_id.get(int(c["receiver_id"]))
                if sender and receiver:
                    view.comms.append({
                        "ref": c["ref"],
                        "a": sender,
                        "b": receiver,
                        "t": parse_dt(c["occurred_at"]),
                        "duration": int(c.get("duration_sec") or 0),
                        "type": c.get("comm_type", "CALL"),
                        "evidence": ev_by_id.get(ev_id),
                        "status": v_status,
                        "origin": origin_key,
                    })

            # Transactions
            for t in txns:
                if int(t["case_id"]) != cid:
                    continue
                ev_id = int(t["evidence_id"]) if t.get("evidence_id") else None
                ev_item = ev_dict.get(ev_by_id.get(ev_id)) if ev_id else None
                v_status = ev_item["status"] if ev_item else "SUPPORTED"
                origin_key = ev_item["origin"] if ev_item else f"RECORD:{t['ref']}"
                from_ent = ents_by_id.get(int(t["from_entity_id"]))
                to_ent = ents_by_id.get(int(t["to_entity_id"]))
                if from_ent and to_ent:
                    view.txns.append({
                        "ref": t["ref"],
                        "a": from_ent,
                        "b": to_ent,
                        "t": parse_dt(t["occurred_at"]),
                        "amount": float(t.get("amount") or 0.0),
                        "evidence": ev_by_id.get(ev_id),
                        "status": v_status,
                        "origin": origin_key,
                    })

            # Relationships
            for rl in rels:
                if int(rl["case_id"]) != cid:
                    continue
                ev_id = int(rl["evidence_id"]) if rl.get("evidence_id") else None
                ev_item = ev_dict.get(ev_by_id.get(ev_id)) if ev_id else None
                v_status = ev_item["status"] if ev_item else "SUPPORTED"
                origin_key = ev_item["origin"] if ev_item else f"RECORD:{rl['ref']}"
                ent_a = ents_by_id.get(int(rl["entity_a"]))
                ent_b = ents_by_id.get(int(rl["entity_b"]))
                if ent_a and ent_b:
                    view.rels.append({
                        "ref": rl["ref"],
                        "a": ent_a,
                        "b": ent_b,
                        "type": rl.get("rel_type", "ASSOCIATE"),
                        "strength": float(rl.get("strength") or 0.0),
                        "valid_from": parse_dt(rl.get("valid_from")),
                        "valid_to": parse_dt(rl.get("valid_to")),
                        "evidence": ev_by_id.get(ev_id),
                        "status": v_status,
                        "origin": origin_key,
                    })

            times = [x["t_to"] for x in view.obs if x.get("t_to")] + [x["t"] for x in view.comms if x.get("t")] + [x["t"] for x in view.txns if x.get("t")]
            view.as_of = max(times) if times else view.incident_time
            view.case_meta = {"case_id": cid, "case_ref": case_ref}

            views[case_ref] = view

        return views


dataset_service = DatasetService()
