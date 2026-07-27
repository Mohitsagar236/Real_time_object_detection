from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch

from object_detection.io import (
    FrameReadError,
    SourceOpenError,
    VideoSink,
    VideoSource,
    is_image_path,
    is_video_path,
    parse_source,
)


class FakeFrame:
    def __init__(self, width=640, height=480):
        self.shape = (height, width, 3)


class FakeCapture:
    def __init__(
        self,
        opened=True,
        frames=None,
        fps=24.0,
        width=640.0,
        height=480.0,
    ):
        self.opened = opened
        self.frames = list(frames or [])
        self.properties = {1: fps, 2: width, 3: height}
        self.set_calls = []
        self.release_calls = 0

    def isOpened(self):
        return self.opened

    def set(self, property_id, value):
        self.set_calls.append((property_id, value))
        self.properties[property_id] = value
        return True

    def get(self, property_id):
        return self.properties.get(property_id, 0.0)

    def read(self):
        return self.frames.pop(0) if self.frames else (False, None)

    def release(self):
        self.release_calls += 1
        self.opened = False


class FakeWriter:
    def __init__(self, opened=True):
        self.opened = opened
        self.frames = []
        self.release_calls = 0

    def isOpened(self):
        return self.opened

    def write(self, frame):
        self.frames.append(frame)

    def release(self):
        self.release_calls += 1
        self.opened = False


class FakeCV2:
    CAP_PROP_FPS = 1
    CAP_PROP_FRAME_WIDTH = 2
    CAP_PROP_FRAME_HEIGHT = 3

    def __init__(
        self,
        capture=None,
        image=None,
        writer=None,
        image_write_result=True,
    ):
        self.capture = capture or FakeCapture()
        self.image = image
        self.writer = writer or FakeWriter()
        self.image_write_result = image_write_result
        self.capture_sources = []
        self.imread_calls = []
        self.imwrite_calls = []
        self.fourcc_calls = []
        self.writer_calls = []

    def VideoCapture(self, source):
        self.capture_sources.append(source)
        return self.capture

    def imread(self, path):
        self.imread_calls.append(path)
        return self.image

    def imwrite(self, path, frame):
        self.imwrite_calls.append((path, frame))
        return self.image_write_result

    def VideoWriter_fourcc(self, *codec):
        self.fourcc_calls.append(codec)
        return 1234

    def VideoWriter(self, path, fourcc, fps, frame_size):
        self.writer_calls.append((path, fourcc, fps, frame_size))
        return self.writer


