import unittest

from object_detection.domain import Detection
from object_detection.rendering import FrameRenderer


class FakeFrame:
    shape = (480, 640, 3)

    def copy(self):
        return self


class FakeCV2:
    FONT_HERSHEY_SIMPLEX = 0
    LINE_AA = 1

    def __init__(self):
        self.text = []
        self.rectangles = []

    def rectangle(self, frame, start, end, color, thickness):
        self.rectangles.append((start, end, color, thickness))

    def getTextSize(self, text, font, scale, thickness):
        return (len(text) * 5, 10), 2

    def putText(self, frame, text, *args):
        self.text.append(text)

    def addWeighted(self, overlay, alpha, frame, beta, gamma, destination):
        return destination


class FrameRendererTests(unittest.TestCase):
    def test_renders_detection_and_status(self):
        cv2 = FakeCV2()
        renderer = FrameRenderer(cv2)
        detection = Detection(1, 2, 30, 40, 0.91, 0, "person", track_id=7)

        result = renderer.render(FakeFrame(), (detection,), 25.5, 8.2)

        self.assertIsInstance(result, FakeFrame)
        self.assertTrue(any("person #7" in value for value in cv2.text))
        self.assertTrue(any("FPS" in value for value in cv2.text))
        self.assertGreaterEqual(len(cv2.rectangles), 3)


if __name__ == "__main__":
    unittest.main()
