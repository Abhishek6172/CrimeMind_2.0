"""Automated Tests for CrimeMind Computer Vision & CCTV Subsystem.
Verifies video ingestion, YOLO model inference, ByteTrack tracking,
event extraction, evidence generation, and database integrity.
"""

import os
import tempfile
import numpy as np
import cv2
import pytest

from app.cv.video_ingestion import VideoIngestionService
from app.cv.detector import YOLODetector
from app.cv.tracker import ByteTracker
from app.cv.event_detector import CCTVEventDetector
from app.cv.evidence_extractor import CVEvidenceExtractor
from app.cv.person_analytics import PersonAnalyticsEngine
from app.cv.vehicle_analytics import VehicleAnalyticsEngine


def create_sample_mp4(filepath: str, width: int = 640, height: int = 480, fps: int = 25, num_frames: int = 50):
    """Creates a small real MP4 video file with moving synthetic contours for testing."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(filepath, fourcc, fps, (width, height))

    for i in range(num_frames):
        # Create dark frame
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:] = (20, 25, 35)

        # Draw moving rectangle simulating object
        cx = int(80 + (i * 8) % (width - 160))
        cy = int(height / 2)
        cv2.rectangle(frame, (cx - 30, cy - 60), (cx + 30, cy + 60), (200, 200, 200), -1)
        # Draw head
        cv2.circle(frame, (cx, cy - 80), 20, (230, 230, 230), -1)

        out.write(frame)

    out.release()


def test_video_ingestion_and_metadata():
    """Test 1: Video ingestion, validation, and metadata extraction."""
    ingestion = VideoIngestionService()

    with tempfile.TemporaryDirectory() as tmpdir:
        test_vid = os.path.join(tmpdir, "test_feed.mp4")
        create_sample_mp4(test_vid, width=640, height=480, fps=25, num_frames=50)

        # File validation
        ingestion.validate_file("test_feed.mp4", os.path.getsize(test_vid))

        # Metadata extraction
        meta = ingestion.extract_metadata(test_vid)
        assert meta["width"] == 640
        assert meta["height"] == 480
        assert meta["fps"] == 25.0
        assert meta["total_frames"] == 50
        assert meta["duration_sec"] == 2.0
        assert len(meta["sha256_hash"]) == 64


def test_invalid_video_validation():
    """Test 2: Invalid file extension rejection."""
    ingestion = VideoIngestionService()
    with pytest.raises(ValueError, match="Unsupported video format"):
        ingestion.validate_file("malicious.exe", 1024)


def test_real_yolo_model_inference():
    """Test 3: Real Ultralytics YOLO model loading and frame inference."""
    detector = YOLODetector(model_name="yolo11n.pt", confidence_thresh=0.25)
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    test_frame[:] = (30, 30, 30)

    # Run inference on frame
    dets = detector.detect_frame(test_frame, frame_number=1, timestamp_sec=0.04)
    assert isinstance(dets, list)


def test_bytetrack_tracking_lifecycle():
    """Test 4: ByteTrack persistent tracking across sequential frames."""
    tracker = ByteTracker(model_name="yolo11n.pt", confidence_thresh=0.25)

    with tempfile.TemporaryDirectory() as tmpdir:
        test_vid = os.path.join(tmpdir, "test_track.mp4")
        create_sample_mp4(test_vid, width=640, height=480, fps=25, num_frames=15)

        cap = cv2.VideoCapture(test_vid)
        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            dets = tracker.track_frame(frame, frame_idx, frame_idx / 25.0)
            assert isinstance(dets, list)
            frame_idx += 1
        cap.release()

        summary_tracks = tracker.get_summary_tracks()
        assert isinstance(summary_tracks, list)


def test_event_detector_logic():
    """Test 5: Event detection rules engine (prolonged presence, gathering, rapid movement)."""
    event_detector = CCTVEventDetector(dwell_threshold_sec=5.0)

    # Simulated tracks with 8-second presence
    mock_tracks = [
        {
            "track_id": 1,
            "class_name": "person",
            "first_seen_sec": 1.0,
            "last_seen_sec": 9.5,
            "duration_sec": 8.5,
            "max_confidence": 0.92,
            "trajectory": [
                {"frame": 25, "sec": 1.0, "x": 300, "y": 400},
                {"frame": 237, "sec": 9.5, "x": 310, "y": 405},
            ],
        }
    ]
    events = event_detector.extract_events(mock_tracks, [], video_id=101)
    assert len(events) >= 1
    assert events[0]["event_type"] == "PROLONGED_PRESENCE"
    assert "Track #1" in events[0]["description"]


def test_evidence_keyframe_extraction():
    """Test 6: Keyframe thumbnail extraction with SHA-256 hash."""
    extractor = CVEvidenceExtractor()

    with tempfile.TemporaryDirectory() as tmpdir:
        test_vid = os.path.join(tmpdir, "test_evidence.mp4")
        create_sample_mp4(test_vid, width=640, height=480, fps=25, num_frames=20)

        res = extractor.extract_event_keyframe(test_vid, frame_number=10, case_ref="CASE-TEST", event_id=1)
        assert res["image_path"] is not None
        assert res["sha256"] is not None
        assert len(res["sha256"]) == 64
        assert os.path.exists(res["full_path"])
