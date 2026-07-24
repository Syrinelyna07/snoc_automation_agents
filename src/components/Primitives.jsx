export function MetricRibbon({ items }) {
  return (
    <section className="metric-ribbon dashboard-card">
      <div className="section-eyebrow">By numbers</div>
      <div className="metric-ribbon-grid">
        {items.map((item) => (
          <div className="metric-ribbon-item" key={item.label}>
            <strong>{item.value}</strong>
            <span>{item.label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

export function KpiCard({ value, label, suffix = "", tone = "default" }) {
  return (
    <article className={`mini-kpi dashboard-card ${tone}`}>
      <strong>{value}<small>{suffix}</small></strong>
      <span>{label}</span>
    </article>
  );
}

export function ChartCard({ title, subtitle, children, className = "" }) {
  return (
    <article className={`chart-card dashboard-card ${className}`}>
      <div className="card-heading">
        <h2>{title}</h2>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
      <div className="chart-content">{children}</div>
    </article>
  );
}

export function StatusBadge({ value }) {
  const normalized = String(value || "Unknown").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
  return <span className={`status-badge ${normalized}`}>{value}</span>;
}

export function EmptyState({ title, description }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <span>{description}</span>
    </div>
  );
}
