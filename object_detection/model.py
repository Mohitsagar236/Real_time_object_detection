"""Model adapters for object detection inference.

The Ultralytics dependency is deliberately imported only when a
``YOLODetector`` needs to construct its own model.  This keeps the rest of the
application importable in lightweight environments and makes the adapter easy
to test with a model double.
"""

from __future__ import annotations

from numbers import Integral, Real
from os import PathLike
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Union,
)

from .domain import Detection, FrameDetections


class ModelLoadError(RuntimeError):
    """Raised when an object detection model cannot be imported or loaded."""


class Detector(Protocol):
    """Interface implemented by frame-level object detectors."""

    def detect(self, frame: Any) -> FrameDetections:
        """Run inference for one frame."""


class YOLODetector:
    """Adapt an Ultralytics YOLO model to the application's domain objects."""

    def __init__(
        self,
        model_path: Union[str, PathLike[str]],
        confidence: float = 0.5,
        iou: float = 0.45,
        device: Optional[Union[str, int]] = None,
        classes: Optional[Sequence[int]] = None,
        track: bool = False,
        *,
        model: Optional[Any] = None,
    ) -> None:
        self.model_path = model_path
        self.confidence = _validate_threshold("confidence", confidence)
        self.iou = _validate_threshold("iou", iou)
        self.device = device
        self.classes = _validate_classes(classes)
        self.track = bool(track)
        self._model = model if model is not None else self._load_model(model_path)

    @staticmethod
    def _load_model(model_path: Union[str, PathLike[str]]) -> Any:
        try:
            from ultralytics import YOLO
        except (ImportError, ModuleNotFoundError) as exc:
            raise ModelLoadError(
                "Ultralytics is required to load a YOLO model. "
                "Install it with `pip install ultralytics`, then try again."
            ) from exc

        try:
            return YOLO(str(model_path))
        except Exception as exc:
            raise ModelLoadError(
                f"Could not load YOLO model from {model_path!s}. "
                "Check that the weights file exists, is readable, and is a "
                "supported Ultralytics model."
            ) from exc

    def detect(self, frame: Any) -> FrameDetections:
        """Run prediction or tracking and convert the first YOLO result."""

        kwargs: Dict[str, Any] = {
            "conf": self.confidence,
            "iou": self.iou,
            "verbose": False,
        }
        if self.device is not None:
            kwargs["device"] = self.device
        if self.classes is not None:
            kwargs["classes"] = list(self.classes)

        if self.track:
            kwargs["persist"] = True
            results = self._model.track(frame, **kwargs)
        else:
            results = self._model.predict(frame, **kwargs)

        result = _first_result(results)
        if result is None:
            return FrameDetections(detections=(), inference_ms=0.0)

        inference_ms = _inference_time(result)
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return FrameDetections(detections=(), inference_ms=inference_ms)

        coordinate_rows = _coordinate_rows(getattr(boxes, "xyxy", None))
        confidences = _values(getattr(boxes, "conf", None))
        class_ids = _values(getattr(boxes, "cls", None))
        track_ids = _values(getattr(boxes, "id", None))
        names = getattr(result, "names", None)
        if names is None:
            names = getattr(self._model, "names", None)

        detections: List[Detection] = []
        count = min(len(coordinate_rows), len(confidences), len(class_ids))
        for index in range(count):
            coordinates = coordinate_rows[index]
            if len(coordinates) < 4:
                continue

            try:
                x1, y1, x2, y2 = (float(_scalar(value)) for value in coordinates[:4])
                confidence = float(_scalar(confidences[index]))
                class_id = int(_scalar(class_ids[index]))
            except (TypeError, ValueError):
                # A malformed model row should not discard other valid results.
                continue

            track_id = _track_id_at(track_ids, index)
            detections.append(
                Detection(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    confidence=confidence,
                    class_id=class_id,
                    label=_class_label(names, class_id),
                    track_id=track_id,
                )
            )

        return FrameDetections(
            detections=tuple(detections),
            inference_ms=inference_ms,
        )


def _validate_threshold(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a number between 0 and 1.")
    validated = float(value)
    if not 0.0 <= validated <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1.")
    return validated


def _validate_classes(classes: Optional[Sequence[int]]) -> Optional[tuple[int, ...]]:
    if classes is None:
        return None
    if isinstance(classes, (str, bytes)):
        raise ValueError("classes must be a sequence of non-negative integers.")

    validated: List[int] = []
    try:
        values: Iterable[Any] = classes
        for value in values:
            if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
                raise ValueError(
                    "classes must be a sequence of non-negative integers."
                )
            validated.append(int(value))
    except TypeError as exc:
        raise ValueError(
            "classes must be a sequence of non-negative integers."
        ) from exc
    return tuple(validated)


def _first_result(results: Any) -> Optional[Any]:
    if results is None:
        return None
    if hasattr(results, "boxes"):
        return results
    try:
        return next(iter(results), None)
    except TypeError:
        return None


def _to_python(value: Any) -> Any:
    if value is None:
        return None

    current = value
    detach = getattr(current, "detach", None)
    if callable(detach):
        current = detach()
    cpu = getattr(current, "cpu", None)
    if callable(cpu):
        current = cpu()
    tolist = getattr(current, "tolist", None)
    if callable(tolist):
        return tolist()
    item = getattr(current, "item", None)
    if callable(item):
        return item()
    return current


def _scalar(value: Any) -> Any:
    current = _to_python(value)
    while isinstance(current, (list, tuple)) and len(current) == 1:
        current = _to_python(current[0])
    return current


def _values(value: Any) -> List[Any]:
    converted = _to_python(value)
    if converted is None:
        return []
    if isinstance(converted, (list, tuple)):
        return list(converted)
    return [converted]


def _coordinate_rows(value: Any) -> List[List[Any]]:
    converted = _to_python(value)
    if converted is None:
        return []
    if not isinstance(converted, (list, tuple)):
        return []
    if not converted:
        return []
    if len(converted) >= 4 and not isinstance(converted[0], (list, tuple)):
        return [list(converted)]

    rows: List[List[Any]] = []
    for row in converted:
        row = _to_python(row)
        while (
            isinstance(row, (list, tuple))
            and len(row) == 1
            and isinstance(row[0], (list, tuple))
        ):
            row = row[0]
        if isinstance(row, (list, tuple)):
            rows.append(list(row))
    return rows


def _track_id_at(track_ids: Sequence[Any], index: int) -> Optional[int]:
    if index >= len(track_ids):
        return None
    value = _scalar(track_ids[index])
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _class_label(names: Any, class_id: int) -> str:
    if isinstance(names, Mapping):
        label = names.get(class_id)
        if label is None:
            label = names.get(str(class_id))
        if label is not None:
            return str(label)
    elif names is not None:
        try:
            return str(names[class_id])
        except (IndexError, KeyError, TypeError):
            pass
    return str(class_id)


def _inference_time(result: Any) -> float:
    speed = getattr(result, "speed", None)
    if not isinstance(speed, Mapping):
        return 0.0
    inference = speed.get("inference")
    if inference is None:
        return 0.0
    try:
        return float(_scalar(inference))
    except (TypeError, ValueError):
        return 0.0


__all__ = ["Detector", "ModelLoadError", "YOLODetector"]
