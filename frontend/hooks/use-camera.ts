"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type RefObject,
} from "react";

export type CameraStatus = "idle" | "requesting" | "active" | "error";

export interface UseCameraResult {
  stream: MediaStream | null;
  videoRef: RefObject<HTMLVideoElement | null>;
  devices: MediaDeviceInfo[];
  selectedDeviceId: string | null;
  status: CameraStatus;
  error: string | null;
  start: (deviceId?: string) => Promise<void>;
  stop: () => void;
  switchCamera: (deviceId: string) => Promise<void>;
}

function stopTracks(stream: MediaStream | null): void {
  stream?.getTracks().forEach((track) => track.stop());
}

function cameraErrorMessage(error: unknown): string {
  if (
    typeof DOMException === "undefined" ||
    !(error instanceof DOMException)
  ) {
    return "The camera could not be started. Check your browser settings and try again.";
  }

  switch (error.name) {
    case "NotAllowedError":
    case "SecurityError":
      return "Camera access was blocked. Allow camera access in your browser settings and try again.";
    case "NotFoundError":
      return "No camera was found. Connect a camera and try again.";
    case "NotReadableError":
    case "AbortError":
      return "The camera is unavailable. Close other apps using it and try again.";
    case "OverconstrainedError":
      return "The selected camera is no longer available. Choose another camera.";
    default:
      return "The camera could not be started. Check your browser settings and try again.";
  }
}

function supportsCamera(): boolean {
  return (
    typeof navigator !== "undefined" &&
    navigator.mediaDevices !== undefined &&
    typeof navigator.mediaDevices.getUserMedia === "function"
  );
}

export function useCamera(): UseCameraResult {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const operationRef = useRef(0);
  const permissionGrantedRef = useRef(false);

  const [stream, setStream] = useState<MediaStream | null>(null);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const [status, setStatus] = useState<CameraStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const enumerateCameras = useCallback(async (): Promise<void> => {
    if (!supportsCamera() || !permissionGrantedRef.current) {
      return;
    }

    try {
      const availableDevices = await navigator.mediaDevices.enumerateDevices();
      setDevices(
        availableDevices.filter((device) => device.kind === "videoinput"),
      );
    } catch {
      setError(
        "Camera access is active, but the camera list could not be refreshed.",
      );
    }
  }, []);

  const stop = useCallback((): void => {
    operationRef.current += 1;
    stopTracks(streamRef.current);
    streamRef.current = null;

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    setStream(null);
    setStatus("idle");
    setError(null);
  }, []);

  const start = useCallback(
    async (deviceId?: string): Promise<void> => {
      const operation = operationRef.current + 1;
      operationRef.current = operation;
      setStatus("requesting");
      setError(null);

      if (!supportsCamera()) {
        setStatus("error");
        setError(
          "Camera access is not supported in this browser. Use a current browser with camera permissions enabled.",
        );
        return;
      }

      const requestedDeviceId = deviceId ?? selectedDeviceId ?? undefined;
      const videoConstraints: MediaTrackConstraints = requestedDeviceId
        ? { deviceId: { exact: requestedDeviceId } }
        : { facingMode: { ideal: "environment" } };

      let nextStream: MediaStream | null = null;
      try {
        nextStream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: videoConstraints,
        });

        if (operation !== operationRef.current) {
          stopTracks(nextStream);
          return;
        }

        stopTracks(streamRef.current);
        streamRef.current = nextStream;
        permissionGrantedRef.current = true;

        const activeDeviceId =
          nextStream.getVideoTracks()[0]?.getSettings().deviceId ??
          requestedDeviceId ??
          null;
        setSelectedDeviceId(activeDeviceId);
        setStream(nextStream);
        setStatus("active");

        const video = videoRef.current;
        if (video) {
          video.srcObject = nextStream;
          video.muted = true;
          video.playsInline = true;
          void video.play().catch(() => {
            if (operation === operationRef.current) {
              setError(
                "The camera is ready, but the preview did not start automatically. Select the preview to begin playback.",
              );
            }
          });
        }

        await enumerateCameras();
      } catch (caughtError) {
        stopTracks(nextStream);
        if (operation !== operationRef.current) {
          return;
        }
        setStream(null);
        setStatus("error");
        setError(cameraErrorMessage(caughtError));
      }
    },
    [enumerateCameras, selectedDeviceId],
  );

  const switchCamera = useCallback(
    async (deviceId: string): Promise<void> => {
      await start(deviceId);
    },
    [start],
  );

  useEffect(() => {
    if (!supportsCamera()) {
      return;
    }

    const handleDeviceChange = (): void => {
      void enumerateCameras();
    };

    navigator.mediaDevices.addEventListener("devicechange", handleDeviceChange);
    return () => {
      navigator.mediaDevices.removeEventListener(
        "devicechange",
        handleDeviceChange,
      );
    };
  }, [enumerateCameras]);

  useEffect(
    () => () => {
      operationRef.current += 1;
      permissionGrantedRef.current = false;
      stopTracks(streamRef.current);
      streamRef.current = null;
      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }
    },
    [],
  );

  return {
    stream,
    videoRef,
    devices,
    selectedDeviceId,
    status,
    error,
    start,
    stop,
    switchCamera,
  };
}
