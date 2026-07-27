import unittest

from object_detection.application import DetectionApplication
from object_detection.domain import Detection, FrameDetections


class FakeFrame:
    def copy(self):
        return self


class FakeSource:
    fps = 24.0
    is_image = False

    def __init__(self, frame_count):
        self.frames = [FakeFrame() for _ in range(frame_count)]
        self.opened = False
        self.released = False

    def open(self):
        self.opened = True
        return self

    def read(self):
        if not self.frames:
            return False, None
        return True, self.frames.pop(0)

    def release(self):
        self.released = True


class FakeDetector:
    def detect(self, frame):
        return FrameDetections(
            (Detection(0, 0, 10, 10, 0.9, 0, "person"),),
            inference_ms=5.0,
        )


class FakeRenderer:
    def __init__(self):
        self.calls = 0

    def render(self, frame, detections, fps, inference_ms):
        self.calls += 1
        return frame


class FakeSink:
    def __init__(self, is_image=False):
        self.frames = []
        self.released = False
        self.is_image = is_image

    def write(self, frame, fps):
        self.frames.append((frame, fps))

    def release(self):
        self.released = True


class SequenceClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        self.value += 0.1
        return self.value


class DetectionApplicationTests(unittest.TestCase):
    def test_pipeline_processes_and_releases_resources(self):
        source = FakeSource(3)
        renderer = FakeRenderer()
        sink = FakeSink()
        application = DetectionApplication(
            detector=FakeDetector(),
            source=source,
            renderer=renderer,
            sink=sink,
            display=False,
            clock=SequenceClock(),
        )

        summary = application.run()

        self.assertEqual(summary.frames_processed, 3)
        self.assertEqual(summary.objects_detected, 3)
        self.assertEqual(renderer.calls, 3)
        self.assertEqual(len(sink.frames), 3)
        self.assertTrue(source.released)
        self.assertTrue(sink.released)

    def test_max_frames_stops_early_without_rendering_headless(self):
        source = FakeSource(5)
        renderer = FakeRenderer()
        application = DetectionApplication(
            detector=FakeDetector(),
            source=source,
            renderer=renderer,
            display=False,
            max_frames=2,
            clock=SequenceClock(),
        )

        summary = application.run()

        self.assertEqual(summary.frames_processed, 2)
        self.assertEqual(renderer.calls, 0)
        self.assertTrue(source.released)

    def test_image_sink_captures_only_the_first_video_frame(self):
        source = FakeSource(3)
        sink = FakeSink(is_image=True)
        application = DetectionApplication(
            detector=FakeDetector(),
            source=source,
            renderer=FakeRenderer(),
            sink=sink,
            display=False,
            clock=SequenceClock(),
        )

        summary = application.run()

        self.assertEqual(summary.frames_processed, 1)
        self.assertEqual(len(sink.frames), 1)
        self.assertTrue(source.released)
        self.assertTrue(sink.released)

    def test_releases_source_when_detection_fails(self):
        source = FakeSource(1)

        class BrokenDetector:
            def detect(self, frame):
                raise RuntimeError("inference failed")

        application = DetectionApplication(
            detector=BrokenDetector(),
            source=source,
            renderer=FakeRenderer(),
            display=False,
        )

        with self.assertRaises(RuntimeError):
            application.run()
        self.assertTrue(source.released)


if __name__ == "__main__":
    unittest.main()
