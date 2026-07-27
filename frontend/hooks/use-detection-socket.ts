"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  RECONNECT_BASE_DELAY_MS,
  RECONNECT_MAX_DELAY_MS,
} from "../lib/detection-config";
import type {
  ConnectionStatus,
  Detection,
  DetectionResult,
  DetectionSettings,
  DetectionStats,
} from "../types/detection";

const INITIAL_STATS: DetectionStats = {
  framesProcessed: 0,
  latencyMs: 0,
  serverFps: 0,
};

export interface UseDetectionSocketResult {
  status: ConnectionStatus;
  error: string | null;
  result: DetectionResult | null;
  latestResult: DetectionResult | null;
  stats: DetectionStats;
  connect: () => void;
  disconnect: () => void;
  sendFrame: (frame: Blob) => boolean;
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isDetection(value: unknown): value is Detection {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const detection = value as Record<string, unknown>;
  return (
    isFiniteNumber(detection.x1) &&
    isFiniteNumber(detection.y1) &&
    isFiniteNumber(detection.x2) &&
    isFiniteNumber(detection.y2) &&
    isFiniteNumber(detection.confidence) &&
    isFiniteNumber(detection.classId) &&
    typeof detection.label === "string" &&
    (detection.trackId === null || isFiniteNumber(detection.trackId))
  );
}

function isClassCounts(value: unknown): value is Record<string, number> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value) &&
    Object.values(value).every(isFiniteNumber)
  );
}

function isDetectionResult(value: unknown): value is DetectionResult {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const result = value as Record<string, unknown>;
  return (
    result.type === "result" &&
    isFiniteNumber(result.frameId) &&
    isFiniteNumber(result.width) &&
    isFiniteNumber(result.height) &&
    isFiniteNumber(result.inferenceMs) &&
    isFiniteNumber(result.totalMs) &&
    Array.isArray(result.detections) &&
    result.detections.every(isDetection) &&
    isClassCounts(result.classCounts) &&
    isFiniteNumber(result.timestamp)
  );
}

function timestampNow(): number {
  return typeof performance === "undefined" ? Date.now() : performance.now();
}

async function messageText(data: unknown): Promise<string | null> {
  if (typeof data === "string") {
    return data;
  }
  if (typeof Blob !== "undefined" && data instanceof Blob) {
    return data.text();
  }
  if (data instanceof ArrayBuffer) {
    return new TextDecoder().decode(data);
  }
  return null;
}

function configMessage(settings: DetectionSettings): string {
  return JSON.stringify({
    type: "configure",
    confidence: settings.confidence,
    iou: settings.iou,
    classes: settings.classes.length === 0 ? null : [...settings.classes],
    tracking: settings.tracking,
  });
}

