"""Ultralytics YOLO Object Detector.
Executes actual deep learning inference on video frames.
"""

import logging
from typing import Any, Dict, List

import numpy as np

from .model_registry import get_model_registry

log = logging.getLogger("crimemind.cv")

# Target forensic classes of investigative interest
INTEREST_CLASSES = {
    "person",
    "car",
    "motorcycle",
    "bus",
    "truck",
    "bicycle",
    "backpack",
    "handbag",
    "suitcase",
    "knife",
}


class YOLODetector:
    """Performs deep learning object detection on CCTV imagery."""

    def __init__(
        self,
        model_name: str = "yolo11n.pt",
        confidence_thresh: float = 0.35,
        iou_thresh: float = 0.45,
    ):
        self.model_name = model_name
        self.confidence_thresh = confidence_thresh
        self.iou_thresh = iou_thresh
        self.registry = get_model_registry()
        self.model = self.registry.get_model(model_name)

    def detect_frame(
        self, frame: np.ndarray, frame_number: int, timestamp_sec: float
    ) -> List[Dict[str, Any]]:
        """Runs model inference on a single BGR video frame."""
        results = self.model(
            frame,
            conf=self.confidence_thresh,
            iou=self.iou_thresh,
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

            # Bounding box coordinates [x1, y1, x2, y2]
            xyxy = box.xyxy[0].tolist()
            x1, y1, x2, y2 = [round(v, 2) for v in xyxy]

            detections.append(
                {
                    "frame_number": frame_number,
                    "timestamp_sec": round(timestamp_sec, 3),
                    "class_name": cls_name,
                    "confidence": round(conf, 3),
                    "bbox": [x1, y1, x2, y2],
                    "is_interest_class": cls_name in INTEREST_CLASSES,
                }
            )

        return detections
