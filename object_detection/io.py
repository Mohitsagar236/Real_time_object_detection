"""OpenCV-backed input and output adapters.

OpenCV is imported only when an adapter is opened or written to.  This keeps
configuration, help, and test code importable in environments where ``cv2`` is
not installed.
"""

from __future__ import annotations

import importlib
import math
import os
from pathlib import Path
from types import ModuleType
from typing import Any, Optional, Tuple, Union
from urllib.parse import urlsplit


Source = Union[int, str]
FrameResult = Tuple[bool, Optional[Any]]

IMAGE_EXTENSIONS = frozenset(
    {
        ".bmp",
        ".dib",
        ".exr",
        ".hdr",
        ".jpe",
        ".jpeg",
        ".jpg",
        ".jp2",
        ".pbm",
        ".pfm",
        ".pgm",
        ".pic",
        ".png",
        ".pnm",
        ".ppm",
        ".pxm",
        ".ras",
        ".sr",
        ".tif",
        ".tiff",
        ".webp",
    }
)

VIDEO_EXTENSIONS = frozenset(
    {
        ".avi",
        ".m4v",
        ".mkv",
        ".mov",
        ".mp4",
        ".mpeg",
        ".mpg",
        ".webm",
        ".wmv",
    }
)


class SourceOpenError(RuntimeError):
    """Raised when an image, video, or camera source cannot be opened."""


class FrameReadError(RuntimeError):
    """Raised when a frame cannot be read because of adapter misuse or failure."""


def parse_source(value: str) -> Source:
    """Convert a nonnegative numeric source string into a camera index.

    All other strings are returned verbatim so paths and network URLs are not
    accidentally normalized.
    """

    if not isinstance(value, str):
        raise TypeError("source value must be a string")
    if value.isascii() and value.isdecimal():
        return int(value)
    return value


def _path_extension(value: Union[str, os.PathLike[str]]) -> str:
    """Return a lowercase suffix while ignoring URL query strings/fragments."""

    raw_value = os.fspath(value)
    parsed_path = urlsplit(raw_value).path
    return Path(parsed_path).suffix.lower()


def is_image_path(value: Union[str, os.PathLike[str]]) -> bool:
    """Return whether *value* has an OpenCV-supported image extension."""

    return _path_extension(value) in IMAGE_EXTENSIONS


def is_video_path(value: Union[str, os.PathLike[str]]) -> bool:
    """Return whether *value* has a supported video-container extension."""

    return _path_extension(value) in VIDEO_EXTENSIONS


def _load_cv2(cv2_module: Optional[Any]) -> Any:
    if cv2_module is not None:
        return cv2_module
    try:
        return importlib.import_module("cv2")
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV is required for video I/O; install the 'opencv-python' package"
        ) from exc


