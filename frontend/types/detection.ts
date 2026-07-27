export interface Detection {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  confidence: number;
  classId: number;
  label: string;
  trackId: number | null;
}

export interface DetectionResult {
  type: "result";
  frameId: number;
  width: number;
  height: number;
  inferenceMs: number;
  totalMs: number;
  detections: Detection[];
  classCounts: Record<string, number>;
  timestamp: number;
}

export interface DetectionSettings {
  confidence: number;
  iou: number;
  classes: number[];
  tracking: boolean;
  targetFps: number;
}

export type ConnectionStatus =
  | "disconnected"
  | "connecting"
  | "connected"
  | "error";

export interface DetectionStats {
  framesProcessed: number;
  latencyMs: number;
  serverFps: number;
}