class IOTests(TestCase):
    def test_parse_source(self):
        cases = (
            ("0", 0),
            ("007", 7),
            ("12", 12),
            ("-1", "-1"),
            (" 0 ", " 0 "),
            ("camera0", "camera0"),
            ("rtsp://camera/live", "rtsp://camera/live"),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(parse_source(value), expected)
        with self.assertRaises(TypeError):
            parse_source(0)

    def test_extension_classification(self):
        self.assertTrue(is_image_path("FRAME.JPEG"))
        self.assertTrue(
            is_image_path("https://example.test/frame.PNG?token=abc#preview")
        )
        self.assertFalse(is_image_path("clip.mp4"))
        self.assertTrue(is_video_path("clip.MP4"))
        self.assertTrue(
            is_video_path("https://example.test/stream.webm?token=abc")
        )
        self.assertFalse(is_video_path("frame.png"))

    def test_construction_loads_opencv_lazily(self):
        with TemporaryDirectory() as directory:
            with patch(
                "object_detection.io.importlib.import_module",
                side_effect=AssertionError("OpenCV must be loaded lazily"),
            ):
                VideoSource("0")
                VideoSink(Path(directory) / "output.mp4")

    def test_read_before_open_raises(self):
        source = VideoSource(0, cv2_module=FakeCV2())
        with self.assertRaisesRegex(FrameReadError, "opened"):
            source.read()

    def test_image_is_loaded_and_returned_once(self):
        frame = FakeFrame(width=320, height=200)
        cv2 = FakeCV2(image=frame)
        source = VideoSource("still.JpG", cv2_module=cv2)

        self.assertTrue(source.is_image)
        self.assertEqual(source.fps, 0.0)
        self.assertEqual(source.frame_size, (0, 0))
        self.assertIs(source.open(), source)
        self.assertIs(source.open(), source)
        self.assertEqual(cv2.imread_calls, ["still.JpG"])
        self.assertEqual(source.frame_size, (320, 200))
        self.assertEqual(source.read(), (True, frame))
        self.assertEqual(source.read(), (False, None))
        source.release()
        with self.assertRaises(FrameReadError):
            source.read()

    def test_image_open_failure_is_reported(self):
        source = VideoSource("missing.png", cv2_module=FakeCV2(image=None))
        with self.assertRaisesRegex(SourceOpenError, "missing.png"):
            source.open()

    def test_video_source_configures_capture_and_properties(self):
        frame = FakeFrame()
        capture = FakeCapture(frames=[(True, frame), (False, FakeFrame())])
        cv2 = FakeCV2(capture=capture)

        with VideoSource("0", width=800, height=600, cv2_module=cv2) as source:
            self.assertEqual(cv2.capture_sources, [0])
            self.assertEqual(capture.set_calls, [(2, 800), (3, 600)])
            self.assertEqual(source.fps, 24.0)
            self.assertEqual(source.frame_size, (800, 600))
            self.assertEqual(source.read(), (True, frame))
            self.assertEqual(source.read(), (False, None))
        self.assertEqual(capture.release_calls, 1)

    def test_video_source_errors_are_reported(self):
        capture = FakeCapture(opened=False)
        source = VideoSource("broken.mp4", cv2_module=FakeCV2(capture=capture))
        with self.assertRaisesRegex(SourceOpenError, "broken.mp4"):
            source.open()
        self.assertEqual(capture.release_calls, 1)

        capture = FakeCapture(frames=[(True, None)])
        source = VideoSource(0, cv2_module=FakeCV2(capture=capture)).open()
        with self.assertRaisesRegex(FrameReadError, "without a frame"):
            source.read()

    def test_source_rejects_invalid_dimensions(self):
        for value in (0, -1, True, 1.5):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    VideoSource(0, width=value)

    def test_sink_without_output_is_noop(self):
        sink = VideoSink(None)
        sink.write(SimpleNamespace())
        sink.release()
        sink.release()

    def test_video_sink_writes_and_uses_fps(self):
        with TemporaryDirectory() as directory:
            writer = FakeWriter()
            cv2 = FakeCV2(writer=writer)
            output = Path(directory) / "result.mp4"
            first = FakeFrame(width=1280, height=720)
            second = FakeFrame(width=1280, height=720)
            sink = VideoSink(output, fps=0, codec="avc1", cv2_module=cv2)

            sink.write(first, fps=25)
            sink.write(second, fps=25)

            self.assertEqual(cv2.fourcc_calls, [("a", "v", "c", "1")])
            self.assertEqual(
                cv2.writer_calls,
                [(str(output), 1234, 25.0, (1280, 720))],
            )
            self.assertEqual(writer.frames, [first, second])
            sink.release()
            sink.release()
            self.assertEqual(writer.release_calls, 1)
            with self.assertRaisesRegex(RuntimeError, "released"):
                sink.write(first)

    def test_image_sink_writes_once_and_reports_failure(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "result.PNG"
            frame = FakeFrame()
            cv2 = FakeCV2(image_write_result=True)
            sink = VideoSink(output, cv2_module=cv2)
            sink.write(frame)
            self.assertEqual(cv2.imwrite_calls, [(str(output), frame)])
            with self.assertRaisesRegex(RuntimeError, "exactly one"):
                sink.write(frame)

            failed = VideoSink(
                Path(directory) / "failed.jpg",
                cv2_module=FakeCV2(image_write_result=False),
            )
            with self.assertRaisesRegex(OSError, "failed to write image"):
                failed.write(frame)

    def test_sink_validates_destination_and_codec(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(FileNotFoundError):
                VideoSink(root / "missing" / "result.mp4")
            with self.assertRaisesRegex(ValueError, "unsupported output extension"):
                VideoSink(root / "result.txt")
            with self.assertRaisesRegex(ValueError, "four characters"):
                VideoSink(root / "result.mp4", codec="bad")

    def test_video_sink_reports_writer_failure(self):
        with TemporaryDirectory() as directory:
            writer = FakeWriter(opened=False)
            sink = VideoSink(
                Path(directory) / "result.mp4",
                cv2_module=FakeCV2(writer=writer),
            )
            with self.assertRaisesRegex(OSError, "failed to open video output"):
                sink.write(FakeFrame())
            self.assertEqual(writer.release_calls, 1)


if __name__ == "__main__":
    main()