def _validate_dimension(name: str, value: Optional[int]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


class VideoSource:
    """A context-managed still-image, video-file, or camera source."""

    def __init__(
        self,
        source: Source,
        width: Optional[int] = None,
        height: Optional[int] = None,
        *,
        cv2_module: Optional[ModuleType] = None,
    ) -> None:
        if isinstance(source, str):
            source = parse_source(source)
        elif isinstance(source, bool) or not isinstance(source, int):
            raise TypeError("source must be a camera index or string path/URL")
        if isinstance(source, int) and source < 0:
            raise ValueError("camera index must be nonnegative")

        self.source = source
        self.width = _validate_dimension("width", width)
        self.height = _validate_dimension("height", height)
        self._provided_cv2 = cv2_module
        self._cv2: Optional[Any] = None
        self._capture: Optional[Any] = None
        self._image_frame: Optional[Any] = None
        self._image_pending = False
        self._is_open = False

    @property
    def is_image(self) -> bool:
        """Whether this source is classified as a still image."""

        return isinstance(self.source, str) and is_image_path(self.source)

    @property
    def fps(self) -> float:
        """Frames per second reported by the capture, or ``0.0`` if unavailable."""

        if self.is_image or self._capture is None or self._cv2 is None:
            return 0.0
        value = float(self._capture.get(self._cv2.CAP_PROP_FPS))
        return value if math.isfinite(value) and value > 0 else 0.0

    @property
    def frame_size(self) -> Tuple[int, int]:
        """Current ``(width, height)``, or ``(0, 0)`` before it is known."""

        if self.is_image:
            if self._image_frame is None:
                return (0, 0)
            height, width = self._image_frame.shape[:2]
            return (int(width), int(height))
        if self._capture is None or self._cv2 is None:
            return (0, 0)
        width = self._capture.get(self._cv2.CAP_PROP_FRAME_WIDTH)
        height = self._capture.get(self._cv2.CAP_PROP_FRAME_HEIGHT)
        return (max(0, int(width)), max(0, int(height)))

    def open(self) -> "VideoSource":
        """Open the configured source and return this adapter."""

        if self._is_open:
            return self

        cv2 = _load_cv2(self._provided_cv2)
        self._cv2 = cv2

        if self.is_image:
            try:
                frame = cv2.imread(self.source)
            except Exception as exc:
                raise SourceOpenError(
                    f"failed to open image source: {self.source!r}"
                ) from exc
            if frame is None:
                raise SourceOpenError(f"failed to open image source: {self.source!r}")
            self._image_frame = frame
            self._image_pending = True
            self._is_open = True
            return self

        capture = None
        try:
            capture = cv2.VideoCapture(self.source)
            if capture is None or not capture.isOpened():
                raise SourceOpenError(f"failed to open video source: {self.source!r}")
            if self.width is not None:
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            if self.height is not None:
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        except SourceOpenError:
            if capture is not None:
                capture.release()
            raise
        except Exception as exc:
            if capture is not None:
                capture.release()
            raise SourceOpenError(
                f"failed to open video source: {self.source!r}"
            ) from exc

        self._capture = capture
        self._is_open = True
        return self

    def read(self) -> FrameResult:
        """Read the next frame using OpenCV's ``(success, frame)`` convention."""

        if not self._is_open:
            raise FrameReadError("source must be opened before reading")

        if self.is_image:
            if not self._image_pending:
                return (False, None)
            self._image_pending = False
            return (True, self._image_frame)

        if self._capture is None:
            raise FrameReadError("video capture is unavailable")
        try:
            result = self._capture.read()
        except Exception as exc:
            raise FrameReadError(
                f"failed while reading video source: {self.source!r}"
            ) from exc
        if not isinstance(result, tuple) or len(result) != 2:
            raise FrameReadError("video backend returned an invalid frame result")
        success, frame = result
        if not success:
            return (False, None)
        if frame is None:
            raise FrameReadError("video backend reported success without a frame")
        return (True, frame)

    def release(self) -> None:
        """Release capture resources. Calling this more than once is safe."""

        if self._capture is not None:
            self._capture.release()
        self._capture = None
        self._image_frame = None
        self._image_pending = False
        self._is_open = False

    def __enter__(self) -> "VideoSource":
        return self.open()

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.release()


class VideoSink:
    """Write frames to an optional still-image or video output."""

    def __init__(
        self,
        output: Optional[Union[str, os.PathLike[str]]],
        fps: Optional[float] = None,
        codec: str = "mp4v",
        *,
        cv2_module: Optional[ModuleType] = None,
    ) -> None:
        self.output = None if output is None else Path(output)
        self.fps = self._normalize_fps(fps)
        if not isinstance(codec, str) or len(codec) != 4:
            raise ValueError("codec must be exactly four characters")
        self.codec = codec
        self._provided_cv2 = cv2_module
        self._cv2: Optional[Any] = None
        self._writer: Optional[Any] = None
        self._image_written = False
        self._released = False

        if self.output is not None:
            parent = self.output.parent
            if not parent.exists():
                raise FileNotFoundError(f"output directory does not exist: {parent}")
            if not parent.is_dir():
                raise NotADirectoryError(f"output parent is not a directory: {parent}")
            if not (is_image_path(self.output) or is_video_path(self.output)):
                raise ValueError(
                    f"unsupported output extension: {self.output.suffix or '<none>'}"
                )

    @staticmethod
    def _normalize_fps(value: Optional[float]) -> float:
        if value is None:
            return 30.0
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("fps must be a number or None")
        number = float(value)
        return number if math.isfinite(number) and number > 0 else 30.0

    @property
    def is_image(self) -> bool:
        return self.output is not None and is_image_path(self.output)

    @staticmethod
    def _frame_size(frame: Any) -> Tuple[int, int]:
        try:
            height, width = frame.shape[:2]
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("frame must expose a valid image shape") from exc
        if int(width) <= 0 or int(height) <= 0:
            raise ValueError("frame dimensions must be positive")
        return (int(width), int(height))

    def write(self, frame: Any, fps: Optional[float] = None) -> None:
        """Write one frame, creating a video writer lazily when necessary."""

        if self._released:
            raise RuntimeError("cannot write after sink has been released")
        if self.output is None:
            return
        self._frame_size(frame)
        cv2 = _load_cv2(self._provided_cv2)
        self._cv2 = cv2

        if self.is_image:
            if self._image_written:
                raise RuntimeError("an image output accepts exactly one frame")
            try:
                written = cv2.imwrite(str(self.output), frame)
            except Exception as exc:
                raise OSError(f"failed to write image: {self.output}") from exc
            if not written:
                raise OSError(f"failed to write image: {self.output}")
            self._image_written = True
            return

        if self._writer is None:
            frame_size = self._frame_size(frame)
            fourcc = cv2.VideoWriter_fourcc(*self.codec)
            output_fps = self._normalize_fps(fps) if fps is not None else self.fps
            writer = cv2.VideoWriter(
                str(self.output), fourcc, output_fps, frame_size
            )
            if writer is None or not writer.isOpened():
                if writer is not None:
                    writer.release()
                raise OSError(f"failed to open video output: {self.output}")
            self._writer = writer
        self._writer.write(frame)

    def release(self) -> None:
        """Flush and release the writer. Calling this more than once is safe."""

        if self._writer is not None:
            self._writer.release()
        self._writer = None
        self._released = True

    def __enter__(self) -> "VideoSink":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.release()


__all__ = [
    "FrameReadError",
    "IMAGE_EXTENSIONS",
    "SourceOpenError",
    "VIDEO_EXTENSIONS",
    "VideoSink",
    "VideoSource",
    "is_image_path",
    "is_video_path",
    "parse_source",
]
