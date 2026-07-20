import { useState, useRef, useEffect } from 'react';
import { fmtTime } from '../data/mockData.js';

export default function TopNav({ now, isAgentActive, toggleAgent, alerts, onSearch }) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const notifRef = useRef(null);
  const activeAlerts = alerts.filter(a => a.status === 'Active');

  useEffect(() => {
    function onClickOutside(e) {
      if (notifRef.current && !notifRef.current.contains(e.target)) setDropdownOpen(false);
    }
    document.addEventListener('click', onClickOutside);
    return () => document.removeEventListener('click', onClickOutside);
  }, []);

  return (
    <header className="top-nav">
      <div className="search-container">
        <svg className="search-icon" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input type="text" id="global-search" placeholder="Search by PDV, sender, email, phone or request..." onChange={e => onSearch(e.target.value)} />
        <span className="search-kbd">⌘K</span>
      </div>

      <div className="top-nav-actions">
        <button id="agent-toggle-btn" className="btn btn-secondary" onClick={toggleAgent}>
          <span className={`btn-indicator${isAgentActive ? ' active' : ''}`}></span>
          <span>{isAgentActive ? 'Pause Agent' : 'Resume Agent'}</span>
        </button>

        <div className="status-bubble-container" title="Current operational status of SNOC AI">
          <span className={`status-bubble${isAgentActive ? ' active' : ''}`}></span>
          <span className="status-bubble-text">{isAgentActive ? 'Agent Active' : 'Agent Paused'}</span>
        </div>

        <div className="sync-panel">
          <span className="sync-label">Sync:</span>
          <span className="sync-value">{fmtTime(now)}</span>
        </div>

        <div className="notifications-btn" ref={notifRef}>
          <div onClick={(e) => { e.stopPropagation(); setDropdownOpen(o => !o); }} style={{ cursor: 'pointer' }}>
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
            <span className="notification-badge">{activeAlerts.length}</span>
          </div>
          <div className={`notifications-dropdown${dropdownOpen ? ' show' : ''}`}>
            <div className="dropdown-header">Active Operational Warnings</div>
            <div className="dropdown-list">
              {activeAlerts.length === 0
                ? <div style={{ padding: '16px', color: '#94A3B8', textAlign: 'center' }}>No active alerts</div>
                : activeAlerts.map(a => (
                  <div className="alert-item" key={a.id}>
                    <span className={`alert-severity sev-${a.severity}`}></span>
                    <span className="alert-item-content">{a.message}</span>
                    <span className="alert-item-region">{a.region}</span>
                    <span className="alert-item-time">{a.time}</span>
                  </div>
                ))}
            </div>
          </div>
        </div>

        <div className="user-profile">
          <div className="avatar">DT</div>
          <div className="user-details">
            <span className="username">TechSupport Ops</span>
            <span className="user-role">Djezzy SNOC supervisor</span>
          </div>
        </div>
      </div>
    </header>
  );
}
