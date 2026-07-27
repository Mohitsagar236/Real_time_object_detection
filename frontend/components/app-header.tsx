import type { ConnectionStatus } from "@/types/detection";

interface AppHeaderProps {
  cameraActive: boolean;
  connectionStatus: ConnectionStatus;
  detecting: boolean;
}

function connectionLabel(status: ConnectionStatus): string {
  if (status === "connected") return "Detector ready";
  if (status === "connecting") return "Starting detector";
  if (status === "error") return "Detector unavailable";
  return "Detector idle";
}

export function AppHeader({
  cameraActive,
  connectionStatus,
  detecting,
}: AppHeaderProps) {
  return (
    <header className="app-header">
      <a className="brand" href="#workspace" aria-label="VisionDesk home">
        <span className="brand-mark" aria-hidden="true">
          VD
        </span>
        <span>
          <strong>VisionDesk</strong>
          <small>Realtime object intelligence</small>
        </span>
      </a>

      <div className="header-status" aria-label="System status">
        <div className="status-item">
          <span
            className={`status-dot ${cameraActive ? "is-live" : ""}`}
            aria-hidden="true"
          />
          <span>{cameraActive ? "Camera ready" : "Camera idle"}</span>
        </div>
        <span className="status-divider" aria-hidden="true" />
        <div className="status-item">
          <span
            className={`status-dot ${
              connectionStatus === "connected" ? "is-live" : ""
            } ${connectionStatus === "error" ? "is-error" : ""}`}
            aria-hidden="true"
          />
          <span>{connectionLabel(connectionStatus)}</span>
        </div>
        {detecting ? <span className="live-pill">Live detection</span> : null}
      </div>
    </header>
  );
}
