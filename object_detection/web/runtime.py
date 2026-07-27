"""Lazy, concurrency-safe runtime used by the detection web API."""

import asyncio
from collections.abc import Mapping, Sequence
import time
from typing import Any, Callable, Dict, List, Optional

from ..domain import FrameDetections
from .protocol import (
    DetectionConfig,
    MAX_FRAME_BYTES,
    result_message,
)


class FramePayloadError(ValueError):
    """Raised when a binary WebSocket frame is not a valid JPEG payload."""


class FrameTooLargeError(FramePayloadError):
    """Raised when a frame exceeds the public payload limit."""


class FrameDecodeError(FramePayloadError):
    """Raised when OpenCV cannot decode a submitted JPEG."""


class DetectorUnavailableError(RuntimeError):
    """Raised when the lazy detector cannot be constructed."""


def decode_jpeg(payload: bytes) -> Any:
    """Decode JPEG bytes while keeping OpenCV and NumPy optional at import time."""
    try:
        import cv2
        import numpy as np
    except (ImportError, ModuleNotFoundError) as exc:
        raise FrameDecodeError(
            "JPEG decoding requires OpenCV and NumPy"
        ) from exc

    encoded = np.frombuffer(payload, dtype=np.uint8)
    frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if frame is None:
        raise FrameDecodeError("payload is not a decodable JPEG image")
    return frame


def _default_detector_factory(model_path: str) -> Any:
    from ..model import YOLODetector

    return YOLODetector(model_path=model_path)


class DetectionRuntime:
    """Own one lazily-loaded detector and serialize access to its model."""

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        *,
        detector: Optional[Any] = None,
        decoder: Optional[Callable[[bytes], Any]] = None,
        detector_factory: Optional[Callable[[str], Any]] = None,
        monotonic: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        self.model_path = str(model_path)
        self._detector = detector
        self._decoder = decoder or decode_jpeg
        self._detector_factory = detector_factory or _default_detector_factory
        self._monotonic = monotonic
        self._wall_clock = wall_clock
        self._lock = asyncio.Lock()
        self._load_attempted = detector is not None
        self._load_error: Optional[BaseException] = None

    @property
    def ready(self) -> bool:
        """Whether a detector has been loaded successfully."""
        return self._detector is not None

    @property
    def device(self) -> Any:
        """Configured model device, or ``None`` before model loading."""
        if self._detector is None:
            return None
        return getattr(self._detector, "device", None)

    def health(self) -> Dict[str, Any]:
        """Return the stable REST health response without forcing model loading."""
        return {
            "status": "ok",
            "model": self.model_path,
            "ready": self.ready,
            "device": self.device,
        }

    def class_names(self) -> List[str]:
        """Return class names exposed by the loaded model, if any."""
        detector = self._detector
        if detector is None:
            return []

        names = getattr(detector, "names", None)
        if names is None:
            model = getattr(detector, "_model", None)
            names = getattr(model, "names", None)
        if isinstance(names, Mapping):
            try:
                keys = sorted(names.keys(), key=lambda key: int(key))
            except (TypeError, ValueError):
                keys = list(names.keys())
            return [str(names[key]) for key in keys]
        if isinstance(names, Sequence) and not isinstance(
            names, (str, bytes, bytearray)
        ):
            return [str(name) for name in names]
        return []

    async def process_frame(
        self,
        payload: bytes,
        frame_id: int,
        config: Optional[DetectionConfig] = None,
    ) -> Dict[str, Any]:
        """Decode, detect, and serialize one binary JPEG frame."""
        encoded = _validated_payload(payload)
        active_config = config or DetectionConfig()
        started_at = self._monotonic()

        try:
            frame = await asyncio.to_thread(self._decoder, encoded)
        except FramePayloadError:
            raise
        except Exception as exc:
            raise FrameDecodeError("payload is not a decodable JPEG image") from exc

        width, height = _frame_dimensions(frame)

        async with self._lock:
            detector = await self._get_detector_locked()
            _configure_detector(detector, active_config)
            detections = await asyncio.to_thread(detector.detect, frame)

        if not isinstance(detections, FrameDetections):
            raise TypeError("detector.detect() must return FrameDetections")

        elapsed_ms = max(0.0, (self._monotonic() - started_at) * 1000.0)
        return result_message(
            frame_id=frame_id,
            width=width,
            height=height,
            detections=detections,
            total_ms=elapsed_ms,
            timestamp=self._wall_clock(),
        )

    async def _get_detector_locked(self) -> Any:
        if self._detector is not None:
            return self._detector
        if self._load_attempted:
            detail = str(self._load_error) if self._load_error else "unknown error"
            raise DetectorUnavailableError(
                "object detection model is unavailable: {}".format(detail)
            )

        self._load_attempted = True
        try:
            self._detector = await asyncio.to_thread(
                self._detector_factory, self.model_path
            )
        except Exception as exc:
            self._load_error = exc
            raise DetectorUnavailableError(
                "object detection model is unavailable: {}".format(exc)
            ) from exc
        return self._detector


def _validated_payload(payload: Any) -> bytes:
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise FramePayloadError("frame payload must be binary JPEG data")
    encoded = bytes(payload)
    if not encoded:
        raise FramePayloadError("frame payload must not be empty")
    if len(encoded) > MAX_FRAME_BYTES:
        raise FrameTooLargeError(
            "frame payload exceeds the {} byte limit".format(MAX_FRAME_BYTES)
        )
    return encoded


def _frame_dimensions(frame: Any) -> tuple:
    shape = getattr(frame, "shape", None)
    if not isinstance(shape, Sequence) or len(shape) < 2:
        raise FrameDecodeError("decoded frame does not expose image dimensions")
    try:
        height = int(shape[0])
        width = int(shape[1])
    except (TypeError, ValueError) as exc:
        raise FrameDecodeError("decoded frame has invalid image dimensions") from exc
    if width <= 0 or height <= 0:
        raise FrameDecodeError("decoded frame has invalid image dimensions")
    return width, height


def _configure_detector(detector: Any, config: DetectionConfig) -> None:
    configure = getattr(detector, "configure", None)
    if callable(configure):
        configure(
            confidence=config.confidence,
            iou=config.iou,
            classes=config.classes,
            tracking=config.tracking,
        )
        return

    values = {
        "confidence": config.confidence,
        "iou": config.iou,
        "classes": config.classes,
        "track": config.tracking,
    }
    for name, value in values.items():
        try:
            setattr(detector, name, value)
        except (AttributeError, TypeError):
            # A minimal injected Detector may deliberately expose only detect().
            continue


__all__ = [
    "DetectionRuntime",
    "DetectorUnavailableError",
    "FrameDecodeError",
    "FramePayloadError",
    "FrameTooLargeError",
    "decode_jpeg",
]
