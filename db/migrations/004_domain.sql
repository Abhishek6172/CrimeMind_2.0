-- =====================================================================
-- CrimeMind — 004_domain.sql
-- Investigation record tables (SRS 5.5-5.8, 6.7-6.11, 8.x inputs) plus
-- registries and integrity triggers.
--
-- Persons, vehicles, locations, accounts are rows of `entities`.
-- Source-backed records (communications, transactions, observations,
-- relationships) optionally point at an `evidence` row; that row's
-- validity_status decides whether the record counts as *current* support
-- (SRS 8.37, 9.40).
-- =====================================================================

INSERT INTO entity_types(entity_type, description) VALUES
  ('PERSON','An individual'),
  ('VEHICLE','A vehicle'),
  ('LOCATION','A physical place (attributes carry lat/lon)'),
  ('ACCOUNT','A financial account'),
  ('DEVICE','A phone or other device'),
  ('ORGANIZATION','A company or institution');

INSERT INTO event_types(event_type, description) VALUES
  ('INCIDENT','The incident under investigation'),
  ('MOVEMENT','Person or vehicle movement'),
  ('MEETING','A meeting'),
  ('PURCHASE','A purchase'),
  ('TRANSACTION','A financial transaction'),
  ('COMMUNICATION','A communication'),
  ('ACCESS','Building or system access'),
  ('CCTV_OBSERVATION','A camera observation'),
  ('EVIDENCE_COLLECTION','Evidence collected');

-- Reliability weights are MANUALLY ASSIGNED heuristics, not probabilities (SRS FR-024).
INSERT INTO evidence_types(evidence_type, description, reliability_weight) VALUES
  ('DNA','Forensic DNA result',1.00),
  ('FINGERPRINT','Fingerprint match',0.90),
  ('TRANSACTION_RECORD','Bank / payment record',0.90),
  ('CDR','Call / message detail record',0.85),
  ('DEVICE_DIAGNOSTIC','Device diagnostic or fault report',0.85),
  ('ACCESS_LOG','Building / card access log',0.80),
  ('GPS','GPS location trace',0.75),
  ('CCTV','Camera observation',0.70),
  ('AUDIO','Audio observation',0.60),
  ('WITNESS_STATEMENT','Witness statement',0.60),
  ('DOCUMENT','Other document',0.50);

-- ---------- event participants ----------
CREATE TABLE event_entities (
  case_id   bigint NOT NULL,
  event_id  bigint NOT NULL,
  entity_id bigint NOT NULL,
  role      text   NOT NULL DEFAULT 'PARTICIPANT',
  PRIMARY KEY (event_id, entity_id),
  FOREIGN KEY (case_id, event_id)  REFERENCES events(case_id, event_id),
  FOREIGN KEY (case_id, entity_id) REFERENCES entities(case_id, entity_id)
);

-- ---------- directly recorded relationships (FACT) ----------
CREATE TABLE relationships (
  rel_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id     bigint NOT NULL REFERENCES cases(case_id),
  ref         text   NOT NULL,
  entity_a    bigint NOT NULL,
  entity_b    bigint NOT NULL,
  rel_type    text   NOT NULL CHECK (rel_type IN
                ('FAMILY','FRIEND','COLLEAGUE','EMPLOYER','OWNS','USES','ASSOCIATE','ACCOUNT_OF')),
  strength    numeric(3,2) CHECK (strength BETWEEN 0 AND 1),   -- approved heuristic, not a probability
  valid_from  timestamptz,
  valid_to    timestamptz,
  evidence_id bigint,
  UNIQUE (case_id, ref),
  CHECK (entity_a <> entity_b),
  FOREIGN KEY (case_id, entity_a)    REFERENCES entities(case_id, entity_id),
  FOREIGN KEY (case_id, entity_b)    REFERENCES entities(case_id, entity_id),
  FOREIGN KEY (case_id, evidence_id) REFERENCES evidence(case_id, evidence_id)
);
CREATE INDEX idx_rel_a ON relationships(case_id, entity_a);
CREATE INDEX idx_rel_b ON relationships(case_id, entity_b);

-- ---------- communications ----------
CREATE TABLE communications (
  comm_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id      bigint NOT NULL REFERENCES cases(case_id),
  ref          text   NOT NULL,
  sender_id    bigint NOT NULL,
  receiver_id  bigint NOT NULL,
  comm_type    text   NOT NULL CHECK (comm_type IN ('CALL','SMS','EMAIL','CHAT')),
  occurred_at  timestamptz NOT NULL,
  duration_sec integer CHECK (duration_sec IS NULL OR duration_sec >= 0),
  evidence_id  bigint,
  UNIQUE (case_id, ref),
  CHECK (sender_id <> receiver_id),
  FOREIGN KEY (case_id, sender_id)   REFERENCES entities(case_id, entity_id),
  FOREIGN KEY (case_id, receiver_id) REFERENCES entities(case_id, entity_id),
  FOREIGN KEY (case_id, evidence_id) REFERENCES evidence(case_id, evidence_id)
);
CREATE INDEX idx_comm_sender   ON communications(case_id, sender_id, occurred_at);
CREATE INDEX idx_comm_receiver ON communications(case_id, receiver_id, occurred_at);

