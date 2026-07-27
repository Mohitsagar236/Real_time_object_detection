import type { DetectionSettings } from "../types/detection";

export interface ClassPreset {
  id: "all" | "people" | "vehicles" | "animals";
  label: string;
  classes: number[];
}

export const DEFAULT_SETTINGS: DetectionSettings = {
  confidence: 0.5,
  iou: 0.45,
  classes: [],
  tracking: true,
  targetFps: 15,
};

export const CLASS_PRESETS: readonly ClassPreset[] = [
  { id: "all", label: "All objects", classes: [] },
  { id: "people", label: "People", classes: [0] },
  { id: "vehicles", label: "Vehicles", classes: [1, 2, 3, 5, 6, 7] },
  {
    id: "animals",
    label: "Animals",
    classes: [14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
  },
];

export const DETECTION_LIMITS = {
  confidence: { min: 0.05, max: 1, step: 0.05 },
  iou: { min: 0.05, max: 1, step: 0.05 },
  targetFps: { min: 1, max: 30, step: 1 },
} as const;

export const RECONNECT_BASE_DELAY_MS = 500;
export const RECONNECT_MAX_DELAY_MS = 10_000;
