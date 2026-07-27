"""Tests for immutable detection-domain values."""

from dataclasses import FrozenInstanceError
import math
import unittest

from object_detection.domain import Detection, FrameDetections


class DetectionTests(unittest.TestCase):
    def test_dimensions_and_numeric_normalization(self) -> None:
        detection = Detection(2, 3, 12, 18, 0.75, 1, "person", track_id=4)

        self.assertEqual(10.0, detection.width)
        self.assertEqual(15.0, detection.height)
        self.assertIsInstance(detection.x1, float)

    def test_detection_is_immutable(self) -> None:
        detection = Detection(0, 0, 1, 1, 1, 0, "object")

        with self.assertRaises(FrozenInstanceError):
            detection.label = "changed"  # type: ignore[misc]

    def test_rejects_invalid_box_coordinates(self) -> None:
        with self.assertRaisesRegex(ValueError, "x2"):
            Detection(10, 0, 2, 1, 0.5, 0, "object")
        with self.assertRaisesRegex(ValueError, "finite"):
            Detection(0, 0, math.inf, 1, 0.5, 0, "object")

    def test_rejects_invalid_confidence(self) -> None:
        for confidence in (-0.01, 1.01, math.nan):
            with self.subTest(confidence=confidence):
                with self.assertRaises(ValueError):
                    Detection(0, 0, 1, 1, confidence, 0, "object")

    def test_rejects_invalid_metadata(self) -> None:
        with self.assertRaises(ValueError):
            Detection(0, 0, 1, 1, 0.5, -1, "object")
        with self.assertRaises(ValueError):
            Detection(0, 0, 1, 1, 0.5, 0, " ")
        with self.assertRaises(ValueError):
            Detection(0, 0, 1, 1, 0.5, 0, "object", track_id=-1)


class FrameDetectionsTests(unittest.TestCase):
    def test_count_and_class_counts(self) -> None:
        people = [
            Detection(0, 0, 10, 10, 0.9, 0, "person"),
            Detection(20, 20, 30, 30, 0.8, 0, "person"),
        ]
        bicycle = Detection(1, 1, 5, 5, 0.7, 1, "bicycle")

        frame = FrameDetections(people + [bicycle], inference_ms=12)

        self.assertEqual(3, frame.count)
        self.assertEqual({"person": 2, "bicycle": 1}, frame.class_counts)
        self.assertIsInstance(frame.detections, tuple)
        self.assertEqual(12.0, frame.inference_ms)

    def test_rejects_invalid_contents_and_timing(self) -> None:
        with self.assertRaises(TypeError):
            FrameDetections(("not a detection",))  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            FrameDetections((), inference_ms=-0.1)


if __name__ == "__main__":
    unittest.main()