-- ---------- transactions ----------
CREATE TABLE transactions (
  txn_id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id            bigint NOT NULL REFERENCES cases(case_id),
  ref                text   NOT NULL,
  from_entity_id     bigint NOT NULL,
  to_entity_id       bigint NOT NULL,
  amount             numeric(14,2) NOT NULL CHECK (amount > 0),
  currency           text   NOT NULL DEFAULT 'INR',
  txn_type           text   NOT NULL CHECK (txn_type IN ('TRANSFER','PAYMENT','WITHDRAWAL','DEPOSIT','PURCHASE')),
  occurred_at        timestamptz NOT NULL,
  location_entity_id bigint,
  evidence_id        bigint,
  UNIQUE (case_id, ref),
  CHECK (from_entity_id <> to_entity_id),
  FOREIGN KEY (case_id, from_entity_id)    REFERENCES entities(case_id, entity_id),
  FOREIGN KEY (case_id, to_entity_id)      REFERENCES entities(case_id, entity_id),
  FOREIGN KEY (case_id, location_entity_id) REFERENCES entities(case_id, entity_id),
  FOREIGN KEY (case_id, evidence_id)       REFERENCES evidence(case_id, evidence_id)
);
CREATE INDEX idx_txn_from ON transactions(case_id, from_entity_id, occurred_at);
CREATE INDEX idx_txn_to   ON transactions(case_id, to_entity_id, occurred_at);

-- ---------- location / vehicle observations (GPS, CCTV, access logs) ----------
CREATE TABLE location_observations (
  obs_id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id            bigint NOT NULL REFERENCES cases(case_id),
  ref                text   NOT NULL,
  subject_entity_id  bigint NOT NULL,      -- a PERSON or VEHICLE
  location_entity_id bigint NOT NULL,      -- a LOCATION
  observed_from      timestamptz NOT NULL,
  observed_to        timestamptz NOT NULL,
  source_kind        text   NOT NULL CHECK (source_kind IN ('GPS','CCTV','ACCESS_LOG','WITNESS','OTHER')),
  source             text   NOT NULL,      -- e.g. GPS-17, CAM-014
  evidence_id        bigint,
  UNIQUE (case_id, ref),
  CHECK (observed_to >= observed_from),
  FOREIGN KEY (case_id, subject_entity_id)  REFERENCES entities(case_id, entity_id),
  FOREIGN KEY (case_id, location_entity_id) REFERENCES entities(case_id, entity_id),
  FOREIGN KEY (case_id, evidence_id)        REFERENCES evidence(case_id, evidence_id)
);
CREATE INDEX idx_obs_subject  ON location_observations(case_id, subject_entity_id, observed_from);
CREATE INDEX idx_obs_location ON location_observations(case_id, location_entity_id, observed_from);

-- ---------- integrity layer (type checks the FK cannot express) ----------
CREATE OR REPLACE FUNCTION entity_type_of(p_case bigint, p_entity bigint) RETURNS text
LANGUAGE sql STABLE AS $$
  SELECT entity_type FROM entities WHERE case_id = p_case AND entity_id = p_entity
$$;

CREATE OR REPLACE FUNCTION validate_domain_record() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME = 'communications' THEN
    IF entity_type_of(NEW.case_id, NEW.sender_id) <> 'PERSON'
       OR entity_type_of(NEW.case_id, NEW.receiver_id) <> 'PERSON' THEN
      RAISE EXCEPTION 'Communication participants must be PERSON entities';
    END IF;
  ELSIF TG_TABLE_NAME = 'transactions' THEN
    IF entity_type_of(NEW.case_id, NEW.from_entity_id) NOT IN ('PERSON','ACCOUNT','ORGANIZATION')
       OR entity_type_of(NEW.case_id, NEW.to_entity_id) NOT IN ('PERSON','ACCOUNT','ORGANIZATION') THEN
      RAISE EXCEPTION 'Transaction parties must be PERSON, ACCOUNT or ORGANIZATION entities';
    END IF;
    IF NEW.location_entity_id IS NOT NULL
       AND entity_type_of(NEW.case_id, NEW.location_entity_id) <> 'LOCATION' THEN
      RAISE EXCEPTION 'Transaction location must be a LOCATION entity';
    END IF;
  ELSIF TG_TABLE_NAME = 'location_observations' THEN
    IF entity_type_of(NEW.case_id, NEW.location_entity_id) <> 'LOCATION' THEN
      RAISE EXCEPTION 'Observation location must be a LOCATION entity';
    END IF;
    IF entity_type_of(NEW.case_id, NEW.subject_entity_id) NOT IN ('PERSON','VEHICLE') THEN
      RAISE EXCEPTION 'Observation subject must be a PERSON or VEHICLE entity';
    END IF;
  ELSIF TG_TABLE_NAME = 'relationships' THEN
    IF NEW.rel_type IN ('OWNS','USES') THEN
      IF entity_type_of(NEW.case_id, NEW.entity_a) <> 'PERSON'
         OR entity_type_of(NEW.case_id, NEW.entity_b) <> 'VEHICLE' THEN
        RAISE EXCEPTION '% requires entity_a PERSON and entity_b VEHICLE', NEW.rel_type;
      END IF;
    ELSIF entity_type_of(NEW.case_id, NEW.entity_a) NOT IN ('PERSON','ORGANIZATION')
       OR entity_type_of(NEW.case_id, NEW.entity_b) NOT IN ('PERSON','ORGANIZATION','ACCOUNT') THEN
      RAISE EXCEPTION 'Relationship % has invalid entity types', NEW.rel_type;
    END IF;
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER trg_validate_comm BEFORE INSERT OR UPDATE ON communications
  FOR EACH ROW EXECUTE FUNCTION validate_domain_record();
