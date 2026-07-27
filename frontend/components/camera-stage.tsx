"use client";

import {
  useCallback,
  useEffect,
  useRef,
  type RefObject,
} from "react";

import type { Detection, DetectionResult } from "@/types/detection";

interface CameraStageProps {
  videoRef: RefObject<HTMLVideoElement | null>;
  canvasRef: RefObject<HTMLCanvasElement | null>;
  stageRef: RefObject<HTMLDivElement | null>;
  result: DetectionResult | null;
  cameraActive: boolean;
  cameraLoading: boolean;
  detecting: boolean;
  mirrored: boolean;
  onStartCamera: () => void;
  onFlip: () => void;
  onSnapshot: () => void;
  onFullscreen: () => void;
}

const BOX_COLORS = ["#f5b942", "#63e6be", "#8fb8ff", "#ff8f70", "#c3a6ff"];

function drawDetection(
  context: CanvasRenderingContext2D,
  detection: Detection,
  scaleX: number,
  scaleY: number,
  mirrored: boolean,
  canvasWidth: number,
) {
  const rawX1 = detection.x1 * scaleX;
  const rawX2 = detection.x2 * scaleX;
  const x1 = mirrored ? canvasWidth - rawX2 : rawX1;
  const x2 = mirrored ? canvasWidth - rawX1 : rawX2;
  const y1 = detection.y1 * scaleY;
  const y2 = detection.y2 * scaleY;
  const width = Math.max(0, x2 - x1);
  const height = Math.max(0, y2 - y1);
  const color = BOX_COLORS[Math.abs(detection.classId) % BOX_COLORS.length];

  context.strokeStyle = color;
  context.lineWidth = Math.max(2, canvasWidth / 640);
  context.strokeRect(x1, y1, width, height);

  const confidence = `${Math.round(detection.confidence * 100)}%`;
  const track =
    detection.trackId === null ? "" : ` · #${detection.trackId}`;
  const label = `${detection.label} ${confidence}${track}`;
  const fontSize = Math.max(12, Math.min(18, canvasWidth / 55));
  context.font = `600 ${fontSize}px Geist, system-ui, sans-serif`;
  const labelWidth = context.measureText(label).width + 16;
  const labelHeight = fontSize + 10;
  const labelY = y1 > labelHeight + 3 ? y1 - labelHeight : y1;

  context.fillStyle = color;
  context.fillRect(x1, labelY, labelWidth, labelHeight);
  context.fillStyle = "#080b0f";
  context.textBaseline = "middle";
  context.fillText(label, x1 + 8, labelY + labelHeight / 2 + 0.5);

  const corner = Math.min(18, width / 4, height / 4);
  context.strokeStyle = "#fff7df";
  context.lineWidth = Math.max(1, canvasWidth / 1100);
  context.beginPath();
  context.moveTo(x1, y1 + corner);
  context.lineTo(x1, y1);
  context.lineTo(x1 + corner, y1);
  context.moveTo(x2 - corner, y1);
  context.lineTo(x2, y1);
  context.lineTo(x2, y1 + corner);
  context.stroke();
}

