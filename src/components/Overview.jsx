import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartCard, KpiCard, MetricRibbon, StatusBadge } from "./Primitives";

function formatSeconds(ms) {
  if (ms === null || ms === undefined) return "—";
  return (Number(ms) / 1000).toFixed(2);
}

export default function Overview({ data, onSelect }) {
  const op = data.summary.operational;
  const intents = data.intents || [];
  const trends = data.trends || [];

  return (
    <>
      <MetricRibbon
        items={[
          { label: "Incoming requests", value: op.totalRequests ?? 0 },
          { label: "Automatically resolved", value: op.autoResolved ?? 0 },
          { label: "In progress", value: op.inProgress ?? 0 },
          { label: "Manual review", value: op.manualReview ?? 0 },
        ]}
      />

      <section className="reference-dashboard-grid">
        <div className="reference-left-column">
          <KpiCard value={formatSeconds(op.averageProcessingMs)} suffix="s" label="Average processing time" />
          <KpiCard value={(op.readinessRate ?? 0).toFixed(1)} suffix="%" label="Agent readiness rate" />
        </div>

        <ChartCard title="Average processing time" subtitle="SNOC request processing trend" className="reference-area-card">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trends} margin={{ top: 12, right: 12, left: -16, bottom: 0 }}>
              <defs>
                <linearGradient id="processingFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2563eb" stopOpacity={0.28} />
                  <stop offset="100%" stopColor="#2563eb" stopOpacity={0.07} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e6e8eb" vertical={false} />
              <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: "#a7abb0" }} tick={{ fill: "#8a8f95", fontSize: 13 }} />
              <YAxis tickFormatter={(value) => `${(value / 1000).toFixed(1)}`} tickLine={false} axisLine={{ stroke: "#a7abb0" }} tick={{ fill: "#8a8f95", fontSize: 12 }} />
              <Tooltip formatter={(value) => [`${(Number(value) / 1000).toFixed(2)} s`, "Processing time"]} />
              <Area type="monotone" dataKey="averageProcessingMs" stroke="#2563eb" strokeWidth={2} fill="url(#processingFill)" />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Intent distribution" subtitle="Current SNOC request mix" className="reference-donut-card">
          <div className="donut-layout">
            <div className="donut-chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={intents} dataKey="value" nameKey="name" innerRadius="72%" outerRadius="83%" paddingAngle={2}>
                    {intents.map((item) => <Cell key={item.name} fill={item.color} />)}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="donut-center">
                <strong>{intents.reduce((sum, item) => sum + Number(item.value || 0), 0)}</strong>
                <span>Requests</span>
              </div>
            </div>
            <div className="donut-legend">
              {intents.map((item) => (
                <div key={item.name}><i style={{ background: item.color }} /><span>{item.name}</span><strong>{item.value}</strong></div>
              ))}
            </div>
          </div>
        </ChartCard>
      </section>

      <section className="requests-card dashboard-card">
        <div className="table-title-row">
          <div>
            <h2>Latest requests and agent decisions</h2>
            <p>Most recent automated and escalated SNOC requests</p>
          </div>
          <span>{data.recent.length} latest</span>
        </div>
        <div className="table-scroll">
          <table>
            <thead><tr><th>Time</th><th>Request</th><th>Sender</th><th>Intent</th><th>Confidence</th><th>POS code</th><th>Action</th><th>Status</th><th>Duration</th></tr></thead>
            <tbody>
              {data.recent.map((row) => (
                <tr key={row.id} onClick={() => onSelect?.(row)}>
                  <td>{row.timestamp}</td><td className="mono-cell">{row.id}</td><td>{row.sender}</td><td>{row.intent}</td>
                  <td>{Math.round(Number(row.confidence || 0) * 100)}%</td><td className="mono-cell">{row.posCode || "—"}</td><td>{row.action}</td>
                  <td><StatusBadge value={row.status} /></td><td>{row.durationMs ? `${(row.durationMs / 1000).toFixed(2)}s` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
