import unittest
from pathlib import Path

from object_detection.config import AppConfig


class AppConfigTests(unittest.TestCase):
    def test_defaults_are_suitable_for_webcam(self):
        config = AppConfig()

        self.assertEqual(config.source, 0)
        self.assertEqual(config.model, Path("yolov8n.pt"))
        self.assertTrue(config.display)

    def test_classes_are_deduplicated_in_order(self):
        config = AppConfig(classes=(2, 0, 2, 1))

        self.assertEqual(config.classes, (2, 0, 1))

    def test_rejects_invalid_values(self):
        invalid_options = (
            {"confidence": -0.1},
            {"iou": 1.1},
            {"width": 0},
            {"height": -1},
            {"max_frames": 0},
            {"codec": "abc"},
            {"classes": (-1,)},
            {"classes": (True,)},
            {"source": -1},
            {"source": True},
            {"confidence": True},
            {"iou": "0.5"},
            {"width": True},
        )

        for options in invalid_options:
            with self.subTest(options=options):
                with self.assertRaises((TypeError, ValueError)):
                    AppConfig(**options)


if __name__ == "__main__":
    unittest.main()
