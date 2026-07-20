import { commas, rndFloat } from '../data/mockData.js';

export default function OperationalQuality({ stats }) {
  const successRate = (stats.successOps / stats.emailsProcessed * 100).toFixed(1);
  const failRate = (stats.failedQueue / stats.emailsProcessed * 100).toFixed(1);
  const avgConfidence = (91.2).toFixed(1);

  const cards = [
    { icon: <polyline points="20 6 9 17 4 12"/>, cls: 'qm-success', val: successRate + '%', label: 'Success Rate' },
    { icon: <><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></>, cls: 'qm-danger', val: failRate + '%', label: 'Failure Rate' },
    { icon: <><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></>, cls: 'qm-info', val: rndFloat(1.4, 1.9, 1) + 's', label: 'Avg Processing Time' },
    { icon: <><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></>, cls: 'qm-info', val: Math.round(600 + Math.random()*180) + 'ms', label: 'Avg API Execution' },
    { icon: <><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></>, cls: 'qm-warning', val: stats.lowConfidencePredictions, label: 'Low Confidence Predictions' },
    { icon: <><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></>, cls: 'qm-warning', val: stats.missingEntities, label: 'Missing Entities' },
    { icon: <><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></>, cls: 'qm-danger', val: stats.unauthorizedRequests, label: 'Unauthorized Requests' },
    { icon: <><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></>, cls: 'qm-muted', val: commas(stats.rejectedEmails), label: 'Rejected Emails' },
    { icon: <><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>, cls: 'qm-warning', val: commas(stats.escalations), label: 'Escalation Count' },
    { icon: <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>, cls: 'qm-info', val: avgConfidence + '%', label: 'Avg Confidence Score' }
  ];

  return (
    <section id="section-op-quality" className="dashboard-section active-section section-op-quality">
      <div className="section-title-bar">
        <h2>📋 Operational Quality</h2>
        <span className="section-question">How reliable is the automation?</span>
      </div>

      <div className="quality-grid">
        {cards.map((c, i) => (
          <div className="quality-metric-card panel-card" key={i}>
            <div className={`qm-icon ${c.cls}`}>
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">{c.icon}</svg>
            </div>
            <div className="qm-val">{c.val}</div>
            <div className="qm-label">{c.label}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
