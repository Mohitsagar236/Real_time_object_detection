"""Unit tests for the YOLO model adapter."""

from __future__ import annotations

import builtins
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from object_detection.model import ModelLoadError, YOLODetector


class FakeTensor:
    def __init__(self, value):
        self.value = value
        self.cpu_called = False

    def cpu(self):
        self.cpu_called = True
        return self

    def tolist(self):
        return self.value


class FakeScalar:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class FakeBoxes:
    def __init__(self, xyxy, confidence, class_ids, track_ids=None):
        self.xyxy = FakeTensor(xyxy)
        self.conf = FakeTensor(confidence)
        self.cls = FakeTensor(class_ids)
        self.id = None if track_ids is None else FakeTensor(track_ids)


class FakeResult:
    def __init__(self, boxes, names=None, speed=None):
        self.boxes = boxes
        self.names = names
        self.speed = speed


class FakeModel:
    def __init__(self, results, names=None):
        self.results = results
        self.names = names
        self.predict_calls = []
        self.track_calls = []

    def predict(self, frame, **kwargs):
        self.predict_calls.append((frame, kwargs))
        return self.results

    def track(self, frame, **kwargs):
        self.track_calls.append((frame, kwargs))
        return self.results


class YOLODetectorTests(unittest.TestCase):
    def test_predict_converts_tensor_like_boxes_to_domain_objects(self):
        boxes = FakeBoxes(
            xyxy=[[1.5, 2, 30.25, 40], [50, 60, 70, 80]],
            confidence=[[0.91], [0.72]],
            class_ids=[1.0, 0.0],
        )
        result = FakeResult(
            boxes=boxes,
            names={0: "person", 1: "bicycle"},
            speed={"inference": FakeScalar(7.25)},
        )
        model = FakeModel([result])
        frame = object()
        detector = YOLODetector(
            "unused.pt",
            confidence=0.6,
            iou=0.3,
            device="cpu",
            classes=[0, 1],
            model=model,
        )

        output = detector.detect(frame)

        self.assertEqual(
            model.predict_calls,
            [
                (
                    frame,
                    {
                        "conf": 0.6,
                        "iou": 0.3,
                        "verbose": False,
                        "device": "cpu",
                        "classes": [0, 1],
                    },
                )
            ],
        )
        self.assertEqual(model.track_calls, [])
        self.assertEqual(output.inference_ms, 7.25)
        self.assertEqual(len(output.detections), 2)
        first = output.detections[0]
        self.assertEqual((first.x1, first.y1, first.x2, first.y2), (1.5, 2, 30.25, 40))
        self.assertEqual(first.confidence, 0.91)
        self.assertEqual(first.class_id, 1)
        self.assertEqual(first.label, "bicycle")
        self.assertIsNone(first.track_id)
        self.assertTrue(boxes.xyxy.cpu_called)

    def test_track_passes_persist_and_converts_track_ids(self):
        result = FakeResult(
            boxes=FakeBoxes(
                xyxy=[10, 20, 30, 40],
                confidence=[FakeScalar(0.8)],
                class_ids=[FakeScalar(3)],
                track_ids=[FakeScalar(42)],
            ),
            names=None,
            speed={},
        )
        model = FakeModel((result,), names=["zero", "one", "two", "car"])
        frame = object()
        detector = YOLODetector("unused.pt", track=True, model=model)

        output = detector.detect(frame)

        self.assertEqual(model.predict_calls, [])
        self.assertEqual(
            model.track_calls,
            [
                (
                    frame,
                    {
                        "conf": 0.5,
                        "iou": 0.45,
                        "verbose": False,
                        "persist": True,
                    },
                )
            ],
        )
        self.assertEqual(output.inference_ms, 0.0)
        self.assertEqual(output.detections[0].track_id, 42)
        self.assertEqual(output.detections[0].label, "car")

    def test_empty_and_missing_results_return_empty_frame_detections(self):
        for results in ([], (), None):
            with self.subTest(results=results):
                output = YOLODetector("unused.pt", model=FakeModel(results)).detect(
                    object()
                )
                self.assertEqual(output.detections, ())
                self.assertEqual(output.inference_ms, 0.0)

        missing_boxes = FakeResult(None, speed={"inference": 2.0})
        output = YOLODetector(
            "unused.pt", model=FakeModel([missing_boxes])
        ).detect(object())
        self.assertEqual(output.detections, ())
        self.assertEqual(output.inference_ms, 2.0)

    def test_empty_boxes_and_malformed_rows_are_handled(self):
        empty = FakeResult(
            FakeBoxes(xyxy=[], confidence=[], class_ids=[]),
            names={},
        )
        output = YOLODetector("unused.pt", model=FakeModel([empty])).detect(object())
        self.assertEqual(output.detections, ())

        partial = FakeResult(
            FakeBoxes(
                xyxy=[[1, 2], [1, 2, 3, 4]],
                confidence=[0.9, 0.8],
                class_ids=[0, 5],
            ),
            names={},
        )
        output = YOLODetector("unused.pt", model=FakeModel([partial])).detect(
            object()
        )
        self.assertEqual(len(output.detections), 1)
        self.assertEqual(output.detections[0].label, "5")

    def test_thresholds_and_classes_are_validated(self):
        invalid_options = (
            {"confidence": -0.01},
            {"confidence": 1.01},
            {"confidence": True},
            {"iou": -0.01},
            {"iou": 1.01},
            {"iou": "0.5"},
            {"classes": [0, -1]},
            {"classes": [False]},
            {"classes": "1"},
        )
        for options in invalid_options:
            with self.subTest(options=options):
                with self.assertRaises(ValueError):
                    YOLODetector("unused.pt", model=FakeModel([]), **options)

        detector = YOLODetector(
            "unused.pt",
            confidence=0,
            iou=1,
            classes=[],
            model=FakeModel([]),
        )
        self.assertEqual(detector.confidence, 0.0)
        self.assertEqual(detector.iou, 1.0)
        self.assertEqual(detector.classes, ())

    def test_injected_model_does_not_import_ultralytics(self):
        real_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name == "ultralytics":
                raise AssertionError("Ultralytics must not be imported")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=guarded_import):
            detector = YOLODetector("unused.pt", model=FakeModel([]))
            self.assertEqual(detector.detect(object()).detections, ())

    def test_missing_ultralytics_raises_actionable_load_error(self):
        real_import = builtins.__import__

        def missing_ultralytics(name, *args, **kwargs):
            if name == "ultralytics":
                raise ModuleNotFoundError("No module named 'ultralytics'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=missing_ultralytics):
            with self.assertRaisesRegex(ModelLoadError, "pip install ultralytics"):
                YOLODetector("missing.pt")

    def test_model_load_failure_includes_weights_path(self):
        fake_module = types.ModuleType("ultralytics")

        def failing_yolo(model_path):
            raise OSError("bad weights")

        fake_module.YOLO = failing_yolo
        weights = Path("broken-weights.pt")

        with patch.dict("sys.modules", {"ultralytics": fake_module}):
            with self.assertRaisesRegex(ModelLoadError, "broken-weights.pt"):
                YOLODetector(weights)


if __name__ == "__main__":
    unittest.main()
