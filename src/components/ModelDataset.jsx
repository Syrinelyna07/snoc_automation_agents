import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartCard, KpiCard, MetricRibbon } from "./Primitives";

export default function ModelDataset({ data }) {
  const model = data.model;
  return (
    <>
      <MetricRibbon items={[
        { label: "Real source rows", value: model.datasetRows },
        { label: "Agent ready", value: model.readyRows },
        { label: "Manual review", value: model.reviewRows },
        { label: "Model accuracy", value: `${model.accuracy}%` },
      ]} />
      <section className="four-kpi-grid"><KpiCard value={model.macroF1} suffix="%" label="Macro F1" /><KpiCard value={model.weightedF1} suffix="%" label="Weighted F1" /><KpiCard value="212" label="Real train rows" /><KpiCard value="53" label="Real test rows" /></section>
      <section className="two-chart-grid">
        <ChartCard title="Class distribution" subtitle="Model evaluation snapshot"><ResponsiveContainer width="100%" height="100%"><BarChart data={model.classes}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="name" /><YAxis /><Tooltip /><Bar dataKey="value" fill="#ea8b00" radius={[5,5,0,0]} /></BarChart></ResponsiveContainer></ChartCard>
        <ChartCard title="Per-class model metrics" subtitle="Precision, recall and F1"><ResponsiveContainer width="100%" height="100%"><BarChart data={model.metrics}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="name" /><YAxis domain={[0,1]} /><Tooltip /><Legend /><Bar dataKey="precision" fill="#2563eb" /><Bar dataKey="recall" fill="#4caf50" /><Bar dataKey="f1" fill="#ea8b00" /></BarChart></ResponsiveContainer></ChartCard>
      </section>
    </>
  );
}
