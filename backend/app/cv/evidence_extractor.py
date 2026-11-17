"""Evidence Extraction & Provenance Module.
Extracts event thumbnails, computes cryptographic SHA-256 digests,
and binds vision events into CrimeMind's Evidence Validity Lifecycle Management (EVLM).
"""

import hashlib
import logging
import os
from typing import Any, Dict

import cv2

log = logging.getLogger("crimemind.cv")


class CVEvidenceExtractor:
    """Creates forensic evidence exhibits from computer vision events."""

    def __init__(self, evidence_dir: str | None = None):
        self.evidence_dir = evidence_dir or os.path.join(
            os.path.dirname(__file__), "..", "..", "storage", "evidence"
        )
        os.makedirs(self.evidence_dir, exist_ok=True)

    def extract_event_keyframe(
        self,
        video_path: str,
        frame_number: int,
        case_ref: str,
        event_id: int,
    ) -> Dict[str, Any]:
        """Extracts a high-resolution keyframe JPEG and calculates its SHA-256 digest."""
        case_out_dir = os.path.join(self.evidence_dir, case_ref)
        os.makedirs(case_out_dir, exist_ok=True)

        cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            log.warning(f"Failed to read frame #{frame_number} from '{video_path}'")
            return {"image_path": None, "sha256": None}

        out_filename = f"ev_frame_{event_id}_f{frame_number}.jpg"
        out_path = os.path.join(case_out_dir, out_filename)
        cv2.imwrite(out_path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])

        # Compute SHA-256
        sha = hashlib.sha256()
        with open(out_path, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        img_hash = sha.hexdigest()

        # Relative path for frontend serving
        rel_path = f"/api/cctv/artifacts/{case_ref}/{out_filename}"

        return {
            "image_path": rel_path,
            "full_path": out_path,
            "sha256": img_hash,
        }
