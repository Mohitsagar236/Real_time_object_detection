"""OpenCV-based visualization kept separate from model inference."""

from collections import Counter
from typing import Any, Iterable, Optional, Tuple

from .domain import Detection


class FrameRenderer:
    """Render detections and run statistics onto a copy of a frame."""

    _PALETTE = (
        (52, 152, 219),
        (46, 204, 113),
        (155, 89, 182),
        (241, 196, 15),
        (230, 126, 34),
        (231, 76, 60),
        (26, 188, 156),
        (149, 165, 166),
    )

    def __init__(self, cv2_module: Optional[Any] = None) -> None:
        self._cv2 = cv2_module

    @property
    def cv2(self) -> Any:
        if self._cv2 is None:
            try:
                import cv2
            except ImportError as exc:
                raise RuntimeError(
                    "OpenCV is required for rendering. Install dependencies with "
                    "`python -m pip install -r requirements.txt`."
                ) from exc
            self._cv2 = cv2
        return self._cv2

    def render(
        self,
        frame: Any,
        detections: Iterable[Detection],
        fps: float,
        inference_ms: float = 0.0,
    ) -> Any:
        canvas = frame.copy()
        items = tuple(detections)
        for detection in items:
            self._draw_detection(canvas, detection)
        self._draw_status(canvas, items, fps, inference_ms)
        return canvas

    def _draw_detection(self, frame: Any, detection: Detection) -> None:
        cv2 = self.cv2
        color = self._PALETTE[detection.class_id % len(self._PALETTE)]
        start = (int(detection.x1), int(detection.y1))
        end = (int(detection.x2), int(detection.y2))
        cv2.rectangle(frame, start, end, color, 2)

        identity = detection.label
        if detection.track_id is not None:
            identity = "{} #{}".format(identity, detection.track_id)
        label = "{} {:.0f}%".format(identity, detection.confidence * 100)
        (text_width, text_height), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1
        )
        text_y = max(start[1], text_height + baseline + 4)
        cv2.rectangle(
            frame,
            (start[0], text_y - text_height - baseline - 4),
            (start[0] + text_width + 6, text_y + 2),
            color,
            -1,
        )
        cv2.putText(
            frame,
            label,
            (start[0] + 3, text_y - baseline),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    def _draw_status(
        self,
        frame: Any,
        detections: Tuple[Detection, ...],
        fps: float,
        inference_ms: float,
    ) -> None:
        cv2 = self.cv2
        width = frame.shape[1]
        panel_height = 46
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (width, panel_height), (20, 24, 32), -1)
        cv2.addWeighted(overlay, 0.78, frame, 0.22, 0, frame)

        performance = "FPS {:5.1f}  |  inference {:5.1f} ms".format(
            fps, inference_ms
        )
        counts = Counter(item.label for item in detections)
        summary = ", ".join(
            "{}: {}".format(label, count)
            for label, count in sorted(counts.items())
        )
        if not summary:
            summary = "No objects detected"
        max_summary = max(24, width // 9)
        if len(summary) > max_summary:
            summary = summary[: max_summary - 1] + "…"

        cv2.putText(
            frame,
            performance,
            (10, 18),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            "{} object(s)  |  {}".format(len(detections), summary),
            (10, 38),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (210, 220, 230),
            1,
            cv2.LINE_AA,
        )
