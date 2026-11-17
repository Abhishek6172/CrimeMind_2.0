"""CrimeMind Deep Learning & Computer Vision Subsystem.
Modular real-time and batch video analytics using Ultralytics YOLO & ByteTrack.
"""

from .model_registry import ModelRegistry, get_model_registry
from .video_ingestion import VideoIngestionService
from .detector import YOLODetector
from .tracker import ByteTracker
from .person_analytics import PersonAnalyticsEngine
from .vehicle_analytics import VehicleAnalyticsEngine
from .event_detector import CCTVEventDetector
from .evidence_extractor import CVEvidenceExtractor
from .event_fusion import MultimodalFusionEngine
from .service import CVProcessingService

__all__ = [
    "ModelRegistry",
    "get_model_registry",
    "VideoIngestionService",
    "YOLODetector",
    "ByteTracker",
    "PersonAnalyticsEngine",
    "VehicleAnalyticsEngine",
    "CCTVEventDetector",
    "CVEvidenceExtractor",
    "MultimodalFusionEngine",
    "CVProcessingService",
]
