"""Unit tests for the optional web detection backend."""

import importlib.util
import math
import unittest

from object_detection.domain import Detection, FrameDetections
from object_detection.web.api import create_app
from object_detection.web.protocol import (
    DetectionConfig,
    MAX_FRAME_BYTES,
    ProtocolError,
    configured_message,
    parse_config_message,
    result_message,
)
from object_detection.web.runtime import (
    DetectionRuntime,
    DetectorUnavailableError,
    FrameDecodeError,
    FramePayloadError,
    FrameTooLargeError,
)


class ProtocolTests(unittest.TestCase):
    def test_configure_message_updates_only_submitted_fields(self) -> None:
        current = DetectionConfig(
            confidence=0.3,
            iou=0.4,
            classes=(1,),
            tracking=False,
        )

        config = parse_config_message(
            {
                "type": "configure",
                "confidence": 0.8,
                "classes": [0, 2, 2],
                "tracking": True,
            },
            current=current,
        )

        self.assertEqual(0.8, config.confidence)
        self.assertEqual(0.4, config.iou)
        self.assertEqual((0, 2), config.classes)
        self.assertTrue(config.tracking)
        self.assertEqual(
            {
                "type": "configured",
                "confidence": 0.8,
                "iou": 0.4,
                "classes": [0, 2],
                "tracking": True,
            },
            configured_message(config),
        )

    def test_configuration_validation_rejects_bad_payloads(self) -> None:
        invalid = [
            None,
            {"type": "other"},
            {"type": "configure", "confidence": math.nan},
            {"type": "configure", "iou": 2},
            {"type": "configure", "classes": [True]},
            {"type": "configure", "tracking": 1},
            {"type": "configure", "unknown": "value"},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(ProtocolError):
                    parse_config_message(payload)

    def test_result_uses_public_camel_case_schema(self) -> None:
        frame = FrameDetections(
            (
                Detection(
                    1,
                    2,
                    11,
                    22,
                    0.9,
                    0,
                    "person",
                    track_id=7,
                ),
            ),
            inference_ms=4.25,
        )

        result = result_message(
            frame_id=3,
            width=640,
            height=480,
            detections=frame,
            total_ms=6.5,
            timestamp=123.0,
        )

        self.assertEqual("result", result["type"])
        self.assertEqual(3, result["frameId"])
        self.assertEqual(4.25, result["inferenceMs"])
        self.assertEqual({"person": 1}, result["classCounts"])
        self.assertEqual(
            {
                "x1": 1.0,
                "y1": 2.0,
                "x2": 11.0,
                "y2": 22.0,
                "confidence": 0.9,
                "classId": 0,
                "label": "person",
                "trackId": 7,
            },
            result["detections"][0],
        )


class FakeFrame:
    shape = (480, 640, 3)


class FakeDetector:
    def __init__(self) -> None:
        self.device = "cpu"
        self.names = {1: "bicycle", 0: "person"}
        self.detect_calls = 0

    def detect(self, frame: object) -> FrameDetections:
        self.detect_calls += 1
        return FrameDetections(
            (
                Detection(0, 0, 10, 20, 0.75, 0, "person"),
            ),
            inference_ms=2.5,
        )


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_process_frame_decodes_detects_and_serializes(self) -> None:
        detector = FakeDetector()
        ticks = iter((10.0, 10.008))
        runtime = DetectionRuntime(
            detector=detector,
            decoder=lambda payload: FakeFrame(),
            monotonic=lambda: next(ticks),
            wall_clock=lambda: 456.0,
        )
        config = DetectionConfig(
            confidence=0.6,
            iou=0.3,
            classes=(0,),
            tracking=True,
        )

        result = await runtime.process_frame(b"jpeg", 9, config)

        self.assertEqual(640, result["width"])
        self.assertEqual(480, result["height"])
        self.assertAlmostEqual(8.0, result["totalMs"])
        self.assertEqual(456.0, result["timestamp"])
        self.assertEqual(1, detector.detect_calls)
        self.assertEqual(0.6, detector.confidence)
        self.assertEqual(0.3, detector.iou)
        self.assertEqual((0,), detector.classes)
        self.assertTrue(detector.track)

    async def test_detector_factory_loads_only_once(self) -> None:
        detector = FakeDetector()
        calls = []

        def factory(model_path: str) -> FakeDetector:
            calls.append(model_path)
            return detector

        runtime = DetectionRuntime(
            model_path="custom.pt",
            detector_factory=factory,
            decoder=lambda payload: FakeFrame(),
        )
        self.assertFalse(runtime.ready)

        await runtime.process_frame(b"one", 0)
        await runtime.process_frame(b"two", 1)

        self.assertEqual(["custom.pt"], calls)
        self.assertTrue(runtime.ready)
        self.assertEqual(["person", "bicycle"], runtime.class_names())
        self.assertEqual(
            {
                "status": "ok",
                "model": "custom.pt",
                "ready": True,
                "device": "cpu",
            },
            runtime.health(),
        )

    async def test_payload_limits_are_checked_before_decode(self) -> None:
        decode_calls = []
        runtime = DetectionRuntime(
            detector=FakeDetector(),
            decoder=lambda payload: decode_calls.append(payload),
        )

        with self.assertRaises(FramePayloadError):
            await runtime.process_frame(b"", 0)
        with self.assertRaises(FrameTooLargeError):
            await runtime.process_frame(b"x" * (MAX_FRAME_BYTES + 1), 1)

        self.assertEqual([], decode_calls)

    async def test_decoder_errors_are_normalized(self) -> None:
        def broken_decoder(payload: bytes) -> object:
            raise ValueError("bad JPEG")

        runtime = DetectionRuntime(
            detector=FakeDetector(),
            decoder=broken_decoder,
        )

        with self.assertRaises(FrameDecodeError):
            await runtime.process_frame(b"invalid", 0)

    async def test_failed_model_load_is_cached(self) -> None:
        calls = []

        def broken_factory(model_path: str) -> object:
            calls.append(model_path)
            raise RuntimeError("weights missing")

        runtime = DetectionRuntime(
            detector_factory=broken_factory,
            decoder=lambda payload: FakeFrame(),
        )

        for frame_id in range(2):
            with self.assertRaises(DetectorUnavailableError):
                await runtime.process_frame(b"jpeg", frame_id)

        self.assertEqual(["yolov8n.pt"], calls)


FASTAPI_AVAILABLE = importlib.util.find_spec("fastapi") is not None


@unittest.skipUnless(FASTAPI_AVAILABLE, "FastAPI is not installed")
class FastAPIIntegrationTests(unittest.TestCase):
    def test_factory_registers_public_routes(self) -> None:
        runtime = DetectionRuntime(
            detector=FakeDetector(),
            decoder=lambda payload: FakeFrame(),
        )

        app = create_app(runtime=runtime)
        routes = {route.path for route in app.routes}

        self.assertIn("/api/health", routes)
        self.assertIn("/api/classes", routes)
        self.assertIn("/ws/detect", routes)
        self.assertIs(runtime, app.state.detection_runtime)


if __name__ == "__main__":
    unittest.main()
