import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartCard, EmptyState, MetricRibbon, StatusBadge } from "./Primitives";

export default function DataQuality({ data }) {
  const q = data.summary.dataQuality;
  return (
    <>
      <MetricRibbon items={[
        { label: "Overall DQ score", value: q.overallQualityScore == null ? "—" : `${q.overallQualityScore}%` },
        { label: "Active rules", value: q.totalRules },
        { label: "Failed rules", value: q.failedRules },
        { label: "Tables monitored", value: q.tablesMonitored },
      ]} />
      <section className="two-chart-grid">
        <ChartCard title="Weighted score by dimension" subtitle="100 × passed rows / total checked rows">
          <ResponsiveContainer width="100%" height="100%"><BarChart data={data.dq.dimensions} layout="vertical"><CartesianGrid strokeDasharray="3 3" horizontal={false} /><XAxis type="number" domain={[0,100]} /><YAxis type="category" dataKey="dimension" width={95} /><Tooltip /><Bar dataKey="score" fill="#2563eb" radius={[0,6,6,0]} /></BarChart></ResponsiveContainer>
        </ChartCard>
        <div className="empty-panels">
          <EmptyState title="Accuracy" description="No Accuracy rules are configured in the current rule set." />
          <EmptyState title="Timeliness" description="No Timeliness rules are configured in the current rule set." />
        </div>
      </section>
      <section className="requests-card dashboard-card">
        <div className="table-title-row"><div><h2>Rules needing attention</h2><p>CACTUV findings sorted by impact</p></div><span>{data.dq.rules.length} findings</span></div>
        <div className="table-scroll"><table><thead><tr><th>Rule</th><th>Dimension</th><th>Table</th><th>Column</th><th>Severity</th><th>Score</th><th>Failed rows</th><th>Status</th></tr></thead><tbody>{data.dq.rules.map((row)=><tr key={row.ruleId}><td className="mono-cell">{row.ruleId}</td><td>{row.dimension}</td><td>{row.table}</td><td>{row.column}</td><td>{row.severity}</td><td>{row.score}%</td><td>{row.failedRows}</td><td><StatusBadge value={row.status} /></td></tr>)}</tbody></table></div>
      </section>
    </>
  );
}
