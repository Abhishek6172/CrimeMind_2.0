// Fallback demo dataset for standalone deployment (e.g. Vercel) when the local Python backend is not connected.

const defaultAiHistory = [
  {
    analysis_id: "AI-SYNTH-8821",
    requested_by: "admin",
    question: "Summarise what the current evidence says about movements near the park around the incident.",
    provider: "gemini-3.5-flash-lite",
    status: "OK",
    created_at: new Date(Date.now() - 3600000).toISOString()
  },
  {
    analysis_id: "AI-SYNTH-8819",
    requested_by: "inv.asha",
    question: "Are there conflicting alibis or impossible speed jumps detected for Karan Bhatt?",
    provider: "gemini-3.5-flash-lite",
    status: "OK",
    created_at: new Date(Date.now() - 7200000).toISOString()
  }
];

let aiHistory = [...defaultAiHistory];

export function getMockResponse(path, method = "GET", body = null) {
  const p = path.split("?")[0].replace(/\/$/, "");

  // AI Intelligence Assistant Status
  if (p === "/ai/status") {
    return {
      provider: "gemini-3.5-flash-lite",
      is_llm: true,
      message: "Google Gemini 3.5 Flash neural intelligence model active and verified."
    };
  }

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

  // AI Analyses History: /cases/:ref/ai/analyses
  if (p.includes("/ai/analyses")) {
    return {
      analyses: [...aiHistory]
    };
  }

  // AI Intelligence Synthesis Query: /cases/:ref/ai/analyze
  if (p.includes("/ai/analyze")) {
    const q = (body?.question || "").toLowerCase();
    let summary = "";
    let findings = [];
    let uncertainties = [];

    if (q.includes("movement") || q.includes("park") || q.includes("gazebo")) {
      summary = "Multi-modal correlation synthesizes CCTV footage (E-001), mobile tower sector pings (F-001), and witness testimony (E-003). Suspect Karan Bhatt's sedan DL-03-AB-4412 crossed Outer Ring Road at 20:58, and an individual matching his profile was sighted near the west gazebo walkway at 21:14. Co-location with victim Meera Sen is verified within a 150-metre radius between 21:15 and 21:30.";
      findings = [
        {
          statement: "Footage from CAM-05 confirms an individual matching Karan Bhatt entering the west perimeter walkway at 21:14.",
          classification: "RECORDED FACT",
          evidence_ids: ["E-001"],
          correlation_ids: [],
          confidence: 0.95
        },
        {
          statement: "Cellular tower sector telemetry places Karan Bhatt's registered mobile device in the Green Park sector at 21:22.",
          classification: "RECORDED FACT",
          evidence_ids: ["E-001"],
          correlation_ids: ["C-01"],
          confidence: 0.99
        },
        {
          statement: "Witness Ananya Sharma placed two arguing individuals matching victim and suspect near the gazebo at 21:25.",
          classification: "CORRELATED",
          evidence_ids: ["E-003"],
          correlation_ids: ["C-01"],
          confidence: 0.88
        },
        {
          statement: "Transit time from Outer Ring Road (20:58) to park walkway (21:14) is consistent with normal urban traffic speeds (38 km/h).",
          classification: "CORRELATED",
          evidence_ids: ["E-001"],
          correlation_ids: ["C-02"],
          confidence: 0.92
        },
        {
          statement: "Spatial co-location suggests opportunity for physical confrontation; subjective intent remains unverified.",
          classification: "AI-INFERRED",
          evidence_ids: ["E-001", "E-003"],
          correlation_ids: ["C-01"],
          confidence: 0.84
        }
      ];
      uncertainties = [
        "Forensic clock drift audit on CAM-05 unit pending final cryptographic sign-off.",
        "Dim lighting along west perimeter limits facial biometric recognition to 87% confidence."
      ];
    } else if (q.includes("comm") || q.includes("fund") || q.includes("transfer") || q.includes("money") || q.includes("call")) {
      summary = "Telemetry and telecom audit reveals high-frequency communication immediately preceding the incident window. Karan Bhatt (P-002) placed 3 unanswered voice calls to Meera Sen (P-001) between 21:05 and 21:12. Banking records reflect a disputed ₹2,50,000 escrow transfer under transaction TX-9942.";
      findings = [
        {
          statement: "Telecom CDR logs record three rapid outbound calls from P-002 to P-001 between 21:05 and 21:12.",
          classification: "RECORDED FACT",
          evidence_ids: ["E-002"],
          correlation_ids: [],
          confidence: 0.98
        },
        {
          statement: "Victim device ceased network signalling after 21:38, coinciding with battery disconnect or suppression.",
          classification: "RECORDED FACT",
          evidence_ids: ["E-002"],
          correlation_ids: [],
          confidence: 0.94
        },
        {
          statement: "Escrow transfer TX-9942 was flagged with status 'DISPUTED_ROYALTY' by issuing bank 48 hours prior.",
          classification: "CORRELATED",
          evidence_ids: ["E-004"],
          correlation_ids: ["C-02"],
          confidence: 0.91
        },
        {
          statement: "Communication frequency spike represents a 4.2x elevation above the 30-day baseline interaction rate.",
          classification: "AI-INFERRED",
          evidence_ids: ["E-002"],
          correlation_ids: [],
          confidence: 0.86
        }
      ];
      uncertainties = [
        "Encrypted messaging channels (Signal/Telegram) remain uninspected pending physical hardware extraction."
      ];
    } else if (q.includes("alibi") || q.includes("speed") || q.includes("jump") || q.includes("conflict")) {
      summary = "The suspect's claimed alibi—asserting continuous presence at Orbit Tech Park until 22:15—is decisively refuted. Electronic turnstile logs confirm physical departure at 20:45, and ANPR sensors captured his sedan en route at 20:58.";
      findings = [
        {
          statement: "Orbit Tech Park access control system logged Karan Bhatt's physical badge exit at 20:45.",
          classification: "RECORDED FACT",
          evidence_ids: ["E-002"],
          correlation_ids: [],
          confidence: 0.99
        },
        {
          statement: "Outer Ring Road ANPR toll camera captured sedan DL-03-AB-4412 in motion at 20:58.",
          classification: "RECORDED FACT",
          evidence_ids: ["E-001"],
          correlation_ids: [],
          confidence: 0.96
        },
        {
          statement: "Claimed alibi contradicts electronic physical access control and ANPR surveillance records.",
          classification: "CORRELATED",
          evidence_ids: ["E-001", "E-002"],
          correlation_ids: ["C-01"],
          confidence: 0.97
        },
        {
          statement: "Maintaining presence at workplace until 22:15 would require an impossible kinematic velocity jump (>110 km/h).",
          classification: "AI-INFERRED",
          evidence_ids: ["E-002"],
          correlation_ids: ["C-01"],
          confidence: 0.93
        }
      ];
      uncertainties = [
        "Possibility of badge credential borrowing or transfer has not been completely ruled out by biometric gates."
      ];
    } else if (q.includes("cctv") || q.includes("sight") || q.includes("camera") || q.includes("video")) {
      summary = "Corroborated optical surveillance isolates two verified feeds in the 60-minute incident window: Outer Ring Road ANPR camera 03 (20:58) and Green Park West Walkway CAM-05 (21:14). Both feeds have matching cryptographic hash records.";
      findings = [
        {
          statement: "ANPR Camera 03 recorded vehicle DL-03-AB-4412 heading southbound at 20:58:12.",
          classification: "RECORDED FACT",
          evidence_ids: ["E-001"],
          correlation_ids: [],
          confidence: 0.98
        },
        {
          statement: "CCTV CAM-05 recorded an individual matching suspect's physical profile entering west perimeter at 21:14:05.",
          classification: "RECORDED FACT",
          evidence_ids: ["E-001"],
          correlation_ids: [],
          confidence: 0.95
        },
        {
          statement: "Witness Ananya Sharma's report aligns temporally with CAM-05 pedestrian detection at 21:14.",
          classification: "CORRELATED",
          evidence_ids: ["E-001", "E-003"],
          correlation_ids: ["C-01"],
          confidence: 0.89
        },
        {
          statement: "Vehicle travel trajectory from toll camera to perimeter parking corresponds to continuous route.",
          classification: "AI-INFERRED",
          evidence_ids: ["E-001"],
          correlation_ids: [],
          confidence: 0.91
        }
      ];
      uncertainties = [
        "CAM-06 (East gate camera) was offline for scheduled sensor maintenance during the event horizon."
      ];
    } else {
      // General intelligence query synthesis
      summary = `Verified intelligence synthesis for inquiry: "${body?.question || "investigative query"}". Evaluated 40 case facts, 12 deterministic correlations, and 4 primary evidence exhibits under strict decision-support integrity rules.`;
      findings = [
        {
          statement: "Karan Bhatt (P-002) is verified present within the Green Park mobile tower sector at 21:22.",
          classification: "RECORDED FACT",
          evidence_ids: ["E-001"],
          correlation_ids: ["C-01"],
          confidence: 0.98
        },
        {
          statement: "Electronic badge access records establish departure from Orbit Tech Park at 20:45, preceding the incident.",
          classification: "RECORDED FACT",
          evidence_ids: ["E-002"],
          correlation_ids: [],
          confidence: 0.99
        },
        {
          statement: "Spatial-temporal coincidence rule confirms co-location between suspect vehicle and incident locus.",
          classification: "CORRELATED",
          evidence_ids: ["E-001", "E-003"],
          correlation_ids: ["C-01", "C-02"],
          confidence: 0.91
        },
        {
          statement: "Evidence exhibits strong correlation with case hypothesis H-01; criminal intent remains unadjudicated.",
          classification: "AI-INFERRED",
          evidence_ids: ["E-001", "E-002", "E-003"],
          correlation_ids: ["C-01"],
          confidence: 0.85
        }
      ];
      uncertainties = [
        "GPS-17 telemetry unit reported potential clock drift, subject to ongoing diagnostic calibration.",
        "Decision-support output: findings require independent judicial and forensic officer verification."
      ];
    }

    const newAnalysis = {
      analysis_id: "AI-SYNTH-" + Math.floor(1000 + Math.random() * 9000),
      status: "OK",
      provider: "gemini-3.5-flash-lite",
      provider_is_llm: true,
      created_at: new Date().toISOString(),
      message: "AI-assisted analysis. Findings are labelled by classification and require investigator review.",
      context_sha256: "7b8e1f04d9c49a620b784fa201bce5539fa08ef91823bbd4484b360bfa25df23",
      context_summary: "40 facts, 12 correlations, 6 evidence exhibits inspected in controlled context.",
      problems: [],
      output: {
        summary,
        findings,
        confidence: 0.94,
        uncertainties
      },
      classification_legend: {
        "RECORDED FACT": "directly recorded in source records",
        "CORRELATED": "result of an approved deterministic rule",
        "AI-INFERRED": "model interpretation; requires review",
        "UNCERTAIN": "insufficient or conflicting support"
      }
    };

    aiHistory.unshift({
      analysis_id: newAnalysis.analysis_id,
      requested_by: "admin",
      question: body?.question || "Investigation query",
      provider: "gemini-3.5-flash-lite",
      status: "OK",
      created_at: newAnalysis.created_at
    });

    return newAnalysis;
  }

  if (p.includes("/reviews")) {
    return {
      review_id: "REV-" + Date.now(),
      status: "RECORDED",
      created_at: new Date().toISOString()
    };
  }

  // Default fallback for any unspecified endpoint
  return {};
}
