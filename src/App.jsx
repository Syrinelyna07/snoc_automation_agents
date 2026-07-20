import { useState } from 'react';
import { useDashboard } from './hooks/useDashboard.js';
import { fmtDate } from './data/mockData.js';

import Sidebar from './components/Sidebar.jsx';
import TopNav from './components/TopNav.jsx';
import CriticalOperations from './components/CriticalOperations.jsx';
import PlatformHealth from './components/PlatformHealth.jsx';
import LiveOperations from './components/LiveOperations.jsx';
import AIIntelligence from './components/AIIntelligence.jsx';
import TimeIntelligence from './components/TimeIntelligence.jsx';
import BusinessIntel from './components/BusinessIntel.jsx';
import BusinessImpact from './components/BusinessImpact.jsx';
import OperationalQuality from './components/OperationalQuality.jsx';
import AuditTrail from './components/AuditTrail.jsx';
import DecisionDrawer from './components/DecisionDrawer.jsx';

export default function App() {
  const {
    requestPool, alerts, stats, isAgentActive, consoleLines, now,
    dismissAlert, toggleAgent
  } = useDashboard();

  const [selectedRequest, setSelectedRequest] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  return (
    <div className="app-container">
      <Sidebar />

      <div className="main-wrapper">
        <TopNav
          now={now}
          isAgentActive={isAgentActive}
          toggleAgent={toggleAgent}
          alerts={alerts}
          onSearch={setSearchQuery}
        />

        <main className="dashboard-content">
          <div className="dashboard-header-row">
            <div className="header-welcome">
              <h1>Welcome back to SNOC 👋</h1>
              <p className="header-subtitle">Digital Technical Support Operations Center</p>
            </div>
          </div>

          <CriticalOperations alerts={alerts} dismissAlert={dismissAlert} />
          <PlatformHealth stats={stats} isAgentActive={isAgentActive} now={now} />
          <LiveOperations requestPool={requestPool} consoleLines={consoleLines} onInspect={setSelectedRequest} />
          <AIIntelligence requestPool={requestPool} />
          <TimeIntelligence stats={stats} />
          <BusinessIntel requestPool={requestPool} />
          <BusinessImpact />
          <OperationalQuality stats={stats} />
          <AuditTrail requestPool={requestPool} searchQuery={searchQuery} onInspect={setSelectedRequest} />
        </main>

        <footer className="app-footer">
          <div className="footer-left">
            SNOC AI Agent Operational Control Center &bull; Version 1.4.2 &bull; Digital Technical Support (DTS)
          </div>
          <div className="footer-right">
            Last synchronization: <span>{fmtDate(now)}</span>
          </div>
        </footer>
      </div>

      <DecisionDrawer request={selectedRequest} onClose={() => setSelectedRequest(null)} />
    </div>
  );
}
