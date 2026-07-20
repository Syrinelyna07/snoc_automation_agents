import { commas, fmtTime, rndFloat } from '../data/mockData.js';

export default function PlatformHealth({ stats, isAgentActive, now }) {
  const automationRate = ((stats.successOps / stats.emailsProcessed) * 100).toFixed(1);

  return (
    <section id="section-health" className="dashboard-section active-section section-platform-health">
      <div className="section-title-bar">
        <h2>⚙️ Platform Health</h2>
        <span className="section-question">Is the platform healthy?</span>
      </div>

      <div className="health-kpi-grid">
        <div className="health-kpi-item">
          <div className="health-kpi-icon status-icon-active">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>
          </div>
          <div className="health-kpi-data">
            <span className="health-kpi-val status-green">{isAgentActive ? 'ACTIVE 🟢' : 'PAUSED 🟠'}</span>
            <span className="health-kpi-label">Agent Status</span>
          </div>
        </div>
        <div className="health-kpi-item">
          <div className="health-kpi-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
          </div>
          <div className="health-kpi-data">
            <span className="health-kpi-val">{automationRate}%</span>
            <span className="health-kpi-label">Automation Rate</span>
          </div>
        </div>
        <div className="health-kpi-item">
          <div className="health-kpi-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
          </div>
          <div className="health-kpi-data">
            <span className="health-kpi-val">{commas(stats.emailsProcessed)}</span>
            <span className="health-kpi-label">Emails Today</span>
          </div>
        </div>
        <div className="health-kpi-item">
          <div className="health-kpi-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
          </div>
          <div className="health-kpi-data">
            <span className="health-kpi-val badge-alert">{stats.waitingQueue + stats.processingQueue}</span>
            <span className="health-kpi-label">Current Queue</span>
          </div>
        </div>
        <div className="health-kpi-item">
          <div className="health-kpi-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          </div>
          <div className="health-kpi-data">
            <span className="health-kpi-val">{rndFloat(1.3, 2.1, 1)}s</span>
            <span className="health-kpi-label">Avg Response Time</span>
          </div>
        </div>
        <div className="health-kpi-item">
          <div className="health-kpi-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          </div>
          <div className="health-kpi-data">
            <span className="health-kpi-val text-warning">{commas(stats.escalations)}</span>
            <span className="health-kpi-label">Human Escalations</span>
          </div>
        </div>
        <div className="health-kpi-item">
          <div className="health-kpi-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
          </div>
          <div className="health-kpi-data">
            <span className="health-kpi-val">{rndFloat(96.5, 99.2, 1)}%</span>
            <span className="health-kpi-label">API Health</span>
          </div>
        </div>
        <div className="health-kpi-item">
          <div className="health-kpi-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
          </div>
          <div className="health-kpi-data">
            <span className="health-kpi-val text-muted">{fmtTime(now)}</span>
            <span className="health-kpi-label">Last Sync</span>
          </div>
        </div>
      </div>
    </section>
  );
}
