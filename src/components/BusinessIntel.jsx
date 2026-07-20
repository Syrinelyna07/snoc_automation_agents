import { useMemo } from 'react';
import ChartCanvas from './ChartCanvas.jsx';

export default function BusinessIntel({ requestPool }) {
  const regionCounts = useMemo(() => {
    const counts = { 'Zone East': 0, 'Zone Center': 0, 'Zone West': 0, 'South Region': 0 };
    requestPool.forEach(r => counts[r.zone] = (counts[r.zone] || 0) + 1);
    return counts;
  }, [requestPool]);

  const regionData = {
    labels: Object.keys(regionCounts),
    datasets: [{ data: Object.values(regionCounts), backgroundColor: ['#0D0E10', '#E30613', '#4A5568', '#94A3B8'], barThickness: 20 }]
  };

  return (
    <section id="section-business-intel" className="dashboard-section active-section section-biz-intel">
      <div className="section-title-bar">
        <h2>📈 Business Intelligence</h2>
        <span className="section-question">Where are the operational problems?</span>
      </div>

      <div className="biz-row-a">
        <div className="panel-card funnel-card">
          <div className="panel-header">
            <h3>Automation Pipeline Funnel</h3>
            <span className="panel-subtitle">Where support requests filter or drop off</span>
          </div>
          <div className="funnel-container">
            <div className="funnel-stage" style={{ width: '100%' }}><span className="stage-name">Incoming Support Emails</span><span className="stage-value">3,400</span></div>
            <div className="funnel-stage" style={{ width: '94%' }}><span className="stage-name">Sender Whitelisted</span><span className="stage-value">3,200</span></div>
            <div className="funnel-stage" style={{ width: '92%' }}><span className="stage-name">Successfully Classified</span><span className="stage-value">3,150</span></div>
            <div className="funnel-stage" style={{ width: '91%' }}><span className="stage-name">Entities Extracted</span><span className="stage-value">3,120</span></div>
            <div className="funnel-stage" style={{ width: '90%' }}><span className="stage-name">API Checks Valid</span><span className="stage-value">3,090</span></div>
            <div className="funnel-stage funnel-stage-success" style={{ width: '88%' }}><span className="stage-name">Completed Automatically</span><span className="stage-value">3,020</span></div>
            <div className="funnel-stage funnel-stage-escalated" style={{ width: '12%' }}><span className="stage-name">Escalated to Human Agent</span><span className="stage-value">70</span></div>
          </div>
        </div>

        <div className="panel-card region-card">
          <div className="panel-header">
            <h3>Regional Traffic Distribution</h3>
            <span className="panel-subtitle">POS distribution by supervisor zones</span>
          </div>
          <div className="chart-wrapper">
            <ChartCanvas type="bar" data={regionData} options={{ indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { color: '#F1F5F9' } }, y: { grid: { display: false } } } }} />
          </div>
        </div>
      </div>

      <div className="biz-row-b">
        <div className="panel-card regional-blocking-card">
          <div className="panel-header">
            <h3>Regional Blocking Analysis</h3>
            <span className="panel-subtitle">Zones generating the most blocked accounts</span>
          </div>
          <div className="blocking-list">
            <div className="blocking-item">
              <div className="blocking-zone">Zone East</div>
              <div className="blocking-bar-wrapper"><div className="blocking-bar" style={{ width: '100%' }}></div></div>
              <div className="blocking-count">520</div>
            </div>
            <div className="blocking-item">
              <div className="blocking-zone">Zone Center</div>
              <div className="blocking-bar-wrapper"><div className="blocking-bar bar-center" style={{ width: '60%' }}></div></div>
              <div className="blocking-count">310</div>
            </div>
            <div className="blocking-item">
              <div className="blocking-zone">Zone West</div>
              <div className="blocking-bar-wrapper"><div className="blocking-bar bar-west" style={{ width: '35%' }}></div></div>
              <div className="blocking-count">180</div>
            </div>
          </div>
          <div className="blocking-avg">
            <span className="lbl">Avg incidents per POS:</span>
            <span className="val">2.4</span>
          </div>
        </div>

        <div className="panel-card unstable-pos-card">
          <div className="panel-header">
            <h3>Top Unstable POS</h3>
            <span className="panel-subtitle">Highest repeat incident terminals</span>
          </div>
          <div className="unstable-pos-list">
            <div className="pos-row"><span className="pos-code">POS 77481232</span><span className="pos-count">12 incidents</span><span className="pos-zone">Zone East</span></div>
            <div className="pos-row"><span className="pos-code">POS 55490112</span><span className="pos-count">10 incidents</span><span className="pos-zone">Zone Center</span></div>
            <div className="pos-row"><span className="pos-code">POS 66123098</span><span className="pos-count">8 incidents</span><span className="pos-zone">Zone East</span></div>
            <div className="pos-row"><span className="pos-code">POS 33246718</span><span className="pos-count">6 incidents</span><span className="pos-zone">Zone West</span></div>
            <div className="pos-row"><span className="pos-code">POS 99346281</span><span className="pos-count">5 incidents</span><span className="pos-zone">Zone Center</span></div>
          </div>
        </div>
      </div>
    </section>
  );
}
