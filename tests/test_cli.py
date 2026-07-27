import argparse
import unittest
from pathlib import Path

from object_detection.cli import _parse_classes, build_parser, config_from_args


class CLITests(unittest.TestCase):
    def test_builds_config_for_headless_video(self):
        args = build_parser().parse_args(
            [
                "--source",
                "input.mp4",
                "--no-display",
                "--output",
                "output.mp4",
                "--classes",
                "0,2,3",
                "--track",
            ]
        )

        config = config_from_args(args)

        self.assertEqual(config.source, "input.mp4")
        self.assertFalse(config.display)
        self.assertEqual(config.output, Path("output.mp4"))
        self.assertEqual(config.classes, (0, 2, 3))
        self.assertTrue(config.track)

    def test_numeric_source_becomes_camera_index(self):
        args = build_parser().parse_args(["--source", "2"])

        self.assertEqual(config_from_args(args).source, 2)

    def test_rejects_bad_class_list(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            _parse_classes("person")


if __name__ == "__main__":
    unittest.main()
