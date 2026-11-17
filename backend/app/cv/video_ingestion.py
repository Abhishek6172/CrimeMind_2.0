"""Video Ingestion and Validation Service.
Extracts video metadata, computes cryptographic SHA-256 hashes, and registers footage in the database.
"""

import hashlib
import logging
import os
import shutil
from typing import Any, Dict

import cv2

log = logging.getLogger("crimemind.cv")

ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
MAX_VIDEO_SIZE_BYTES = int(os.environ.get("CV_MAX_VIDEO_SIZE_MB", "500")) * 1024 * 1024


class VideoIngestionService:
    """Manages file persistence, validation, and metadata extraction for CCTV uploads."""

    def __init__(self, storage_root: str | None = None):
        self.storage_root = storage_root or os.path.join(
            os.path.dirname(__file__), "..", "..", "storage", "cctv"
        )
        os.makedirs(self.storage_root, exist_ok=True)

    def validate_file(self, filename: str, file_size: int) -> None:
        """Validates format extension and file size."""
        _, ext = os.path.splitext(filename.lower())
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Unsupported video format '{ext}'. Supported formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )
        if file_size > MAX_VIDEO_SIZE_BYTES:
            max_mb = MAX_VIDEO_SIZE_BYTES // (1024 * 1024)
            raise ValueError(
                f"File size exceeds limit of {max_mb} MB (received {file_size / (1024*1024):.1f} MB)"
            )

    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extracts FPS, duration, resolution, total frames, and SHA-256 hash from video."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                sha256.update(chunk)
        file_hash = sha256.hexdigest()

        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file '{file_path}' with OpenCV")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration_sec = total_frames / fps if fps > 0 else 0.0

        cap.release()

        return {
            "fps": round(float(fps), 2),
            "width": width,
            "height": height,
            "total_frames": total_frames,
            "duration_sec": round(float(duration_sec), 3),
            "sha256_hash": file_hash,
            "file_size_bytes": os.path.getsize(file_path),
        }

    def save_upload(self, case_ref: str, filename: str, src_stream) -> str:
        """Saves uploaded video stream to case storage directory."""
        case_dir = os.path.join(self.storage_root, case_ref)
        os.makedirs(case_dir, exist_ok=True)
        dest_path = os.path.join(case_dir, filename)

        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(src_stream, buffer)

        return dest_path