export function useDetectionSocket(
  url: string,
  settings: DetectionSettings,
): UseDetectionSocketResult {
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);
  const connectionGenerationRef = useRef(0);
  const shouldReconnectRef = useRef(false);
  const inFlightRef = useRef(false);
  const frameSentAtRef = useRef<number | null>(null);
  const lastResultAtRef = useRef<number | null>(null);
  const settingsRef = useRef(settings);

  const [status, setStatus] =
    useState<ConnectionStatus>("disconnected");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DetectionResult | null>(null);
  const [stats, setStats] = useState<DetectionStats>(INITIAL_STATS);

  const disconnect = useCallback((): void => {
    shouldReconnectRef.current = false;
    connectionGenerationRef.current += 1;
    inFlightRef.current = false;
    frameSentAtRef.current = null;
    lastResultAtRef.current = null;

    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    const socket = socketRef.current;
    socketRef.current = null;
    if (socket) {
      socket.onopen = null;
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;
      if (socket.readyState === 0 || socket.readyState === 1) {
        socket.close(1000, "Client disconnected");
      }
    }

    setStatus("disconnected");
    setError(null);
  }, []);

  const connect = useCallback((): void => {
    const generation = connectionGenerationRef.current + 1;
    connectionGenerationRef.current = generation;
    shouldReconnectRef.current = true;
    reconnectAttemptRef.current = 0;
    inFlightRef.current = false;
    frameSentAtRef.current = null;
    lastResultAtRef.current = null;
    setStats(INITIAL_STATS);
    setResult(null);

    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    const previousSocket = socketRef.current;
    socketRef.current = null;
    if (previousSocket) {
      previousSocket.onopen = null;
      previousSocket.onmessage = null;
      previousSocket.onerror = null;
      previousSocket.onclose = null;
      if (previousSocket.readyState === 0 || previousSocket.readyState === 1) {
        previousSocket.close(1000, "Connection replaced");
      }
    }

    const openSocket = (): void => {
      if (
        !shouldReconnectRef.current ||
        generation !== connectionGenerationRef.current
      ) {
        return;
      }

      if (typeof WebSocket === "undefined") {
        shouldReconnectRef.current = false;
        setStatus("error");
        setError(
          "Live detection is not supported in this browser because WebSocket access is unavailable.",
        );
        return;
      }

      if (url.trim() === "") {
        shouldReconnectRef.current = false;
        setStatus("error");
        setError("The detection server address is missing.");
        return;
      }

      setStatus("connecting");
      setError(null);

      let socket: WebSocket;
      try {
        socket = new WebSocket(url);
      } catch {
        setStatus("error");
        setError(
          "The detection server address is invalid. Check the address and try again.",
        );
        return;
      }

      socket.binaryType = "arraybuffer";
      socketRef.current = socket;

      socket.onopen = () => {
        if (
          generation !== connectionGenerationRef.current ||
          socket !== socketRef.current
        ) {
          socket.close(1000, "Stale connection");
          return;
        }

        reconnectAttemptRef.current = 0;
        inFlightRef.current = false;
        setStatus("connected");
        setError(null);
        try {
          socket.send(configMessage(settingsRef.current));
        } catch {
          setError(
            "Connected to the detection server, but settings could not be sent.",
          );
        }
      };

      socket.onmessage = (event) => {
        void (async () => {
          const text = await messageText(event.data);
          if (
            generation !== connectionGenerationRef.current ||
            socket !== socketRef.current
          ) {
            return;
          }

          let parsed: unknown;
          try {
            parsed = text === null ? null : JSON.parse(text);
          } catch {
            parsed = null;
          }

          if (
            typeof parsed === "object" &&
            parsed !== null &&
            ((parsed as { type?: unknown }).type === "status" ||
              (parsed as { type?: unknown }).type === "configured")
          ) {
            return;
          }

          if (
            typeof parsed === "object" &&
            parsed !== null &&
            (parsed as { type?: unknown }).type === "error"
          ) {
            inFlightRef.current = false;
            frameSentAtRef.current = null;
            const serverMessage = (parsed as { message?: unknown }).message;
            setError(
              typeof serverMessage === "string"
                ? serverMessage
                : "The detection server could not process this frame.",
            );
            return;
          }

          if (!isDetectionResult(parsed)) {
            inFlightRef.current = false;
            frameSentAtRef.current = null;
            setError(
              "The detection server returned an invalid response. The next frame can still be sent.",
            );
            return;
          }

          const receivedAt = timestampNow();
          const sentAt = frameSentAtRef.current;
          const previousResultAt = lastResultAtRef.current;
          const latencyMs =
            sentAt === null
              ? Math.max(0, parsed.totalMs)
              : Math.max(0, receivedAt - sentAt);
          const instantaneousFps =
            previousResultAt === null
              ? parsed.totalMs > 0
                ? 1000 / parsed.totalMs
                : 0
              : receivedAt > previousResultAt
                ? 1000 / (receivedAt - previousResultAt)
                : 0;

          inFlightRef.current = false;
          frameSentAtRef.current = null;
          lastResultAtRef.current = receivedAt;
          setResult(parsed);
          setError(null);
          setStats((previous) => ({
            framesProcessed: previous.framesProcessed + 1,
            latencyMs,
            serverFps:
              previous.serverFps === 0
                ? instantaneousFps
                : previous.serverFps * 0.8 + instantaneousFps * 0.2,
          }));
        })();
      };

      socket.onerror = () => {
        if (
          generation !== connectionGenerationRef.current ||
          socket !== socketRef.current
        ) {
          return;
        }
        setStatus("error");
        setError(
          "The detection server connection encountered an error. Reconnecting automatically.",
        );
      };

      socket.onclose = () => {
        if (
          generation !== connectionGenerationRef.current ||
          socket !== socketRef.current
        ) {
          return;
        }

        socketRef.current = null;
        inFlightRef.current = false;
        frameSentAtRef.current = null;

        if (!shouldReconnectRef.current) {
          setStatus("disconnected");
          return;
        }

        const attempt = reconnectAttemptRef.current;
        reconnectAttemptRef.current += 1;
        const delay = Math.min(
          RECONNECT_BASE_DELAY_MS * 2 ** attempt,
          RECONNECT_MAX_DELAY_MS,
        );
        setStatus("connecting");
        setError(
          "The detection server connection was lost. Reconnecting automatically.",
        );
        reconnectTimerRef.current = setTimeout(openSocket, delay);
      };
    };

    openSocket();
  }, [url]);

  const sendFrame = useCallback((frame: Blob): boolean => {
    const socket = socketRef.current;
    if (socket === null || socket.readyState !== 1 || inFlightRef.current) {
      return false;
    }
    if (frame.size === 0) {
      setError("The camera produced an empty frame. Try capturing another frame.");
      return false;
    }

    try {
      socket.send(frame);
      inFlightRef.current = true;
      frameSentAtRef.current = timestampNow();
      return true;
    } catch {
      inFlightRef.current = false;
      frameSentAtRef.current = null;
      setError(
        "The camera frame could not be sent to the detection server. Try again.",
      );
      return false;
    }
  }, []);

  useEffect(() => {
    settingsRef.current = settings;
    const socket = socketRef.current;
    if (socket === null || socket.readyState !== 1) {
      return;
    }

    let errorTimer: ReturnType<typeof setTimeout> | null = null;
    try {
      socket.send(configMessage(settings));
    } catch {
      errorTimer = setTimeout(() => {
        setError(
          "The updated detection settings could not be sent to the server.",
        );
      }, 0);
    }

    return () => {
      if (errorTimer !== null) {
        clearTimeout(errorTimer);
      }
    };
  }, [settings]);

  useEffect(() => {
    return () => disconnect();
  }, [disconnect]);

  return {
    status,
    error,
    result,
    latestResult: result,
    stats,
    connect,
    disconnect,
    sendFrame,
  };
}
