"""SQL module + investigation question registry (SRS 8.5, 8.9, 8.10, 8.25, 8.35).

The DATABASE registry (tables sql_modules / investigation_questions) is authoritative at runtime;
this file is the version-controlled source that `sync_registry()` loads into it. The frontend
never contains question logic.
"""
import re
from functools import lru_cache
from pathlib import Path

MODULE_DIR = Path(__file__).parent / "sql_modules"
_FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|call|do)\b", re.I)

COMMON = ["start_time", "end_time", "result_limit"]


def _q(qid, text, category, module, variant="default", req=(), opt=(), fixed=None):
    return dict(question_id=qid, display_text=text, category=category, module_id=module, variant=variant,
                required_params=list(req), optional_params=list(opt) + ["include_historical"], fixed_params=fixed or {})


QUESTIONS = [
    _q("Q1", "Which entities communicated with a given entity during a specified period?", "Communication", "M1", "contacts", ["entity_id"], COMMON),
    _q("Q2", "What communications occurred between two entities during a specified period?", "Communication", "M2", "default", ["entity_id_1", "entity_id_2"], COMMON),
    _q("Q3", "Which entities had the highest communication frequency with a given entity?", "Communication", "M1", "frequency", ["entity_id"], COMMON),
    _q("Q4", "Which entity pairs show repeated communication within a period?", "Communication", "M1", "pairs", [], COMMON + ["min_count"]),
    _q("Q5", "Which entities were recorded at a location during a specified period?", "Location", "M3", "present", ["location_id", "start_time", "end_time"], ["result_limit"]),
    _q("Q6", "What is the location history of an entity during a specified period?", "Location", "M5", "history", ["entity_id"], COMMON),
    _q("Q7", "Which locations did an entity visit, and how frequently?", "Location", "M5", "frequency", ["entity_id"], COMMON),
    _q("Q8", "Which entities were recorded at the same locations in overlapping periods?", "Location", "M3", "copresence", [], COMMON + ["location_id", "window_minutes"]),
    _q("Q9", "Which locations were commonly visited by two specified entities?", "Location", "M4", "shared", ["entity_id_1", "entity_id_2"], COMMON),
    _q("Q10", "How frequently did each entity visit the locations in the investigation?", "Location", "M4", "frequency", [], COMMON + ["entity_id", "location_id"]),
    _q("Q11", "What is the chronological timeline of events associated with an entity?", "Timeline", "M6", "default", ["entity_id"], COMMON),
    _q("Q12", "What events occurred around an entity during a specified period?", "Timeline", "M6", "default", ["entity_id", "start_time", "end_time"], ["result_limit"]),
    _q("Q13", "Are there significant gaps in an entity's recorded timeline?", "Timeline", "M7", "default", ["entity_id"], COMMON + ["gap_minutes"]),
    _q("Q14", "What happened immediately before a specified incident?", "Incident", "M8", "before", ["event_id"], ["window_minutes", "result_limit"]),
    _q("Q15", "What happened immediately after a specified incident?", "Incident", "M8", "after", ["event_id"], ["window_minutes", "result_limit"]),
    _q("Q16", "Which entities were active or recorded around the time of the incident?", "Incident", "M8", "around", ["event_id"], ["window_minutes", "result_limit"]),
    _q("Q17", "What direct relationships does an entity have?", "Relationship", "M9", "default", ["entity_id"], ["result_limit"]),
    _q("Q18", "What relationship is recorded between two entities?", "Relationship", "M10", "default", ["entity_id_1", "entity_id_2"], []),
    _q("Q19", "Are two entities connected indirectly through other entities?", "Relationship", "M11", "connected", ["entity_id_1", "entity_id_2"], ["max_hops", "result_limit"]),
    _q("Q20", "What are the shortest known relationship paths between two entities?", "Relationship", "M11", "shortest", ["entity_id_1", "entity_id_2"], ["max_hops", "result_limit"]),
    _q("Q21", "Which entities have the strongest recorded relationships with an entity?", "Relationship", "M12", "default", ["entity_id"], ["minimum_strength", "result_limit"]),
    _q("Q22", "Which vehicles are associated with an entity?", "Vehicle", "M13", "default", ["entity_id"], []),
    _q("Q23", "Which vehicles were recorded near a location during a specified period?", "Vehicle", "M14", "near_location", ["location_id", "start_time", "end_time"], ["result_limit"]),
    _q("Q24", "Which entities were associated with a vehicle during a specified period?", "Vehicle", "M14", "associated_entities", ["vehicle_id"], ["start_time", "end_time"]),
    _q("Q25", "Which vehicles appear repeatedly across locations or periods?", "Vehicle", "M14", "repeated", [], COMMON + ["location_id", "min_count"]),
    _q("Q26", "What financial transactions are associated with an entity?", "Transaction", "M15", "entity", ["entity_id"], COMMON),
    _q("Q27", "What transactions occurred between two entities?", "Transaction", "M15", "between", ["entity_id_1", "entity_id_2"], COMMON),
    _q("Q28", "Which entities sent or received the highest amounts within a period?", "Transaction", "M15", "top_amounts", ["start_time", "end_time"], ["result_limit"]),
    _q("Q29", "What transaction patterns exist in the selected investigation context?", "Transaction", "M15", "patterns", [], COMMON + ["entity_id"]),
    _q("Q30", "Are there repeated or unusual financial relationships among entities?", "Transaction", "M15", "repeated_or_unusual", [], COMMON + ["min_count"]),
    _q("Q31", "What evidence is associated with an entity?", "Evidence", "M16", "entity", ["entity_id"], ["result_limit"]),
    _q("Q32", "What evidence is associated with an event or incident?", "Evidence", "M16", "event", ["event_id"], ["result_limit"]),
    _q("Q33", "Which evidence items connect multiple entities?", "Evidence", "M17", "multi_entity", [], ["result_limit"]),
    _q("Q34", "Which evidence items have the highest reliability scores?", "Evidence", "M18", "reliability", [], ["result_limit"]),
    _q("Q35", "Which entities have the strongest overall evidence associations?", "Evidence", "M18", "evidence_strength", [], ["result_limit"]),
    _q("Q36", "Which entities are supported by multiple independent evidence types?", "Evidence", "M17", "multi_type", [], ["min_count", "result_limit"]),
    _q("Q37", "Which evidence items independently corroborate the same entity?", "Evidence", "M17", "corroborating", [], ["entity_id", "result_limit"]),
    _q("Q38", "Which entities are connected to both a specified entity and a specified location?", "Cross-domain", "M18", "connected_both", ["entity_id", "location_id"], ["start_time", "end_time", "result_limit"]),
    _q("Q39", "Which entities have multiple independent links to a specified entity across domains?", "Cross-domain", "M18", "multi_domain", ["entity_id"], ["min_count", "window_minutes", "result_limit"]),
    _q("Q40", "Which entities have the strongest combined association with the incident?", "Cross-domain", "M18", "overall", ["event_id"], ["window_minutes", "result_limit"]),
]

