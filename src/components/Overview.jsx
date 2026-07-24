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
import { KpiCard, MetricRibbon, StatusBadge } from "./Primitives";

function formatSeconds(ms) {
  if (ms === null || ms === undefined) return "—";
  return (Number(ms) / 1000).toFixed(2);
}

export default function Overview({ data, onSelect }) {
  const op = data.summary.operational;
  const intents = data.intents || [];
  const trends = data.trends || [];
  const totalIntents = intents.reduce((sum, item) => sum + Number(item.value || 0), 0);

  return (
    <>
      {/* Stats Overview Cards — same block used across every page */}
      <MetricRibbon
        items={[
          { label: "Incoming requests", value: op.totalRequests ?? 0 },
          { label: "Automatically resolved", value: op.autoResolved ?? 0 },
          { label: "In progress", value: op.inProgress ?? 0 },
          { label: "Manual review", value: op.manualReview ?? 0 },
        ]}
      />

      {/* Middle Row — mirrors ESI Logis' Dashboard "Middle Row" grid-cols-5 layout */}
      <div className="mb-6 grid grid-cols-1 gap-3 rounded-2xl bg-transparent text-sm md:grid-cols-5">
        {/* KPI stack (Resolution time & Staff-style cards) */}
        <div className="flex h-full flex-col gap-3 rounded-2xl bg-transparent md:col-span-1">
          <KpiCard value={formatSeconds(op.averageProcessingMs)} suffix="s" label="Average processing time" />
          <KpiCard value={(op.readinessRate ?? 0).toFixed(1)} suffix="%" label="Agent readiness rate" />
        </div>

        {/* Area Chart */}
        <div className="relative flex h-full min-h-[370px] flex-col justify-between rounded-2xl bg-gray-100 p-6 shadow-2xl md:col-span-2">
          <div className="mb-2 flex w-full justify-center">
            <h3 className="text-center font-outfit text-lg font-medium text-[#757575]">Average processing time</h3>
          </div>
          <div className="flex flex-1 items-center">
            <ResponsiveContainer width="100%" height="90%">
              <AreaChart data={trends} margin={{ top: 12, right: 12, left: -16, bottom: 0 }}>
                <defs>
                  <linearGradient id="processingFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#2563eb" stopOpacity={0.28} />
                    <stop offset="100%" stopColor="#2563eb" stopOpacity={0.07} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
                <XAxis dataKey="label" stroke="#999" tick={{ fill: "#8a8f95", fontSize: 12 }} />
                <YAxis
                  stroke="#999"
                  tickFormatter={(value) => `${(value / 1000).toFixed(1)}`}
                  tick={{ fill: "#8a8f95", fontSize: 12 }}
                />
                <Tooltip formatter={(value) => [`${(Number(value) / 1000).toFixed(2)} s`, "Processing time"]} />
                <Area type="monotone" dataKey="averageProcessingMs" stroke="#2563eb" strokeWidth={2} fill="url(#processingFill)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Donut chart — same visual language as ESI Logis' Equipment Status pie */}
        <div className="flex h-full min-h-[370px] flex-row rounded-lg bg-gray-100 p-4 shadow-2xl md:col-span-2">
          <div className="flex w-3.5/5 flex-1 flex-col items-center">
            <h3 className="text-center font-outfit text-md font-medium text-[#757575]">Intent Distribution</h3>
            <div className="relative w-full flex-1">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={intents} dataKey="value" nameKey="name" innerRadius="72%" outerRadius="83%" paddingAngle={2}>
                    {intents.map((item) => (
                      <Cell key={item.name} fill={item.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                <strong className="text-2xl">{totalIntents}</strong>
                <span className="text-[11px] text-[#888]">Requests</span>
              </div>
            </div>
          </div>
          <div className="mt-4 flex w-2.5/5 flex-col justify-center gap-3">
            {intents.map((item) => (
              <div key={item.name} className="flex items-center">
                <div className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: item.color }} />
                <span className="pl-2 text-[10px] text-[#757575]">{item.name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Latest Requests table — mirrors ESI Logis' "Latest Interventions" card */}
      <div className="rounded-lg bg-gray-100 shadow-2xl">
        <div className="border-b p-6">
          <h3 className="font-outfit text-lg font-semibold">
            Latest requests and agent decisions{" "}
            <span className="text-sm font-normal text-gray-500">/ {data.recent.length} latest</span>
          </h3>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Request</th>
                <th>Sender</th>
                <th>Intent</th>
                <th>Confidence</th>
                <th>POS code</th>
                <th>Action</th>
                <th>Status</th>
                <th>Duration</th>
              </tr>
            </thead>
            <tbody>
              {data.recent.map((row) => (
                <tr key={row.id} onClick={() => onSelect?.(row)} className="cursor-pointer">
                  <td>{row.timestamp}</td>
                  <td className="mono-cell">{row.id}</td>
                  <td>{row.sender}</td>
                  <td>{row.intent}</td>
                  <td>{Math.round(Number(row.confidence || 0) * 100)}%</td>
                  <td className="mono-cell">{row.posCode || "—"}</td>
                  <td>{row.action}</td>
                  <td>
                    <StatusBadge value={row.status} />
                  </td>
                  <td>{row.durationMs ? `${(row.durationMs / 1000).toFixed(2)}s` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
