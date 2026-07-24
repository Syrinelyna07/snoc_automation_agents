import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartCard, KpiCard, MetricRibbon } from "./Primitives";

export default function AgentOperations({ data }) {
  const op = data.operations;
  return (
    <>
      <MetricRibbon items={[
        { label: "Emails received", value: op.emailsReceived },
        { label: "Whitelist pass", value: `${op.whitelistPassRate}%` },
        { label: "Average confidence", value: `${op.classificationConfidence}%` },
        { label: "API success", value: `${op.apiSuccessRate}%` },
      ]} />
      <section className="four-kpi-grid">
        <KpiCard value={op.extractionSuccessRate} suffix="%" label="Entity extraction success" />
        <KpiCard value={op.validationPassRate} suffix="%" label="Business validation pass" />
        <KpiCard value={op.manualReviewRate} suffix="%" label="Manual review rate" />
        <KpiCard value={(op.p95ProcessingMs / 1000).toFixed(2)} suffix="s" label="P95 processing time" />
      </section>
      <section className="two-chart-grid">
        <ChartCard title="Requests by hour" subtitle="Incoming SNOC workload">
          <ResponsiveContainer width="100%" height="100%"><BarChart data={op.hourly}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="label" /><YAxis /><Tooltip /><Bar dataKey="value" fill="#2563eb" radius={[5,5,0,0]} /></BarChart></ResponsiveContainer>
        </ChartCard>
        <ChartCard title="API actions" subtitle="Successful and failed deterministic routes">
          <ResponsiveContainer width="100%" height="100%"><BarChart data={op.actions}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="label" tick={{ fontSize: 11 }} /><YAxis /><Tooltip /><Legend /><Bar dataKey="success" fill="#4caf50" radius={[5,5,0,0]} /><Bar dataKey="failed" fill="#f44336" radius={[5,5,0,0]} /></BarChart></ResponsiveContainer>
        </ChartCard>
      </section>
    </>
  );
}