_HEADER = re.compile(r"^--\s*@(\w+)\s+(.*)$")


def _parse(path: Path) -> dict:
    meta: dict = {"variants": {}}
    cur = None
    buf: list[str] = []
    for line in path.read_text().splitlines():
        m = _HEADER.match(line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if key == "variant":
                if cur:
                    meta["variants"][cur] = "\n".join(buf).strip()
                cur, buf = val, []
            else:
                meta[key] = val
            continue
        if cur is not None:
            buf.append(line)
    if cur:
        meta["variants"][cur] = "\n".join(buf).strip()
    meta["file_name"] = path.name
    return meta


@lru_cache(maxsize=1)
def load_modules() -> dict[str, dict]:
    modules = {}
    for p in sorted(MODULE_DIR.glob("*.sql")):
        meta = _parse(p)
        for name, sql in meta["variants"].items():
            bare = re.sub(r"'[^']*'", "''", re.sub(r"--[^\n]*", "", sql))   # ignore literals and comments
            if ";" in bare or _FORBIDDEN.search(bare):
                raise RuntimeError(f"Module {meta['module']} variant {name} is not a single read-only statement")
        modules[meta["module"]] = meta
    return modules


def sync_registry(conn) -> None:
    """Load modules and questions into the database registry (run by admin tooling, not by the app role)."""
    for m in load_modules().values():
        conn.execute(
            """INSERT INTO sql_modules(module_id, file_name, version, description)
               VALUES (%s,%s,%s,%s)
               ON CONFLICT (module_id) DO UPDATE SET file_name=EXCLUDED.file_name,
                 version=EXCLUDED.version, description=EXCLUDED.description""",
            (m["module"], m["file_name"], m["version"], m["description"]))
    import json
    for q in QUESTIONS:
        conn.execute(
            """INSERT INTO investigation_questions
                 (question_id, display_text, category, module_id, variant, required_params, optional_params, fixed_params)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
               ON CONFLICT (question_id) DO UPDATE SET display_text=EXCLUDED.display_text, category=EXCLUDED.category,
                 module_id=EXCLUDED.module_id, variant=EXCLUDED.variant, required_params=EXCLUDED.required_params,
                 optional_params=EXCLUDED.optional_params, fixed_params=EXCLUDED.fixed_params""",
            (q["question_id"], q["display_text"], q["category"], q["module_id"], q["variant"],
             q["required_params"], q["optional_params"], json.dumps(q["fixed_params"])))
