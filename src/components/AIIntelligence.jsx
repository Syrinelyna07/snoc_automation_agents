import { useMemo } from 'react';
import ChartCanvas from './ChartCanvas.jsx';
import { REQUEST_TYPES } from '../data/mockData.js';

const INTENT_COLORS = ['#E30613', '#0D0E10', '#4A5568', '#94A3B8', '#F59E0B', '#3B82F6', '#CBD5E1'];

export default function AIIntelligence({ requestPool }) {
  const intentLabels = Object.values(REQUEST_TYPES).map(t => t.key);

  const intentCounts = useMemo(() => {
    const counts = {};
    intentLabels.forEach(l => counts[l] = 0);
    requestPool.forEach(r => counts[r.intent] = (counts[r.intent] || 0) + 1);
    return counts;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestPool]);

  const confidenceBuckets = useMemo(() => {
    const buckets = [0, 0, 0, 0, 0];
    requestPool.forEach(r => {
      if (r.confidence < 70) buckets[0]++;
      else if (r.confidence < 80) buckets[1]++;
      else if (r.confidence < 90) buckets[2]++;
      else if (r.confidence < 95) buckets[3]++;
      else buckets[4]++;
    });
    return buckets;
  }, [requestPool]);

  const entityStats = useMemo(() => {
    let pdv = 0, otp = 0, phones = 0, missing = 0;
    requestPool.forEach(r => {
      if (r.pdv) pdv++;
      if (r.typeKey === 'OTP') otp++;
      if (r.phone) phones++;
      if (r.entity === 'Missing' || r.entity === 'Missing PDV') missing++;
    });
    return { pdv: pdv + 1150, otp: otp + 290, phones: phones + 60, missing: missing + 12 };
  }, [requestPool]);

  const intentData = {
    labels: intentLabels,
    datasets: [{ data: intentLabels.map(l => intentCounts[l]), backgroundColor: INTENT_COLORS, borderWidth: 0 }]
  };

  const confidenceData = {
    labels: ['<70%', '70-80%', '80-90%', '90-95%', '95-100%'],
    datasets: [{ data: confidenceBuckets, backgroundColor: '#E30613', borderRadius: 4 }]
  };

  return (
    <section id="section-ai-intelligence" className="dashboard-section active-section section-ai-intel">
      <div className="section-title-bar">
        <h2>🧠 AI Intelligence</h2>
        <span className="section-question">How well is the AI performing?</span>
      </div>

      <div className="ai-row-a">
        <div className="panel-card chart-card ai-card-large">
          <div className="panel-header">
            <h3>Intent Distribution</h3>
            <span className="panel-subtitle">Classification volume per intent class</span>
          </div>
          <div className="chart-wrapper doughnut-chart-container">
            <ChartCanvas type="doughnut" data={intentData} options={{ responsive: true, maintainAspectRatio: false, cutout: '70%', plugins: { legend: { display: false } } }} />
          </div>
          <div className="intent-legend">
            {intentLabels.map((label, i) => (
              <div key={label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ display: 'flex', alignItems: 'center' }}>
                  <span style={{ width: 10, height: 10, background: INTENT_COLORS[i], display: 'inline-block', marginRight: 8, borderRadius: 2 }}></span>
                  <span style={{ fontSize: 12 }}>{label}</span>
                </span>
                <span style={{ fontSize: 12, fontWeight: 600, color: '#64748B' }}>{intentCounts[label]}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="panel-card chart-card ai-card-large">
          <div className="panel-header">
            <h3>Confidence Distribution</h3>
            <span className="panel-subtitle">Volume vs classification certainty score</span>
          </div>
          <div className="chart-wrapper">
            <ChartCanvas type="bar" data={confidenceData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { grid: { color: '#F1F5F9' } }, x: { grid: { display: false } } } }} />
          </div>
        </div>
      </div>

      <div className="ai-row-b">
        <div className="panel-card entity-stats-card">
          <div className="panel-header">
            <h3>Entity Extraction Pipeline</h3>
            <span className="panel-subtitle">Parsed tokens and validation failures</span>
          </div>
          <div className="entity-stat-grid">
            <div className="entity-stat-box">
              <span className="num">{entityStats.pdv.toLocaleString('en-US')}</span>
              <span className="label">🔒 PDV Codes</span>
              <span className="desc">Point of Sale unique IDs</span>
            </div>
            <div className="entity-stat-box">
              <span className="num">{entityStats.otp.toLocaleString('en-US')}</span>
              <span className="label">🔑 OTP Keys</span>
              <span className="desc">One Time Password strings</span>
            </div>
            <div className="entity-stat-box">
              <span className="num">{entityStats.phones.toLocaleString('en-US')}</span>
              <span className="label">📱 Phone Numbers</span>
              <span className="desc">Customer MSISDN tags</span>
            </div>
            <div className="entity-stat-box text-danger">
              <span className="num">{entityStats.missing.toLocaleString('en-US')}</span>
              <span className="label">⚠ Missing Entities</span>
              <span className="desc">Caused human redirection</span>
            </div>
          </div>
        </div>

        <div className="panel-card model-info-card">
          <div className="panel-header">
            <h3>Model & Dataset Configuration</h3>
          </div>
          <div className="model-meta-grid">
            <div className="meta-item"><span className="meta-label">LLM Engine</span><span className="meta-val">Gemini 2.5 Flash</span></div>
            <div className="meta-item"><span className="meta-label">Pipeline Version</span><span className="meta-val">v1.4.2</span></div>
            <div className="meta-item"><span className="meta-label">Last Retrained</span><span className="meta-val">July 18, 2026</span></div>
            <div className="meta-item"><span className="meta-label">Grounding Dataset</span><span className="meta-val">3,500 Support Emails</span></div>
          </div>
          <div className="model-languages">
            <div className="lang-title">Supported Dialects</div>
            <div className="lang-tags">
              <span className="lang-tag">French (FR)</span>
              <span className="lang-tag">Algerian Arabic (DZ)</span>
              <span className="lang-tag">English (EN)</span>
              <span className="lang-tag">Franco-Arabic SMS</span>
            </div>
          </div>
          <div className="confidence-threshold-box">
            <div className="threshold-header">
              <span className="lbl">Confidence Decision Threshold</span>
              <span className="val">85%</span>
            </div>
            <div className="threshold-slider-wrapper">
              <div className="threshold-bar-bg">
                <div className="threshold-bar-fill" style={{ width: '85%' }}></div>
                <div className="threshold-indicator" style={{ left: '85%' }}></div>
              </div>
              <div className="threshold-legend">
                <span>0% (Escalate All)</span>
                <span className="threshold-active-marker">85% (Target)</span>
                <span>100% (Strict)</span>
              </div>
            </div>
            <p className="threshold-desc">Emails scoring below 85% are automatically flagged and routed to Human Escalation queues.</p>
          </div>
        </div>
      </div>
    </section>
  );
}
