# Real-Time Object Detection with YOLOv8

A real-time object detection system using YOLOv8 and OpenCV for webcam-based detection.

## Features

- **Real-time Detection**: Detects objects in real-time using your webcam
- **YOLOv8 Model**: Uses the lightweight YOLOv8n (nano) model for fast inference
- **80 Object Classes**: Detects people, vehicles, animals, and common objects from the COCO dataset
- **Live Visualization**: Displays bounding boxes, labels, and confidence scores
- **FPS Display**: Shows current frames per second in the video feed

## Requirements

- Python 3.8 or higher
- Webcam/Camera

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Mohitsagar236/Real_time_object_detection.git
cd Real_time_object_detection
```

2. Create a virtual environment (recommended):
```bash
python -m venv .venv
```

3. Activate the virtual environment:
- Windows:
  ```bash
  .venv\Scripts\activate
  ```
- Linux/Mac:
  ```bash
  source .venv/bin/activate
  ```

4. Install required packages:
```bash
pip install ultralytics opencv-python numpy
```

## Usage

Run the object detection script:
```bash
python real_time_detect.py
```

### Controls

- **Press 'q'**: Quit the application

## Project Structure

```
Real_time_object_detection/
├── real_time_detect.py    # Main detection script
├── yolov8n.pt            # YOLOv8 nano model weights
├── datasets/             # Training datasets
│   └── coco128/         # COCO dataset subset
├── ByteTrack/           # Object tracking utilities
├── deep_sort/           # Deep SORT tracking algorithm
├── ultralytics/         # Ultralytics library
└── yolo_tracking/       # YOLO tracking implementations
```

## How It Works

1. **Model Loading**: The script loads the pre-trained YOLOv8n model (`yolov8n.pt`)
2. **Camera Access**: Opens the default webcam (camera index 0)
3. **Frame Processing**: Each frame is processed through the YOLO model
4. **Detection**: Objects are detected with confidence threshold of 0.5
5. **Visualization**: Results are drawn on the frame with bounding boxes and labels
6. **Display**: The annotated frame is shown in a window

## Detected Object Classes

The model can detect 80 different object classes including:
- **People**: person
- **Vehicles**: car, truck, bus, motorcycle, bicycle, train, airplane, boat
- **Animals**: cat, dog, horse, sheep, cow, elephant, bear, zebra, giraffe
- **Objects**: backpack, umbrella, handbag, tie, suitcase, bottle, cup, fork, knife, spoon, bowl
- **Electronics**: laptop, mouse, keyboard, cell phone, TV, remote
- **Furniture**: chair, couch, bed, dining table
- And many more...

## Configuration

You can modify the following parameters in `real_time_detect.py`:

- **Confidence Threshold**: Change `conf=0.5` to adjust detection sensitivity (0.0-1.0)
- **Camera Index**: Change `cv2.VideoCapture(0)` to use a different camera
- **Model**: Replace `yolov8n.pt` with other YOLO models (yolov8s.pt, yolov8m.pt, yolov8l.pt, yolov8x.pt)

## Troubleshooting

**Camera not opening:**
- Ensure your webcam is connected and not in use by another application
- Try changing the camera index: `cv2.VideoCapture(1)` or `cv2.VideoCapture(2)`

**Low FPS:**
- Use a lighter model (yolov8n.pt is the fastest)
- Reduce frame resolution
- Ensure GPU support is available (install `torch` with CUDA)

**Module not found errors:**
- Ensure all packages are installed: `pip install ultralytics opencv-python numpy`
- Activate your virtual environment before running

## Performance

- **Model**: YOLOv8n (nano)
- **Parameters**: ~3.2M
- **Speed**: Real-time on most modern CPUs
- **Accuracy**: mAP of 37.3% on COCO dataset

## License

This project is open source and available under the MIT License.

## Acknowledgments

- [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics)
- [COCO Dataset](https://cocodataset.org/)
- [OpenCV](https://opencv.org/)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Contact

For questions or support, please open an issue in the repository.
