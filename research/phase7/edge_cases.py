"""Edge-case mutations applied to a disposable seed database (never the application DB). Each mutation is logged with whether the
database accepted it, because a rejected insert (constraint) is itself a documented behaviour."""
import json


def mutate(conn, case_id: int, d, log: list):
    """d = Data loaded from the unmutated DB. Returns dict of ids useful for targeted parameter sets."""
    ids = {}

    def attempt(name, sql, args=()):
        conn.execute("SAVEPOINT sp")
        try:
            cur = conn.execute(sql, args)
            row = cur.fetchone() if cur.description else None
            conn.execute("RELEASE SAVEPOINT sp")
            log.append(dict(mutation=name, accepted=True))
            return row
        except Exception as e:
            conn.execute("ROLLBACK TO SAVEPOINT sp")
            log.append(dict(mutation=name, accepted=False, reason=f"{type(e).__name__}: {str(e).splitlines()[0][:140]}"))
            return None

    persons = sorted(i for i, e in d.entities.items() if e["type"] == "PERSON")
    locs = sorted(i for i, e in d.entities.items() if e["type"] == "LOCATION")
    c0 = d.comms[0]
    # 1 empty entity (no records at all)
    r = attempt("insert entity with no records", "INSERT INTO entities(case_id,entity_type,ref,display_name) VALUES (%s,'PERSON','P-EDGE-EMPTY','Edge Empty') RETURNING entity_id", (case_id,))
    ids["empty"] = r["entity_id"] if r else None
    r = attempt("insert second person for duplicate/null cases", "INSERT INTO entities(case_id,entity_type,ref,display_name) VALUES (%s,'PERSON','P-EDGE-B','Edge B') RETURNING entity_id", (case_id,))
    ids["edge_b"] = r["entity_id"] if r else None
    a, b = persons[0], ids["edge_b"] or persons[1]
    ids["a"], ids["b"] = a, b
    t0 = c0["at"]
    # 2 communications: exact duplicates (same parties+time), NULL evidence, self-communication, boundary
    for i in range(2):
        attempt(f"duplicate communication #{i}", "INSERT INTO communications(case_id,ref,sender_id,receiver_id,comm_type,occurred_at,duration_sec,evidence_id) VALUES (%s,%s,%s,%s,'CALL',%s,10,NULL)",
                (case_id, f"COMM-EDGE-D{i}", a, b, t0))
    attempt("communication with NULL evidence and NULL duration", "INSERT INTO communications(case_id,ref,sender_id,receiver_id,comm_type,occurred_at,duration_sec,evidence_id) VALUES (%s,'COMM-EDGE-N',%s,%s,'SMS',%s,NULL,NULL)", (case_id, b, a, t0))
    attempt("self-communication", "INSERT INTO communications(case_id,ref,sender_id,receiver_id,comm_type,occurred_at,duration_sec,evidence_id) VALUES (%s,'COMM-EDGE-S',%s,%s,'SMS',%s,1,NULL)", (case_id, a, a, t0))
    # 3 observations: zero-length, identical duplicates, observed_to NULL
    L = locs[0]
    for i in range(2):
        attempt(f"duplicate zero-length observation #{i}", "INSERT INTO location_observations(case_id,ref,subject_entity_id,location_entity_id,observed_from,observed_to,source_kind,source,evidence_id) VALUES (%s,%s,%s,%s,%s,%s,'CCTV','CAM-EDGE',NULL)",
                (case_id, f"OBS-EDGE-Z{i}", a, L, t0, t0))
    attempt("observation with NULL observed_to", "INSERT INTO location_observations(case_id,ref,subject_entity_id,location_entity_id,observed_from,observed_to,source_kind,source,evidence_id) VALUES (%s,'OBS-EDGE-NULLTO',%s,%s,%s,NULL,'CCTV','CAM-EDGE',NULL)", (case_id, b, L, t0))
    attempt("observation ending before it starts", "INSERT INTO location_observations(case_id,ref,subject_entity_id,location_entity_id,observed_from,observed_to,source_kind,source,evidence_id) VALUES (%s,'OBS-EDGE-NEG',%s,%s,%s,%s,'CCTV','CAM-EDGE',NULL)",
            (case_id, b, L, t0, t0.replace(year=t0.year - 1)))
    # 4 transactions: zero amount, huge outlier, repeated pair
    for i, amt in enumerate(("0.00", "99999999.00", "10.00", "10.00", "10.00")):
        attempt(f"transaction amount {amt}", "INSERT INTO transactions(case_id,ref,from_entity_id,to_entity_id,amount,currency,txn_type,occurred_at,location_entity_id,evidence_id) VALUES (%s,%s,%s,%s,%s,'INR','TRANSFER',%s,NULL,NULL)",
                (case_id, f"TXN-EDGE-{i}", a, b, amt, t0))
    # 5 relationships: NULL strength, contradictory duplicate pair, self relationship (must be rejected)
    attempt("relationship with NULL strength", "INSERT INTO relationships(case_id,ref,entity_a,entity_b,rel_type,strength) VALUES (%s,'REL-EDGE-N',%s,%s,'FRIEND',NULL)", (case_id, a, b))
    attempt("contradictory relationship (same pair, other type)", "INSERT INTO relationships(case_id,ref,entity_a,entity_b,rel_type,strength) VALUES (%s,'REL-EDGE-C',%s,%s,'EMPLOYER',0.9)", (case_id, b, a))
    attempt("self relationship", "INSERT INTO relationships(case_id,ref,entity_a,entity_b,rel_type,strength) VALUES (%s,'REL-EDGE-X',%s,%s,'FRIEND',0.5)", (case_id, a, a))
    attempt("relationship strength out of range", "INSERT INTO relationships(case_id,ref,entity_a,entity_b,rel_type,strength) VALUES (%s,'REL-EDGE-R',%s,%s,'FRIEND',1.5)", (case_id, a, b))
    # 5b vehicle with ownership (current + historical) and repeated observations
    r = attempt("insert vehicle", "INSERT INTO entities(case_id,entity_type,ref,display_name,attributes) VALUES (%s,'VEHICLE','V-EDGE','Edge Vehicle','{\"plate\": \"EDGE-1\"}') RETURNING entity_id", (case_id,))
    ids["veh"] = r["entity_id"] if r else None
    if ids["veh"]:
        attempt("vehicle OWNS (open-ended)", "INSERT INTO relationships(case_id,ref,entity_a,entity_b,rel_type,strength,valid_from,valid_to) VALUES (%s,'REL-EDGE-V1',%s,%s,'OWNS',0.8,%s,NULL)", (case_id, a, ids["veh"], t0))
        attempt("vehicle USES (ended in the past)", "INSERT INTO relationships(case_id,ref,entity_a,entity_b,rel_type,strength,valid_from,valid_to) VALUES (%s,'REL-EDGE-V2',%s,%s,'USES',0.4,%s,%s)", (case_id, b, ids["veh"], t0.replace(year=t0.year - 2), t0.replace(year=t0.year - 1)))
        for i in range(3):
            attempt(f"vehicle observation #{i}", "INSERT INTO location_observations(case_id,ref,subject_entity_id,location_entity_id,observed_from,observed_to,source_kind,source,evidence_id) VALUES (%s,%s,%s,%s,%s,%s,'ANPR','ANPR-EDGE',NULL)",
                    (case_id, f"OBS-EDGE-V{i}", ids["veh"], L, t0 + __import__('datetime').timedelta(minutes=i), t0 + __import__('datetime').timedelta(minutes=i + 1)))
    # 6 contradictory validity states: spread statuses over evidence that backs records
    backed = sorted({c["eid"] for c in d.comms if c["eid"]} | {o["eid"] for o in d.obs if o["eid"]} | {r["eid"] for r in d.rels if r["eid"]} | {t["eid"] for t in d.txns if t["eid"]})
    plan = [("CHALLENGED", "DOCUMENTED_CONTRADICTION", "CONTRADICTED_BY_STRONGER_SOURCE"), ("INVALIDATED", "CONFIRMED_INVALIDITY", "DEVICE_FAULT"), ("SUPERSEDED", "REPLACEMENT_RECORD", "CORRECTED_RECORD")]
    for i, eid in enumerate(backed[:: max(1, len(backed) // 30)][:30]):
        st, tr, rs = plan[i % 3]
        trig = next(x for x in reversed(backed) if x != eid)
        attempt(f"validity {st}", "SELECT change_validity(%s,%s,%s::validity_status,%s::validity_trigger,%s::validity_reason,'edge test',%s,'admin') AS id", (case_id, eid, st, tr, rs, trig))
    conn.commit()
    return ids
