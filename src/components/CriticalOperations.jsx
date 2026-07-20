export default function CriticalOperations({ alerts, dismissAlert }) {
  const active = alerts.filter(a => a.status === 'Active');

  return (
    <section id="section-critical" className="dashboard-section active-section section-critical-ops">
      <div className="section-title-bar">
        <h2>🚨 Critical Operations</h2>
        <span className="section-question">Is something wrong right now?</span>
      </div>

      <div className="alerts-log-container panel-card priority-alerts">
        <div className="panel-header">
          <div className="alert-title-group">
            <h3>Active Alerts</h3>
            <span className="panel-subtitle">Issues requiring immediate attention</span>
          </div>
          <span className="alerts-count-badge">{active.length} Active</span>
        </div>
        <div className="alerts-list-wrapper">
          {active.length === 0
            ? <div style={{ padding: '20px', color: '#94A3B8', textAlign: 'center' }}>No active alerts 🎉</div>
            : active.map(a => (
              <div className="alert-item" key={a.id}>
                <span className={`alert-severity sev-${a.severity}`}></span>
                <span className="alert-item-content">{a.message}</span>
                <span className="alert-item-region">{a.region}</span>
                <span className="alert-item-time">{a.time}</span>
                <button className="alert-dismiss-btn" onClick={() => dismissAlert(a.id)}>Dismiss</button>
              </div>
            ))}
        </div>
      </div>
    </section>
  );
}