CREATE TRIGGER trg_validate_txn  BEFORE INSERT OR UPDATE ON transactions
  FOR EACH ROW EXECUTE FUNCTION validate_domain_record();
CREATE TRIGGER trg_validate_obs  BEFORE INSERT OR UPDATE ON location_observations
  FOR EACH ROW EXECUTE FUNCTION validate_domain_record();
CREATE TRIGGER trg_validate_rel  BEFORE INSERT OR UPDATE ON relationships
  FOR EACH ROW EXECUTE FUNCTION validate_domain_record();

-- Source records are history too: never deleted.
CREATE TRIGGER trg_comm_no_delete BEFORE DELETE ON communications
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_txn_no_delete  BEFORE DELETE ON transactions
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_obs_no_delete  BEFORE DELETE ON location_observations
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- ---------- current-belief views (SRS 8.37 / 8.38) ----------
-- validity_status is the status of the backing evidence; a record with no
-- backing evidence row is reported as SUPPORTED ("recorded, unchallenged").
-- origin_key identifies the independent source behind the record (SRS 9.22).
CREATE OR REPLACE VIEW v_comms AS
SELECT c.*, e.ref AS evidence_ref,
       coalesce(e.validity_status, 'SUPPORTED') AS validity_status,
       coalesce(e.provenance->>'origin_root', e.source, 'RECORD:' || c.ref) AS origin_key
FROM communications c
LEFT JOIN evidence e ON e.case_id = c.case_id AND e.evidence_id = c.evidence_id;

CREATE OR REPLACE VIEW v_txns AS
SELECT t.*, e.ref AS evidence_ref,
       coalesce(e.validity_status, 'SUPPORTED') AS validity_status,
       coalesce(e.provenance->>'origin_root', e.source, 'RECORD:' || t.ref) AS origin_key
FROM transactions t
LEFT JOIN evidence e ON e.case_id = t.case_id AND e.evidence_id = t.evidence_id;

CREATE OR REPLACE VIEW v_obs AS
SELECT o.*, e.ref AS evidence_ref,
       coalesce(e.validity_status, 'SUPPORTED') AS validity_status,
       coalesce(e.provenance->>'origin_root', e.source, 'RECORD:' || o.ref) AS origin_key
FROM location_observations o
LEFT JOIN evidence e ON e.case_id = o.case_id AND e.evidence_id = o.evidence_id;

CREATE OR REPLACE VIEW v_rels AS
SELECT r.*, e.ref AS evidence_ref,
       coalesce(e.validity_status, 'SUPPORTED') AS validity_status,
       coalesce(e.provenance->>'origin_root', e.source, 'RECORD:' || r.ref) AS origin_key
FROM relationships r
LEFT JOIN evidence e ON e.case_id = r.case_id AND e.evidence_id = r.evidence_id;

-- Great-circle distance in metres between two LOCATION entities (PostGIS-free baseline).
CREATE OR REPLACE FUNCTION location_distance_m(p_case bigint, p_a bigint, p_b bigint) RETURNS double precision
LANGUAGE sql STABLE AS $$
  SELECT 2 * 6371000 * asin(sqrt(
           power(sin(radians((b.lat - a.lat) / 2)), 2) +
           cos(radians(a.lat)) * cos(radians(b.lat)) * power(sin(radians((b.lon - a.lon) / 2)), 2)))
  FROM (SELECT (attributes->>'lat')::float AS lat, (attributes->>'lon')::float AS lon
        FROM entities WHERE case_id = p_case AND entity_id = p_a) a,
       (SELECT (attributes->>'lat')::float AS lat, (attributes->>'lon')::float AS lon
        FROM entities WHERE case_id = p_case AND entity_id = p_b) b
$$;

-- audit hooks for the new tables
CREATE TRIGGER trg_audit_rels  AFTER INSERT OR UPDATE ON relationships
  FOR EACH ROW EXECUTE FUNCTION audit_row_change('rel_id');
CREATE TRIGGER trg_audit_comms AFTER INSERT OR UPDATE ON communications
  FOR EACH ROW EXECUTE FUNCTION audit_row_change('comm_id');
CREATE TRIGGER trg_audit_txns  AFTER INSERT OR UPDATE ON transactions
  FOR EACH ROW EXECUTE FUNCTION audit_row_change('txn_id');
