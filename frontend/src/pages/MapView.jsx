import React, { useMemo, useState, useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useLoad } from "../hooks.js";
import { Async, Badge, Card, Notice, StatBox, time } from "../components/ui.jsx";
import { cyberAudio } from "../utils/cyberAudio.js";

// Tactical marker colors per tracked person
const PERSON_COLORS = [
  { ref: "P-002", color: "#FFB52E", label: "Amber" },   // Rohit Sethi
  { ref: "P-004", color: "#A855F7", label: "Violet" },  // Karan Bhatt
  { ref: "P-001", color: "#FF4655", label: "Crimson" }, // Meera Kulkarni (Victim)
  { ref: "P-003", color: "#00E5FF", label: "Cyan" },    // Dev Malhotra
  { ref: "P-005", color: "#00E6A0", label: "Emerald" },
  { ref: "P-006", color: "#F59E0B", label: "Gold" },
];

const MAP_LAYERS = {
  googleHybrid: {
    name: "Google Maps (Satellite Hybrid)",
    url: "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
    attribution: "&copy; Google Maps Satellite",
  },
  googleRoad: {
    name: "Google Maps (Roadmap)",
    url: "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
    attribution: "&copy; Google Maps Street",
  },
  darkMatter: {
    name: "Cyber Dark Matter",
    url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    attribution: "&copy; CartoDB Cyber Dark",
  },
  osm: {
    name: "OpenStreetMap",
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: "&copy; OpenStreetMap contributors",
  },
};

