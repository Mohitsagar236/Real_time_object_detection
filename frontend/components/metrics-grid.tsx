interface MetricsGridProps {
  fps: number;
  latencyMs: number;
  inferenceMs: number;
  objectCount: number;
}

const metrics = [
  { key: "fps", label: "Live rate", suffix: "FPS", icon: "↗" },
  { key: "latency", label: "Round trip", suffix: "ms", icon: "⌁" },
  { key: "inference", label: "Inference", suffix: "ms", icon: "◫" },
  { key: "objects", label: "In frame", suffix: "objects", icon: "◎" },
] as const;

export function MetricsGrid({
  fps,
  latencyMs,
  inferenceMs,
  objectCount,
}: MetricsGridProps) {
  const values = {
    fps: fps > 0 ? fps.toFixed(1) : "—",
    latency: latencyMs > 0 ? Math.round(latencyMs).toString() : "—",
    inference: inferenceMs > 0 ? inferenceMs.toFixed(1) : "—",
    objects: objectCount.toString(),
  };

  return (
    <section className="metrics-grid" aria-label="Live performance metrics">
      {metrics.map((metric) => (
        <article className="metric-card" key={metric.key}>
          <div className="metric-icon" aria-hidden="true">
            {metric.icon}
          </div>
          <div>
            <span>{metric.label}</span>
            <strong>
              {values[metric.key]} <small>{metric.suffix}</small>
            </strong>
          </div>
        </article>
      ))}
    </section>
  );
}
