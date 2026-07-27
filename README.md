# VisionDesk Real-Time Object Detection

VisionDesk is a modular YOLOv8 application with a complete browser workspace
and a CLI for detecting and tracking objects from cameras, videos, images, and
network streams. The browser sends camera frames to a local WebSocket inference
service and draws the returned detections over the live preview.

## Features

- Responsive live-camera workspace
- Browser-to-YOLO WebSocket streaming with frame backpressure
- Bounding boxes, labels, confidence, and persistent tracking IDs
- Live class counts, latency, inference time, and measured FPS
- Camera switching, mirrored preview, fullscreen, and snapshots
- Confidence, IoU, target-rate, tracking, and class-preset controls
- Image, video, webcam, and stream URL support from the CLI
- Headless processing and annotated image/video export
- Lazy dependency loading and resource-safe cleanup
- Automated backend, frontend, API, and rendered-output tests

The bundled `yolov8n.pt` model recognizes the 80 COCO classes.

## Requirements

- Python 3.9 or newer; Python 3.10 or 3.11 is recommended
- Node.js 22.13 or newer
- A webcam when using the live-camera workspace

## Install

From this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
cd frontend
npm ci
cd ..
```

On macOS or Linux, activate with `source .venv/bin/activate`.

## Run VisionDesk

On Windows, start the API and frontend together:

```powershell
.\start_visiondesk.ps1
```

The browser opens at `http://127.0.0.1:3000`. Select **Start camera**, allow
camera permission, frame the scene, and select **Start detection**.

Stop both services with:

```powershell
.\stop_visiondesk.ps1
```

To run the services separately:

```powershell
object-detect-web
cd frontend
npm run dev:local
```

The detection API listens on `127.0.0.1:8765` by default. Set
`DETECTION_PORT` and `NEXT_PUBLIC_DETECTION_WS_URL` together to use another
port.

## Run the CLI

Start the original camera workflow:

```powershell
object-detect
```

The compatibility entry points are also supported:

```powershell
python real_time_detect.py
python -m object_detection
```

Press **Q** or **Escape** in the OpenCV preview to stop.

### CLI examples

Process a video and save the annotated result:

```powershell
object-detect --source input.mp4 --output output.mp4
```

Process an image without a preview:

```powershell
object-detect --source photo.jpg --output detected.jpg --no-display
```

Track people and vehicles from camera 1:

```powershell
object-detect --source 1 --track --classes 0,2,3,5,7
```

Run headlessly on a network stream:

```powershell
object-detect --source "rtsp://example/stream" --no-display --output result.mp4
```

See every CLI option:

```powershell
object-detect --help
```

## Architecture

```text
object_detection/
|-- application.py      # resource-safe desktop/CLI pipeline
|-- domain.py           # backend-independent detection records
|-- io.py               # camera, image, video, and output adapters
|-- model.py            # lazy Ultralytics YOLO adapter
|-- rendering.py        # OpenCV visualization
`-- web/
    |-- api.py           # FastAPI routes and WebSocket lifecycle
    |-- protocol.py      # validated public wire format
    `-- runtime.py       # concurrency-safe inference service

frontend/
|-- app/                 # VisionDesk application shell and visual system
|-- components/          # camera, controls, metrics, and object inspector
|-- hooks/               # camera and detection socket lifecycles
|-- lib/                 # shared detection configuration
`-- types/               # frontend API contracts
```

The frontend, transport, inference, rendering, and input/output layers depend
on explicit shared contracts. Tests replace model, camera, and socket
dependencies with small fakes.

## Test

Run the Python suite:

```powershell
python -m unittest discover -s tests -v
```

Run the production frontend build and rendered-output tests:

```powershell
cd frontend
npm test
```

## Troubleshooting

**The browser cannot use the camera**

- Allow camera access in the browser permission prompt.
- Close other applications using the camera.
- Choose another camera from the inspector when one is available.

**The model shows as offline**

- Confirm `object-detect-web` is running on port `8765`.
- Run `.\start_visiondesk.ps1` to start both services together.

**Inference is slow**

- Keep the included nano model.
- Lower the target rate or camera resolution.
- Use a CUDA-enabled PyTorch installation when a supported GPU is available.

**A model or module cannot be loaded**

- Activate the intended environment and run `python -m pip install -e .`.
- Run from this directory so `yolov8n.pt` is found, or provide another model
  path to the Python API.

## License

MIT. See [LICENSE](LICENSE).
