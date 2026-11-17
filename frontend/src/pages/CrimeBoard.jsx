import React, { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { useLoad } from "../hooks.js";
import { Async, Badge, Card, Notice } from "../components/ui.jsx";
import { cyberAudio } from "../utils/cyberAudio.js";

export default function CrimeBoard({ c, caseRef }) {
  // Load real case data from backend APIs
  const caseState = useLoad(() => c.get(""), [c, caseRef]);
  const evState = useLoad(() => c.get("/evidence"), [c, caseRef]);
  const entState = useLoad(() => c.get("/entities?limit=50"), [c, caseRef]);
  const relState = useLoad(() => c.get("/relationships"), [c, caseRef]);
  const notesState = useLoad(() => c.get("/notes"), [c, caseRef]);

  // Board state (isolated per caseRef)
  const [nodes, setNodes] = useState([]);
  const [connections, setConnections] = useState([]);
  const [stickyNotes, setStickyNotes] = useState([]);
  const [newNoteText, setNewNoteText] = useState("");
  const [activeStringStart, setActiveStringStart] = useState(null);

  // Dragging state
  const [draggingId, setDraggingId] = useState(null);
  const dragOffset = useRef({ x: 0, y: 0 });

  const storageKey = `cm_corkboard_v5_${caseRef}`;

  // Helper to build case-specific default board layout
  const buildDefaultLayout = useCallback(() => {
    if (!caseState.data || !entState.data?.entities || !evState.data?.evidence) return null;

    const initialNodes = [];
    const caseInfo = caseState.data.case || {};
    const incidents = caseState.data.incidents || [];
    const primaryIncident = incidents[0] || {};

    // 1. Center Incident Node
    const incidentRef = primaryIncident.ref || `${caseRef}-INCIDENT`;
    const incidentTitle = caseInfo.title || primaryIncident.description || `${caseRef} Primary Incident`;
    const incidentTag = primaryIncident.location_name || "PRIMARY CRIME SCENE";

    initialNodes.push({
      id: incidentRef,
      title: incidentTitle,
      type: "INCIDENT",
      tag: incidentTag,
      x: 380,
      y: 210,
    });

    // 2. Person Nodes (Strictly filter entity_type === 'PERSON')
    const allEntities = entState.data.entities || [];
    const personEntities = allEntities.filter((e) => e.entity_type === "PERSON");
    const topPersons = personEntities.slice(0, 4);

    const personPositions = [
      { x: 70, y: 80 },    // Top Left
      { x: 700, y: 80 },   // Top Right
      { x: 70, y: 250 },   // Mid Left
      { x: 700, y: 250 },  // Mid Right
    ];

    topPersons.forEach((p, idx) => {
      initialNodes.push({
        id: p.ref,
        title: p.display_name || p.name || p.ref,
        type: "PERSON",
        tag: p.attributes?.role || p.incident_role || "PERSON OF INTEREST",
        x: personPositions[idx]?.x ?? 70,
        y: personPositions[idx]?.y ?? (80 + idx * 120),
      });
    });

    // 3. Location Nodes (Strictly filter entity_type === 'LOCATION')
    const locEntities = allEntities.filter((e) => e.entity_type === "LOCATION");
    const topLocations = locEntities.slice(0, 2);

    const locPositions = [
      { x: 70, y: 430 },   // Bottom Left
      { x: 700, y: 430 },  // Bottom Right
    ];

    topLocations.forEach((loc, idx) => {
      initialNodes.push({
        id: loc.ref,
        title: loc.display_name || loc.name || loc.ref,
        type: "LOCATION",
        tag: loc.attributes?.category || "KEY LOCATION",
        x: locPositions[idx]?.x ?? 70,
        y: locPositions[idx]?.y ?? 430,
      });
    });

    // 4. Evidence Exhibits (from current case evidence items)
    const keyEv = (evState.data.evidence || []).slice(0, 4);
    keyEv.forEach((e, idx) => {
      initialNodes.push({
        id: e.ref,
        title: `${e.evidence_type}: ${e.source || e.ref}`,
        type: "EVIDENCE",
        tag: e.validity_status || "SUPPORTED",
        x: 230 + idx * 135,
        y: 430,
      });
    });

    // 5. Red-string connections
    const initialConnections = [];

    // Connect Incident to primary suspect if present
    if (topPersons[0]) {
      initialConnections.push({
        from: incidentRef,
        to: topPersons[0].ref,
        label: "Primary Suspect / POI",
      });
    }

    // Connect Incident to crime scene location
    if (topLocations[0]) {
      initialConnections.push({
        from: incidentRef,
        to: topLocations[0].ref,
        label: "Crime Scene Location",
      });
    }

    // Connect Incident to first evidence item
    if (keyEv[0]) {
      initialConnections.push({
        from: incidentRef,
        to: keyEv[0].ref,
        label: "Forensic Evidence Link",
      });
    }

    // Connect any verified cross-entity relationships for this case
    const caseRels = relState.data?.relationships || [];
    caseRels.slice(0, 4).forEach((r) => {
      const from = r.from_entity_ref || r.subject_ref || r.from_ref;
      const to = r.to_entity_ref || r.object_ref || r.to_ref;
      if (from && to && initialConnections.length < 6) {
        initialConnections.push({
          from,
          to,
          label: r.relationship_type || r.predicate || "Observed Tie",
        });
      }
    });

    // 6. Case-specific Investigator Sticky Note
    let defaultNoteText = "";
    if (notesState.data?.notes && notesState.data.notes.length > 0) {
      const topNote = notesState.data.notes[0];
      defaultNoteText = `[${topNote.author || "LEAD"}] ${topNote.title ? topNote.title + ": " : ""}${topNote.content}`;
    } else if (caseRef === "CASE-2026-001") {
      defaultNoteText = "Meera Kulkarni found at Green Park Lawn. Alibi contradictions flagged for Karan Bhatt.";
    } else if (caseRef === "CASE-2026-002") {
      defaultNoteText = "Forced entry detected at Riverside Warehouse perimeter. Reviewing night shift rosters, access card logs, and vehicle movements.";
    } else {
      defaultNoteText = `Active investigation for ${caseInfo.title || caseRef}. Reviewing core exhibits and spatial timeline anomalies.`;
    }

    const initialStickyNotes = [
      {
        id: `note-init-${caseRef}`,
        text: defaultNoteText,
        x: 400,
        y: 65,
      },
    ];

    return {
      nodes: initialNodes,
      connections: initialConnections,
      stickyNotes: initialStickyNotes,
    };
  }, [caseState.data, entState.data, evState.data, relState.data, notesState.data, caseRef]);

  // Load from localStorage or initialize with case data
  useEffect(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.nodes && parsed.nodes.length > 0) {
          setNodes(parsed.nodes);
          setConnections(parsed.connections || []);
          setStickyNotes(parsed.stickyNotes || []);
          return;
        }
      }
    } catch {
      // Fallback to fresh layout
    }

    const defaultLayout = buildDefaultLayout();
    if (defaultLayout) {
      setNodes(defaultLayout.nodes);
      setConnections(defaultLayout.connections);
      setStickyNotes(defaultLayout.stickyNotes);
    }
  }, [buildDefaultLayout, storageKey]);

  // Save changes to localStorage scoped to current caseRef
  useEffect(() => {
    if (nodes.length === 0) return;
    try {
      localStorage.setItem(
        storageKey,
        JSON.stringify({
          nodes,
          connections,
          stickyNotes,
        })
      );
    } catch {
      // Ignore quota errors
    }
  }, [nodes, connections, stickyNotes, storageKey]);

  // Reset Corkboard Layout for current case
  const resetLayout = () => {
    try {
      cyberAudio?.playClickChirp?.();
    } catch {}
    localStorage.removeItem(storageKey);
    const defaultLayout = buildDefaultLayout();
    if (defaultLayout) {
      setNodes(defaultLayout.nodes);
      setConnections(defaultLayout.connections);
      setStickyNotes(defaultLayout.stickyNotes);
    }
  };

  // Handle Dragging
  const handlePointerDown = (id, e) => {
    e.stopPropagation();
    try {
      cyberAudio?.playHoverBlip?.();
    } catch {}
    setDraggingId(id);
    const node = nodes.find((n) => n.id === id) || stickyNotes.find((n) => n.id === id);
    if (node) {
      dragOffset.current = { x: e.clientX - node.x, y: e.clientY - node.y };
    }
  };

  const handlePointerMove = (e) => {
    if (!draggingId) return;
    const newX = e.clientX - dragOffset.current.x;
    const newY = e.clientY - dragOffset.current.y;

    if (draggingId.startsWith("note-")) {
      setStickyNotes((notes) =>
        notes.map((n) => (n.id === draggingId ? { ...n, x: newX, y: newY } : n))
      );
    } else {
      setNodes((nds) =>
        nds.map((n) => (n.id === draggingId ? { ...n, x: newX, y: newY } : n))
      );
    }
  };

  const handlePointerUp = () => {
    setDraggingId(null);
  };

  // Red string connection creation
  const handlePinClick = (nodeId, e) => {
    e.stopPropagation();
    try {
      cyberAudio?.playClickChirp?.();
    } catch {}

    if (!activeStringStart) {
      setActiveStringStart(nodeId);
    } else {
      if (activeStringStart !== nodeId) {
        setConnections((prev) => [
          ...prev,
          { from: activeStringStart, to: nodeId, label: "Manual Link" },
        ]);
        try {
          cyberAudio?.playAccessGranted?.();
        } catch {}
      }
      setActiveStringStart(null);
    }
  };

  const addStickyNote = (e) => {
    e.preventDefault();
    if (!newNoteText.trim()) return;
    try {
      cyberAudio?.playClickChirp?.();
    } catch {}

    setStickyNotes((prev) => [
      ...prev,
      {
        id: `note-${Date.now()}`,
        text: newNoteText,
        x: 360 + Math.random() * 80,
        y: 110 + Math.random() * 80,
      },
    ]);
    setNewNoteText("");
  };

  const deleteStickyNote = (id, e) => {
    e.stopPropagation();
    try {
      cyberAudio?.playHoverBlip?.();
    } catch {}
    setStickyNotes((prev) => prev.filter((n) => n.id !== id));
  };

  // Calculate coordinates for red strings
  const stringLines = useMemo(() => {
    return connections
      .map((conn) => {
        const fromNode = nodes.find((n) => n.id === conn.from);
        const toNode = nodes.find((n) => n.id === conn.to);
        if (!fromNode || !toNode) return null;
        return {
          ...conn,
          x1: fromNode.x + 85,
          y1: fromNode.y + 40,
          x2: toNode.x + 85,
          y2: toNode.y + 40,
        };
      })
      .filter(Boolean);
  }, [connections, nodes]);

  return (
    <div className="cm-corkboard-workspace">
      {/* Top Banner Ribbon */}
      <div className="cm-cctv-banner">
        <div className="cm-cctv-banner-left">
          <span className="cm-pulse-emerald" />
          <strong className="font-mono">VIRTUAL DETECTIVE RED-STRING INVESTIGATION CORKBOARD</strong>
          <span className="cm-pipeline-badge offline">
            CASE-ISOLATED PHYSICAL EVIDENCE ENGINE
          </span>
        </div>
        <div className="cm-cctv-banner-right font-mono text-muted small">
          CASE: {caseRef} · {nodes.length} PINNED EXHIBITS · {connections.length} RED STRINGS
        </div>
      </div>

      <Notice level="info">
        Case-Isolated Detective Corkboard: Freely click and drag suspects, evidence exhibits, and sticky notes anywhere.
        Click a brass pushpin on one card and then another to string a red thread connection. All pins and threads are saved per-case.
      </Notice>

      {/* Action Toolbar */}
      <div className="cm-corkboard-toolbar">
        <div className="row items-center justify-between" style={{ width: "100%" }}>
          <div className="row items-center gap-2">
            <form onSubmit={addStickyNote} className="row items-center gap-2">
              <input
                type="text"
                placeholder="Add investigator sticky note…"
                value={newNoteText}
                onChange={(e) => setNewNoteText(e.target.value)}
                className="cm-cyber-input"
                style={{ width: 280, fontSize: 12 }}
              />
              <button className="primary small" disabled={!newNoteText.trim()}>
                📌 Pin Sticky Note
              </button>
            </form>
            {activeStringStart && (
              <span className="cm-stringing-badge font-mono text-crimson small">
                STRINGING FROM: {activeStringStart} (Click destination pin to attach)
              </span>
            )}
          </div>

          <div className="row items-center gap-2">
            <button
              type="button"
              className="cm-filter-pill"
              onClick={resetLayout}
              title="Reset cards to auto-arranged case layout"
            >
              ↺ Reset Case Layout
            </button>
          </div>
        </div>
      </div>

      {/* Main Corkboard Surface */}
      <div
        className="cm-corkboard-surface"
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
      >
        <div className="cm-cork-texture" />

        {/* SVG Red Thread Laser Layer */}
        <svg className="cm-red-strings-svg">
          <defs>
            <filter id="string-glow">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {stringLines.map((str, i) => (
            <g key={i}>
              <line
                x1={str.x1}
                y1={str.y1}
                x2={str.x2}
                y2={str.y2}
                stroke="#FF2A3D"
                strokeWidth="2.5"
                filter="url(#string-glow)"
                opacity="0.9"
              />
              <circle cx={(str.x1 + str.x2) / 2} cy={(str.y1 + str.y2) / 2} r="3.5" fill="#FFF" />
            </g>
          ))}
        </svg>

        {/* Pinned Exhibit Cards */}
        {nodes.map((node) => {
          const isSelectedForString = activeStringStart === node.id;
          return (
            <div
              key={node.id}
              className={`cm-cork-card type-${node.type.toLowerCase()} ${isSelectedForString ? "string-active" : ""}`}
              style={{ left: node.x, top: node.y }}
              onPointerDown={(e) => handlePointerDown(node.id, e)}
            >
              {/* Brass Pushpin */}
              <button
                className="cm-brass-pushpin"
                onClick={(e) => handlePinClick(node.id, e)}
                title="Click to string red line"
              />

              <div className="cm-cork-card-header">
                <span className="font-mono text-cyan text-xs"><b>{node.id}</b></span>
                <Badge kind={node.tag} />
              </div>
              <strong className="cm-cork-card-title">{node.title}</strong>
              <div className="cm-cork-card-meta font-mono small text-muted">
                {node.type} EXHIBIT
              </div>
            </div>
          );
        })}

        {/* Investigator Sticky Notes */}
        {stickyNotes.map((note) => (
          <div
            key={note.id}
            className="cm-cork-sticky-note"
            style={{ left: note.x, top: note.y }}
            onPointerDown={(e) => handlePointerDown(note.id, e)}
          >
            <div className="cm-sticky-pin" />
            <button
              className="cm-sticky-delete-btn"
              onClick={(e) => deleteStickyNote(note.id, e)}
              title="Remove note"
            >
              ×
            </button>
            <p className="cm-sticky-text">{note.text}</p>
            <span className="cm-sticky-footer font-mono small text-muted">LEAD NOTE</span>
          </div>
        ))}
      </div>
    </div>
  );
}
