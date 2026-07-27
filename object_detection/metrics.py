"""Lightweight runtime metrics for object detection."""

from collections import deque
import math
import time
from typing import Callable, Deque


class FPSMeter:
    """Measure frames per second over a rolling window.

    ``update`` records one completed frame and returns the average rate across
    up to ``window_size`` most-recent frame intervals. A clock can be injected
    to make the meter deterministic in tests.
    """

    def __init__(
        self,
        window_size: int = 30,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if isinstance(window_size, bool) or not isinstance(window_size, int):
            raise TypeError("window_size must be an integer")
        if window_size <= 0:
            raise ValueError("window_size must be greater than zero")
        if not callable(clock):
            raise TypeError("clock must be callable")

        self._window_size = window_size
        self._clock = clock
        self._timestamps: Deque[float] = deque(maxlen=window_size + 1)

    @property
    def window_size(self) -> int:
        """Maximum number of frame intervals included in the rate."""
        return self._window_size

    def update(self) -> float:
        """Record a completed frame and return the rolling FPS value."""
        timestamp = float(self._clock())
        if not math.isfinite(timestamp):
            raise ValueError("clock must return a finite timestamp")
        if self._timestamps and timestamp < self._timestamps[-1]:
            raise ValueError("clock timestamps must be monotonic")

        self._timestamps.append(timestamp)
        if len(self._timestamps) < 2:
            return 0.0

        elapsed = self._timestamps[-1] - self._timestamps[0]
        if elapsed <= 0.0:
            return 0.0
        return (len(self._timestamps) - 1) / elapsed

    def reset(self) -> None:
        """Discard all timing samples."""
        self._timestamps.clear()
