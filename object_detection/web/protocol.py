"""Validation and wire-format helpers for the detection web API."""

from collections.abc import Mapping
from dataclasses import dataclass
import math
from numbers import Integral, Real
from typing import Any, Dict, Iterable, Optional, Tuple

from ..domain import Detection, FrameDetections

MAX_FRAME_BYTES = 8 * 1024 * 1024


class ProtocolError(ValueError):
    """Raised when a client message does not satisfy the wire protocol."""


@dataclass(frozen=True)
class DetectionConfig:
    """Validated inference settings for one WebSocket connection."""

    confidence: float = 0.5
    iou: float = 0.45
    classes: Optional[Tuple[int, ...]] = None
    tracking: bool = False

    def __post_init__(self) -> None:
        confidence = _threshold("confidence", self.confidence)
        iou = _threshold("iou", self.iou)
        classes = _classes(self.classes)
        if not isinstance(self.tracking, bool):
            raise ProtocolError("tracking must be a boolean")

        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "iou", iou)
        object.__setattr__(self, "classes", classes)


def parse_config_message(
    payload: Any,
    current: Optional[DetectionConfig] = None,
) -> DetectionConfig:
    """Parse a full or partial ``configure`` client message."""
    if not isinstance(payload, Mapping):
        raise ProtocolError("configuration message must be a JSON object")
    if payload.get("type") != "configure":
        raise ProtocolError("message type must be 'configure'")

    allowed = {"type", "confidence", "iou", "classes", "tracking"}
    unknown = sorted(str(key) for key in payload.keys() if key not in allowed)
    if unknown:
        raise ProtocolError(
            "unknown configuration field(s): {}".format(", ".join(unknown))
        )

    base = current or DetectionConfig()
    return DetectionConfig(
        confidence=payload.get("confidence", base.confidence),
        iou=payload.get("iou", base.iou),
        classes=payload.get("classes", base.classes),
        tracking=payload.get("tracking", base.tracking),
    )


def configured_message(config: DetectionConfig) -> Dict[str, Any]:
    """Serialize the server acknowledgement for a configuration change."""
    return {
        "type": "configured",
        "confidence": config.confidence,
        "iou": config.iou,
        "classes": list(config.classes) if config.classes is not None else None,
        "tracking": config.tracking,
    }


def status_message(
    model: str,
    ready: bool,
    device: Any,
) -> Dict[str, Any]:
    """Serialize the initial WebSocket runtime status."""
    return {
        "type": "status",
        "status": "ok",
        "model": model,
        "ready": ready,
        "device": device,
    }


def error_message(
    code: str,
    message: str,
    frame_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Serialize a recoverable protocol or frame-processing error."""
    payload: Dict[str, Any] = {
        "type": "error",
        "code": code,
        "message": message,
    }
    if frame_id is not None:
        payload["frameId"] = frame_id
    return payload


def detection_message(detection: Detection) -> Dict[str, Any]:
    """Serialize one domain detection using the public camelCase schema."""
    return {
        "x1": detection.x1,
        "y1": detection.y1,
        "x2": detection.x2,
        "y2": detection.y2,
        "confidence": detection.confidence,
        "classId": detection.class_id,
        "label": detection.label,
        "trackId": detection.track_id,
    }


def result_message(
    frame_id: int,
    width: int,
    height: int,
    detections: FrameDetections,
    total_ms: float,
    timestamp: float,
) -> Dict[str, Any]:
    """Serialize the result for one submitted JPEG frame."""
    if isinstance(frame_id, bool) or not isinstance(frame_id, Integral) or frame_id < 0:
        raise ValueError("frame_id must be a non-negative integer")
    if (
        isinstance(width, bool)
        or not isinstance(width, Integral)
        or isinstance(height, bool)
        or not isinstance(height, Integral)
        or width <= 0
        or height <= 0
    ):
        raise ValueError("width and height must be positive integers")

    total = _finite_non_negative("total_ms", total_ms)
    captured_at = _finite_non_negative("timestamp", timestamp)
    return {
        "type": "result",
        "frameId": int(frame_id),
        "width": int(width),
        "height": int(height),
        "inferenceMs": detections.inference_ms,
        "totalMs": total,
        "detections": [
            detection_message(detection) for detection in detections.detections
        ],
        "classCounts": detections.class_counts,
        "timestamp": captured_at,
    }


def _threshold(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ProtocolError("{} must be a number between 0 and 1".format(name))
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ProtocolError("{} must be between 0 and 1".format(name))
    return normalized


def _classes(values: Any) -> Optional[Tuple[int, ...]]:
    if values is None:
        return None
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(
        values, Iterable
    ):
        raise ProtocolError(
            "classes must be null or a list of non-negative integers"
        )

    classes = []
    seen = set()
    for value in values:
        if (
            isinstance(value, bool)
            or not isinstance(value, Integral)
            or value < 0
        ):
            raise ProtocolError(
                "classes must be null or a list of non-negative integers"
            )
        class_id = int(value)
        if class_id not in seen:
            classes.append(class_id)
            seen.add(class_id)
    return tuple(classes)


def _finite_non_negative(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("{} must be a non-negative finite number".format(name))
    normalized = float(value)
    if not math.isfinite(normalized) or normalized < 0.0:
        raise ValueError("{} must be a non-negative finite number".format(name))
    return normalized


__all__ = [
    "DetectionConfig",
    "MAX_FRAME_BYTES",
    "ProtocolError",
    "configured_message",
    "detection_message",
    "error_message",
    "parse_config_message",
    "result_message",
    "status_message",
]
