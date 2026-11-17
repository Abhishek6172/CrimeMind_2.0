"""ByteTrack Multi-Object Tracking Module.
Maintains persistent track IDs, trajectories, and temporal lifecycle across frames.
"""

import logging
from typing import Any, Dict, List

import numpy as np

from .model_registry import get_model_registry

log = logging.getLogger("crimemind.cv")


class ByteTracker:
    """ByteTrack wrapper leveraging Ultralytics tracking engine."""

    def __init__(
        self,
        model_name: str = "yolo11n.pt",
        tracker_config: str = "bytetrack.yaml",
        confidence_thresh: float = 0.35,
        iou_thresh: float = 0.45,
    ):
        self.model_name = model_name
        self.tracker_config = tracker_config
        self.confidence_thresh = confidence_thresh
        self.iou_thresh = iou_thresh
        self.registry = get_model_registry()
        self.model = self.registry.get_model(model_name)

        # Tracks lifecycle state cache
        # track_id -> { track_id, class_name, first_seen_sec, last_seen_sec, total_frames, trajectory: [], max_conf }
        self.active_tracks: Dict[int, Dict[str, Any]] = {}

    def track_frame(
        self, frame: np.ndarray, frame_number: int, timestamp_sec: float
    ) -> List[Dict[str, Any]]:
        """Runs tracking on a frame and updates persistent trajectory states."""
        results = self.model.track(
            frame,
            conf=self.confidence_thresh,
            iou=self.iou_thresh,
            persist=True,
            tracker=self.tracker_config,
            device=self.registry.device,
            verbose=False,
        )

        detections = []
        if not results:
            return detections

        res = results[0]
        boxes = res.boxes
        if boxes is None or len(boxes) == 0:
            return detections

        names = res.names
        for box in boxes:
            cls_id = int(box.cls[0].item())
            cls_name = names.get(cls_id, f"class_{cls_id}").lower()
            conf = float(box.conf[0].item())
            xyxy = box.xyxy[0].tolist()
            x1, y1, x2, y2 = [round(v, 2) for v in xyxy]

            track_id = int(box.id[0].item()) if box.id is not None else None

            # Calculate center coordinate for trajectory tracking
            cx = round((x1 + x2) / 2.0, 2)
            cy = round((y1 + y2) / 2.0, 2)

            if track_id is not None:
                if track_id not in self.active_tracks:
                    self.active_tracks[track_id] = {
                        "track_id": track_id,
                        "class_name": cls_name,
                        "first_seen_sec": round(timestamp_sec, 3),
                        "last_seen_sec": round(timestamp_sec, 3),
                        "total_frames": 1,
                        "trajectory": [{"frame": frame_number, "sec": round(timestamp_sec, 3), "x": cx, "y": cy}],
                        "max_confidence": round(conf, 3),
                    }
                else:
                    t = self.active_tracks[track_id]
                    t["last_seen_sec"] = round(timestamp_sec, 3)
                    t["total_frames"] += 1
                    t["max_confidence"] = max(t["max_confidence"], round(conf, 3))
                    t["trajectory"].append({"frame": frame_number, "sec": round(timestamp_sec, 3), "x": cx, "y": cy})

            detections.append(
                {
                    "frame_number": frame_number,
                    "timestamp_sec": round(timestamp_sec, 3),
                    "class_name": cls_name,
                    "confidence": round(conf, 3),
                    "bbox": [x1, y1, x2, y2],
                    "track_id": track_id,
                    "center": [cx, cy],
                }
            )

        return detections

    def get_summary_tracks(self) -> List[Dict[str, Any]]:
        """Returns summarized track records formatted for database insertion."""
        tracks = []
        for tid, t in self.active_tracks.items():
            dur = max(0.0, t["last_seen_sec"] - t["first_seen_sec"])
            tracks.append(
                {
                    "track_id": tid,
                    "class_name": t["class_name"],
                    "first_seen_sec": t["first_seen_sec"],
                    "last_seen_sec": t["last_seen_sec"],
                    "duration_sec": round(dur, 3),
                    "total_frames": t["total_frames"],
                    "trajectory": t["trajectory"],
                    "max_confidence": t["max_confidence"],
                }
            )
        return sorted(tracks, key=lambda x: x["first_seen_sec"])
