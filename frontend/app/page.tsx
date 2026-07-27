"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AppHeader } from "@/components/app-header";
import { CameraStage } from "@/components/camera-stage";
import { ControlPanel } from "@/components/control-panel";
import { MetricsGrid } from "@/components/metrics-grid";
import { ObjectList } from "@/components/object-list";
import { useCamera } from "@/hooks/use-camera";
import { useDetectionSocket } from "@/hooks/use-detection-socket";
import {
  CLASS_PRESETS,
  DEFAULT_SETTINGS,
  type ClassPreset,
} from "@/lib/detection-config";
import type { DetectionSettings } from "@/types/detection";

const DETECTION_SOCKET_URL =
  process.env.NEXT_PUBLIC_DETECTION_WS_URL ?? "ws://127.0.0.1:8765/ws/detect";

function sameClasses(left: number[], right: number[]) {
  return (
    left.length === right.length &&
    left.every((classId, index) => classId === right[index])
  );
}

export default function Home() {
  const {
    stream,
    videoRef,
    devices,
    selectedDeviceId,
    status: cameraStatus,
    error: cameraError,
    start,
    stop,
    switchCamera,
  } = useCamera();
  const [settings, setSettings] = useState<DetectionSettings>(() => ({
    ...DEFAULT_SETTINGS,
    classes: [...DEFAULT_SETTINGS.classes],
  }));
  const {
    status: connectionStatus,
    error: socketError,
    latestResult,
    stats,
    connect,
    disconnect,
    sendFrame,
  } = useDetectionSocket(DETECTION_SOCKET_URL, settings);
  const [sessionRunning, setSessionRunning] = useState(false);
  const [mirrored, setMirrored] = useState(false);
  const captureCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const stageRef = useRef<HTMLDivElement | null>(null);

  const cameraActive = cameraStatus === "active" && stream !== null;
  const cameraLoading = cameraStatus === "requesting";
  const socketReady = connectionStatus === "connected";
  const detectionActive = sessionRunning && socketReady && socketError === null;
  const activePresetId =
    CLASS_PRESETS.find((preset) =>
      sameClasses(settings.classes, preset.classes),
    )?.id ?? "custom";
  const visiblePresets = useMemo(
    () =>
      CLASS_PRESETS.filter(
        (preset) =>
          preset.id === "all" ||
          preset.id === "people" ||
          preset.id === "vehicles",
      ),
    [],
  );

  const startCamera = useCallback(() => {
    void start();
  }, [start]);

  const startDetection = useCallback(() => {
    setSessionRunning(true);
    if (connectionStatus !== "connected") {
      connect();
    }
  }, [connect, connectionStatus]);

  const stopSession = useCallback(() => {
    setSessionRunning(false);
    disconnect();
    stop();
  }, [disconnect, stop]);

  useEffect(() => {
    if (!sessionRunning || !socketReady || !stream) return;
    let active = true;

    const captureFrame = () => {
      const video = videoRef.current;
      const canvas = captureCanvasRef.current;
      if (!active || !video || !canvas || video.readyState < 2) return;
      const width = video.videoWidth;
      const height = video.videoHeight;
      if (width === 0 || height === 0) return;

      if (canvas.width !== width) canvas.width = width;
      if (canvas.height !== height) canvas.height = height;
      const context = canvas.getContext("2d");
      if (!context) return;
      context.drawImage(video, 0, 0, width, height);
      canvas.toBlob(
        (blob) => {
          if (active && blob) sendFrame(blob);
        },
        "image/jpeg",
        0.82,
      );
    };

    captureFrame();
    const timer = window.setInterval(
      captureFrame,
      Math.max(33, Math.round(1000 / settings.targetFps)),
    );
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [
    sendFrame,
    sessionRunning,
    settings.targetFps,
    socketReady,
    stream,
    videoRef,
  ]);

  const handlePresetChange = useCallback((preset: ClassPreset) => {
    setSettings((current) => ({
      ...current,
      classes: [...preset.classes],
    }));
  }, []);

  const handleSnapshot = useCallback(() => {
    const video = videoRef.current;
    const overlay = overlayCanvasRef.current;
    if (!video || video.videoWidth === 0 || video.videoHeight === 0) return;

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    if (!context) return;

    if (mirrored) {
      context.save();
      context.translate(canvas.width, 0);
      context.scale(-1, 1);
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      context.restore();
    } else {
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
    }
    if (overlay && overlay.width > 0) {
      context.drawImage(overlay, 0, 0, canvas.width, canvas.height);
    }

    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = `visiondesk-${new Date()
          .toISOString()
          .replace(/[:.]/g, "-")}.jpg`;
        anchor.click();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      },
      "image/jpeg",
      0.92,
    );
  }, [mirrored, videoRef]);

  const handleFullscreen = useCallback(() => {
    const stage = stageRef.current;
    if (!stage) return;
    if (document.fullscreenElement) {
      void document.exitFullscreen();
    } else {
      void stage.requestFullscreen();
    }
  }, []);

  const handleDeviceChange = useCallback(
    (deviceId: string) => {
      if (deviceId) void switchCamera(deviceId);
    },
    [switchCamera],
  );

  const errorMessage = cameraError ?? socketError;

  return (
    <main id="workspace" className="app-shell">
      <AppHeader
        cameraActive={cameraActive}
        connectionStatus={connectionStatus}
        detecting={detectionActive}
      />

      {errorMessage ? (
        <div className="error-banner" role="alert">
          <span aria-hidden="true">!</span>
          <p>{errorMessage}</p>
          {cameraError ? (
            <button type="button" onClick={startCamera}>
              Try again
            </button>
          ) : null}
        </div>
      ) : null}

      <div className="workspace-grid">
        <div className="workspace-main">
          <CameraStage
            videoRef={videoRef}
            canvasRef={overlayCanvasRef}
            stageRef={stageRef}
            result={latestResult}
            cameraActive={cameraActive}
            cameraLoading={cameraLoading}
            detecting={detectionActive}
            mirrored={mirrored}
            onStartCamera={startCamera}
            onFlip={() => setMirrored((current) => !current)}
            onSnapshot={handleSnapshot}
            onFullscreen={handleFullscreen}
          />
          <MetricsGrid
            fps={stats.serverFps}
            latencyMs={stats.latencyMs}
            inferenceMs={latestResult?.inferenceMs ?? 0}
            objectCount={latestResult?.detections.length ?? 0}
          />
          <ObjectList result={latestResult} detecting={detectionActive} />
        </div>

        <ControlPanel
          settings={settings}
          presets={visiblePresets}
          activePresetId={activePresetId}
          cameraActive={cameraActive}
          cameraLoading={cameraLoading}
          sessionRunning={sessionRunning}
          detecting={detectionActive}
          connecting={connectionStatus === "connecting"}
          error={socketError}
          devices={devices}
          selectedDeviceId={selectedDeviceId}
          onSettingsChange={setSettings}
          onPresetChange={handlePresetChange}
          onDeviceChange={handleDeviceChange}
          onStartCamera={startCamera}
          onStartDetection={startDetection}
          onStop={stopSession}
        />
      </div>

      <canvas ref={captureCanvasRef} className="capture-canvas" aria-hidden="true" />

      <footer className="app-footer">
        <span>VisionDesk · Private browser vision</span>
        <span>
          {stats.framesProcessed.toLocaleString()} frames processed this session
        </span>
      </footer>
    </main>
  );
}
