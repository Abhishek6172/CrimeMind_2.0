"""Correlation rule registry (SRS 9.32-9.33). Rules are versioned data; thresholds are recorded with every result."""
import json

RULES = [
    dict(rule_id="FACT_REL_001", version=1, rule_name="Recorded relationship", rule_type="direct",
         description="Explicitly recorded relationship between two entities.", thresholds={},
         input_types=["relationships"], output_classification="FACT"),
    dict(rule_id="FACT_COMM_001", version=1, rule_name="Recorded communication", rule_type="direct",
         description="Communication records between two entities (content is not known).", thresholds={},
         input_types=["communications"], output_classification="FACT"),
    dict(rule_id="FACT_TXN_001", version=1, rule_name="Recorded transaction", rule_type="direct",
         description="Transaction records between two entities (purpose is not known).", thresholds={},
         input_types=["transactions"], output_classification="FACT"),
    dict(rule_id="FACT_VEH_001", version=1, rule_name="Recorded vehicle association", rule_type="direct",
         description="A person is recorded as owner/user of a vehicle.", thresholds={},
         input_types=["relationships"], output_classification="FACT"),
    dict(rule_id="TEMPORAL_SPATIAL_001", version=1, rule_name="Temporal-spatial co-presence", rule_type="temporal_spatial",
         description="Two persons separately recorded at the same or nearby location within a time threshold.",
         thresholds={"time_minutes": 30, "distance_meters": 100, "excluded_location_kinds": ["RESIDENCE", "WORKPLACE"]},
         input_types=["location_observations"], output_classification="CORRELATED"),
    dict(rule_id="INCIDENT_PROXIMITY_001", version=1, rule_name="Incident proximity", rule_type="temporal_spatial",
         description="A person or vehicle recorded near the incident location within a window around the incident time.",
         thresholds={"time_minutes": 60, "distance_meters": 150},
         input_types=["location_observations", "events"], output_classification="CORRELATED"),
    dict(rule_id="SHARED_VEHICLE_001", version=1, rule_name="Shared vehicle association", rule_type="shared_object",
         description="Two persons are recorded as owner/user of the same vehicle.", thresholds={},
         input_types=["relationships"], output_classification="CORRELATED"),
    dict(rule_id="SHARED_EVIDENCE_001", version=1, rule_name="Shared evidence", rule_type="cross_evidence",
         description="One currently-supported evidence record is linked to two persons.", thresholds={},
         input_types=["evidence", "evidence_entities"], output_classification="INFERRED"),
    dict(rule_id="CONTRADICTION_001", version=1, rule_name="Conflicting location records", rule_type="contradiction",
         description="Independent sources place the same person at distant locations during overlapping times.",
         thresholds={"distance_meters": 1000}, input_types=["location_observations"], output_classification="INFERRED"),
    dict(rule_id="MULTI_DOMAIN_001", version=1, rule_name="Multi-domain link", rule_type="cross_domain",
         description="Two persons are linked in several independent domains (communication, transaction, shared vehicle, "
                     "co-presence, shared evidence, joint incident proximity).",
         thresholds={"min_domains": 3}, input_types=["correlations", "communications", "transactions"],
         output_classification="INFERRED"),
]
RULE_BY_ID = {r["rule_id"]: r for r in RULES}


def sync_rules(conn) -> None:
    for r in RULES:
        conn.execute(
            """INSERT INTO correlation_rules(rule_id, version, rule_name, description, rule_type, thresholds,
                                              input_types, output_classification)
               VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
               ON CONFLICT (rule_id, version) DO UPDATE SET rule_name=EXCLUDED.rule_name,
                 description=EXCLUDED.description, rule_type=EXCLUDED.rule_type, thresholds=EXCLUDED.thresholds,
                 input_types=EXCLUDED.input_types, output_classification=EXCLUDED.output_classification""",
            (r["rule_id"], r["version"], r["rule_name"], r["description"], r["rule_type"],
             json.dumps(r["thresholds"]), r["input_types"], r["output_classification"]))
