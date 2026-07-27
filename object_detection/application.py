"""Detection pipeline orchestration independent from concrete model and I/O."""

from dataclasses import dataclass
from time import monotonic
from typing import Any, Callable, Optional

from .metrics import FPSMeter


@dataclass(frozen=True)
class RunSummary:
    """Aggregate information returned after a detection run."""

    frames_processed: int
    objects_detected: int
    elapsed_seconds: float
    stopped_by_user: bool = False

    @property
    def average_fps(self) -> float:
        if self.elapsed_seconds <= 0:
            return 0.0
        return self.frames_processed / self.elapsed_seconds


class DetectionApplication:
    """Coordinate a frame source, detector, renderer, and optional sink."""

    WINDOW_TITLE = "Real-Time Object Detection"

    def __init__(
        self,
        detector: Any,
        source: Any,
        renderer: Any,
        sink: Optional[Any] = None,
        display: bool = True,
        max_frames: Optional[int] = None,
        quiet: bool = False,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.detector = detector
        self.source = source
        self.renderer = renderer
        self.sink = sink
        self.display = display
        self.max_frames = max_frames
        self.quiet = quiet
        self._clock = clock

    def run(self) -> RunSummary:
        frames_processed = 0
        objects_detected = 0
        stopped_by_user = False
        start_time = self._clock()
        fps_meter = FPSMeter(clock=self._clock)

        try:
            self.source.open()
            while self.max_frames is None or frames_processed < self.max_frames:
                ok, frame = self.source.read()
                if not ok:
                    break

                result = self.detector.detect(frame)
                current_fps = fps_meter.update()
                frames_processed += 1
                objects_detected += result.count

                output_frame = frame
                if self.display or self.sink is not None:
                    output_frame = self.renderer.render(
                        frame,
                        result.detections,
                        current_fps,
                        result.inference_ms,
                    )

                if self.sink is not None:
                    self.sink.write(
                        output_frame,
                        fps=self.source.fps,
                    )
                    if self.sink.is_image and not self.source.is_image:
                        break

                if self.display and self._show_frame(output_frame):
                    stopped_by_user = True
                    break
        finally:
            self.source.release()
            if self.sink is not None:
                self.sink.release()
            if self.display:
                self._destroy_windows()

        elapsed = max(0.0, self._clock() - start_time)
        return RunSummary(
            frames_processed=frames_processed,
            objects_detected=objects_detected,
            elapsed_seconds=elapsed,
            stopped_by_user=stopped_by_user,
        )

    def _show_frame(self, frame: Any) -> bool:
        cv2 = self.renderer.cv2
        cv2.imshow(self.WINDOW_TITLE, frame)
        delay = 0 if self.source.is_image else 1
        key = cv2.waitKey(delay) & 0xFF
        return key in (27, ord("q"), ord("Q"))

    def _destroy_windows(self) -> None:
        try:
            self.renderer.cv2.destroyAllWindows()
        except Exception:
            # Some headless OpenCV builds expose the symbol but cannot execute it.
            pass
