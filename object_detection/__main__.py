"""Allow `python -m object_detection` execution."""

from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())