export function CameraStage({
  videoRef,
  canvasRef,
  stageRef,
  result,
  cameraActive,
  cameraLoading,
  detecting,
  mirrored,
  onStartCamera,
  onFlip,
  onSnapshot,
  onFullscreen,
}: CameraStageProps) {
  const internalStageRef = useRef<HTMLDivElement | null>(null);

  const setStageRef = useCallback(
    (node: HTMLDivElement | null) => {
      internalStageRef.current = node;
      if (stageRef && "current" in stageRef) {
        stageRef.current = node;
      }
    },
    [stageRef],
  );

  const drawOverlay = useCallback(() => {
    const canvas = canvasRef.current;
    const stage = internalStageRef.current;
    const video = videoRef.current;
    if (!canvas || !stage) return;

    const sourceWidth = result?.width || video?.videoWidth || 1280;
    const sourceHeight = result?.height || video?.videoHeight || 720;
    const stageRect = stage.getBoundingClientRect();
    const sourceRatio = sourceWidth / sourceHeight;
    const stageRatio = stageRect.width / Math.max(stageRect.height, 1);
    let displayWidth = stageRect.width;
    let displayHeight = stageRect.height;

    if (stageRatio > sourceRatio) {
      displayHeight = stageRect.height;
      displayWidth = displayHeight * sourceRatio;
    } else {
      displayWidth = stageRect.width;
      displayHeight = displayWidth / sourceRatio;
    }

    canvas.style.width = `${displayWidth}px`;
    canvas.style.height = `${displayHeight}px`;
    canvas.style.left = `${(stageRect.width - displayWidth) / 2}px`;
    canvas.style.top = `${(stageRect.height - displayHeight) / 2}px`;
    canvas.width = sourceWidth;
    canvas.height = sourceHeight;

    const context = canvas.getContext("2d");
    if (!context) return;
    context.clearRect(0, 0, sourceWidth, sourceHeight);
    if (!result) return;

    const scaleX = sourceWidth / result.width;
    const scaleY = sourceHeight / result.height;
    result.detections.forEach((detection) =>
      drawDetection(
        context,
        detection,
        scaleX,
        scaleY,
        mirrored,
        sourceWidth,
      ),
    );
  }, [canvasRef, mirrored, result, videoRef]);

  useEffect(() => {
    drawOverlay();
    const stage = internalStageRef.current;
    if (!stage || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(drawOverlay);
    observer.observe(stage);
    return () => observer.disconnect();
  }, [drawOverlay]);

  return (
    <section className="camera-card" aria-label="Live camera workspace">
      <div className="stage-topbar">
        <div className="stage-title">
          <span
            className={`status-dot ${detecting ? "is-live pulse" : ""}`}
            aria-hidden="true"
          />
          <span>{detecting ? "Live analysis" : "Camera preview"}</span>
        </div>
        <div className="stage-meta">
          <span>16:9</span>
          <span className="stage-meta-divider" aria-hidden="true" />
          <span>{result ? `Frame ${result.frameId}` : "Waiting for signal"}</span>
        </div>
      </div>

      <div className="camera-stage" ref={setStageRef}>
        <video
          ref={videoRef}
          className={mirrored ? "is-mirrored" : ""}
          autoPlay
          muted
          playsInline
          aria-label="Live camera preview"
        />
        <canvas ref={canvasRef} aria-hidden="true" />

        {!cameraActive ? (
          <div className="stage-empty">
            <div className="stage-empty-icon" aria-hidden="true">
              <span />
            </div>
            <p className="eyebrow">No camera signal</p>
            <h1>Bring the scene into view.</h1>
            <p>
              Camera processing stays in this browser until frames are sent for
              detection.
            </p>
            <button
              className="button button-primary"
              onClick={onStartCamera}
              disabled={cameraLoading}
              type="button"
            >
              <span aria-hidden="true">●</span>
              {cameraLoading ? "Requesting access…" : "Start camera"}
            </button>
          </div>
        ) : null}

        {cameraActive && !detecting ? (
          <div className="stage-hint">
            <span aria-hidden="true">◎</span>
            Preview ready · Start detection when the scene is framed
          </div>
        ) : null}

        {detecting && result && result.detections.length === 0 ? (
          <div className="stage-hint is-detecting">
            <span className="scan-dot" aria-hidden="true" />
            Scanning · No objects above threshold
          </div>
        ) : null}
      </div>

      <div className="stage-toolbar" aria-label="Camera tools">
        <button
          className="tool-button"
          type="button"
          onClick={onFlip}
          disabled={!cameraActive}
          aria-label="Mirror camera preview"
          title="Mirror preview"
        >
          <span aria-hidden="true">↔</span>
          <span>Flip</span>
        </button>
        <button
          className="tool-button"
          type="button"
          onClick={onSnapshot}
          disabled={!cameraActive}
          aria-label="Download snapshot"
          title="Download snapshot"
        >
          <span aria-hidden="true">◉</span>
          <span>Snapshot</span>
        </button>
        <button
          className="tool-button"
          type="button"
          onClick={onFullscreen}
          disabled={!cameraActive}
          aria-label="Enter fullscreen"
          title="Enter fullscreen"
        >
          <span aria-hidden="true">⛶</span>
          <span>Fullscreen</span>
        </button>
        <div className="toolbar-spacer" />
        <span className="stage-privacy">
          <span aria-hidden="true">◇</span>
          Local camera access
        </span>
      </div>
    </section>
  );
}
