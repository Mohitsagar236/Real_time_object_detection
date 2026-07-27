"""Application configuration and validation."""

from dataclasses import dataclass
from numbers import Integral, Real
from pathlib import Path
from typing import Optional, Tuple, Union


Source = Union[int, str]


@dataclass(frozen=True)
class AppConfig:
    """Validated settings for an object-detection run."""

    source: Source = 0
    model: Path = Path("yolov8n.pt")
    confidence: float = 0.5
    iou: float = 0.45
    device: Optional[str] = None
    classes: Optional[Tuple[int, ...]] = None
    track: bool = False
    display: bool = True
    output: Optional[Path] = None
    width: Optional[int] = None
    height: Optional[int] = None
    max_frames: Optional[int] = None
    codec: str = "mp4v"
    quiet: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.source, bool) or not isinstance(self.source, (int, str)):
            raise TypeError("source must be a camera index or string path/URL")
        if isinstance(self.source, int) and self.source < 0:
            raise ValueError("camera index must be zero or greater")
        if isinstance(self.confidence, bool) or not isinstance(self.confidence, Real):
            raise TypeError("confidence must be a number")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if isinstance(self.iou, bool) or not isinstance(self.iou, Real):
            raise TypeError("IoU threshold must be a number")
        if not 0.0 <= self.iou <= 1.0:
            raise ValueError("IoU threshold must be between 0 and 1")
        if self.width is not None and (
            isinstance(self.width, bool)
            or not isinstance(self.width, Integral)
            or self.width <= 0
        ):
            raise ValueError("width must be greater than zero")
        if self.height is not None and (
            isinstance(self.height, bool)
            or not isinstance(self.height, Integral)
            or self.height <= 0
        ):
            raise ValueError("height must be greater than zero")
        if self.max_frames is not None and (
            isinstance(self.max_frames, bool)
            or not isinstance(self.max_frames, Integral)
            or self.max_frames <= 0
        ):
            raise ValueError("max_frames must be greater than zero")
        if not isinstance(self.codec, str) or len(self.codec) != 4:
            raise ValueError("codec must contain exactly four characters")
        if self.classes is not None:
            normalized = tuple(dict.fromkeys(self.classes))
            if any(
                isinstance(class_id, bool)
                or not isinstance(class_id, Integral)
                or class_id < 0
                for class_id in normalized
            ):
                raise ValueError("class IDs must be zero or greater")
            object.__setattr__(self, "classes", normalized)
        object.__setattr__(self, "confidence", float(self.confidence))
        object.__setattr__(self, "iou", float(self.iou))
        object.__setattr__(self, "model", Path(self.model))
        if self.output is not None:
            object.__setattr__(self, "output", Path(self.output))
