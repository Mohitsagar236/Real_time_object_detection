"use client";

import { useEffect, useState } from "react";

import type { ClassPreset } from "@/lib/detection-config";
import type { DetectionSettings } from "@/types/detection";

interface ControlPanelProps {
  settings: DetectionSettings;
  presets: readonly ClassPreset[];
  activePresetId: string;
  cameraActive: boolean;
  cameraLoading: boolean;
  sessionRunning: boolean;
  detecting: boolean;
  connecting: boolean;
  error: string | null;
  devices: MediaDeviceInfo[];
  selectedDeviceId: string | null;
  onSettingsChange: (settings: DetectionSettings) => void;
  onPresetChange: (preset: ClassPreset) => void;
  onDeviceChange: (deviceId: string) => void;
  onStartCamera: () => void;
  onStartDetection: () => void;
  onStop: () => void;
}

function SliderField({
  id,
  label,
  value,
  valueLabel,
  min,
  max,
  step,
  onChange,
}: {
  id: string;
  label: string;
  value: number;
  valueLabel: string;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
}) {
  const fill = ((value - min) / (max - min)) * 100;
  return (
    <div className="slider-field">
      <div className="field-label">
        <label htmlFor={id}>{label}</label>
        <output htmlFor={id}>{valueLabel}</output>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        style={{ "--range-fill": `${fill}%` } as React.CSSProperties}
      />
    </div>
  );
}

export function ControlPanel({
  settings,
  presets,
  activePresetId,
  cameraActive,
  cameraLoading,
  sessionRunning,
  detecting,
  connecting,
  error,
  devices,
  selectedDeviceId,
  onSettingsChange,
  onPresetChange,
  onDeviceChange,
  onStartCamera,
  onStartDetection,
  onStop,
}: ControlPanelProps) {
  const [settingsOpen, setSettingsOpen] = useState(true);

  useEffect(() => {
    const compactLayout = window.matchMedia("(max-width: 760px)");
    const syncWithLayout = () => setSettingsOpen(!compactLayout.matches);

    syncWithLayout();
    compactLayout.addEventListener("change", syncWithLayout);
    return () => compactLayout.removeEventListener("change", syncWithLayout);
  }, []);

  const modeLabel = error
    ? "Issue"
    : detecting
      ? "Running"
      : sessionRunning || connecting
        ? "Starting"
        : "Standby";

  return (
    <aside className="control-panel" aria-label="Detection inspector">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Quick start</p>
          <h2>Run controls</h2>
        </div>
        <span
          className={`mode-badge ${detecting ? "is-active" : ""} ${
            error ? "is-error" : ""
          }`}
        >
          {modeLabel}
        </span>
      </div>

      <div className="run-actions">
        {!cameraActive ? (
          <button
            className="button button-primary button-wide"
            type="button"
            onClick={onStartCamera}
            disabled={cameraLoading}
          >
            <span aria-hidden="true">●</span>
            {cameraLoading ? "Opening camera…" : "Start camera"}
          </button>
        ) : !sessionRunning ? (
          <button
            className="button button-primary button-wide"
            type="button"
            onClick={onStartDetection}
            disabled={connecting}
          >
            <span aria-hidden="true">⌁</span>
            {connecting ? "Connecting…" : "Start detection"}
          </button>
        ) : detecting ? (
          <button
            className="button button-danger button-wide"
            type="button"
            onClick={onStop}
          >
            <span aria-hidden="true">■</span>
            Stop session
          </button>
        ) : (
          <button
            className="button button-danger button-wide"
            type="button"
            onClick={onStop}
          >
            Cancel startup
          </button>
        )}
      </div>

      {error ? (
        <div className="panel-inline-error" role="status">
          <span aria-hidden="true">!</span>
          <p>{error}</p>
        </div>
      ) : null}

      {devices.length > 1 ? (
        <div className="select-field">
          <label htmlFor="camera-device">Camera source</label>
          <select
            id="camera-device"
            value={selectedDeviceId ?? ""}
            onChange={(event) => onDeviceChange(event.target.value)}
          >
            {devices.map((device, index) => (
              <option key={device.deviceId} value={device.deviceId}>
                {device.label || `Camera ${index + 1}`}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      <details
        className="settings-details"
        open={settingsOpen}
        onToggle={(event) => setSettingsOpen(event.currentTarget.open)}
      >
        <summary>
          <span>
            <strong>Detection settings</strong>
            <small>Confidence, speed, tracking and classes</small>
          </span>
          <span className="summary-action">
            {settingsOpen ? "Close" : "Adjust"}
          </span>
        </summary>

        <div className="settings-content">
          <div className="settings-heading">
            <h3>Detection settings</h3>
            <span>Applied live</span>
          </div>

          <div className="settings-stack">
            <SliderField
              id="confidence"
              label="Confidence"
              value={settings.confidence}
              valueLabel={`${Math.round(settings.confidence * 100)}%`}
              min={0.05}
              max={1}
              step={0.05}
              onChange={(confidence) =>
                onSettingsChange({ ...settings, confidence })
              }
            />
            <SliderField
              id="iou"
              label="Overlap (IoU)"
              value={settings.iou}
              valueLabel={settings.iou.toFixed(2)}
              min={0.05}
              max={1}
              step={0.05}
              onChange={(iou) => onSettingsChange({ ...settings, iou })}
            />
            <SliderField
              id="target-fps"
              label="Target rate"
              value={settings.targetFps}
              valueLabel={`${settings.targetFps} FPS`}
              min={1}
              max={30}
              step={1}
              onChange={(targetFps) =>
                onSettingsChange({ ...settings, targetFps })
              }
            />
          </div>

          <div className="switch-row">
            <div>
              <strong>Object tracking</strong>
              <span>Keep stable IDs between frames</span>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={settings.tracking}
              className={`switch ${settings.tracking ? "is-on" : ""}`}
              onClick={() =>
                onSettingsChange({ ...settings, tracking: !settings.tracking })
              }
            >
              <span />
              <span className="sr-only">
                {settings.tracking ? "Disable" : "Enable"} object tracking
              </span>
            </button>
          </div>

          <div className="preset-section">
            <div className="field-label">
              <span>Class filter</span>
              <span className="filter-count">
                {settings.classes.length === 0
                  ? "80 classes"
                  : `${settings.classes.length} selected`}
              </span>
            </div>
            <div
              className="segmented-control"
              role="group"
              aria-label="Class filter"
            >
              {presets.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  className={activePresetId === preset.id ? "is-selected" : ""}
                  onClick={() => onPresetChange(preset)}
                  aria-pressed={activePresetId === preset.id}
                >
                  {preset.label.replace(" objects", "")}
                </button>
              ))}
            </div>
          </div>
        </div>
      </details>
    </aside>
  );
}
