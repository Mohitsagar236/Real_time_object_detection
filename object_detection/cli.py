"""Command-line interface for the object detection application."""

import argparse
import logging
from pathlib import Path
from typing import Optional, Sequence, Tuple

from . import __version__
from .application import DetectionApplication, RunSummary
from .config import AppConfig
from .io import SourceOpenError, VideoSink, VideoSource, parse_source
from .model import ModelLoadError, YOLODetector
from .rendering import FrameRenderer


LOGGER = logging.getLogger("object_detection")


def _parse_classes(value: str) -> Tuple[int, ...]:
    try:
        classes = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "classes must be comma-separated integer IDs, for example 0,2,3"
        ) from exc
    if not classes or any(item < 0 for item in classes):
        raise argparse.ArgumentTypeError(
            "classes must contain one or more nonnegative integer IDs"
        )
    return classes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="object-detect",
        description=(
            "Detect and optionally track COCO objects in a camera, video, or image."
        ),
    )
    parser.add_argument(
        "--source",
        default="0",
        help="camera index, image path, video path, or stream URL (default: 0)",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("yolov8n.pt"),
        help="YOLO model path or model name (default: yolov8n.pt)",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.5,
        help="minimum detection confidence from 0 to 1 (default: 0.5)",
    )
    parser.add_argument(
        "--iou",
        type=float,
        default=0.45,
        help="non-maximum suppression IoU threshold (default: 0.45)",
    )
    parser.add_argument("--device", help="inference device such as cpu, 0, or cuda:0")
    parser.add_argument(
        "--classes",
        type=_parse_classes,
        help="only these COCO class IDs, comma separated (example: 0,2,3)",
    )
    parser.add_argument(
        "--track",
        action="store_true",
        help="enable persistent object IDs using the YOLO tracker",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="write the annotated result to an image or video",
    )
    parser.add_argument(
        "--no-display",
        action="store_true",
        help="run without opening a preview window",
    )
    parser.add_argument("--width", type=int, help="requested camera capture width")
    parser.add_argument("--height", type=int, help="requested camera capture height")
    parser.add_argument(
        "--max-frames",
        type=int,
        help="stop after this many frames (useful for automation)",
    )
    parser.add_argument(
        "--codec",
        default="mp4v",
        help="four-character output video codec (default: mp4v)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="only print errors",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s {}".format(__version__),
    )
    return parser


def config_from_args(args: argparse.Namespace) -> AppConfig:
    return AppConfig(
        source=parse_source(args.source),
        model=args.model,
        confidence=args.confidence,
        iou=args.iou,
        device=args.device,
        classes=args.classes,
        track=args.track,
        display=not args.no_display,
        output=args.output,
        width=args.width,
        height=args.height,
        max_frames=args.max_frames,
        codec=args.codec,
        quiet=args.quiet,
    )


def create_application(config: AppConfig) -> DetectionApplication:
    detector = YOLODetector(
        model_path=str(config.model),
        confidence=config.confidence,
        iou=config.iou,
        device=config.device,
        classes=config.classes,
        track=config.track,
    )
    source = VideoSource(
        config.source,
        width=config.width,
        height=config.height,
    )
    sink = (
        VideoSink(config.output, codec=config.codec)
        if config.output is not None
        else None
    )
    return DetectionApplication(
        detector=detector,
        source=source,
        renderer=FrameRenderer(),
        sink=sink,
        display=config.display,
        max_frames=config.max_frames,
        quiet=config.quiet,
    )


def _format_summary(summary: RunSummary, output: Optional[Path]) -> str:
    message = (
        "Processed {frames} frame(s), found {objects} object(s), "
        "average {fps:.1f} FPS."
    ).format(
        frames=summary.frames_processed,
        objects=summary.objects_detected,
        fps=summary.average_fps,
    )
    if output is not None:
        message += " Saved annotated output to {}.".format(output)
    return message


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    try:
        config = config_from_args(parser.parse_args(argv))
    except ValueError as exc:
        parser.error(str(exc))

    logging.basicConfig(
        level=logging.ERROR if config.quiet else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    try:
        application = create_application(config)
        if not config.quiet:
            LOGGER.info("Loading model %s", config.model)
            LOGGER.info("Opening source %s", config.source)
            if config.display:
                LOGGER.info("Press Q or Escape in the preview window to stop")
        summary = application.run()
    except (ModelLoadError, SourceOpenError, OSError, RuntimeError) as exc:
        LOGGER.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        LOGGER.info("Stopped by user")
        return 130

    if not config.quiet:
        LOGGER.info("%s", _format_summary(summary, config.output))
    return 0
