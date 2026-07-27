"""Optional web API for real-time object detection."""

from .api import create_app
from .protocol import DetectionConfig, ProtocolError
from .runtime import DetectionRuntime

__all__ = [
    "DetectionConfig",
    "DetectionRuntime",
    "ProtocolError",
    "create_app",
]
