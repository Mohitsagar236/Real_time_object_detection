"""Run the local detection web API with Uvicorn."""

import os

from .api import create_app


def _port_from_environment() -> int:
    raw_port = os.environ.get("DETECTION_PORT", "8765")
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise SystemExit("DETECTION_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise SystemExit("DETECTION_PORT must be between 1 and 65535")
    return port


def main() -> None:
    try:
        import uvicorn
    except (ImportError, ModuleNotFoundError) as exc:
        raise SystemExit(
            "The web API requires Uvicorn. Install fastapi and uvicorn first."
        ) from exc

    uvicorn.run(
        create_app(),
        host="127.0.0.1",
        port=_port_from_environment(),
    )


if __name__ == "__main__":
    main()
