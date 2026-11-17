"""CV Model Registry & Device Manager.
Handles model weight resolution, device selection (CUDA / CPU), and inference caching.
"""

import logging
import os
from typing import Any, Dict

log = logging.getLogger("crimemind.cv")

DEFAULT_MODEL_NAME = os.environ.get("CV_MODEL", "yolo11n.pt")
DEFAULT_DEVICE = os.environ.get("CV_DEVICE", "auto")

# Ensure Ultralytics writes config to project directory rather than roaming AppData
_cfg_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models", "cfg"))
os.makedirs(_cfg_dir, exist_ok=True)
os.environ["YOLO_CONFIG_DIR"] = _cfg_dir


class ModelRegistry:
    """Manages loaded deep learning vision models and hardware device routing."""

    def __init__(self, cache_dir: str | None = None):
        self.cache_dir = cache_dir or os.path.join(os.path.dirname(__file__), "..", "..", "models")
        os.makedirs(self.cache_dir, exist_ok=True)
        self._loaded_models: Dict[str, Any] = {}
        self._device = self._detect_device()
        log.info(f"ModelRegistry initialized with device: {self._device}, cache: {self.cache_dir}")

    def _detect_device(self) -> str:
        if DEFAULT_DEVICE.lower() in ("cpu", "cuda"):
            return DEFAULT_DEVICE.lower()
        try:
            import torch
            if torch.cuda.is_available():
                device_name = torch.cuda.get_device_name(0)
                log.info(f"NVIDIA CUDA available: {device_name}")
                return "cuda:0"
        except Exception as e:
            log.warning(f"CUDA detection failed, falling back to CPU: {e}")
        return "cpu"

    @property
    def device(self) -> str:
        return self._device

    def get_model(self, model_name: str | None = None) -> Any:
        """Retrieves or loads Ultralytics YOLO model instance on the active device."""
        name = model_name or DEFAULT_MODEL_NAME
        if name in self._loaded_models:
            return self._loaded_models[name]

        from ultralytics import YOLO

        model_path = os.path.join(self.cache_dir, name)
        backend_root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", name))
        backend_models_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models", name))

        if os.path.exists(model_path):
            target = model_path
        elif os.path.exists(backend_root_path):
            target = backend_root_path
        elif os.path.exists(backend_models_path):
            target = backend_models_path
        else:
            target = name

        log.info(f"Loading YOLO model from '{target}' onto device '{self._device}'...")
        try:
            model = YOLO(target)
            self._loaded_models[name] = model
            log.info(f"YOLO model '{name}' successfully loaded.")
            return model
        except Exception as err:
            log.error(f"Failed to load YOLO model '{name}': {err}")
            raise


_registry_instance: ModelRegistry | None = None


def get_model_registry() -> ModelRegistry:
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ModelRegistry()
    return _registry_instance
