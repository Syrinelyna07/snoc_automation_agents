import { useMemo, Fragment } from 'react';
import ChartCanvas from './ChartCanvas.jsx';
import { pad2, rnd } from '../data/mockData.js';

function useHeatmapData() {
  return useMemo(() => {
    const data = Array(7).fill().map(() => Array(24).fill(0));
    for (let d = 0; d < 7; d++) {
      for (let h = 0; h < 24; h++) {
        if (d < 5) {
          if (h >= 8 && h <= 11) data[d][h] = rnd(15, 30);
          else if (h >= 14 && h <= 16) data[d][h] = rnd(10, 20);
          else data[d][h] = rnd(1, 8);
        } else {
          data[d][h] = rnd(1, 6);
        }
      }
    }
    return data;
  }, []);
}

function heatClass(val) {
  if (val >= 25) return 'heat-5';
  if (val >= 19) return 'heat-4';
  if (val >= 14) return 'heat-3';
  if (val >= 9) return 'heat-2';
  if (val >= 4) return 'heat-1';
  return 'heat-0';
}

export default function TimeIntelligence({ stats }) {
  const heatmap = useHeatmapData();
  const days = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  const hours = Array.from({ length: 24 }, (_, i) => pad2(i));

  const hourlyData = { labels: hours, datasets: [{ data: stats.hourlyRequests, borderColor: '#E30613', backgroundColor: 'rgba(227,6,19,0.08)', fill: true, tension: 0.4, pointRadius: 2, pointHoverRadius: 5 }] };
  const weeklyData = { labels: days, datasets: [{ data: stats.weeklyRequests, backgroundColor: '#E30613', borderRadius: 4 }] };

  return (
    <section id="section-time-intelligence" className="dashboard-section active-section section-time-intel">
      <div className="section-title-bar">
        <h2>⏰ Time Intelligence</h2>
        <span className="section-question">When do problems happen?</span>
      </div>

      <div className="time-intel-grid">
        <div className="panel-card chart-card time-hourly-card">
          <div className="panel-header">
            <h3>Requests Per Hour</h3>
            <span className="panel-subtitle">24-hour volume distribution</span>
          </div>
          <div className="chart-wrapper">
            <ChartCanvas type="line" data={hourlyData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: '#F1F5F9' } }, x: { grid: { display: false } } } }} />
          </div>
        </div>

        <div className="time-summary-stack">
          <div className="panel-card peak-hours-card">
            <div className="panel-header"><h3>Peak Support Hours</h3></div>
            <div className="peak-hours-list">
              <div className="peak-item peak-critical"><span className="peak-rank">1</span><span className="peak-time">09:00 – 10:00</span><span className="peak-vol">218</span></div>
              <div className="peak-item peak-high"><span className="peak-rank">2</span><span className="peak-time">10:00 – 11:00</span><span className="peak-vol">186</span></div>
              <div className="peak-item peak-medium"><span className="peak-rank">3</span><span className="peak-time">14:00 – 15:00</span><span className="peak-vol">154</span></div>
            </div>
          </div>

          <div className="panel-card weekly-trend-card">
            <div className="panel-header">
              <h3>Weekly Trend</h3>
              <span className="panel-subtitle">7-day request evolution</span>
            </div>
            <div className="chart-wrapper">
              <ChartCanvas type="bar" data={weeklyData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: '#F1F5F9' } }, x: { grid: { display: false } } } }} />
            </div>
          </div>
        </div>
      </div>

      <div className="panel-card heatmap-card">
        <div className="panel-header">
          <h3>Support Load Heatmap</h3>
          <span className="panel-subtitle">Day × Hour intensity — darker = higher volume</span>
        </div>
        <div className="heatmap-container" style={{ display: 'grid', gridTemplateColumns: 'auto repeat(24, 1fr)', gap: 2 }}>
          <div></div>
          {hours.map(h => <div key={'h'+h} className="heatmap-hour-label" style={{ fontSize: 10, textAlign: 'center' }}>{h}</div>)}
          {days.map((day, d) => (
            <Fragment key={day}>
              <div className="heatmap-label" style={{ fontSize: 12, paddingRight: 8, textAlign: 'right' }}>{day}</div>
              {hours.map((_, h) => (
                <div key={`${day}-${h}`} className={`heatmap-cell ${heatClass(heatmap[d][h])}`} title={`${day} ${pad2(h)}:00 — ${heatmap[d][h]} requests`} style={{ borderRadius: 2 }}></div>
              ))}
            </Fragment>
          ))}
        </div>
      </div>
    </section>
  );
}
