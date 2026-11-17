-- =====================================================================
-- CrimeMind — 009_cv_cctv.sql
-- Real Deep Learning & Computer Vision Subsystem Schema
-- Supports YOLO object detection, ByteTrack multi-object tracking,
-- event extraction, video evidence provenance, and multimodal fusion.
-- =====================================================================

-- 1. Camera Management Subsystem
CREATE TABLE IF NOT EXISTS cctv_cameras (
  camera_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id            bigint NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  ref                text   NOT NULL,                 -- e.g. CAM-01, CAM-EAST-P01
  name               text   NOT NULL,
  location_entity_id bigint,
  resolution         text   DEFAULT '1920x1080',
  fps                numeric(5,2) DEFAULT 30.00,
  rtsp_url           text,
  coverage_zone      text,                            -- descriptive zone e.g. "East Perimeter Gate"
  calibration_data   jsonb  NOT NULL DEFAULT '{}'::jsonb,
  is_active          boolean NOT NULL DEFAULT true,
  created_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (case_id, ref),
  UNIQUE (case_id, camera_id),
  FOREIGN KEY (case_id, location_entity_id) REFERENCES entities(case_id, entity_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_cctv_cameras_case ON cctv_cameras(case_id);

-- 2. Ingested CCTV Video Storage & Metadata
CREATE TABLE IF NOT EXISTS cctv_videos (
  video_id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id            bigint NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  camera_id          bigint,
  filename           text   NOT NULL,
  file_path          text   NOT NULL,
  file_size_bytes    bigint NOT NULL,
  sha256_hash        text   NOT NULL,
  duration_sec       numeric(8,3) DEFAULT 0.000,
  fps                numeric(5,2) DEFAULT 30.00,
  total_frames       integer DEFAULT 0,
  width              integer DEFAULT 1920,
  height             integer DEFAULT 1080,
  mime_type          text   NOT NULL DEFAULT 'video/mp4',
  recorded_start     timestamptz,
  status             text   NOT NULL DEFAULT 'UPLOADED' CHECK (status IN ('UPLOADED','PROCESSING','COMPLETED','FAILED')),
  evidence_id        bigint,
  created_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (case_id, video_id),
  FOREIGN KEY (case_id, camera_id) REFERENCES cctv_cameras(case_id, camera_id) ON DELETE SET NULL,
  FOREIGN KEY (case_id, evidence_id) REFERENCES evidence(case_id, evidence_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_cctv_videos_case ON cctv_videos(case_id);

-- 3. Asynchronous Computer Vision Processing Jobs
CREATE TABLE IF NOT EXISTS cv_processing_jobs (
  job_id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id            bigint NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  video_id           bigint NOT NULL,
  model_name         text   NOT NULL DEFAULT 'yolo11n.pt',
  tracker_type       text   NOT NULL DEFAULT 'bytetrack',
  confidence_thresh  numeric(3,2) NOT NULL DEFAULT 0.35,
  iou_thresh         numeric(3,2) NOT NULL DEFAULT 0.45,
  frame_skip         integer NOT NULL DEFAULT 1,
  status             text   NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED','PROCESSING','COMPLETED','FAILED','CANCELLED')),
  progress_pct       numeric(5,2) NOT NULL DEFAULT 0.00,
  frames_processed   integer NOT NULL DEFAULT 0,
  total_frames       integer NOT NULL DEFAULT 0,
  detections_count   integer NOT NULL DEFAULT 0,
  tracks_count       integer NOT NULL DEFAULT 0,
  events_count       integer NOT NULL DEFAULT 0,
  processing_fps     numeric(6,2) DEFAULT 0.00,
  error_message      text,
  started_at         timestamptz,
  completed_at       timestamptz,
  created_at         timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (case_id, video_id) REFERENCES cctv_videos(case_id, video_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_cv_jobs_case ON cv_processing_jobs(case_id, status);

-- 4. Deep Learning Frame-by-Frame Detections
CREATE TABLE IF NOT EXISTS cv_detections (
  detection_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id            bigint NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  video_id           bigint NOT NULL,
  frame_number       integer NOT NULL,
  timestamp_sec      numeric(8,3) NOT NULL,
  class_name         text   NOT NULL,                 -- person, car, motorcycle, bus, truck, bicycle
  confidence         numeric(4,3) NOT NULL,
  bbox_x1            numeric(8,2) NOT NULL,           -- normalized or pixel coords
  bbox_y1            numeric(8,2) NOT NULL,
  bbox_x2            numeric(8,2) NOT NULL,
  bbox_y2            numeric(8,2) NOT NULL,
  track_id           integer,                         -- ByteTrack assigned persistent track ID
  FOREIGN KEY (case_id, video_id) REFERENCES cctv_videos(case_id, video_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_cv_det_video_frame ON cv_detections(video_id, frame_number);
CREATE INDEX IF NOT EXISTS idx_cv_det_track ON cv_detections(video_id, track_id);
CREATE INDEX IF NOT EXISTS idx_cv_det_class ON cv_detections(case_id, class_name);

-- 5. Persistent ByteTrack Multi-Object Tracks
CREATE TABLE IF NOT EXISTS cv_tracks (
  track_pk           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id            bigint NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  video_id           bigint NOT NULL,
  track_id           integer NOT NULL,
  class_name         text   NOT NULL,
  first_seen_sec     numeric(8,3) NOT NULL,
  last_seen_sec      numeric(8,3) NOT NULL,
  duration_sec       numeric(8,3) NOT NULL,
  total_frames       integer NOT NULL DEFAULT 1,
  trajectory         jsonb  NOT NULL DEFAULT '[]'::jsonb, -- array of {frame, sec, x, y}
  max_confidence     numeric(4,3) NOT NULL,
  entity_match_id    bigint,                          -- tentative link to case entity if correlated
  UNIQUE (video_id, track_id),
  FOREIGN KEY (case_id, video_id) REFERENCES cctv_videos(case_id, video_id) ON DELETE CASCADE,
  FOREIGN KEY (case_id, entity_match_id) REFERENCES entities(case_id, entity_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_cv_tracks_video ON cv_tracks(video_id);

-- 6. CCTV Event Detection Engine Output
CREATE TABLE IF NOT EXISTS cctv_events (
  event_id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id            bigint NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  video_id           bigint NOT NULL,
  camera_id          bigint,
  event_type         text   NOT NULL,                 -- RESTRICTED_ENTRY, LOITERING, RAPID_DEPARTURE, GATHERING, OBJECT_STATIONARY
  start_sec          numeric(8,3) NOT NULL,
  end_sec            numeric(8,3) NOT NULL,
  track_ids          integer[] NOT NULL DEFAULT '{}',
  confidence         numeric(3,2) NOT NULL DEFAULT 0.85,
  description        text   NOT NULL,
  frame_number       integer,
  thumbnail_path     text,
  clip_path          text,
  evidence_id        bigint,                          -- EVLM Evidence record created for this event
  verification_status text  NOT NULL DEFAULT 'PENDING' CHECK (verification_status IN ('PENDING','VERIFIED','CHALLENGED','DISMISSED')),
  metadata           jsonb  NOT NULL DEFAULT '{}'::jsonb,
  created_at         timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (case_id, video_id) REFERENCES cctv_videos(case_id, video_id) ON DELETE CASCADE,
  FOREIGN KEY (case_id, camera_id) REFERENCES cctv_cameras(case_id, camera_id) ON DELETE SET NULL,
  FOREIGN KEY (case_id, evidence_id) REFERENCES evidence(case_id, evidence_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_cctv_events_case ON cctv_events(case_id, event_type);

-- 7. Event Keyframe Artifacts
CREATE TABLE IF NOT EXISTS cctv_event_frames (
  frame_id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  event_id           bigint NOT NULL REFERENCES cctv_events(event_id) ON DELETE CASCADE,
  case_id            bigint NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  frame_number       integer NOT NULL,
  timestamp_sec      numeric(8,3) NOT NULL,
  image_path         text   NOT NULL,
  sha256_hash        text   NOT NULL,
  created_at         timestamptz NOT NULL DEFAULT now()
);

-- 8. Audio Forensics Extension Events
CREATE TABLE IF NOT EXISTS cctv_audio_events (
  audio_event_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id            bigint NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  video_id           bigint NOT NULL,
  sound_category     text   NOT NULL,                 -- GLASS_BREAK, GUNSHOT_LIKE, SIREN, IMPACT, ALARM
  start_sec          numeric(8,3) NOT NULL,
  end_sec            numeric(8,3) NOT NULL,
  confidence         numeric(3,2) NOT NULL,
  model_name         text   NOT NULL DEFAULT 'audio-spec-v1',
  evidence_id        bigint,
  created_at         timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (case_id, video_id) REFERENCES cctv_videos(case_id, video_id) ON DELETE CASCADE,
  FOREIGN KEY (case_id, evidence_id) REFERENCES evidence(case_id, evidence_id) ON DELETE SET NULL
);

-- 9. Multimodal Event Correlations
CREATE TABLE IF NOT EXISTS cctv_event_correlations (
  correlation_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_id             bigint NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
  primary_event_id    bigint NOT NULL REFERENCES cctv_events(event_id) ON DELETE CASCADE,
  correlated_event_id bigint REFERENCES cctv_events(event_id) ON DELETE CASCADE,
  audio_event_id      bigint REFERENCES cctv_audio_events(audio_event_id) ON DELETE CASCADE,
  correlation_type    text   NOT NULL,                -- AUDIO_VISUAL_SYNC, MULTI_CAMERA_TRAIL, SUSPICIOUS_COINCIDENCE
  time_diff_sec       numeric(8,3) NOT NULL DEFAULT 0.000,
  confidence          numeric(3,2) NOT NULL DEFAULT 0.80,
  description         text   NOT NULL,
  created_at          timestamptz NOT NULL DEFAULT now()
);

-- 10. CV Model Registry Table
CREATE TABLE IF NOT EXISTS cv_model_registry (
  model_id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  model_name         text   NOT NULL UNIQUE,          -- yolo11n.pt, yolov8n.pt
  task               text   NOT NULL DEFAULT 'detect',
  version            text   NOT NULL DEFAULT '11.0.0',
  is_default         boolean NOT NULL DEFAULT false,
  weights_path       text   NOT NULL,
  input_size         integer NOT NULL DEFAULT 640,
  supported_classes  jsonb  NOT NULL DEFAULT '["person","car","motorcycle","bus","truck","bicycle"]'::jsonb,
  created_at         timestamptz NOT NULL DEFAULT now()
);

-- Seed default model registry entry
INSERT INTO cv_model_registry (model_name, task, version, is_default, weights_path, input_size)
VALUES ('yolo11n.pt', 'detect', '11.0.0', true, 'yolo11n.pt', 640)
ON CONFLICT (model_name) DO NOTHING;
