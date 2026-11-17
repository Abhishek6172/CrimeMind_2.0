"""CV Processing Service Orchestrator.
Asynchronously processes uploaded CCTV footage through YOLO object detection,
ByteTrack tracking, event extraction, and EVLM evidence creation.
"""

import json
import logging
import time
from typing import Any, Dict

import cv2
import psycopg
from psycopg.rows import dict_row

from .. import config, db
from .detector import YOLODetector
from .event_detector import CCTVEventDetector
from .evidence_extractor import CVEvidenceExtractor
from .event_fusion import MultimodalFusionEngine
from .person_analytics import PersonAnalyticsEngine
from .tracker import ByteTracker
from .vehicle_analytics import VehicleAnalyticsEngine

log = logging.getLogger("crimemind.cv")


class CVProcessingService:
    """Orchestrates end-to-end video processing pipelines."""

    def __init__(self):
        self.evidence_extractor = CVEvidenceExtractor()
        self.event_detector = CCTVEventDetector()
        self.person_engine = PersonAnalyticsEngine()
        self.vehicle_engine = VehicleAnalyticsEngine()
        self.fusion_engine = MultimodalFusionEngine()

    def run_pipeline_sync(
        self,
        job_id: int,
        case_id: int,
        video_id: int,
        video_path: str,
        case_ref: str,
        model_name: str = "yolo11n.pt",
        tracker_type: str = "bytetrack",
        confidence_thresh: float = 0.35,
        iou_thresh: float = 0.45,
        frame_skip: int = 1,
    ) -> None:
        """Executes YOLO detection and ByteTrack tracking loop over the video."""
        start_time = time.time()
        log.info(f"[Job {job_id}] Starting CV Pipeline on '{video_path}' (Model: {model_name})")

        with db.connection() as conn:
            conn.execute(
                """
                UPDATE cv_processing_jobs
                SET status = 'PROCESSING', started_at = now()
                WHERE job_id = %s
                """,
                (job_id,),
            )
            conn.commit()

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            err_msg = f"Failed to open video file '{video_path}'"
            log.error(err_msg)
            self._mark_job_failed(job_id, err_msg)
            return

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

        tracker = ByteTracker(
            model_name=model_name,
            tracker_config=f"{tracker_type}.yaml" if not tracker_type.endswith(".yaml") else tracker_type,
            confidence_thresh=confidence_thresh,
            iou_thresh=iou_thresh,
        )

        all_detections = []
        frame_idx = 0
        processed_count = 0

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % frame_skip == 0:
                    t_sec = frame_idx / fps
                    frame_dets = tracker.track_frame(frame, frame_idx, t_sec)
                    all_detections.extend(frame_dets)
                    processed_count += 1

                    # Update progress every 30 frames
                    if processed_count % 30 == 0:
                        pct = round((frame_idx / total_frames) * 100, 1)
                        elapsed = max(0.1, time.time() - start_time)
                        curr_fps = round(processed_count / elapsed, 1)
                        self._update_progress(
                            job_id, pct, frame_idx, total_frames, len(all_detections), len(tracker.active_tracks), curr_fps
                        )

                frame_idx += 1

            cap.release()

            # Summarize tracks and extract events
            tracks = tracker.get_summary_tracks()
            events = self.event_detector.extract_events(tracks, all_detections, video_id)

            log.info(f"[Job {job_id}] Inference complete: {len(all_detections)} detections, {len(tracks)} tracks, {len(events)} events")

            # Persist results in PostgreSQL transaction
            with db.connection() as conn:
                # 1. Bulk insert detections
                if all_detections:
                    det_tuples = [
                        (
                            case_id,
                            video_id,
                            d["frame_number"],
                            d["timestamp_sec"],
                            d["class_name"],
                            d["confidence"],
                            d["bbox"][0],
                            d["bbox"][1],
                            d["bbox"][2],
                            d["bbox"][3],
                            d.get("track_id"),
                        )
                        for d in all_detections
                    ]
                    with conn.cursor() as cur:
                        cur.executemany(
                            """
                            INSERT INTO cv_detections (
                                case_id, video_id, frame_number, timestamp_sec, class_name,
                                confidence, bbox_x1, bbox_y1, bbox_x2, bbox_y2, track_id
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            det_tuples,
                        )

                # 2. Bulk insert tracks
                if tracks:
                    track_tuples = [
                        (
                            case_id,
                            video_id,
                            t["track_id"],
                            t["class_name"],
                            t["first_seen_sec"],
                            t["last_seen_sec"],
                            t["duration_sec"],
                            t["total_frames"],
                            json.dumps(t["trajectory"]),
                            t["max_confidence"],
                        )
                        for t in tracks
                    ]
                    with conn.cursor() as cur:
                        cur.executemany(
                            """
                            INSERT INTO cv_tracks (
                                case_id, video_id, track_id, class_name, first_seen_sec,
                                last_seen_sec, duration_sec, total_frames, trajectory, max_confidence
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (video_id, track_id) DO UPDATE SET
                                last_seen_sec = EXCLUDED.last_seen_sec,
                                duration_sec = EXCLUDED.duration_sec,
                                total_frames = EXCLUDED.total_frames,
                                trajectory = EXCLUDED.trajectory,
                                max_confidence = EXCLUDED.max_confidence
                            """,
                            track_tuples,
                        )

                # 3. Insert events and create EVLM evidence items
                for idx, ev in enumerate(events):
                    # Extract keyframe thumbnail
                    fn = ev.get("frame_number", 0)
                    thumb_data = self.evidence_extractor.extract_event_keyframe(
                        video_path, fn, case_ref, idx + 1
                    )

                    # Create corresponding CrimeMind EVLM Evidence record
                    ev_ref = f"E-CCTV-{video_id}-{idx+1}"
                    row_ev = conn.execute(
                        """
                        INSERT INTO evidence (
                            case_id, ref, evidence_type, source, evidence_timestamp,
                            description, provenance, reliability_score, validity_status
                        ) VALUES (
                            %s, %s, 'CCTV', %s, now(),
                            %s, %s, 0.85, 'SUPPORTED'
                        )
                        ON CONFLICT (case_id, ref) DO UPDATE SET
                            description = EXCLUDED.description
                        RETURNING evidence_id
                        """,
                        (
                            case_id,
                            ev_ref,
                            f"CAM-PROC-{video_id}",
                            ev["description"],
                            json.dumps({
                                "video_id": video_id,
                                "model": model_name,
                                "start_sec": ev["start_sec"],
                                "sha256": thumb_data.get("sha256"),
                                "confidence": ev["confidence"],
                            }),
                        ),
                    ).fetchone()

                    evidence_id = row_ev["evidence_id"] if row_ev else None

                    # Insert into cctv_events
                    conn.execute(
                        """
                        INSERT INTO cctv_events (
                            case_id, video_id, event_type, start_sec, end_sec,
                            track_ids, confidence, description, frame_number,
                            thumbnail_path, evidence_id, verification_status
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'VERIFIED')
                        """,
                        (
                            case_id,
                            video_id,
                            ev["event_type"],
                            ev["start_sec"],
                            ev["end_sec"],
                            ev["track_ids"],
                            ev["confidence"],
                            ev["description"],
                            fn,
                            thumb_data.get("image_path"),
                            evidence_id,
                        ),
                    )

                # 4. Update video status & complete job
                conn.execute(
                    "UPDATE cctv_videos SET status = 'COMPLETED' WHERE video_id = %s",
                    (video_id,),
                )

                elapsed = max(0.1, time.time() - start_time)
                overall_fps = round(processed_count / elapsed, 1)

                conn.execute(
                    """
                    UPDATE cv_processing_jobs
                    SET status = 'COMPLETED', progress_pct = 100.0,
                        frames_processed = %s, total_frames = %s,
                        detections_count = %s, tracks_count = %s,
                        events_count = %s, processing_fps = %s,
                        completed_at = now()
                    WHERE job_id = %s
                    """,
                    (
                        frame_idx,
                        total_frames,
                        len(all_detections),
                        len(tracks),
                        len(events),
                        overall_fps,
                        job_id,
                    ),
                )
                conn.commit()

            log.info(f"[Job {job_id}] Pipeline completed successfully in {elapsed:.1f}s ({overall_fps} FPS)")

        except Exception as e:
            log.exception(f"[Job {job_id}] Processing encountered error: {e}")
            self._mark_job_failed(job_id, str(e))

    def _update_progress(
        self, job_id: int, pct: float, f_proc: int, f_tot: int, d_count: int, t_count: int, fps: float
    ) -> None:
        try:
            with db.connection() as conn:
                conn.execute(
                    """
                    UPDATE cv_processing_jobs
                    SET progress_pct = %s, frames_processed = %s, total_frames = %s,
                        detections_count = %s, tracks_count = %s, processing_fps = %s
                    WHERE job_id = %s
                    """,
                    (pct, f_proc, f_tot, d_count, t_count, fps, job_id),
                )
                conn.commit()
        except Exception:
            pass

    def _mark_job_failed(self, job_id: int, error_msg: str) -> None:
        try:
            with db.connection() as conn:
                conn.execute(
                    """
                    UPDATE cv_processing_jobs
                    SET status = 'FAILED', error_message = %s, completed_at = now()
                    WHERE job_id = %s
                    """,
                    (error_msg, job_id),
                )
                conn.commit()
        except Exception:
            pass
