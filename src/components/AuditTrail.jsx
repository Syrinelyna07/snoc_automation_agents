import { useState, useMemo } from 'react';

const FILTERS = [
  { key: 'all', label: 'All Requests' },
  { key: 'Locked', label: 'Locked Accounts' },
  { key: 'OTP', label: 'OTP Update' },
  { key: 'VPN', label: 'VPN Creation' },
  { key: 'Reset Password', label: 'Password Reset' },
  { key: 'Escalated', label: 'Escalated', danger: true },
  { key: 'Irrelevant', label: 'Irrelevant' }
];

function statusBadgeClass(status) {
  return { Success: 'badge-success', Processing: 'badge-processing', Escalated: 'badge-escalated', Rejected: 'badge-rejected' }[status] || 'badge-warning';
}

export default function AuditTrail({ requestPool, searchQuery, onInspect }) {
  const [filter, setFilter] = useState('all');

  const filtered = useMemo(() => {
    const q = (searchQuery || '').toLowerCase().trim();
    return requestPool.filter(req => {
      let matchFilter = true;
      if (filter !== 'all') {
        matchFilter = filter === 'Escalated' ? req.status === 'Escalated' : req.intent.toLowerCase().includes(filter.toLowerCase());
      }
      const matchSearch = q === '' ||
        req.id.toLowerCase().includes(q) || req.sender.toLowerCase().includes(q) ||
        req.intent.toLowerCase().includes(q) || (req.pdv && req.pdv.includes(q)) ||
        (req.phone && req.phone.includes(q)) || req.status.toLowerCase().includes(q) ||
        req.zone.toLowerCase().includes(q);
      return matchFilter && matchSearch;
    });
  }, [requestPool, filter, searchQuery]);

  const shown = filtered.slice(0, 40);

  return (
    <section id="section-audit" className="dashboard-section active-section section-audit-trail">
      <div className="section-title-bar">
        <h2>📜 Audit Trail</h2>
        <span className="section-question">What exactly happened?</span>
      </div>

      <div className="audit-history-container panel-card">
        <div className="filters-container">
          <div className="quick-filters">
            {FILTERS.map(f => (
              <button
                key={f.key}
                className={`filter-btn${filter === f.key ? ' active' : ''}${f.danger ? ' text-danger' : ''}`}
                onClick={() => setFilter(f.key)}
              >{f.label}</button>
            ))}
          </div>
          <div className="table-results-counter">
            Showing <span>{shown.length}</span> of <span>{requestPool.length}</span> audit logs
          </div>
        </div>

        <div className="table-scroll-wrapper">
          <table className="audit-table">
            <thead>
              <tr>
                <th>Timestamp</th><th>Sender (Supervisor)</th><th>Zone</th><th>Intent</th>
                <th>Confidence</th><th>PDV Code</th><th>Execution Time</th><th>Status</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {shown.length === 0 ? (
                <tr><td colSpan="9" style={{ textAlign: 'center', padding: 40, color: '#94A3B8' }}>🤖 No requests match this filter</td></tr>
              ) : shown.map(req => (
                <tr key={req.id} style={{ cursor: 'pointer' }} onClick={() => onInspect(req)}>
                  <td>{req.time}</td>
                  <td>{req.sender}</td>
                  <td>{req.zone}</td>
                  <td>{req.icon} {req.intent}</td>
                  <td>{req.confidence}%</td>
                  <td>{req.pdv || '—'}</td>
                  <td>{req.duration}</td>
                  <td><span className={`badge ${statusBadgeClass(req.status)}`}>{req.status}</span></td>
                  <td><button className="actions-btn" title="Inspect">🔍</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
