import React, { useMemo, useState, useEffect, useRef } from "react";
import { api, apiUpload } from "../api.js";
import { useLoad } from "../hooks.js";
import { Async, Badge, Card, Notice, StatBox, Table, time } from "../components/ui.jsx";
import { cyberAudio } from "../utils/cyberAudio.js";

const CLASS_COLORS = {
  person: "#00E5FF",
  car: "#FFB52E",
  motorcycle: "#00E6A0",
  bus: "#FF4655",
  truck: "#A855F7",
  bicycle: "#38BDF8",
  default: "#E2E8F0",
};

export default function CctvAnalysis({ c, caseRef, go }) {
  // 1. Load registered cameras and uploaded videos
  const [refreshKey, setRefreshKey] = useState(0);
  const [videos, setVideos] = useState([]);
  const [cameras, setCameras] = useState([]);
  const [selectedVideoId, setSelectedVideoId] = useState(null);
  const [loadingVideos, setLoadingVideos] = useState(true);

  // 2. Video playback & tracking state
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);

  // 3. Inference data for active video
  const [detections, setDetections] = useState([]);
  const [tracks, setTracks] = useState([]);
  const [events, setEvents] = useState([]);
  const [activeJob, setActiveJob] = useState(null);
  const [activeJobStatus, setActiveJobStatus] = useState(null);

  // 4. Filters
  const [selectedClass, setSelectedClass] = useState("all");
  const [minConfidence, setMinConfidence] = useState(0.25);
  const [highlightTrackId, setHighlightTrackId] = useState(null);

  // 5. Upload Modal / Drawer State
  const [showUpload, setShowUpload] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadCamId, setUploadCamId] = useState("");
  const [uploadModel, setUploadModel] = useState("yolo11n.pt");
  const [uploadConf, setUploadConf] = useState(0.35);
  const [autoProcess, setAutoProcess] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");

  // Load videos and cameras
  useEffect(() => {
    let mounted = true;
    setLoadingVideos(true);
    Promise.all([
      api("/cctv/videos", { params: { case: caseRef } }).catch(() => []),
      api("/cctv/cameras", { params: { case: caseRef } }).catch(() => []),
    ]).then(([vList, cList]) => {
      if (!mounted) return;
      const list = vList || [];
      setVideos(list);
      setCameras(cList || []);
      // Preserve existing selectedVideoId if valid; otherwise default to newest video
      setSelectedVideoId((currentId) => {
        if (currentId && list.some((v) => v.video_id === currentId)) {
          return currentId;
        }
        return list.length > 0 ? list[0].video_id : null;
      });
      setLoadingVideos(false);
    });
    return () => { mounted = false; };
  }, [caseRef, refreshKey]);

  const activeVideo = useMemo(() => {
    return videos.find((v) => v.video_id === selectedVideoId) || videos[0] || null;
  }, [videos, selectedVideoId]);

  // Load detections, tracks, and events for the active video
  useEffect(() => {
    if (!activeVideo) return;
    let mounted = true;

    Promise.all([
      api(`/cctv/videos/${activeVideo.video_id}/detections`, { params: { limit: 1000 } }).catch(() => []),
      api(`/cctv/videos/${activeVideo.video_id}/tracks`).catch(() => []),
      api(`/cctv/videos/${activeVideo.video_id}/events`).catch(() => []),
    ]).then(([dList, tList, eList]) => {
      if (!mounted) return;
      setDetections(dList || []);
      setTracks(tList || []);
      setEvents(eList || []);
    });

    return () => { mounted = false; };
  }, [activeVideo, refreshKey]);

  // Poll active background job if running
  useEffect(() => {
    if (!activeJob) return;
    let failCount = 0;
    const interval = setInterval(async () => {
      try {
        const job = await api(`/cctv/jobs/${activeJob}`);
        failCount = 0;
        setActiveJobStatus(job);
        if (job.status === "COMPLETED" || job.status === "FAILED") {
          clearInterval(interval);
          setActiveJob(null);
          setRefreshKey((k) => k + 1);
          cyberAudio.playSuccess();
        }
      } catch (err) {
        failCount += 1;
        if (failCount >= 6) {
          clearInterval(interval);
          setActiveJob(null);
        }
      }
    }, 1500);
    return () => clearInterval(interval);
  }, [activeJob]);

  // Handle Video Upload
  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!uploadFile) return;

    try {
      setIsUploading(true);
      setUploadError("");
      try { cyberAudio?.playScan?.(); } catch {}

      const formData = new FormData();
      formData.append("file", uploadFile);
      formData.append("case", caseRef);
      if (uploadCamId) formData.append("camera_id", uploadCamId);
      formData.append("auto_process", autoProcess ? "true" : "false");

      const res = await apiUpload("/cctv/videos/upload", formData);
      try { cyberAudio?.playAccessGranted?.(); } catch {}
      setShowUpload(false);
      setUploadFile(null);

      if (res.video?.video_id) {
        setSelectedVideoId(res.video.video_id);
      }
      if (res.job_id) {
        setActiveJob(res.job_id);
      }
      setRefreshKey((k) => k + 1);
    } catch (err) {
      setUploadError(err.message || "Failed to upload footage");
      try { cyberAudio?.playGlitch?.(); } catch {}
    } finally {
      setIsUploading(false);
    }
  };

  // Trigger Manual Inference on active video
  const triggerInference = async () => {
    if (!activeVideo) return;
    try {
      cyberAudio.playClickChirp();
      const res = await api(`/cctv/videos/${activeVideo.video_id}/process`, {
        method: "POST",
        body: {
          model_name: uploadModel,
          tracker_type: "bytetrack",
          confidence_thresh: minConfidence,
          iou_thresh: 0.45,
          frame_skip: 1,
        },
      });
      if (res.job_id) {
        setActiveJob(res.job_id);
      }
    } catch (err) {
      alert("Inference trigger failed: " + err.message);
    }
  };

  // Video Time Update & Synchronized Bounding Box Rendering
  const handleTimeUpdate = () => {
    const vid = videoRef.current;
    if (!vid) return;
    setCurrentTime(vid.currentTime);
    setDuration(vid.duration || 0);

    // Render Canvas Bounding Boxes
    const canvas = canvasRef.current;
    if (!canvas || !activeVideo) return;
    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    // Frame scale factors
    const scaleX = width / (activeVideo.width || 1920);
    const scaleY = height / (activeVideo.height || 1080);

    // Find detections matching current video time (+/- 0.08 seconds)
    const t = vid.currentTime;
    const currentDets = detections.filter(
      (d) => Math.abs(d.timestamp_sec - t) <= 0.09 && d.confidence >= minConfidence
    );

    currentDets.forEach((d) => {
      if (selectedClass !== "all" && d.class_name !== selectedClass) return;

      const isHighlight = highlightTrackId && d.track_id === highlightTrackId;
      const col = CLASS_COLORS[d.class_name] || CLASS_COLORS.default;

      const x1 = d.bbox_x1 * scaleX;
      const y1 = d.bbox_y1 * scaleY;
      const x2 = d.bbox_x2 * scaleX;
      const y2 = d.bbox_y2 * scaleY;
      const boxW = x2 - x1;
      const boxH = y2 - y1;

      // Draw bounding box
      ctx.strokeStyle = isHighlight ? "#FFFFFF" : col;
      ctx.lineWidth = isHighlight ? 3 : 2;
      ctx.strokeRect(x1, y1, boxW, boxH);

      // Corner technical reticles
      const cornerLen = Math.min(10, boxW * 0.2);
      ctx.strokeStyle = "#FFFFFF";
      ctx.lineWidth = 2;
      // Top-left corner
      ctx.beginPath();
      ctx.moveTo(x1, y1 + cornerLen);
      ctx.lineTo(x1, y1);
      ctx.lineTo(x1 + cornerLen, y1);
      ctx.stroke();

      // Label background
      const labelText = `${d.class_name.toUpperCase()} ${d.track_id ? `[#${d.track_id}]` : ""} ${(d.confidence * 100).toFixed(0)}%`;
      ctx.font = "bold 10px monospace";
      const textWidth = ctx.measureText(labelText).width;

      ctx.fillStyle = isHighlight ? "#FFFFFF" : col;
      ctx.fillRect(x1, Math.max(0, y1 - 18), textWidth + 10, 18);

      ctx.fillStyle = "#05090F";
      ctx.fillText(labelText, x1 + 5, Math.max(12, y1 - 5));
    });

    // Draw active track trajectory if highlighted
    if (highlightTrackId) {
      const activeTrack = tracks.find((tr) => tr.track_id === highlightTrackId);
      if (activeTrack && activeTrack.trajectory) {
        ctx.strokeStyle = "rgba(0, 229, 255, 0.7)";
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        let first = true;
        activeTrack.trajectory.forEach((pt) => {
          const px = pt.x * scaleX;
          const py = pt.y * scaleY;
          if (first) {
            ctx.moveTo(px, py);
            first = false;
          } else {
            ctx.lineTo(px, py);
          }
        });
        ctx.stroke();
        ctx.setLineDash([]);
      }
    }
  };

  // Playback Controls
  const togglePlay = () => {
    const vid = videoRef.current;
    if (!vid) return;
    cyberAudio.playClickChirp();
    if (vid.paused) {
      vid.play();
      setIsPlaying(true);
    } else {
      vid.pause();
      setIsPlaying(false);
    }
  };

  const seekTo = (sec) => {
    const vid = videoRef.current;
    if (!vid) return;
    cyberAudio.playHoverBlip();
    vid.currentTime = sec;
    setCurrentTime(sec);
  };

  const changeSpeed = (sp) => {
    const vid = videoRef.current;
    if (!vid) return;
    cyberAudio.playClickChirp();
    vid.playbackRate = sp;
    setPlaybackSpeed(sp);
  };

  // Filtered detections for table view
  const filteredDetections = useMemo(() => {
    return detections.filter((d) => {
      const matchClass = selectedClass === "all" || d.class_name === selectedClass;
      const matchConf = d.confidence >= minConfidence;
      return matchClass && matchConf;
    });
  }, [detections, selectedClass, minConfidence]);

  return (
    <div className="cm-cctv-workspace">
      {/* CCTV Top Status Ribbon */}
      <div className="cm-cctv-banner">
        <div className="cm-cctv-banner-left">
          <span className="cm-pulse-emerald" />
          <strong className="font-mono">INTELLIGENCE SURVEILLANCE & DEEP LEARNING CV SYSTEM</strong>
          <span className="cm-pipeline-badge online">
            YOLOv11 & BYTETRACK: ACTIVE (REAL MODEL INFERENCE)
          </span>
        </div>
        <div className="cm-cctv-banner-right font-mono text-muted small">
          CASE: {caseRef} · {videos.length} FOOTAGE ARCHIVES · {cameras.length} CAMERAS
        </div>
      </div>

      {/* Main Top Actions & Telemetry HUD */}
      <div className="cm-metrics-hud">
        <StatBox
          label="ACTIVE FOOTAGE"
          value={activeVideo ? activeVideo.filename.slice(0, 18) + "…" : "NO FOOTAGE"}
          sub={activeVideo ? `${activeVideo.total_frames} frames · ${activeVideo.duration_sec}s · ${activeVideo.fps} FPS` : "Upload CCTV to begin"}
          icon="🎥"
          accent="cyan"
        />
        <StatBox
          label="OBJECT DETECTIONS"
          value={detections.length}
          sub={`${tracks.length} persistent ByteTracks identified`}
          icon="◈"
          accent="amber"
        />
        <StatBox
          label="INVESTIGATIVE EVENTS"
          value={events.length}
          sub="Objective spatial-temporal transitions"
          icon="⚡"
          accent="emerald"
        />
        <StatBox
          label="CAMERA OPTIC"
          value={activeVideo?.camera_ref || "UNASSIGNED"}
          sub={activeVideo?.camera_name || "Perimeter Stream"}
          icon="⌕"
          accent="purple"
        />
      </div>

      {/* Action Deck: Upload & Video Switcher */}
      <div className="row justify-between items-center gap-3" style={{ marginBottom: 16 }}>
        {/* Video Selector Dropdown */}
        <div className="row items-center gap-2">
          <label className="font-mono small text-muted">SELECT CCTV FOOTAGE:</label>
          <select
            value={selectedVideoId || ""}
            onChange={(e) => {
              cyberAudio.playClickChirp();
              setSelectedVideoId(Number(e.target.value));
            }}
            className="cm-cyber-input font-mono small"
            style={{ minWidth: 260 }}
          >
            {videos.map((v) => (
              <option key={v.video_id} value={v.video_id}>
                {v.camera_ref ? `[${v.camera_ref}] ` : ""}{v.filename} ({v.duration_sec}s · {v.status})
              </option>
            ))}
          </select>

          {activeVideo && activeVideo.status !== "PROCESSING" && (
            <button
              className="cm-filter-pill"
              onClick={triggerInference}
              title="Re-run YOLOv11 & ByteTrack Inference Pipeline"
            >
              ⚡ RE-RUN YOLOV11
            </button>
          )}
        </div>

        {/* Upload Button */}
        <button
          className="cm-courtroom-export-btn"
          onClick={() => {
            cyberAudio.playClickChirp();
            setShowUpload(true);
          }}
        >
          ＋ UPLOAD CCTV FOOTAGE
        </button>
      </div>

      {/* CCTV Footage Library Interactive Cards */}
      {videos.length > 0 && (
        <div className="cm-footage-reel row gap-2" style={{ marginBottom: 16, overflowX: "auto", paddingBottom: 6 }}>
          {videos.map((v) => {
            const isSelected = v.video_id === selectedVideoId;
            return (
              <div
                key={v.video_id}
                onClick={() => {
                  cyberAudio.playClickChirp();
                  setSelectedVideoId(v.video_id);
                }}
                className={`cm-footage-card ${isSelected ? "active" : ""}`}
                style={{
                  cursor: "pointer",
                  padding: "8px 14px",
                  borderRadius: 6,
                  border: isSelected ? "1px solid var(--cm-cyan, #00e5ff)" : "1px solid rgba(255,255,255,0.08)",
                  background: isSelected ? "rgba(0, 229, 255, 0.08)" : "rgba(18, 22, 28, 0.6)",
                  boxShadow: isSelected ? "0 0 12px rgba(0, 229, 255, 0.2)" : "none",
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  transition: "all 0.2s ease",
                  flexShrink: 0,
                }}
              >
                <div style={{ fontSize: 18 }}>{isSelected ? "🎥" : "📹"}</div>
                <div>
                  <div className="row items-center gap-2">
                    <span className="font-mono text-cyan" style={{ fontSize: "0.8rem", fontWeight: 700 }}>
                      {v.camera_ref ? `[${v.camera_ref}]` : "[UNASSIGNED]"}
                    </span>
                    <span className="font-mono" style={{ fontSize: "0.8rem", color: isSelected ? "#fff" : "#a0aec0" }}>
                      {v.filename}
                    </span>
                  </div>
                  <div className="row items-center gap-2 font-mono text-xs text-muted" style={{ marginTop: 2 }}>
                    <span>{Number(v.duration_sec || 0).toFixed(1)}s · {v.total_frames} frames</span>
                    <span style={{
                      color: v.status === "COMPLETED" ? "#10b981" : v.status === "PROCESSING" ? "#00e5ff" : "#f59e0b",
                      fontWeight: 600
                    }}>
                      • {v.status}
                    </span>
                    {isSelected && (
                      <span className="cm-badge-tag" style={{ background: "rgba(0, 229, 255, 0.2)", color: "#00e5ff", padding: "1px 6px", fontSize: "0.65rem", borderRadius: 3 }}>
                        ACTIVE FEED
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Active Processing Job Banner */}
      {activeJob && (
        <div className="cm-job-progress-banner">
          <div className="row justify-between items-center" style={{ marginBottom: 8 }}>
            <div className="row items-center gap-2">
              <span className="cm-pulse-cyan" />
              <strong className="font-mono text-cyan small">
                YOLOV11 & BYTETRACK INFERENCE IN PROGRESS (JOB #{activeJob})
              </strong>
            </div>
            <span className="font-mono text-amber small">
              {activeJobStatus?.progress_pct ? `${activeJobStatus.progress_pct}%` : "INITIALIZING..."}
            </span>
          </div>

          <div className="cm-timeline-track-wrap">
            <div
              className="cm-timeline-progress"
              style={{ width: `${activeJobStatus?.progress_pct || 5}%` }}
            />
          </div>

          <div className="row justify-between font-mono text-xs text-muted" style={{ marginTop: 8 }}>
            <span>Frames: {activeJobStatus?.frames_processed ?? 0} / {activeJobStatus?.total_frames ?? "—"}</span>
            <span>Detections: {activeJobStatus?.detections_count ?? 0}</span>
            <span>Tracks: {activeJobStatus?.tracks_count ?? 0}</span>
            <span>Throughput: {activeJobStatus?.processing_fps ?? 0} FPS</span>
          </div>
        </div>
      )}

      {/* Main CCTV Workspace Layout */}
      <div className="cm-cctv-layout">
        {/* Left Column: Interactive Video Player with Canvas Overlay */}
        <div className="cm-cctv-main-column">
          <Card
            title={activeVideo ? `ACTIVE FEED: ${activeVideo.camera_ref || "CAM"} — ${activeVideo.filename}` : "SURVEILLANCE VIEWPORT"}
            aside={
              activeVideo && (
                <div className="row items-center gap-2">
                  <Badge kind={activeVideo.status === "COMPLETED" ? "SUPPORTED" : "CHALLENGED"} />
                  <span className="font-mono text-xs text-muted">
                    SHA: {activeVideo.sha256_hash.slice(0, 10)}…
                  </span>
                </div>
              )
            }
          >
            {activeVideo ? (
              <div className="cm-viewport-screen-container">
                {/* HTML5 Native Video Stream */}
                <video
                  key={activeVideo.video_id}
                  ref={videoRef}
                  src={`/api/cctv/videos/${activeVideo.video_id}/stream`}
                  className="cm-video-element"
                  onTimeUpdate={handleTimeUpdate}
                  onPlay={() => setIsPlaying(true)}
                  onPause={() => setIsPlaying(false)}
                  playsInline
                  preload="auto"
                />

                {/* Overlaid Bounding Box Canvas */}
                <canvas
                  ref={canvasRef}
                  width={960}
                  height={540}
                  className="cm-bbox-canvas-overlay"
                />

                {/* Scanlines & HUD Watermark */}
                <div className="cm-viewport-scanlines" />

                {/* Top Overlay HUD Telemetry */}
                <div className="cm-hud-top-left">
                  <div className="cm-hud-rec">
                    <span className={`cm-hud-rec-pulse ${isPlaying ? "live" : "paused"}`} />
                    <span>{isPlaying ? "PLAYING" : "PAUSED"}</span>
                  </div>
                  <div className="cm-hud-meta">TIME: {currentTime.toFixed(2)}s / {duration.toFixed(2)}s</div>
                  <div className="cm-hud-meta">RES: {activeVideo.width}×{activeVideo.height}</div>
                </div>

                <div className="cm-hud-top-right">
                  <div className="font-mono text-xs text-cyan">
                    ACTIVE TRACKS: {tracks.length}
                  </div>
                  {highlightTrackId && (
                    <div className="font-mono text-xs text-amber">
                      LOCKED TRACK #{highlightTrackId}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="cm-empty-viewport">
                <span className="text-muted font-mono">No video footage selected. Please upload or choose a video.</span>
              </div>
            )}

            {/* Scrubber & Player Controls Deck */}
            {activeVideo && (
              <div className="cm-player-control-deck">
                <div className="row items-center gap-3">
                  <button className="cm-play-btn" onClick={togglePlay}>
                    {isPlaying ? "❚❚ PAUSE" : "▶ PLAY"}
                  </button>

                  <button className="cm-filter-pill" onClick={() => seekTo(Math.max(0, currentTime - 1))}>
                    -1s
                  </button>

                  <button className="cm-filter-pill" onClick={() => seekTo(Math.min(duration, currentTime + 1))}>
                    +1s
                  </button>

                  {/* Playback Speed */}
                  <div className="row items-center gap-1 font-mono text-xs text-muted">
                    <span>SPEED:</span>
                    {[0.5, 1, 2].map((s) => (
                      <button
                        key={s}
                        className={`cm-filter-pill ${playbackSpeed === s ? "active" : ""}`}
                        onClick={() => changeSpeed(s)}
                      >
                        {s}x
                      </button>
                    ))}
                  </div>

                  <div className="grow" />

                  {highlightTrackId && (
                    <button className="cm-filter-pill text-amber" onClick={() => setHighlightTrackId(null)}>
                      CLEAR TRACK #{highlightTrackId}
                    </button>
                  )}
                </div>

                {/* Video Seek Scrubber */}
                <input
                  type="range"
                  min={0}
                  max={duration || 10}
                  step={0.04}
                  value={currentTime}
                  onChange={(e) => seekTo(Number(e.target.value))}
                  className="cm-cyber-range"
                  style={{ marginTop: 10 }}
                />
              </div>
            )}
          </Card>

          {/* Section 2: Real Detection Explorer Table */}
          <Card
            title={`YOLO Detections Explorer (${filteredDetections.length} Total Matches)`}
            aside={
              <div className="row items-center gap-2">
                <span className="font-mono text-xs text-muted">CLASS:</span>
                {["all", "person", "car", "motorcycle", "truck"].map((cls) => (
                  <button
                    key={cls}
                    className={`cm-filter-pill ${selectedClass === cls ? "active" : ""}`}
                    onClick={() => {
                      cyberAudio.playClickChirp();
                      setSelectedClass(cls);
                    }}
                  >
                    {cls.toUpperCase()}
                  </button>
                ))}
              </div>
            }
          >
            <div className="row items-center gap-3" style={{ marginBottom: 12 }}>
              <span className="font-mono text-xs text-muted">
                CONFIDENCE THRESHOLD: <strong className="text-cyan">{(minConfidence * 100).toFixed(0)}%</strong>
              </span>
              <input
                type="range"
                min={0.15}
                max={0.9}
                step={0.05}
                value={minConfidence}
                onChange={(e) => setMinConfidence(Number(e.target.value))}
                className="cm-cyber-range"
                style={{ width: 140 }}
              />
            </div>

            <div className="cm-table-wrap" style={{ maxHeight: 240, overflowY: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th>Frame #</th>
                    <th>Time</th>
                    <th>Object Class</th>
                    <th>Confidence</th>
                    <th>ByteTrack ID</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredDetections.slice(0, 100).map((d) => (
                    <tr key={d.detection_id}>
                      <td className="font-mono">{d.frame_number}</td>
                      <td className="font-mono text-cyan">{d.timestamp_sec.toFixed(2)}s</td>
                      <td>
                        <span
                          className="cm-split-badge"
                          style={{
                            color: CLASS_COLORS[d.class_name] || CLASS_COLORS.default,
                            borderColor: CLASS_COLORS[d.class_name] || CLASS_COLORS.default,
                          }}
                        >
                          {d.class_name.toUpperCase()}
                        </span>
                      </td>
                      <td className="font-mono">{(d.confidence * 100).toFixed(1)}%</td>
                      <td>
                        {d.track_id ? (
                          <button
                            className={`cm-filter-pill ${highlightTrackId === d.track_id ? "active" : ""}`}
                            onClick={() => {
                              cyberAudio.playClickChirp();
                              setHighlightTrackId(d.track_id);
                            }}
                          >
                            Track #{d.track_id}
                          </button>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td>
                        <button
                          className="small cm-filter-pill"
                          onClick={() => seekTo(d.timestamp_sec)}
                          title="Jump to frame"
                        >
                          ▶ Jump
                        </button>
                      </td>
                    </tr>
                  ))}
                  {filteredDetections.length === 0 && (
                    <tr>
                      <td colSpan={6} className="text-muted small">
                        No detections matching filter criteria.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>
        </div>

        {/* Right Column: Extracted Events & EVLM Evidence Artifacts */}
        <div className="cm-cctv-side-column">
          {/* Extracted Events Drawer */}
          <Card
            title="Extracted Investigation Events"
            aside={<span className="font-mono text-xs text-cyan">{events.length} Events</span>}
          >
            <div className="stack gap-3" style={{ maxHeight: 420, overflowY: "auto" }}>
              {events.map((ev) => (
                <div key={ev.event_id} className="cm-cctv-event-card">
                  <div className="row justify-between items-center" style={{ marginBottom: 6 }}>
                    <span className="cm-split-badge all">{ev.event_type}</span>
                    <span className="font-mono text-xs text-amber">
                      {ev.start_sec.toFixed(1)}s – {ev.end_sec.toFixed(1)}s
                    </span>
                  </div>

                  <p className="font-mono text-xs text-white" style={{ margin: "4px 0", lineHeight: 1.4 }}>
                    {ev.description}
                  </p>

                  {/* Thumbnail if generated */}
                  {ev.thumbnail_path && (
                    <img
                      src={ev.thumbnail_path}
                      alt="Event Thumbnail"
                      className="cm-event-thumb-img"
                      onClick={() => seekTo(ev.start_sec)}
                      title="Click to seek to event timestamp"
                    />
                  )}

                  <div className="row justify-between items-center" style={{ marginTop: 8 }}>
                    <span className="font-mono text-xs text-muted">
                      Tracks: {ev.track_ids?.join(", ") || "None"}
                    </span>
                    <button
                      className="small cm-filter-pill"
                      onClick={() => seekTo(ev.start_sec)}
                    >
                      ▶ Seek
                    </button>
                  </div>

                  {ev.evidence_ref && (
                    <div className="cm-evlm-ref-tag font-mono text-xs" style={{ marginTop: 6 }}>
                      EVLM EVIDENCE: <strong className="text-cyan">{ev.evidence_ref}</strong> ({ev.evidence_validity || "SUPPORTED"})
                    </div>
                  )}
                </div>
              ))}

              {events.length === 0 && (
                <p className="muted small font-mono">
                  No spatial-temporal anomalies extracted yet. Run YOLOv11 & ByteTrack inference to generate events.
                </p>
              )}
            </div>
          </Card>

          {/* Persistent ByteTracks Summary */}
          <Card title="ByteTrack Multi-Object Tracks" aside={<span className="font-mono text-xs text-muted">{tracks.length} Tracks</span>}>
            <div className="stack gap-2" style={{ maxHeight: 260, overflowY: "auto" }}>
              {tracks.map((tr) => (
                <div
                  key={tr.track_id}
                  className={`cm-track-card ${highlightTrackId === tr.track_id ? "active" : ""}`}
                  onClick={() => {
                    cyberAudio.playHoverBlip();
                    setHighlightTrackId(tr.track_id);
                    seekTo(tr.first_seen_sec);
                  }}
                >
                  <div className="row justify-between items-center">
                    <strong className="font-mono text-cyan small">Track #{tr.track_id}</strong>
                    <span className="font-mono text-xs text-amber">{tr.class_name.toUpperCase()}</span>
                  </div>
                  <div className="row justify-between font-mono text-xs text-muted" style={{ marginTop: 4 }}>
                    <span>Duration: {tr.duration_sec.toFixed(1)}s</span>
                    <span>Max Conf: {(tr.max_confidence * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
              {tracks.length === 0 && (
                <p className="muted small font-mono">No active tracks generated.</p>
              )}
            </div>
          </Card>
        </div>
      </div>

      {/* Upload Modal Drawer */}
      {showUpload && (
        <div className="cm-upload-modal-overlay">
          <div className="cm-upload-modal-box">
            <div className="row justify-between items-center" style={{ marginBottom: 16 }}>
              <div className="row items-center gap-2">
                <span className="cm-pulse-amber" />
                <h3 className="font-mono" style={{ margin: 0, fontSize: 14 }}>
                  UPLOAD CCTV SURVEILLANCE FOOTAGE (GENUINE CV PIPELINE)
                </h3>
              </div>
              <button className="cm-filter-pill" onClick={() => setShowUpload(false)}>
                ✕ Close
              </button>
            </div>

            <form onSubmit={handleUploadSubmit} className="stack gap-3 font-mono small">
              {/* File Select */}
              <div>
                <label className="text-muted">SELECT FOOTAGE FILE (MP4, AVI, MOV, MKV):</label>
                <input
                  type="file"
                  accept=".mp4,.avi,.mov,.mkv"
                  required
                  onChange={(e) => setUploadFile(e.target.files[0])}
                  className="cm-cyber-input"
                  style={{ marginTop: 6 }}
                />
              </div>

              {/* Camera Association */}
              <div>
                <label className="text-muted">ASSOCIATE WITH SURVEILLANCE CAMERA:</label>
                <select
                  value={uploadCamId}
                  onChange={(e) => setUploadCamId(e.target.value)}
                  className="cm-cyber-input"
                  style={{ marginTop: 6 }}
                >
                  <option value="">-- Unassigned Camera --</option>
                  {cameras.map((c) => (
                    <option key={c.camera_id} value={c.camera_id}>
                      [{c.ref}] {c.name} ({c.coverage_zone || "General Zone"})
                    </option>
                  ))}
                </select>
              </div>

              {/* Inference Config */}
              <div className="row gap-3">
                <div style={{ flex: 1 }}>
                  <label className="text-muted">YOLO MODEL WEIGHTS:</label>
                  <select
                    value={uploadModel}
                    onChange={(e) => setUploadModel(e.target.value)}
                    className="cm-cyber-input"
                    style={{ marginTop: 6 }}
                  >
                    <option value="yolo11n.pt">YOLOv11 Nano (Official COCO)</option>
                    <option value="yolov8n.pt">YOLOv8 Nano (Official COCO)</option>
                  </select>
                </div>

                <div style={{ flex: 1 }}>
                  <label className="text-muted">CONFIDENCE THRESHOLD:</label>
                  <input
                    type="number"
                    min="0.1"
                    max="0.9"
                    step="0.05"
                    value={uploadConf}
                    onChange={(e) => setUploadConf(Number(e.target.value))}
                    className="cm-cyber-input"
                    style={{ marginTop: 6 }}
                  />
                </div>
              </div>

              {/* Auto Process Checkbox */}
              <label className="row items-center gap-2" style={{ cursor: "pointer", marginTop: 4 }}>
                <input
                  type="checkbox"
                  checked={autoProcess}
                  onChange={(e) => setAutoProcess(e.target.checked)}
                />
                <span>Automatically dispatch YOLOv11 & ByteTrack inference upon upload</span>
              </label>

              {uploadError && (
                <div className="text-crimson font-mono small" style={{ marginTop: 6 }}>
                  ⚠️ {uploadError}
                </div>
              )}

              <div className="row justify-end gap-2" style={{ marginTop: 12 }}>
                <button
                  type="button"
                  className="cm-filter-pill"
                  onClick={() => setShowUpload(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="cm-play-btn"
                  disabled={isUploading || !uploadFile}
                >
                  {isUploading ? "UPLOADING & DISPATCHING..." : "CONFIRM UPLOAD & INGEST"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
