import { useEffect, useRef } from 'react';

function statusBadgeClass(status) {
  return { Success: 'badge-success', Processing: 'badge-processing', Escalated: 'badge-escalated', Rejected: 'badge-rejected' }[status] || 'badge-warning';
}

export default function LiveOperations({ requestPool, consoleLines, onInspect }) {
  const consoleRef = useRef(null);

  useEffect(() => {
    if (consoleRef.current) consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
  }, [consoleLines]);

  const rows = requestPool.slice(0, 22);

  return (
    <section id="section-operations" className="dashboard-section active-section section-live-ops">
      <div className="section-title-bar">
        <h2>📩 Live Operations</h2>
        <div className="section-title-right">
          <span className="section-question">What is the AI doing right now?</span>
          <span className="live-pulse">LIVE</span>
        </div>
      </div>

      <div className="live-ops-grid">
        {/* Left: Live Email Timeline */}
        <div className="timeline-container panel-card">
          <div className="panel-header">
            <h3>Live Email Activity Timeline</h3>
            <span className="panel-subtitle">Click any row to inspect AI decision lifecycle</span>
          </div>
          <div className="timeline-scroll-area">
            {rows.map(req => (
              <div className="timeline-row" key={req.id} onClick={() => onInspect(req)}>
                <div className="time-col">{req.time}</div>
                <div className="sender-col">{req.sender}</div>
                <div className="intent-col">{req.icon} {req.intent}</div>
                <div className="pdv-col">{req.entity}</div>
                <div className="duration-col">{req.duration}</div>
                <div><span className={`badge ${statusBadgeClass(req.status)}`}>{req.status}</span></div>
                <div style={{ textAlign: 'right', color: '#94A3B8' }}>›</div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Execution Console */}
        <div className="monitoring-right-grid">
          <div className="console-container panel-card">
            <div className="panel-header">
              <h3>💻 Execution Console</h3>
              <div className="console-actions">
                <span className="console-status-dot"></span>
                <span className="console-status-label">SYS_LOGS</span>
              </div>
            </div>
            <div className="console-body" ref={consoleRef}>
              {consoleLines.map((l, i) => (
                <div className={`console-line ${l.cls || ''}`} key={i}>{l.text}</div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
