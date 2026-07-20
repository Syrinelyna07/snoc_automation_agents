import { useState } from 'react';

const NAV_ITEMS = [
  { id: 'overview', href: '#section-critical', label: 'Dashboard', icon: <rect x="3" y="3" width="7" height="9"/> },
  { id: 'operations', href: '#section-operations', label: 'Live Operations', icon: <polygon points="12 2 2 7 12 12 22 7 12 2"/> },
  { id: 'ai', href: '#section-ai-intelligence', label: 'AI Intelligence', icon: <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/> },
  { id: 'time', href: '#section-time-intelligence', label: 'Time Analytics', icon: <circle cx="12" cy="12" r="10"/> },
  { id: 'business', href: '#section-business-intel', label: 'Business Intel', icon: <line x1="18" y1="20" x2="18" y2="10"/> },
  { id: 'impact', href: '#section-business-impact', label: 'Business Impact', icon: <path d="M21.21 15.89A10 10 0 1 1 8 2.83"/> },
  { id: 'quality', href: '#section-op-quality', label: 'Quality Log', icon: <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/> },
  { id: 'audit', href: '#section-audit', label: 'Audit Trail', icon: <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/> }
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const [active, setActive] = useState('overview');

  return (
    <aside className={`sidebar${collapsed ? ' collapsed' : ''}`} id="sidebar">
      <div className="sidebar-header">
        <div className="logo">
          <span className="logo-red-dot"></span>
          <span className="logo-text">SNOC <span className="logo-subtext">AI AGENT</span></span>
        </div>
        <button id="sidebar-toggle" className="sidebar-collapse-btn" title="Collapse Sidebar" onClick={() => setCollapsed(c => !c)}>
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="11 17 6 12 11 7"/><polyline points="18 17 13 12 18 7"/></svg>
        </button>
      </div>

      <nav className="sidebar-nav">
        <ul>
          {NAV_ITEMS.map(item => (
            <li key={item.id} className={active === item.id ? 'active' : ''} onClick={() => setActive(item.id)}>
              <a href={item.href}>
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{item.icon}</svg>
                <span>{item.label}</span>
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <div className="sidebar-system-info">
        <div className="info-label">DEPLOYMENT</div>
        <div className="info-value">Djezzy Central SNOC</div>
        <div className="info-label">VERSION</div>
        <div className="info-value">v1.4.2</div>
      </div>
    </aside>
  );
}
