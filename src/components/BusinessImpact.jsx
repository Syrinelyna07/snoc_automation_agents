export default function BusinessImpact() {
  return (
    <section id="section-business-impact" className="dashboard-section active-section section-biz-impact">
      <div className="section-title-bar">
        <h2>💰 Business Impact</h2>
        <span className="section-question">What value is the AI creating?</span>
      </div>

      <div className="impact-grid">
        <div className="panel-card impact-hero-card">
          <div className="panel-header">
            <h3>Financial ROI & Operational Value</h3>
            <span className="panel-subtitle">Real-time business impact of AI automation</span>
          </div>
          <div className="roi-metrics-grid">
            <div className="roi-metric">
              <span className="roi-metric-val">126 h</span>
              <span className="roi-metric-label">Hours Saved (Monthly)</span>
              <div className="roi-progress"><div className="fill" style={{ width: '78%' }}></div></div>
            </div>
            <div className="roi-metric">
              <span className="roi-metric-val">1.8M DZD</span>
              <span className="roi-metric-label">Estimated Financial Gain</span>
              <div className="roi-progress"><div className="fill" style={{ width: '65%' }}></div></div>
            </div>
            <div className="roi-metric">
              <span className="roi-metric-val">98.7%</span>
              <span className="roi-metric-label">Recovered POS Availability</span>
              <div className="roi-progress"><div className="fill" style={{ width: '98.7%' }}></div></div>
            </div>
            <div className="roi-metric">
              <span className="roi-metric-val">1,480</span>
              <span className="roi-metric-label">Manual Operations Avoided</span>
              <div className="roi-progress"><div className="fill" style={{ width: '87%' }}></div></div>
            </div>
            <div className="roi-metric">
              <span className="roi-metric-val">4.2 h</span>
              <span className="roi-metric-label">POS Downtime Avoided</span>
              <div className="roi-progress"><div className="fill" style={{ width: '42%' }}></div></div>
            </div>
            <div className="roi-metric">
              <span className="roi-metric-val">3.4×</span>
              <span className="roi-metric-label">Productivity Gain vs Manual</span>
              <div className="roi-progress"><div className="fill" style={{ width: '85%' }}></div></div>
            </div>
          </div>
        </div>

        <div className="panel-card api-monitor-card">
          <div className="panel-header">
            <h3>SNOC API Health</h3>
            <span className="panel-subtitle">Response rates & latency profiles</span>
          </div>
          <div className="api-grid">
            <div className="api-item">
              <div className="api-header-row"><span className="api-name">POS Unlock API</span><span className="api-pct success-green">98%</span></div>
              <div className="api-bar"><div className="fill bg-success" style={{ width: '98%' }}></div></div>
              <span className="api-latency">Latency: 720ms</span>
            </div>
            <div className="api-item">
              <div className="api-header-row"><span className="api-name">Password Reset API</span><span className="api-pct success-green">100%</span></div>
              <div className="api-bar"><div className="fill bg-success" style={{ width: '100%' }}></div></div>
              <span className="api-latency">Latency: 450ms</span>
            </div>
            <div className="api-item">
              <div className="api-header-row"><span className="api-name">VPN Whitelist API</span><span className="api-pct text-warning">96%</span></div>
              <div className="api-bar"><div className="fill bg-warning" style={{ width: '96%' }}></div></div>
              <span className="api-latency">Latency: 940ms</span>
            </div>
            <div className="api-item">
              <div className="api-header-row"><span className="api-name">OTP Config API</span><span className="api-pct success-green">97%</span></div>
              <div className="api-bar"><div className="fill bg-success" style={{ width: '97%' }}></div></div>
              <span className="api-latency">Latency: 510ms</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
