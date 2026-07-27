import type { Detection, DetectionResult } from "@/types/detection";

interface ObjectListProps {
  result: DetectionResult | null;
  detecting: boolean;
}

function ObjectRow({
  detection,
  index,
}: {
  detection: Detection;
  index: number;
}) {
  return (
    <li>
      <div className={`object-swatch swatch-${index % 5}`} aria-hidden="true" />
      <div className="object-name">
        <strong>{detection.label}</strong>
        <span>
          Class {detection.classId}
          {detection.trackId === null ? "" : ` · Track #${detection.trackId}`}
        </span>
      </div>
      <div className="confidence-value">
        <strong>{Math.round(detection.confidence * 100)}%</strong>
        <span>conf.</span>
      </div>
    </li>
  );
}

export function ObjectList({ result, detecting }: ObjectListProps) {
  const detections = [...(result?.detections ?? [])].sort(
    (left, right) => right.confidence - left.confidence,
  );
  const counts = Object.entries(result?.classCounts ?? {}).sort(
    (left, right) => right[1] - left[1],
  );

  return (
    <section className="objects-card" aria-labelledby="objects-heading">
      <div className="objects-header">
        <div>
          <p className="eyebrow">Current frame</p>
          <h2 id="objects-heading">Detected objects</h2>
        </div>
        <span className="object-total">
          {detections.length.toString().padStart(2, "0")}
        </span>
      </div>

      {counts.length > 0 ? (
        <div className="class-counts" aria-label="Class counts">
          {counts.map(([label, count]) => (
            <span key={label}>
              {label} <strong>{count}</strong>
            </span>
          ))}
        </div>
      ) : null}

      {detections.length > 0 ? (
        <ul className="object-rows">
          {detections.slice(0, 8).map((detection, index) => (
            <ObjectRow
              key={`${detection.trackId ?? "untracked"}-${detection.classId}-${index}`}
              detection={detection}
              index={index}
            />
          ))}
        </ul>
      ) : (
        <div className="objects-empty">
          <div className="radar-icon" aria-hidden="true">
            <span />
          </div>
          <strong>
            {detecting ? "Watching the scene" : "Detection is standing by"}
          </strong>
          <p>
            {detecting
              ? "Objects above your confidence threshold will appear here."
              : "Start the camera, then detection, to populate this live feed."}
          </p>
        </div>
      )}

      <div className="objects-footer">
        <span>
          {result ? `Frame ${result.frameId}` : "No frame received"}
        </span>
        <span>
          {result ? `${Math.round(result.totalMs)} ms total` : "— ms total"}
        </span>
      </div>
    </section>
  );
}