export default function MapView({ c }) {
  // Currently tracked person refs (multi-person tracking)
  const [trackedRefs, setTrackedRefs] = useState(["P-002", "P-004"]);
  const [activeLayer, setActiveLayer] = useState("googleHybrid");
  const [timelinePct, setTimelinePct] = useState(100);
  const [isPlaying, setIsPlaying] = useState(false);
  const [searchPerson, setSearchPerson] = useState("");
  const [selectedPin, setSelectedPin] = useState(null);

  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const tileLayerRef = useRef(null);
  const markersLayerRef = useRef(null);

  // Load case locations & incidents
  const baseMapState = useLoad(() => c.get("/insights/map"), [c]);
  const entitiesState = useLoad(() => c.get("/entities?type=PERSON&limit=50"), [c]);

  // Load individual trails for all tracked persons
  const [personTrails, setPersonTrails] = useState({});

  useEffect(() => {
    let isMounted = true;
    Promise.all(
      trackedRefs.map((ref) =>
        c.get("/insights/map", { person: ref }).then((res) => ({ ref, data: res }))
      )
    ).then((results) => {
      if (!isMounted) return;
      const trailsMap = {};
      results.forEach(({ ref, data }) => {
        trailsMap[ref] = {
          person: data.person,
          trail: data.trail || [],
        };
      });
      setPersonTrails(trailsMap);
    });
    return () => {
      isMounted = false;
    };
  }, [c, trackedRefs]);

  // Timeline playback animation
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setTimelinePct((t) => {
        if (t >= 100) {
          setIsPlaying(false);
          return 100;
        }
        return t + 2;
      });
    }, 250);
    return () => clearInterval(interval);
  }, [isPlaying]);

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      // Default coordinates centered on case city (Bhubaneswar/Green Park)
      const map = L.map(mapContainerRef.current, {
        center: [20.2961, 85.8245],
        zoom: 13,
        zoomControl: false,
      });

      L.control.zoom({ position: "topright" }).addTo(map);

      const tileConfig = MAP_LAYERS[activeLayer];
      const tile = L.tileLayer(tileConfig.url, {
        attribution: tileConfig.attribution,
        maxZoom: 20,
      }).addTo(map);

      tileLayerRef.current = tile;
      markersLayerRef.current = L.layerGroup().addTo(map);
      mapInstanceRef.current = map;
    }

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // Update Tile Layer when layer selector changes
  useEffect(() => {
    if (!mapInstanceRef.current || !tileLayerRef.current) return;
    mapInstanceRef.current.removeLayer(tileLayerRef.current);
    const tileConfig = MAP_LAYERS[activeLayer];
    const newTile = L.tileLayer(tileConfig.url, {
      attribution: tileConfig.attribution,
      maxZoom: 20,
    }).addTo(mapInstanceRef.current);
    tileLayerRef.current = newTile;
  }, [activeLayer]);

  // Render Markers and Paths onto Map
  useEffect(() => {
    if (!mapInstanceRef.current || !markersLayerRef.current) return;
    const layer = markersLayerRef.current;
    layer.clearLayers();

    const locations = baseMapState.data?.locations || [];
    const incidents = baseMapState.data?.incidents || [];

    // 1. Render Case Locations & Landmarks
    locations.forEach((loc) => {
      const isIncident = incidents.some((i) => i.location === loc.ref);
      const iconHtml = `<div class="cm-map-pin ${loc.kind?.toLowerCase()} ${isIncident ? "incident" : ""}">
        <span class="cm-pin-dot"></span>
        <span class="cm-pin-label">${loc.name.split(" ")[0]}</span>
      </div>`;

      const customIcon = L.divIcon({
        html: iconHtml,
        className: "cm-leaflet-pin-wrapper",
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      });

      const marker = L.marker([loc.lat, loc.lon], { icon: customIcon });
      marker.bindPopup(`
        <div class="cm-map-popup font-mono">
          <strong class="text-cyan">${loc.name}</strong> (${loc.ref})
          <div class="text-muted small">TYPE: ${loc.kind || "PUBLIC"}</div>
          <div class="small">LAT: ${loc.lat.toFixed(5)} · LON: ${loc.lon.toFixed(5)}</div>
          <a href="https://www.google.com/maps/search/?api=1&query=${loc.lat},${loc.lon}" target="_blank" rel="noreferrer" class="cm-popup-gmaps-link">
            Open in Google Maps ↗
          </a>
        </div>
      `);
      marker.on("click", () => {
        cyberAudio.playClickChirp();
        setSelectedPin({ type: "location", item: loc });
      });
      layer.addLayer(marker);
    });

    // 2. Render Person Tracking Trails
    const allLatLngs = [];

    Object.entries(personTrails).forEach(([ref, { person, trail }], pIdx) => {
      if (!trail.length) return;
      const colorDef = PERSON_COLORS[pIdx % PERSON_COLORS.length];
      const color = colorDef.color;

      // Filter trail points based on timeline slider percentage
      const visibleCount = Math.max(1, Math.ceil((trail.length * timelinePct) / 100));
      const visibleTrail = trail.slice(0, visibleCount);
      const latlngs = visibleTrail.map((t) => [t.lat, t.lon]);

      allLatLngs.push(...latlngs);

      // Draw polyline connecting sightings
      if (latlngs.length > 1) {
        const polyline = L.polyline(latlngs, {
          color: color,
          weight: 4,
          opacity: 0.85,
          dashArray: "8, 6",
        });
        layer.addLayer(polyline);
      }

      // Draw numbered radar sighting markers
      visibleTrail.forEach((point, idx) => {
        const isLatest = idx === visibleTrail.length - 1;
        const iconHtml = `
          <div class="cm-person-map-marker ${isLatest ? "latest" : ""}" style="--p-color: ${color}">
            <span class="cm-marker-radar"></span>
            <span class="cm-marker-core">${idx + 1}</span>
            ${isLatest ? `<span class="cm-marker-name">${person?.name || ref}</span>` : ""}
          </div>
        `;

        const customIcon = L.divIcon({
          html: iconHtml,
          className: "cm-leaflet-person-wrapper",
          iconSize: [32, 32],
          iconAnchor: [16, 16],
        });

        const marker = L.marker([point.lat, point.lon], { icon: customIcon });
        marker.bindPopup(`
          <div class="cm-map-popup font-mono">
            <div class="row items-center gap-1">
              <span class="cm-tag" style="background: ${color}; color: #000; font-weight: bold; padding: 2px 6px; border-radius: 4px;">${ref}</span>
              <strong>${person?.name || ref}</strong>
            </div>
            <div class="small" style="margin-top: 4px;">SIGHTING #${idx + 1} (${point.location})</div>
            <div class="text-muted small">SOURCE: ${point.source_kind} (${point.source})</div>
            <div class="text-muted small">EVIDENCE: ${point.evidence_ref || "—"}</div>
            <div class="small">FROM: ${time(point.from)}</div>
            <div class="small">LAT: ${point.lat.toFixed(5)} · LON: ${point.lon.toFixed(5)}</div>
            <a href="https://www.google.com/maps/search/?api=1&query=${point.lat},${point.lon}" target="_blank" rel="noreferrer" class="cm-popup-gmaps-link">
              View on Google Maps ↗
            </a>
          </div>
        `);
        marker.on("click", () => {
          cyberAudio.playHoverBlip();
          setSelectedPin({ type: "person", item: point, person, ref });
        });
        layer.addLayer(marker);
      });
    });

    // Fit map bounds if tracking points exist
    if (allLatLngs.length > 0 && timelinePct === 100) {
      const bounds = L.latLngBounds(allLatLngs);
      mapInstanceRef.current.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
    }
  }, [baseMapState.data, personTrails, timelinePct]);

  // Add / remove tracked person
  const toggleTrackPerson = (ref) => {
    cyberAudio.playClickChirp();
    setTrackedRefs((prev) =>
      prev.includes(ref) ? prev.filter((r) => r !== ref) : [...prev, ref]
    );
  };

  const personOptions = entitiesState.data?.entities || [];

  return (
    <div className="cm-geo-workspace">
      {/* Top Map Ribbon */}
      <div className="cm-geo-header">
        <div className="row items-center gap-2">
          <span className="cm-pulse-emerald" />
          <strong className="font-mono text-cyan">GEOSPATIAL SURVEILLANCE & PERSON TRACKER</strong>
          <span className="font-mono small text-muted">
            CASE: {baseMapState.data?.case_ref || "ACTIVE"} · GOOGLE MAPS API READY
          </span>
        </div>

        {/* Map Layer Selector */}
        <div className="cm-geo-layer-switch">
          {Object.entries(MAP_LAYERS).map(([key, cfg]) => (
            <button
              key={key}
              className={`cm-layer-btn ${activeLayer === key ? "active" : ""}`}
              onClick={() => {
                cyberAudio.playClickChirp();
                setActiveLayer(key);
              }}
            >
              {cfg.name}
            </button>
          ))}
        </div>
      </div>

      <Notice level="info">
        Geospatial Positioning Engine: Renders real GPS traces, verified CCTV sightings, and badge access coordinates.
        Click any marker to inspect evidence references or navigate directly to Google Maps coordinates.
      </Notice>

      <div className="cm-geo-layout">
        {/* Main Map Viewport */}
        <div className="cm-geo-map-pane">
          <Card
            title="Interactive City Coordinates Grid"
            aside={
              <div className="row items-center gap-2">
                <span className="font-mono small text-amber">
                  TRACKING {trackedRefs.length} TARGETS
                </span>
              </div>
            }
          >
            {/* Map Container */}
            <div ref={mapContainerRef} className="cm-leaflet-container" />

            {/* Timeline Playback Scrubber */}
            <div className="cm-geo-timeline">
              <div className="row justify-between items-center font-mono small text-muted">
                <span>TIME RECONSTRUCTION: {timelinePct}%</span>
                <div className="row items-center gap-2">
                  <button
                    className="cm-ctrl-btn"
                    onClick={() => {
                      cyberAudio.playClickChirp();
                      setIsPlaying(!isPlaying);
                    }}
                  >
                    {isPlaying ? "❚❚ Pause Playback" : "▶ Play Sequence"}
                  </button>
                  <button
                    className="cm-ctrl-btn"
                    onClick={() => {
                      cyberAudio.playClickChirp();
                      setTimelinePct(100);
                    }}
                  >
                    All Sightings
                  </button>
                </div>
              </div>
              <input
                type="range"
                min="10"
                max="100"
                value={timelinePct}
                onChange={(e) => setTimelinePct(+e.target.value)}
                className="cm-timeline-slider"
              />
            </div>
          </Card>
        </div>

        {/* Side Panel: Multi-Person Tracker Selectors & Inspection */}
        <div className="cm-geo-side-pane">
          <Card title="Tracked Persons Matrix">
            <p className="small muted">
              Select individuals to overlay and cross-compare their location sightings simultaneously:
            </p>

            <div className="cm-tracked-person-chips">
              {PERSON_COLORS.slice(0, 5).map((pc) => {
                const isTracked = trackedRefs.includes(pc.ref);
                const ent = personOptions.find((e) => e.ref === pc.ref);
                const name = typeof ent?.display_name === "string" ? ent.display_name : typeof ent?.name === "string" ? ent.name : pc.ref;

                return (
                  <button
                    key={pc.ref}
                    className={`cm-person-chip ${isTracked ? "active" : ""}`}
                    style={{ "--chip-color": pc.color }}
                    onClick={() => toggleTrackPerson(pc.ref)}
                  >
                    <span className="cm-chip-dot" />
                    <span className="font-mono">{pc.ref}</span>
                    <span>{name}</span>
                    <span className="cm-chip-toggle">{isTracked ? "✓ TRACKING" : "+ TRACK"}</span>
                  </button>
                );
              })}
            </div>

            {/* Quick Person Search Selector */}
            <div style={{ marginTop: 14 }}>
              <input
                type="text"
                placeholder="Search other persons (e.g. P-003)…"
                value={searchPerson}
                onChange={(e) => setSearchPerson(e.target.value)}
                className="cm-cyber-input"
                style={{ width: "100%", fontSize: 12 }}
              />
              {searchPerson.trim() && (
                <div className="cm-search-person-results">
                  {personOptions
                    .filter(
                      (p) =>
                        p.ref.toLowerCase().includes(searchPerson.toLowerCase()) ||
                        (p.display_name || p.name || "").toLowerCase().includes(searchPerson.toLowerCase())
                    )
                    .slice(0, 4)
                    .map((p) => (
                      <div
                        key={p.ref}
                        className="cm-search-person-row"
                        onClick={() => {
                          toggleTrackPerson(p.ref);
                          setSearchPerson("");
                        }}
                      >
                        <span className="font-mono text-cyan">{p.ref}</span>
                        <span>{typeof p.display_name === "string" ? p.display_name : typeof p.name === "string" ? p.name : p.ref}</span>
                        <span className="small text-amber">
                          {trackedRefs.includes(p.ref) ? "Remove" : "Add"}
                        </span>
                      </div>
                    ))}
                </div>
              )}
            </div>
          </Card>

          {/* Sighting Detail Telemetry Drawer */}
          {selectedPin && (
            <Card
              title={selectedPin.type === "person" ? "Target Sighting Telemetry" : "Landmark Telemetry"}
              aside={<button className="small" onClick={() => setSelectedPin(null)}>Close</button>}
            >
              {selectedPin.type === "person" ? (
                <div className="stack font-mono small">
                  <div className="row items-center gap-2">
                    <strong className="text-cyan text-base">
                      {typeof selectedPin.person?.name === "string" ? selectedPin.person.name : String(selectedPin.ref || "PERSON")}
                    </strong>
                    <Badge kind="GPS" />
                  </div>
                  <div className="kv"><span>Location Ref</span><b>{selectedPin.item.location}</b></div>
                  <div className="kv"><span>Sensor Kind</span><span>{selectedPin.item.source_kind}</span></div>
                  <div className="kv"><span>Sensor Source</span><span>{selectedPin.item.source}</span></div>
                  <div className="kv"><span>Evidence Link</span><span>{selectedPin.item.evidence_ref || "—"}</span></div>
                  <div className="kv"><span>Observed At</span><span>{time(selectedPin.item.from)}</span></div>
                  <div className="kv"><span>GPS Coordinates</span><span>{selectedPin.item.lat.toFixed(5)}, {selectedPin.item.lon.toFixed(5)}</span></div>
                  <div style={{ marginTop: 8 }}>
                    <a
                      href={`https://www.google.com/maps/search/?api=1&query=${selectedPin.item.lat},${selectedPin.item.lon}`}
                      target="_blank"
                      rel="noreferrer"
                      className="cm-gmaps-direct-btn"
                    >
                      🗺️ Open Coordinates in Google Maps ↗
                    </a>
                  </div>
                </div>
              ) : (
                <div className="stack font-mono small">
                  <strong className="text-cyan text-base">{selectedPin.item.name}</strong>
                  <div className="kv"><span>Reference</span><span>{selectedPin.item.ref}</span></div>
                  <div className="kv"><span>Landmark Kind</span><span>{selectedPin.item.kind || "PUBLIC"}</span></div>
                  <div className="kv"><span>Coordinates</span><span>{selectedPin.item.lat.toFixed(5)}, {selectedPin.item.lon.toFixed(5)}</span></div>
                  <div style={{ marginTop: 8 }}>
                    <a
                      href={`https://www.google.com/maps/search/?api=1&query=${selectedPin.item.lat},${selectedPin.item.lon}`}
                      target="_blank"
                      rel="noreferrer"
                      className="cm-gmaps-direct-btn"
                    >
                      🗺️ View on Google Maps ↗
                    </a>
                  </div>
                </div>
              )}
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
