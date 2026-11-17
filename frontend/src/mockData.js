// Fallback demo dataset for standalone deployment (e.g. Vercel) when the local Python backend is not connected.
export function getMockResponse(path, method = "GET", body = null) {
  const p = path.split("?")[0].replace(/\/$/, "");

  // Auth
  if (p === "/auth/login") {
    const username = (body && body.username) || "admin";
    const role = username.startsWith("sup") ? "SUPERVISOR" : username.startsWith("inv") ? "INVESTIGATOR" : "ADMINISTRATOR";
    return {
      access_token: "crimemind-standalone-session-token",
      token_type: "bearer",
      user: { username, role }
    };
  }

  if (p === "/auth/me") {
    return { username: "admin", role: "ADMINISTRATOR" };
  }

  if (p === "/users") {
    return {
      users: [
        { user_id: 1, username: "admin", role: "ADMINISTRATOR" },
        { user_id: 2, username: "inv.asha", role: "INVESTIGATOR" },
        { user_id: 3, username: "sup.rao", role: "SUPERVISOR" }
      ]
    };
  }

  // Cases List
  if (p === "/cases") {
    return {
      cases: [
        {
          case_id: 1,
          case_ref: "CASE-2026-001",
          title: "Homicide at Green Park Gazebo",
          status: "ACTIVE",
          incident_time: "2026-08-14T21:40:00Z",
          created_at: "2026-08-14T21:45:00Z"
        },
        {
          case_id: 2,
          case_ref: "CASE-2026-002",
          title: "Burglary at Riverside Apartments",
          status: "ACTIVE",
          incident_time: "2026-08-15T09:15:00Z",
          created_at: "2026-08-15T09:20:00Z"
        }
      ]
    };
  }

  // Case Overview / Dashboard: /cases/:ref
  if (p.match(/^\/cases\/[^/]+$/)) {
    const ref = p.split("/")[2];
    return {
      case: {
        case_id: ref === "CASE-2026-002" ? 2 : 1,
        case_ref: ref,
        title: ref === "CASE-2026-002" ? "Burglary at Riverside Apartments" : "Homicide at Green Park Gazebo",
        status: "ACTIVE"
      },
      counts: {
        evidence: 386,
        entities: 188,
        people: 42,
        vehicles: 16,
        locations: 18,
        hypotheses: 4,
        communications: 1211,
        transactions: 249,
        observations: 1304
      },
      evidence_by_validity: {
        SUPPORTED: 340,
        CHALLENGED: 28,
        INVALIDATED: 12,
        SUPERSEDED: 6
      },
      findings_by_status: {
        VERIFIED: 85,
        UNCONFIRMED: 27
      },
      incidents: [
        {
          ref: "INC-01",
          description: "Homicide discovered near central Green Park gazebo",
          occurred_at: "2026-08-14T21:40:00Z",
          location_name: "Green Park Gazebo",
          location_ref: "L-001"
        }
      ],
      investigation_state: {
        open_impacts: 0,
        hypotheses_needing_review: 0,
        open_hypotheses: 2,
        queries_run: 40,
        reviews: 3
      },
      notice: "Standalone preview mode. Full decision engine active."
    };
  }

  // Entities
  if (p.includes("/entities")) {
    return {
      case_reference: "CASE-2026-001",
      entities: [
        { entity_id: 1, ref: "P-001", entity_type: "PERSON", display_name: "Meera Sen", attributes: { role: "Victim", age: 29, occupation: "Biochemist" } },
        { entity_id: 2, ref: "P-002", entity_type: "PERSON", display_name: "Karan Bhatt", attributes: { role: "Suspect", age: 31, occupation: "Software Engineer" } },
        { entity_id: 3, ref: "P-003", entity_type: "PERSON", display_name: "Ananya Sharma", attributes: { role: "Witness", age: 27, occupation: "Designer" } },
        { entity_id: 4, ref: "P-004", entity_type: "PERSON", display_name: "Rohit Sethi", attributes: { role: "Associate", age: 34, occupation: "Manager" } },
        { entity_id: 5, ref: "L-001", entity_type: "LOCATION", display_name: "Green Park Gazebo", attributes: { kind: "CRIME_SCENE", lat: 28.558, lon: 77.202 } },
        { entity_id: 6, ref: "L-002", entity_type: "LOCATION", display_name: "Orbit Tech Park", attributes: { kind: "WORKPLACE", lat: 28.562, lon: 77.210 } },
        { entity_id: 7, ref: "V-001", entity_type: "VEHICLE", display_name: "Dark Blue Sedan (DL-03-AB-4412)", attributes: { make: "Honda", model: "City" } }
      ]
    };
  }

  // Evidence
  if (p.includes("/evidence") && !p.includes("/evidence-search")) {
    return {
      case_reference: "CASE-2026-001",
      evidence: [
        {
          ref: "E-001",
          evidence_type: "CCTV",
          source: "CAM-05: Green Park West Perimeter",
          description: "Footage captures person matching Karan Bhatt's profile near west walkway at 21:14.",
          evidence_timestamp: "2026-08-14T21:14:00Z",
          validity_status: "SUPPORTED",
          reliability_score: 0.95,
          provenance: "SHA256: 4f1a... Verified CCTV Controller"
        },
        {
          ref: "E-002",
          evidence_type: "ACCESS_LOG",
          source: "Orbit Tech Park Badge System",
          description: "Badge scan record: exit logged at 20:45.",
          evidence_timestamp: "2026-08-14T20:45:00Z",
          validity_status: "SUPPORTED",
          reliability_score: 0.92,
          provenance: "Badge Server R2 Audit Dump"
        },
        {
          ref: "E-003",
          evidence_type: "WITNESS_STATEMENT",
          source: "Ananya Sharma (Witness)",
          description: "Witness states seeing two individuals arguing near gazebo between 21:20 and 21:30.",
          evidence_timestamp: "2026-08-14T21:25:00Z",
          validity_status: "SUPPORTED",
          reliability_score: 0.80,
          provenance: "Recorded by Det. Roy"
        },
        {
          ref: "E-004",
          evidence_type: "DEVICE_DIAGNOSTIC",
          source: "GPS-17 Telemetry Logger",
          description: "Diagnostic report: unit GPS-17 logged clock drift on 14 Aug.",
          evidence_timestamp: "2026-08-14T22:00:00Z",
          validity_status: "CHALLENGED",
          reliability_score: 0.60,
          provenance: "Manufacturer Diagnostic Telemetry"
        }
      ]
    };
  }

  // Evidence Search
  if (p.includes("/evidence-search")) {
    return {
      case_reference: "CASE-2026-001",
      query: "CCTV",
      method: "LEXICAL_BM25",
      hits: [
        {
          ref: "E-001",
          evidence_type: "CCTV",
          source: "CAM-05",
          description: "Footage captures person matching Karan Bhatt's profile near west walkway at 21:14.",
          score: 0.94
        }
      ]
    };
  }

  // Correlations
  if (p.includes("/correlations")) {
    return {
      correlations: [
        {
          correlation_id: 1,
          rule_id: "R-SPATIO-TEMPORAL-COINCIDENCE",
          result_type: "CORRELATED",
          summary: "Karan Bhatt and victim Meera Sen co-located within 150m at 21:15–21:30.",
          confidence: 0.91,
          evidence_refs: ["E-001", "E-003"]
        },
        {
          correlation_id: 2,
          rule_id: "R-COMMUNICATION-BURST-PRE-INCIDENT",
          result_type: "FACT",
          summary: "Three unanswered calls placed to victim immediately prior to incident.",
          confidence: 0.98,
          evidence_refs: ["E-002"]
        }
      ]
    };
  }

  // Relationships / Graph
  if (p.includes("/relationship") || p.includes("/graph")) {
    return {
      nodes: [
        { id: "P-001", label: "Meera Sen (Victim)", type: "PERSON", role: "VICTIM" },
        { id: "P-002", label: "Karan Bhatt", type: "PERSON", role: "SUSPECT" },
        { id: "P-003", label: "Ananya Sharma", type: "PERSON", role: "WITNESS" },
        { id: "L-001", label: "Green Park Gazebo", type: "LOCATION" },
        { id: "V-001", label: "Sedan DL-03", type: "VEHICLE" }
      ],
      edges: [
        { id: "e1", source: "P-002", target: "P-001", label: "Colleague / Frequent Comms", weight: 0.8 },
        { id: "e2", source: "P-002", target: "L-001", label: "Sighted Nearby", weight: 0.9 },
        { id: "e3", source: "P-003", target: "L-001", label: "Walkway Witness", weight: 0.7 },
        { id: "e4", source: "P-002", target: "V-001", label: "Owner / Driver", weight: 1.0 }
      ]
    };
  }

  // Hypotheses
  if (p.includes("/hypotheses")) {
    return {
      hypotheses: [
        {
          hypothesis_id: "H-01",
          statement: "Karan Bhatt met victim Meera Sen at Green Park Gazebo to dispute project ownership.",
          status: "OPEN",
          probability_weight: 0.78,
          needs_review: false
        },
        {
          hypothesis_id: "H-02",
          statement: "An unidentified third party entered through the north-east service road.",
          status: "OPEN",
          probability_weight: 0.32,
          needs_review: false
        }
      ]
    };
  }

  // Findings
  if (p.includes("/findings")) {
    return {
      findings: [
        {
          finding_key: "F-001",
          statement: "Karan Bhatt was within the Green Park mobile tower sector at 21:22.",
          classification: "RECORDED FACT",
          status: "CURRENT",
          confidence: 0.99
        },
        {
          finding_key: "F-002",
          statement: "Vehicle DL-03-AB-4412 passed Outer Ring Road ANPR toll camera at 20:58.",
          classification: "RECORDED FACT",
          status: "CURRENT",
          confidence: 0.96
        }
      ]
    };
  }

  // Notes
  if (p.includes("/notes")) {
    return {
      notes: [
        {
          note_id: 1,
          author: "inv.asha",
          title: "Timeline Clarification",
          body: "Request forensic clock audit on CAM-05 controller unit to verify 21:14 timestamp accuracy.",
          bookmarked: true,
          tag: "TIMELINE",
          created_at: "2026-08-15T09:30:00Z"
        }
      ]
    };
  }

  // Insights / ML / Spatial
  if (p.includes("/insights/map")) {
    return {
      points: [
        { lat: 28.558, lon: 77.202, label: "Green Park Gazebo", kind: "CRIME_SCENE" },
        { lat: 28.562, lon: 77.210, label: "Orbit Tech Park", kind: "WORKPLACE" }
      ],
      trails: []
    };
  }

  if (p.includes("/insights")) {
    return {
      results: [],
      jumps: [],
      anomalies: [],
      network: { density: 0.42, clustering: 0.65 },
      meetings: []
    };
  }

  if (p.includes("/ml/")) {
    return {
      status: "COMPLETED",
      score: 0.89,
      analysis: "Machine learning module executed successfully (standalone preview mode).",
      anomalies: [],
      predictions: []
    };
  }

  if (p.includes("/nlp")) {
    return {
      statements: [
        {
          id: 1,
          speaker: "Karan Bhatt",
          credibility_index: 0.62,
          deception_markers: ["EQUIVOCATION", "TEMPORAL_RIGIDITY"],
          status: "ANALYZED"
        }
      ]
    };
  }

  if (p.includes("/cctv")) {
    return [];
  }

  if (p.includes("/questions")) {
    return {
      questions: [
        { id: "Q01", title: "Who was in contact with the victim within 24 hours?", category: "Communications" },
        { id: "Q02", title: "Which vehicles were observed near the location?", category: "Vehicles" }
      ]
    };
  }

  if (p.includes("/reports")) {
    return { reports: [] };
  }

  if (p.includes("/audit") || p.includes("/impacts")) {
    return [];
  }

  // Default fallback for any unspecified endpoint
  return {};
}
