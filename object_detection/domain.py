"""Core data structures shared by the object-detection application."""

from collections import Counter
from dataclasses import dataclass
import math
from numbers import Real
from typing import Dict, Optional, Tuple


def _finite_float(value: Real, field_name: str) -> float:
    """Return *value* as a finite float or raise a helpful validation error."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError("{} must be a real number".format(field_name))

    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError("{} must be finite".format(field_name))
    return normalized


def _non_negative_int(value: int, field_name: str) -> int:
    """Validate integer identifiers without accepting booleans as integers."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("{} must be an integer".format(field_name))
    if value < 0:
        raise ValueError("{} must be non-negative".format(field_name))
    return value


@dataclass(frozen=True)
class Detection:
    """One labelled bounding-box detection.

    Coordinates use the conventional ``(x1, y1, x2, y2)`` layout. They may
    be negative before a caller clips a box to an image, but they must be
    finite and ordered.
    """

    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int
    label: str
    track_id: Optional[int] = None

    def __post_init__(self) -> None:
        x1 = _finite_float(self.x1, "x1")
        y1 = _finite_float(self.y1, "y1")
        x2 = _finite_float(self.x2, "x2")
        y2 = _finite_float(self.y2, "y2")
        confidence = _finite_float(self.confidence, "confidence")

        if x2 < x1:
            raise ValueError("x2 must be greater than or equal to x1")
        if y2 < y1:
            raise ValueError("y2 must be greater than or equal to y1")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")

        class_id = _non_negative_int(self.class_id, "class_id")
        if not isinstance(self.label, str):
            raise TypeError("label must be a string")
        if not self.label.strip():
            raise ValueError("label must not be empty")

        track_id = self.track_id
        if track_id is not None:
            track_id = _non_negative_int(track_id, "track_id")

        # Frozen dataclasses still permit normalization during initialization.
        object.__setattr__(self, "x1", x1)
        object.__setattr__(self, "y1", y1)
        object.__setattr__(self, "x2", x2)
        object.__setattr__(self, "y2", y2)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "class_id", class_id)
        object.__setattr__(self, "track_id", track_id)

    @property
    def width(self) -> float:
        """Bounding-box width."""
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        """Bounding-box height."""
        return self.y2 - self.y1


@dataclass(frozen=True)
class FrameDetections:
    """All detections and inference timing for one video frame."""

    detections: Tuple[Detection, ...]
    inference_ms: float = 0.0

    def __post_init__(self) -> None:
        try:
            detections = tuple(self.detections)
        except TypeError as exc:
            raise TypeError(
                "detections must be an iterable of Detection objects"
            ) from exc

        if not all(isinstance(detection, Detection) for detection in detections):
            raise TypeError("detections must contain only Detection objects")

        inference_ms = _finite_float(self.inference_ms, "inference_ms")
        if inference_ms < 0.0:
            raise ValueError("inference_ms must be non-negative")

        object.__setattr__(self, "detections", detections)
        object.__setattr__(self, "inference_ms", inference_ms)

    @property
    def count(self) -> int:
        """Number of detections in this frame."""
        return len(self.detections)

    @property
    def class_counts(self) -> Dict[str, int]:
        """Detection counts keyed by class label."""
        return dict(Counter(detection.label for detection in self.detections))
