"""Tests for rolling runtime metrics."""

import unittest

from object_detection.metrics import FPSMeter


class FakeClock:
    def __init__(self, *timestamps: float) -> None:
        self._timestamps = iter(timestamps)

    def __call__(self) -> float:
        return next(self._timestamps)


class FPSMeterTests(unittest.TestCase):
    def test_first_frame_has_no_measurable_interval(self) -> None:
        meter = FPSMeter(clock=FakeClock(5.0))

        self.assertEqual(0.0, meter.update())

    def test_reports_average_fps(self) -> None:
        meter = FPSMeter(clock=FakeClock(0.0, 0.5, 1.0))

        self.assertEqual(0.0, meter.update())
        self.assertAlmostEqual(2.0, meter.update())
        self.assertAlmostEqual(2.0, meter.update())

    def test_rolls_old_intervals_out_of_window(self) -> None:
        meter = FPSMeter(window_size=2, clock=FakeClock(0.0, 1.0, 2.0, 2.5))

        rates = [meter.update() for _ in range(4)]

        self.assertAlmostEqual(4.0 / 3.0, rates[-1])

    def test_reset_discards_existing_samples(self) -> None:
        meter = FPSMeter(clock=FakeClock(0.0, 0.5, 10.0, 10.25))
        meter.update()
        self.assertAlmostEqual(2.0, meter.update())

        meter.reset()

        self.assertEqual(0.0, meter.update())
        self.assertAlmostEqual(4.0, meter.update())

    def test_rejects_invalid_configuration(self) -> None:
        with self.assertRaises(ValueError):
            FPSMeter(window_size=0)
        with self.assertRaises(TypeError):
            FPSMeter(window_size=1.5)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            FPSMeter(clock=None)  # type: ignore[arg-type]

    def test_rejects_backwards_clock(self) -> None:
        meter = FPSMeter(clock=FakeClock(2.0, 1.0))
        meter.update()

        with self.assertRaisesRegex(ValueError, "monotonic"):
            meter.update()


if __name__ == "__main__":
    unittest.main()
