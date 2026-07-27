"""FastAPI integration for the optional real-time detection web service."""

import json
from typing import Any, Optional

from .protocol import (
    DetectionConfig,
    ProtocolError,
    configured_message,
    error_message,
    parse_config_message,
    status_message,
)
from .runtime import (
    DetectionRuntime,
    FramePayloadError,
    FrameTooLargeError,
)


def create_app(
    runtime: Optional[DetectionRuntime] = None,
    model_path: str = "yolov8n.pt",
) -> Any:
    """Create the ASGI application, importing FastAPI only when requested."""
    try:
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError(
            "The web API requires FastAPI. Install fastapi and uvicorn first."
        ) from exc

    detection_runtime = runtime or DetectionRuntime(model_path=model_path)
    app = FastAPI(
        title="Real-Time Object Detection API",
        version="1.0.0",
    )
    app.state.detection_runtime = detection_runtime

    @app.get("/api/health")
    async def health() -> Any:
        return detection_runtime.health()

    @app.get("/api/classes")
    async def classes() -> Any:
        return detection_runtime.class_names()

    @app.websocket("/ws/detect")
    async def detect(websocket: WebSocket) -> None:
        await websocket.accept()
        config = DetectionConfig()
        next_frame_id = 0
        await websocket.send_json(
            status_message(
                model=detection_runtime.model_path,
                ready=detection_runtime.ready,
                device=detection_runtime.device,
            )
        )
        await websocket.send_json(configured_message(config))

        try:
            while True:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    return

                text = message.get("text")
                binary = message.get("bytes")
                if text is not None:
                    config = await _handle_text_message(
                        websocket, text, config
                    )
                    continue
                if binary is None:
                    await websocket.send_json(
                        error_message(
                            "invalid_message",
                            "send a configure JSON message or binary JPEG frame",
                        )
                    )
                    continue

                frame_id = next_frame_id
                next_frame_id += 1
                try:
                    result = await detection_runtime.process_frame(
                        binary,
                        frame_id=frame_id,
                        config=config,
                    )
                except FrameTooLargeError as exc:
                    await websocket.send_json(
                        error_message("frame_too_large", str(exc), frame_id)
                    )
                except FramePayloadError as exc:
                    await websocket.send_json(
                        error_message("invalid_frame", str(exc), frame_id)
                    )
                except Exception as exc:
                    await websocket.send_json(
                        error_message("processing_error", str(exc), frame_id)
                    )
                else:
                    await websocket.send_json(result)
        except WebSocketDisconnect:
            return
        except Exception:
            # Socket send/receive errors generally mean the peer has gone away.
            # Starlette owns connection cleanup; do not let them crash the app.
            return

    return app


async def _handle_text_message(
    websocket: Any,
    text: str,
    current: DetectionConfig,
) -> DetectionConfig:
    try:
        payload = json.loads(text)
        configured = parse_config_message(payload, current=current)
    except json.JSONDecodeError:
        await websocket.send_json(
            error_message("invalid_json", "message must contain valid JSON")
        )
        return current
    except ProtocolError as exc:
        await websocket.send_json(
            error_message("invalid_config", str(exc))
        )
        return current

    await websocket.send_json(configured_message(configured))
    return configured


__all__ = ["create_app"]
