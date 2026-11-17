"""Pydantic Request & Response Schemas for CCTV Computer Vision Endpoints."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CameraCreate(BaseModel):
    ref: str
    name: str
    resolution: str = "1920x1080"
    fps: float = 30.0
    coverage_zone: Optional[str] = None
    rtsp_url: Optional[str] = None


class CameraOut(BaseModel):
    camera_id: int
    case_id: int
    ref: str
    name: str
    resolution: Optional[str]
    fps: Optional[float]
    coverage_zone: Optional[str]
    is_active: bool


class VideoOut(BaseModel):
    video_id: int
    case_id: int
    camera_id: Optional[int]
    filename: str
    file_size_bytes: int
    sha256_hash: str
    duration_sec: float
    fps: float
    total_frames: int
    width: int
    height: int
    status: str
    created_at: str


class ProcessVideoRequest(BaseModel):
    model_name: str = "yolo11n.pt"
    tracker_type: str = "bytetrack"
    confidence_thresh: float = Field(0.35, ge=0.05, le=0.95)
    iou_thresh: float = Field(0.45, ge=0.05, le=0.95)
    frame_skip: int = Field(1, ge=1, le=10)


class JobStatusOut(BaseModel):
    job_id: int
    case_id: int
    video_id: int
    status: str
    progress_pct: float
    frames_processed: int
    total_frames: int
    detections_count: int
    tracks_count: int
    events_count: int
    processing_fps: float
    error_message: Optional[str]


class DetectionOut(BaseModel):
    detection_id: int
    frame_number: int
    timestamp_sec: float
    class_name: str
    confidence: float
    bbox_x1: float
    bbox_y1: float
    bbox_x2: float
    bbox_y2: float
    track_id: Optional[int]


class TrackOut(BaseModel):
    track_id: int
    class_name: str
    first_seen_sec: float
    last_seen_sec: float
    duration_sec: float
    total_frames: int
    max_confidence: float
    trajectory: List[Dict[str, Any]]


class EventOut(BaseModel):
    event_id: int
    case_id: int
    video_id: int
    event_type: str
    start_sec: float
    end_sec: float
    track_ids: List[int]
    confidence: float
    description: str
    thumbnail_path: Optional[str]
    evidence_id: Optional[int]
    verification_status: str
