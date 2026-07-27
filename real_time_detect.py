"""Backward-compatible entry point for the object_detection package."""

from object_detection.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
